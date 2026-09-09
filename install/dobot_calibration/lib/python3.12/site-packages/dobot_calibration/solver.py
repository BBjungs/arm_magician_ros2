"""Constrained Magician AX=XB solver and independent verification."""

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .geometry import (
    CalibrationError, Limits, apply, inverse, plane_difference, pose_distance,
    rotation_deg, transform, transform_plane,
)
from .registration import cloud_consistency, predicted_camera_motion, register


@dataclass
class Solution:
    tool_T_camera: np.ndarray
    metrics: dict
    observability: dict
    training_poses: np.ndarray


def excitation(captures, limits=Limits(), min_count=6):
    if len(captures) < min_count:
        raise CalibrationError('Insufficient independent robot poses')
    poses = np.array([c.base_T_tool for c in captures])
    stamps = [c.stamp for c in captures]
    if len(set(stamps)) != len(stamps):
        raise CalibrationError('Repeated capture timestamps')
    for i, j in combinations(range(len(poses)), 2):
        distance, angle = pose_distance(poses[i], poses[j])
        if distance < 0.004 and angle < 2:
            raise CalibrationError('Repeated or insufficiently distinct robot poses')
    translations = poses[:, :3, 3] - poses[0, :3, 3]
    spread = np.linalg.svd(translations, compute_uv=False)
    yaw = np.unwrap(np.arctan2(poses[:, 1, 0], poses[:, 0, 0]))
    if (np.linalg.norm(np.ptp(translations, axis=0)) < limits.min_translation_span_m
            or spread[1] < 0.010 or np.rad2deg(np.ptp(yaw)) < limits.min_yaw_span_deg):
        raise CalibrationError('Insufficient translation/yaw excitation')
    if not np.allclose(poses[:, :3, 2], [0, 0, 1], atol=0.01):
        raise CalibrationError('Robot motion is not the expected Magician XYZ/yaw kinematics')
    return {'rotation_axis_rank': 1, 'free_parameter_count': 5,
            'unobservable_component': 'tool_translation_z',
            'axial_constraint': 'verified_mount_model',
            'translation_singular_values_m': spread.tolist(),
            'yaw_span_deg': float(np.rad2deg(np.ptp(yaw)))}


def collect_pairs(captures, limits=Limits()):
    # Anchor edges tie every observation to a fixed scene; adjacent edges
    # expose inconsistent registrations without integrating a drifting chain.
    edges = sorted({(0, j) for j in range(1, len(captures))}
                   | {(j - 1, j) for j in range(2, len(captures))})
    return [(i, j, register(captures[i], captures[j], limits, seed=i * 100 + j))
            for i, j in edges]


def quality_metrics(captures, pairs, value, limits=Limits()):
    translations, rotations, clouds, fitness, registration_rmse = [], [], [], [], []
    plane_offsets, plane_angles = [], []
    planes = [transform_plane(c.base_T_tool @ value, c.plane) for c in captures]
    for i, j, pair in pairs:
        a = inverse(captures[i].base_T_tool) @ captures[j].base_T_tool
        delta = inverse(a @ value) @ (value @ pair.first_T_second)
        translations.append(np.linalg.norm(delta[:3, 3]))
        rotations.append(rotation_deg(delta[:3, :3]))
        predicted = predicted_camera_motion(captures[i], captures[j], value)
        overlap, cloud_rmse, _, _ = cloud_consistency(captures[j].cloud, captures[i].cloud,
                                                     predicted, limits)
        clouds.append(cloud_rmse)
        fitness.extend([overlap, pair.quality['registration_fitness']])
        registration_rmse.append(pair.quality['registration_rmse_m'])
        offset, angle = plane_difference(planes[i], planes[j])
        plane_offsets.append(offset)
        plane_angles.append(angle)
    if not pairs:
        raise CalibrationError('No registration evidence')
    return {
        'translation_residual_m': float(max(translations)),
        'rotation_residual_deg': float(max(rotations)),
        'table_plane_offset_m': float(max(plane_offsets)),
        'table_plane_angle_deg': float(max(plane_angles)),
        'cloud_rmse_m': float(max(clouds)),
        'registration_fitness': float(min(fitness)),
        'registration_rmse_m': float(max(registration_rmse)),
        'depth_valid_ratio': float(min(c.quality['depth_valid_ratio'] for c in captures)),
        'pose_count': len(captures), 'pair_count': len(pairs),
    }


def require_quality(metrics, limits=Limits()):
    maximums = {
        'translation_residual_m': limits.max_translation_residual_m,
        'rotation_residual_deg': limits.max_rotation_residual_deg,
        'table_plane_offset_m': limits.max_plane_offset_m,
        'table_plane_angle_deg': limits.max_plane_angle_deg,
        'cloud_rmse_m': limits.max_cloud_rmse_m,
        'registration_rmse_m': limits.max_registration_rmse_m,
    }
    minimums = {'registration_fitness': limits.min_registration_fitness,
                'depth_valid_ratio': limits.min_depth_valid_ratio}
    for key, bound in maximums.items():
        if not np.isfinite(metrics[key]) or not 0 <= metrics[key] <= bound:
            raise CalibrationError(f'{key} exceeds quality limit: {metrics[key]} > {bound}')
    for key, bound in minimums.items():
        if not np.isfinite(metrics[key]) or not bound <= metrics[key] <= 1:
            raise CalibrationError(f'{key} below quality limit: {metrics[key]} < {bound}')


def require_mount_agreement(value, mount, limits=Limits()):
    distance, angle = pose_distance(value, mount.tool_T_camera)
    if (abs(value[2, 3] - mount.tool_T_camera[2, 3]) > 1e-9
            or distance > limits.max_mount_deviation_m or angle > limits.max_mount_deviation_deg):
        raise CalibrationError('Solution disagrees with the trusted mount constraint')


def solve(captures, mount, limits=Limits(), pairs=None):
    observable = excitation(captures, limits)
    pairs = collect_pairs(captures, limits) if pairs is None else pairs
    initial = np.r_[Rotation.from_matrix(mount.tool_T_camera[:3, :3]).as_rotvec(),
                    mount.tool_T_camera[:2, 3]]

    def unpack(parameters):
        return transform(Rotation.from_rotvec(parameters[:3]).as_matrix(),
                         np.r_[parameters[3:], mount.tool_T_camera[2, 3]])

    def residuals(parameters, refine=False):
        value = unpack(parameters)
        parts = []
        for i, j, pair in pairs:
            a = inverse(captures[i].base_T_tool) @ captures[j].base_T_tool
            delta = inverse(a @ value) @ value @ pair.first_T_second
            parts.extend([delta[:3, 3] / 0.003,
                          Rotation.from_matrix(delta[:3, :3]).as_rotvec() / np.deg2rad(1)])
            if refine:
                predicted = inverse(value) @ a @ value
                # Fixed natural-feature correspondences avoid a nearest-neighbour
                # optimizer sliding along the dominant plane.
                count = min(len(pair.source), 100)
                indices = np.linspace(0, len(pair.source) - 1, count).astype(int)
                errors = apply(predicted, pair.source[indices]) - pair.target[indices]
                parts.append(errors.ravel() / (0.004 * np.sqrt(count)))
                p1 = transform_plane(captures[i].base_T_tool @ value, captures[i].plane)
                p2 = transform_plane(captures[j].base_T_tool @ value, captures[j].plane)
                if p1[:3] @ p2[:3] < 0:
                    p2 = -p2
                parts.extend([(p1[:3] - p2[:3]) / np.deg2rad(1),
                              np.array([(p1[3] - p2[3]) / 0.003])])
        return np.concatenate(parts)

    fit = least_squares(residuals, initial, loss='soft_l1', max_nfev=250,
                        x_scale='jac', ftol=1e-10, xtol=1e-10, gtol=1e-10)
    fit = least_squares(lambda p: residuals(p, True), fit.x, loss='soft_l1',
                        max_nfev=250, x_scale='jac') if fit.success else fit
    if not fit.success or not np.isfinite(fit.x).all():
        raise CalibrationError('Constrained hand-eye optimization did not converge')
    # Scale translation columns to a 10 mm perturbation before testing conditioning. Compute
    # rank from motion evidence alone so plane terms cannot hide a missing DOF.
    eps = 1e-6
    jacobian = np.column_stack([(residuals(fit.x + np.eye(5)[i] * eps)
                                - residuals(fit.x - np.eye(5)[i] * eps)) / (2 * eps)
                               for i in range(5)])
    jacobian[:, 3:] *= 0.01
    singular = np.linalg.svd(jacobian, compute_uv=False)
    if singular[-1] < 1e-4 or singular[0] / singular[-1] > 10000:
        raise CalibrationError('Remaining five calibration parameters are not observable')
    value = unpack(fit.x)
    require_mount_agreement(value, mount, limits)
    metrics = quality_metrics(captures, pairs, value, limits)
    require_quality(metrics, limits)
    observable.update({'motion_jacobian_singular_values': singular.tolist(),
                       'axial_sigma_m': mount.axial_sigma_m,
                       'mount_source': mount.source})
    return Solution(value, metrics, observable, np.array([c.base_T_tool for c in captures]))


def verify(solution, anchor, captures, mount, limits=Limits(), pairs=None):
    """Return PASS/FAIL without fitting or modifying the saved transform."""
    metrics = {}
    try:
        require_mount_agreement(solution.tool_T_camera, mount, limits)
        excitation(captures, limits, min_count=3)
        for capture in captures:
            if capture.stamp <= anchor.stamp:
                raise CalibrationError('Verification must use fresh captures')
            for training in solution.training_poses:
                distance, angle = pose_distance(capture.base_T_tool, training)
                if distance < 0.008 and angle < 4:
                    raise CalibrationError('Verification pose overlaps a calibration pose')
        observations = [anchor, *captures]
        pairs = collect_pairs(observations, limits) if pairs is None else pairs
        metrics = quality_metrics(observations, pairs, solution.tool_T_camera, limits)
        require_quality(metrics, limits)
        return {'result': 'PASS', 'metrics': metrics, 'reason': ''}
    except (CalibrationError, ValueError, np.linalg.LinAlgError) as error:
        return {'result': 'FAIL', 'metrics': {k: v if np.isfinite(v) else None
                                            for k, v in metrics.items()}, 'reason': str(error)}
