from dataclasses import replace
import json

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from dobot_calibration.geometry import (
    CalibrationError, Limits, Mount, apply, inverse, pose_distance, scene_geometry,
    table_plane, transform, transform_plane,
)
from dobot_calibration.registration import Registration, make_capture, register
from dobot_calibration.solver import (
    collect_pairs, excitation, require_quality, solve, verify,
)
from dobot_calibration.workflow import (
    Workflow, calibration_origin, calibration_poses, check_path, load_bundle, save_bundle,
    settled_pose,
)
from dobot_calibration.picking_guard import ReadinessLease
from synthetic_scene import MOUNT, START, TRUE_X, held_out, render, training


@pytest.fixture(scope='module')
def observations():
    return training()


@pytest.fixture(scope='module')
def calibrated(observations):
    return solve(observations, MOUNT)


def test_rgbd_recovers_camera_motion(observations):
    first, second = observations[0], observations[2]
    pair = register(first, second)
    truth = inverse(first.base_T_tool @ TRUE_X) @ second.base_T_tool @ TRUE_X
    distance, angle = pose_distance(truth, pair.first_T_second)
    assert distance < 0.002
    assert angle < 0.5
    assert pair.quality['registration_fitness'] > 0.75


def test_constrained_solution_and_independent_verification(calibrated, observations):
    distance, angle = pose_distance(TRUE_X, calibrated.tool_T_camera)
    assert distance < 0.003
    assert angle < 1
    assert calibrated.observability['free_parameter_count'] == 3
    assert calibrated.observability['fixed_parameters'] == 'tool_translation_xyz'
    np.testing.assert_array_equal(
        calibrated.tool_T_camera[:3, 3], MOUNT.tool_T_camera[:3, 3])
    assert verify(calibrated, observations[0], held_out(), MOUNT)['result'] == 'PASS'


@pytest.mark.parametrize('axis', [0, 2])
def test_independent_verification_detects_moved_mount(calibrated, observations, axis):
    moved = TRUE_X.copy()
    moved[axis, 3] += 0.018
    captures = [render(pose, 300 + i * 2, value=moved)
                for i, pose in enumerate(calibration_poses(START, True))]
    assert verify(calibrated, observations[0], captures, MOUNT)['result'] == 'FAIL'


def test_reused_training_poses_fail(calibrated, observations):
    reused = [replace(c, stamp=c.stamp + 1000) for c in observations[1:4]]
    report = verify(calibrated, observations[0], reused, MOUNT)
    assert report['result'] == 'FAIL'
    assert 'overlaps' in report['reason']


def test_four_dof_axial_gauge_is_not_claimed_observable(observations):
    shifted = TRUE_X.copy()
    shifted[2, 3] += 0.1
    # No relative motion, scene registration, or unknown table height can
    # distinguish these transforms on an XYZ/yaw-only robot.
    for capture in observations[1:]:
        a = inverse(observations[0].base_T_tool) @ capture.base_T_tool
        assert np.allclose(inverse(TRUE_X) @ a @ TRUE_X, inverse(shifted) @ a @ shifted)


def test_measured_camera_reference_is_composed_with_factory_optical_tf():
    internal = transform(
        Rotation.from_euler('xyz', [90, 0, -90], degrees=True).as_matrix(),
        [0.012, -0.003, 0.004])
    measured_xyz = np.array([-0.050, 0.0, -0.105])
    seed_reference = transform(
        Rotation.from_euler('xyz', [175, 3, 8], degrees=True).as_matrix(),
        measured_xyz)
    mount = Mount(seed_reference @ internal, 0.001, 0.15,
                  'synthetic measured datum', 'factory-tf-test', internal)
    solved_rotation = Rotation.from_euler('xyz', [180, 1, 4], degrees=True).as_matrix()
    optical = mount.compose_optical(solved_rotation)
    expected = transform(solved_rotation, measured_xyz) @ internal
    np.testing.assert_allclose(optical, expected, atol=1e-12)
    np.testing.assert_allclose(
        (optical @ inverse(internal))[:3, 3], measured_xyz, atol=1e-12)


def test_pending_rotation_mount_loader_uses_measurement_and_factory_tf(tmp_path):
    import yaml
    path = tmp_path / 'mount.yaml'
    path.write_text(yaml.safe_dump({
        'geometry_verified': False,
        'translation_verified': True,
        'rigid_to_rotating_tool': True,
        'measurement_source': 'as-built fixture',
        'translation_units': 'm',
        'translation_error_bound_m': 0.003,
        'envelope_radius_m': 0.15,
        'initial_mount_constraint': {
            'tool_to_camera_reference': [-0.05, 0.0, -0.105],
        },
    }))
    internal = transform(
        Rotation.from_euler('x', 90, degrees=True).as_matrix(), [0.01, 0, 0])
    mount = Mount.load_translation_constraint(path, internal)
    assert mount.rotation_seed_verified is False
    np.testing.assert_allclose(
        mount.tool_T_camera_reference[:3, 3], [-0.05, 0.0, -0.105])
    np.testing.assert_allclose(mount.camera_reference_T_optical, internal)


def test_pending_mount_preflight_names_only_missing_safety_inputs(tmp_path):
    import yaml
    path = tmp_path / 'mount.yaml'
    path.write_text(yaml.safe_dump({
        'geometry_verified': False,
        'translation_verified': True,
        'rigid_to_rotating_tool': True,
        'measurement_source': 'as-built fixture',
        'translation_units': 'm',
        'translation_error_bound_m': None,
        'envelope_radius_m': None,
        'initial_mount_constraint': {
            'tool_to_camera_reference': [-0.05, 0.0, -0.105],
        },
    }))
    blockers = Mount.translation_constraint_blockers(path)
    assert blockers == [
        'translation_error_bound_m is missing or outside (0, 0.006]',
        'envelope_radius_m must be greater than 0.116297 and below 0.30',
    ]


def test_insufficient_excitation_rejected(observations):
    poses = [replace(c, base_T_tool=transform(translation=[0.2 + i * 0.01, 0, 0.2]))
             for i, c in enumerate(observations)]
    with pytest.raises(CalibrationError, match='excitation'):
        excitation(poses)


def test_flat_scene_and_sparse_depth_rejected():
    with pytest.raises(CalibrationError, match='geometry'):
        render(START, 1, flat=True)
    rng = np.random.default_rng(3)
    points = rng.uniform([-0.15, -0.15, 0.3], [0.15, 0.15, 0.3], size=(2000, 3))
    with pytest.raises(CalibrationError, match='geometry'):
        scene_geometry(points)


def test_textureless_scene_rejected(observations):
    blank = replace(observations[0], rgb=np.zeros_like(observations[0].rgb))
    with pytest.raises(CalibrationError, match='features'):
        register(blank, observations[1])


def test_plane_robust_to_outliers():
    rng = np.random.default_rng(5)
    table = np.c_[rng.uniform(-0.2, 0.2, (1500, 2)), rng.normal(0.45, 0.0005, 1500)]
    clutter = rng.uniform([-0.2, -0.2, 0.2], [0.2, 0.2, 0.7], (500, 3))
    plane, quality = table_plane(np.r_[table, clutter], [0, 0, -1])
    assert abs(plane[3] - 0.45) < 0.001
    assert quality['plane_inlier_ratio'] > 0.6
    assert quality['plane_rmse_m'] < 0.001


def test_reload_requires_matching_context_and_fresh_verification(tmp_path, calibrated, observations):
    path = tmp_path / 'calibration.npz'
    context = {'camera_id': 'synthetic-1', 'mount_digest': MOUNT.digest}
    report = verify(calibrated, observations[0], held_out(), MOUNT)
    save_bundle(path, calibrated, observations[0], context, report)
    restored, anchor = load_bundle(path, context, MOUNT)
    assert np.array_equal(restored.tool_T_camera, calibrated.tool_T_camera)
    assert verify(restored, anchor, held_out(), MOUNT)['result'] == 'PASS'
    with pytest.raises(CalibrationError, match='changed'):
        load_bundle(path, {'camera_id': 'different'}, MOUNT)
    with pytest.raises(CalibrationError, match='unverified'):
        save_bundle(path, calibrated, anchor, context, {'result': 'FAIL'})
    with pytest.raises(CalibrationError, match='Cannot load'):
        load_bundle(tmp_path / 'missing.npz', context, MOUNT)


def test_motion_paths_and_held_out_poses(observations):
    current = START
    for pose in calibration_poses(START) + calibration_poses(START, True):
        check_path(current, pose, observations[0], MOUNT)
        current = pose
    low = START.copy()
    low[2, 3] = 0.07
    with pytest.raises(CalibrationError, match='clearance'):
        check_path(START, low, observations[0], MOUNT)
    far = START.copy()
    far[0, 3] += 0.10
    with pytest.raises(CalibrationError, match='bounds'):
        check_path(START, far, observations[0], MOUNT)


def test_calibration_origin_repairs_current_home_workspace_boundary():
    current = transform(translation=[0.149924, 0.0, 0.100094])
    origin = calibration_origin(current)
    assert np.linalg.norm(origin[:3, 3] - current[:3, 3]) < 0.075
    planned = [origin, *calibration_poses(origin),
               *calibration_poses(origin, verification=True)]
    for pose in planned:
        radius = np.linalg.norm(pose[:2, 3])
        assert radius >= 0.142 - 1e-12
        assert radius <= 0.298 + 1e-12
        assert pose[0, 3] >= 0.082 - 1e-12
        assert 0.072 - 1e-12 <= pose[2, 3] <= 0.228 + 1e-12


def test_settled_capture_rejects_stale_moving_or_gapped_telemetry():
    history = [(float(t), START.copy(), np.zeros(4)) for t in np.arange(1.1, 2.11, 0.05)]
    assert np.allclose(settled_pose(history, 2.0, 1.0), START)
    with pytest.raises(CalibrationError, match='settle'):
        settled_pose(history, 1.5, 1.0)
    moving = [(t, p, q + (0.1 if i == 10 else 0)) for i, (t, p, q) in enumerate(history)]
    with pytest.raises(CalibrationError, match='moving'):
        settled_pose(moving, 2.0, 1.0)
    with pytest.raises(CalibrationError, match='gap|bracket'):
        settled_pose(history[:9] + history[15:], 2.0, 1.0)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -0.1, 0.5])
def test_bad_quality_is_rejected(calibrated, bad):
    metrics = dict(calibrated.metrics, translation_residual_m=bad)
    with pytest.raises(CalibrationError):
        require_quality(metrics)


def test_readiness_lease_blocks_missing_stale_failed_replayed_status():
    lease = ReadinessLease()
    assert not lease.ready(10, 10)
    ready = {'ready': True, 'state': 'READY', 'result': 'PASS', 'stamp': 10.0}
    lease.update(json.dumps(ready), 10.1, 20)
    assert lease.ready(10.2, 20.1)
    assert not lease.ready(11.1, 20.1)
    assert not lease.ready(10.2, 21.1)
    lease.update(json.dumps(ready), 10.2, 20.2)
    assert not lease.ready(10.2, 20.2)
    ready.update(stamp=10.3, state='FAIL', ready=False, result='FAIL')
    lease.update(json.dumps(ready), 10.4, 20.3)
    assert not lease.ready(10.4, 20.3)
    lease.update('{invalid', 10.5, 20.4)
    assert not lease.ready(10.5, 20.4)


@pytest.mark.parametrize('settings', [
    {'max_translation_residual_m': float('nan')},
    {'min_depth_valid_ratio': 1.2},
    {'min_points': 2},
    {'min_depth_m': 2.0},
    {'max_registration_rmse_m': -1.0},
])
def test_invalid_quality_settings_are_rejected(settings):
    with pytest.raises(CalibrationError):
        Limits(**settings)


def test_path_accounts_for_uncertain_mount(observations):
    # An obstacle clear of the nominal enclosure can still intersect it for
    # a mount within the accepted calibration deviation.
    capture = observations[0]
    obstacle_base = np.array([[START[0, 3], START[1, 3], START[2, 3] - 0.16]])
    obstacle_camera = apply(inverse(START @ MOUNT.tool_T_camera), obstacle_base)
    capture = replace(capture, cloud=np.r_[capture.cloud, obstacle_camera])
    with pytest.raises(CalibrationError, match='obstacle'):
        check_path(START, START, capture, MOUNT)


def test_sparse_depth_observation_fails_before_registration(observations):
    capture = observations[0]
    depth = np.zeros_like(capture.depth)
    depth[:10] = capture.depth[:10]
    with pytest.raises(CalibrationError, match='depth-valid ratio'):
        make_capture(capture.stamp, capture.base_T_tool, capture.rgb, depth,
                     capture.intrinsics, capture.cloud, MOUNT.tool_T_camera)
