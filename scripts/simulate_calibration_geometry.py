#!/usr/bin/env python3
"""Offline MOVL geometry audit. No ROS init, services, actions, or robot commands."""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pybullet as pb
import yaml

ROOT = Path(__file__).resolve().parents[1]
for package in ('dobot_calibration', 'dobot_kinematics'):
    sys.path.insert(0, str(ROOT / 'src/magician_ros2' / package))
from ament_index_python.packages import get_package_share_directory
from dobot_calibration.calibration_workspace import automatic_plan
from dobot_calibration.geometry import transform
from dobot_kinematics.collision_detection_server import PyBulletCollisionServer as Collision
from dobot_kinematics.dobot_inv_kin import calc_inv_kin
from dobot_kinematics.trajectory_validator_server import PoseValidatorService
from scipy.spatial.transform import Rotation


def samples(start, target, step_mm, step_deg):
    distance = np.linalg.norm(target[:3] - start[:3])
    yaw_delta = (target[3] - start[3] + 180) % 360 - 180
    count = max(2, math.ceil(distance / step_mm) + 1,
                math.ceil(abs(yaw_delta) / step_deg) + 1)
    for fraction in np.linspace(0, 1, count):
        yield np.r_[start[:3] + fraction * (target[:3] - start[:3]),
                    start[3] + fraction * yaw_delta]


def update_minimum(results, name, distance, pose_index, sample_index):
    if distance is not None and (name not in results or distance < results[name]['distance_mm']):
        results[name] = dict(distance_mm=float(distance), pose_index=pose_index,
                             sample_index=sample_index)


def closest(client, robot, other, link_a, link_b):
    points = pb.getClosestPoints(robot, other, distance=2., linkIndexA=link_a,
                                linkIndexB=link_b, physicsClientId=client)
    return min((p[8] * 1000 for p in points), default=None)


def run(scenario):
    if scenario.get('simulation_only') is not True:
        raise ValueError('Only simulation scenarios are supported')
    lower, upper = (np.asarray(scenario[k], dtype=float) for k in ('tcp_min_mm', 'tcp_max_mm'))
    anchor = np.asarray(scenario['simulated_anchor_xyz_j4_mm_deg'], dtype=float)
    if (lower.shape != (3,) or upper.shape != (3,) or anchor.shape != (4,)
            or not np.isfinite(np.r_[lower, upper, anchor]).all() or np.any(lower >= upper)):
        raise ValueError('Invalid hypothetical TCP bounds or anchor')
    step_mm, step_deg = scenario['sampling_step_mm'], scenario['sampling_step_deg']
    if not (0 < step_mm <= 2 and 0 < step_deg <= 2):
        raise ValueError('Sampling must be positive and no coarser than 2 mm / 2 degrees')
    limits = np.asarray(scenario['controller_joint_limits_deg'], dtype=float)
    policy = SimpleNamespace(**{f'axis_{i+1}_range': {'min': lo, 'max': hi}
                                for i, (lo, hi) in enumerate(limits)})
    soft = scenario['planning_soft_margin_deg']
    mount = yaml.safe_load((ROOT / scenario['mount_model']).read_text())
    radius = mount['envelope_radius_m'] + mount['translation_error_bound_m']
    table = scenario['reported_table_z_m']
    origin = transform(Rotation.from_euler('z', anchor[3], degrees=True).as_matrix(), anchor[:3] / 1000)
    plan = automatic_plan(origin)
    targets = [np.r_[p[:3, 3] * 1000, math.degrees(math.atan2(p[1, 0], p[0, 0]))] for p in plan]
    os.environ['MAGICIAN_TOOL'] = 'suction_cup'  # This offline process only.
    client = pb.connect(pb.DIRECT)
    if client < 0:
        raise RuntimeError('PyBullet DIRECT connection failed')
    results, segment_reports = {}, []
    try:
        bodies = Collision.load_environment(client)
        robot, ground = bodies['robot'], bodies['ground']
        model_table_z = pb.getBasePositionAndOrientation(ground, physicsClientId=client)[0][2]
        info = {i: pb.getJointInfo(robot, i, physicsClientId=client)
                for i in range(pb.getNumJoints(robot, physicsClientId=client))}
        names = {i: value[12].decode() for i, value in info.items()}
        index = {name: i for i, name in names.items()}
        links = [i for i in info if pb.getCollisionShapeData(robot, i, physicsClientId=client)]
        # Adjacent links have intentional joints/contact; all other pairs are
        # exploratory diagnostics, not an approved allowed-collision matrix.
        pairs = [(a, b) for a, b in itertools.combinations(links, 2)
                 if info[a][16] != b and info[b][16] != a]
        policy_pairs = [(index[a], index[b]) for a in ('magician_link_4', 'end_effector_part')
                        for b in ('magician_base_link', 'magician_link_1')]
        current = anchor
        for pose_index, target in enumerate(targets, 1):
            failures, joints_all, urdf_limit_violations = [], [], []
            sample_count = 0
            for sample_index, point in enumerate(samples(current, target, step_mm, step_deg)):
                sample_count += 1
                if np.any(point[:3] < lower - 1e-9) or np.any(point[:3] > upper + 1e-9):
                    failures.append({'sample': sample_index, 'gate': 'SIMULATION_TCP_BOUNDS'})
                angles = calc_inv_kin(*point)
                if angles is False:
                    failures.append({'sample': sample_index, 'gate': 'IK'})
                    continue
                joints_all.append(angles)
                if not PoseValidatorService.are_angles_in_range_cartesian(policy, angles, point):
                    failures.append({'sample': sample_index, 'gate': 'CONTROLLER_CARTESIAN_LIMITS'})
                angles_array = np.asarray(angles)
                if np.any(angles_array <= limits[:, 0] + soft) or np.any(angles_array >= limits[:, 1] - soft):
                    failures.append({'sample': sample_index, 'gate': 'AUTOMATIC_SOFT_LIMITS'})
                q = Collision.set_robot_configuration(angles[:3])
                for joint_id, value in enumerate(q, 1):
                    lo, hi = info[joint_id][8:10]
                    if lo < hi and not lo <= value <= hi:
                        urdf_limit_violations.append(dict(sample=sample_index,
                            joint=info[joint_id][1].decode(), value_deg=math.degrees(value),
                            min_deg=math.degrees(lo), max_deg=math.degrees(hi)))
                Collision.update_robot_configuration(robot, q, client)
                for a, b in pairs:
                    update_minimum(results, f'nonadjacent/{names[a]}/{names[b]}',
                                   closest(client, robot, robot, a, b), pose_index, sample_index)
                for a, b in policy_pairs:
                    update_minimum(results, f'policy_self/{names[a]}/{names[b]}',
                                   closest(client, robot, robot, a, b), pose_index, sample_index)
                for label, z in (('model_ground', model_table_z), ('reported_table', table)):
                    pb.resetBasePositionAndOrientation(ground, [0, 0, z], [0, 0, 0, 1], physicsClientId=client)
                    for link in links:
                        update_minimum(results, f'{label}/{names[link]}',
                                       closest(client, robot, ground, link, -1), pose_index, sample_index)
                # Analytic conservative sphere/table distance, not a detailed
                # camera mesh or evidence of actual physical penetration.
                sphere_gap = point[2] - 1000 * (table + radius)
                update_minimum(results, 'attachment_sphere/reported_table', sphere_gap, pose_index, sample_index)
                update_minimum(results, 'attachment_sphere/table_policy_margin',
                               sphere_gap - scenario['minimum_clearance_m'] * 1000, pose_index, sample_index)
            joint_values = np.asarray(joints_all)
            segment_reports.append(dict(pose_index=pose_index, target_xyz_j4_mm_deg=target.tolist(),
                samples=sample_count, failures=failures,
                urdf_articulation_limit_violations=urdf_limit_violations,
                joint_min_deg=joint_values.min(axis=0).tolist() if joints_all else None,
                joint_max_deg=joint_values.max(axis=0).tolist() if joints_all else None))
            current = target
        urdf = Path(get_package_share_directory('dobot_description')) / 'meshes/collision/urdf_models/suction_cup.urdf'
        policy_names = [k for k in results if k.startswith('policy_self/')]
        policy_names += [f'model_ground/{name}' for name in ('magician_link_4', 'end_effector_part')]
        required_reported = [f'reported_table/{names[i]}' for i in links]
        coverage = [
            'Camera/bracket/cables/hoses represented only by existing enclosing sphere, not detailed meshes',
            'Collision URDF has no rotating J4 tool-yaw joint; mesh yaw sweep is not represented',
            'External obstacles/free volume not measured; TCP box is not an obstacle map',
            'Expanded nonadjacent checks lack a certified allowed-collision matrix',
            'PyBullet mesh collision distances are model distances, not measured physical clearances',
            '2 mm / 2 degree sampling is not a proof of continuous mesh collision freedom',
            'No dynamics, speed/time validation, sensor capture, or robot feedback in this offline run',
        ]
        return dict(utc=datetime.now(timezone.utc).isoformat(), mode='OFFLINE_SIMULATION',
            scenario=scenario, model_urdf=str(urdf), model_sha256=hashlib.sha256(urdf.read_bytes()).hexdigest(),
            model_table_z_m=model_table_z, modeled_collision_links=[names[i] for i in links],
            sample_count=sum(s['samples'] for s in segment_reports), segments=segment_reports,
            ik_limits_tcp_path_pass=not any(s['failures'] for s in segment_reports),
            urdf_articulation_limits_pass=not any(s['urdf_articulation_limit_violations'] for s in segment_reports),
            sampled_existing_collision_policy_pass=all(results[k]['distance_mm'] >= 0 for k in policy_names),
            sampled_all_modeled_links_reported_table_pass=all(results[k]['distance_mm'] >= 0 for k in required_reported),
            attachment_sphere_table_clearance_pass=results['attachment_sphere/table_policy_margin']['distance_mm'] >= 0,
            minimum_distances=results, coverage_limitations=coverage,
            entire_equipment_minimum_physical_clearance_mm=None,
            all_equipment_continuous_collision_verified=False,
            simulation_safety_result='NOT_CERTIFIED_FOR_REAL_MOTION',
            motion_command_sent=False, runtime_configuration_changed=False,
            real_motion_ready_unlocked=False)
    finally:
        pb.disconnect(client)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', type=Path, default=ROOT / 'docs/simulation-tcp-scenario-2026-10-11.yaml')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(yaml.safe_load(args.scenario.read_text()))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: result[k] for k in ('sample_count', 'ik_limits_tcp_path_pass',
        'sampled_existing_collision_policy_pass', 'sampled_all_modeled_links_reported_table_pass',
        'attachment_sphere_table_clearance_pass', 'simulation_safety_result')}, indent=2))


if __name__ == '__main__':
    main()
