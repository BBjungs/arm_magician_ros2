from dataclasses import replace
import json

import numpy as np
import pytest

from dobot_calibration.geometry import CalibrationError, Limits, inverse, pose_distance
from dobot_calibration.object_reference import ObjectReference, combine_stationary, make_object_capture, stationary_pair
from dobot_calibration.registration import register
from dobot_calibration.solver import collect_pairs, solve, verify
from dobot_calibration.workflow import calibration_poses, save_bundle, load_bundle
from dobot_calibration.validation_status import live_acceptance_error
from object_scene import START, TRUE_X, MOUNT, K, capture, packet, render_object


@pytest.fixture(scope='module')
def observations():
    poses = [START, *calibration_poses(START)]
    return [capture(p, 10. + i * 2) for i, p in enumerate(poses)]


@pytest.fixture(scope='module')
def solution(observations):
    return solve(observations, MOUNT, object_only=True)


def test_object_capture_and_registration_never_call_plane_functions(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Object calibration must not inspect a plane')
    for name in ('dominant_plane', 'table_plane'):
        monkeypatch.setattr('dobot_calibration.registration.' + name, forbidden)
    monkeypatch.setattr('dobot_calibration.geometry.table_plane', forbidden)
    first, second = capture(), capture(calibration_poses(START)[0], 2.)
    assert first.plane.size == 0
    pair = register(first, second)
    truth = inverse(first.calibration_pose @ TRUE_X) @ second.calibration_pose @ TRUE_X
    distance, angle = pose_distance(truth, pair.first_T_second)
    assert distance < .002 and angle < .5


def test_object_solver_observability_and_independent_frames(solution, observations, monkeypatch):
    monkeypatch.setattr('dobot_calibration.solver.transform_plane',
                        lambda *args: pytest.fail('No plane terms allowed'))
    distance, angle = pose_distance(TRUE_X, solution.tool_T_camera)
    assert distance < .003 and angle < 1.
    assert solution.observability['free_parameter_count'] == 3
    assert solution.observability['fixed_parameters'] == 'tool_translation_xyz'
    independent = [capture(p, 100. + i * 2) for i, p in enumerate(calibration_poses(START, True))]
    report = verify(solution, observations[0], independent, MOUNT, object_only=True)
    assert report['result'] == 'PASS', report
    assert not any('plane' in key for key in report['metrics'])
    reused = [replace(c, stamp=c.stamp + 200) for c in observations[1:4]]
    assert verify(solution, observations[0], reused, MOUNT, object_only=True)['result'] == 'FAIL'


def test_moving_object_fails_stationary_check():
    with pytest.raises(CalibrationError, match='REFERENCE_OBJECT_MOVED'):
        stationary_pair(capture(), capture(stamp=2., shift=.012))


def test_multiframe_filter_and_duplicate_exposure_rejection():
    frames = [capture(stamp=i, noise=.0003) for i in (1., 2., 3.)]
    merged = combine_stationary(frames)
    assert merged.quality['object_stationary_verified']
    assert merged.quality['object_depth_noise_p95_m'] < .001
    with pytest.raises(CalibrationError, match='FRESH_FRAMES'):
        combine_stationary([frames[0]] * 3)


def test_single_suitable_object_auto_selects_without_table_eligibility():
    rgb, depth, mask = render_object()
    tracker = ObjectReference(); tracker.update(packet(rgb, mask))
    result = tracker.capture(1., START, rgb, depth, K, 'optical')
    assert result.quality['calibration_method'] == 'object_based'


def test_multiple_objects_never_auto_select_or_trust_reused_detector_id():
    rgb, depth, mask = render_object()
    value = packet(rgb, mask)
    value['detections'] *= 2
    tracker = ObjectReference(); tracker.update(value)
    with pytest.raises(CalibrationError, match='AMBIGUOUS'):
        tracker.capture(1., START, rgb, depth, K, 'optical')


@pytest.mark.parametrize('change', [
    {'rgb_frame_id': 'wrong'}, {'rgb_stamp': .5}, {'registered_depth': False},
    {'image_size': [320, 240]},
])
def test_detection_provenance_is_required(change):
    rgb, depth, mask = render_object()
    value = packet(rgb, mask); value.update(change)
    tracker = ObjectReference(); tracker.update(value)
    with pytest.raises(CalibrationError, match='EXPOSURE_MISMATCH'):
        tracker.capture(1., START, rgb, depth, K, 'optical')


def test_symmetric_detection_rejected_even_with_texture():
    rgb, depth, mask = render_object()
    value = packet(rgb, mask); value['detections'][0]['shape'] = 'circle'
    tracker = ObjectReference(); tracker.update(value)
    with pytest.raises(CalibrationError, match='SYMMETRIC'):
        tracker.capture(1., START, rgb, depth, K, 'optical')


def test_flat_featureless_and_invalid_depth_rejected():
    rgb, depth, mask = render_object()
    with pytest.raises(CalibrationError):
        make_object_capture(1., START, rgb, np.full_like(depth, .3), K, mask)
    with pytest.raises(CalibrationError, match='TEXTURE'):
        capture(blank=True)
    with pytest.raises(CalibrationError, match='DEPTH'):
        make_object_capture(1., START, rgb, np.zeros_like(depth), K, mask)


def test_distinct_axis_lengths_do_not_hide_half_turn_symmetry():
    yy, xx = np.mgrid[:480, :640]
    x, y = (xx - 320) / 200, (yy - 240) / 100
    mask = x * x + y * y < 1
    depth = .45 + .045 * np.maximum(0, 1 - x * x - y * y)
    rgb = np.random.default_rng(14).integers(0, 256, (480, 640, 3), dtype=np.uint8)
    with pytest.raises(CalibrationError, match='SYMMETRIC'):
        make_object_capture(1., START, rgb, depth, K, mask)


def test_stale_click_rejected():
    rgb, _, mask = render_object()
    tracker = ObjectReference(); tracker.update(packet(rgb, mask))
    with pytest.raises(CalibrationError, match='IMAGE_CHANGED'):
        tracker.select({'pixel': [300, 200], 'image_size': [640, 480], 'rgb_stamp': .5}, 1.1)


def test_nonobservable_and_mixed_methods_rejected(observations):
    with pytest.raises(CalibrationError, match='Repeated'):
        solve([replace(observations[0], stamp=i) for i in range(7)], MOUNT, object_only=True)
    with pytest.raises(CalibrationError, match='METHOD_MISMATCH'):
        solve(observations, MOUNT)


def test_object_bundle_round_trip_no_plane_and_corruption_fails(tmp_path, solution, observations):
    path = tmp_path / 'object.npz'
    context = {'camera': 'synthetic'}
    report = {'result': 'PASS', 'calibration_method': 'object_based'}
    save_bundle(path, solution, observations[0], context, report)
    restored, anchor = load_bundle(path, context, MOUNT)
    np.testing.assert_allclose(restored.tool_T_camera, solution.tool_T_camera)
    assert anchor.plane.size == 0
    assert anchor.quality['calibration_method'] == 'object_based'
    assert live_acceptance_error(report).startswith('LIVE_VALIDATION_NOT_COMPLETED')
    with np.load(path, allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    arrays['sensor_depth'] = np.zeros_like(arrays['sensor_depth'])
    np.savez_compressed(path, **arrays)
    with pytest.raises(CalibrationError):
        load_bundle(path, context, MOUNT)


def test_object_live_validation_requires_object_stability_instead_of_plane():
    checks = {key: {'result': 'PASS'} for key in ('hardware', 'object_stability', 'observability',
        'independent_verification', 'repeatability', 'reload_verification', 'real_object_validation')}
    checks['health_check'] = {'status': 'READY'}
    report = {'validation_source': 'live', 'calibration_method': 'object_based', 'live_checks': checks}
    assert live_acceptance_error(report) == ''
    del checks['object_stability']
    checks['table_stability'] = {'result': 'PASS'}
    assert 'object_stability' in live_acceptance_error(report)
