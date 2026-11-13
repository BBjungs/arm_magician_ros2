from dataclasses import replace

import numpy as np
import pytest

from dobot_vision_yolo.visual_servo_controller import ServoConfig, SafeStop, TargetTracker


def packet(stamp=10., **changes):
    result = dict(rgb_stamp=stamp, depth_stamp=stamp, registered_depth=True,
                  image_size=[640, 480], rgb_frame_id='rgb_optical', depth_frame_id='depth_optical',
                  detections=[dict(class_name='black_cap', depth_valid=True, depth_mm=250.,
                                   center_pixel=[320., 240.], bbox=[300., 220., 340., 260.],
                                   confidence=.95)])
    result.update(changes)
    return result


def geometry_config(**changes):
    return replace(ServoConfig(), free_volume_min_mm=[100., -150., 0.],
                   free_volume_max_mm=[400., 150., 400.], assembly_radius_mm=20.,
                   geometry_confirmed=True, **changes)


@pytest.mark.parametrize('name', ['require_fresh_rgbd', 'require_robot_feedback',
    'require_trajectory_validation', 'require_operator_enable', 'stop_on_target_loss'])
def test_safety_flags_cannot_be_disabled(name):
    with pytest.raises(ValueError):
        replace(ServoConfig(), **{name: False})


@pytest.mark.parametrize('changes', [dict(max_step_mm=3.01), dict(initial_probe_mm=.01),
    dict(velocity_ratio=.001), dict(acceleration_ratio=.11), dict(damping=0),
    dict(gain=float('nan')), dict(max_iterations=81), dict(stationary_samples=2),
    dict(calibration_required=True)])
def test_config_rejects_unsafe_or_ineffective_limits(changes):
    with pytest.raises(ValueError):
        replace(ServoConfig(), **changes)


def test_tracking_uses_geometry_not_per_frame_ids():
    tracker = TargetTracker(ServoConfig())
    first = packet()
    first['detections'][0]['id'] = 1
    tracker.select(first, 10.)
    second = packet(10.1)
    second['detections'][0]['id'] = 99
    value, reference, confidence, _, _, _ = tracker.select(second, 10.1)
    assert value.tolist() == [320., 240., 250.]
    assert reference.tolist() == [320., 240.]
    assert confidence == .95


@pytest.mark.parametrize('change', [dict(rgb_stamp=8.), dict(depth_stamp=9.8),
    dict(rgb_stamp=11.), dict(registered_depth=False), dict(error='camera failure'),
    dict(image_size=[]), dict(rgb_frame_id=''), dict(detections=[])])
def test_stale_invalid_or_missing_target_fails_closed(change):
    with pytest.raises(SafeStop):
        TargetTracker(ServoConfig()).select(packet(**change), 10.)


def test_repeated_and_pre_motion_exposures_rejected():
    tracker = TargetTracker(ServoConfig())
    tracker.select(packet(), 10.)
    with pytest.raises(SafeStop):
        tracker.select(packet(), 10.1)
    with pytest.raises(SafeStop):
        tracker.select(packet(10.2), 10.2, after_stamp=10.3)


@pytest.mark.parametrize('change', [dict(image_size=[1280, 960]), dict(rgb_frame_id='other_camera')])
def test_camera_identity_and_resolution_must_stay_constant(change):
    tracker = TargetTracker(ServoConfig())
    tracker.select(packet(), 10.)
    with pytest.raises(SafeStop):
        tracker.select(packet(10.1, **change), 10.1)


def test_ambiguous_target_is_never_chosen_arbitrarily():
    data = packet()
    data['detections'].append(dict(data['detections'][0]))
    with pytest.raises(SafeStop, match='ambiguous'):
        TargetTracker(ServoConfig()).select(data, 10.)


@pytest.mark.parametrize('field,value', [('confidence', .2), ('depth_mm', float('nan')),
    ('depth_valid', False), ('class_name', 'white_cap'), ('bbox', [-1, 2, 40, 30]),
    ('center_pixel', [20, 20])])
def test_invalid_detection_rejected(field, value):
    data = packet()
    data['detections'][0][field] = value
    with pytest.raises(SafeStop):
        TargetTracker(ServoConfig()).select(data, 10.)


def test_camera_tool_swept_volume_is_mandatory_even_without_calibration():
    start, end = np.array([220., 0., 160., 0.]), np.array([223., 0., 160., 0.])
    with pytest.raises(SafeStop, match='not confirmed'):
        ServoConfig().check_geometry(start, end)
    geometry_config().check_geometry(start, end)
    with pytest.raises(SafeStop, match='Swept'):
        geometry_config().check_geometry(start, [120, 0, 160, 0])
    with pytest.raises(SafeStop, match='Stop depth'):
        geometry_config(stop_depth_mm=50).check_geometry(start, end)
