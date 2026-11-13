import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dobot_kinematics.trajectory_validator_server import PoseValidatorService
from dobot_kinematics.collision_detection_server import PyBulletCollisionServer


@pytest.mark.parametrize('change', ['collision_off', 'ground_off', 'stale', 'future',
    'joint_motion', 'long_step', 'rotation', 'nan', 'short_target', 'collision_reject', 'valid'])
def test_strict_visual_servo_path_admission(change):
    validator = PoseValidatorService.__new__(PoseValidatorService)
    validator.enable_collision_check = True
    validator.detect_ground_collision = True
    validator.pose_received_monotonic = time.monotonic()
    validator.dobot_pose = [220., 0., 160., 0.]
    validator.is_target_valid = Mock(return_value=(change != 'collision_reject', 'collision result'))
    request = SimpleNamespace(target=[221., 0., 160., 0.], motion_type=2)
    if change == 'collision_off': validator.enable_collision_check = False
    if change == 'ground_off': validator.detect_ground_collision = False
    if change == 'stale': validator.pose_received_monotonic -= 1
    if change == 'future': validator.pose_received_monotonic += 1
    if change == 'joint_motion': request.motion_type = 1
    if change == 'long_step': request.target[0] += 3
    if change == 'rotation': request.target[3] = 1
    if change == 'nan': request.target[0] = float('nan')
    if change == 'short_target': request.target = [220.]
    response = validator.visual_servo_trajectory_callback(request, SimpleNamespace())
    assert response.is_valid == (change == 'valid')
    assert validator.is_target_valid.called == (change in ('valid', 'collision_reject'))


def test_real_urdf_collision_simulation_for_a_short_linear_path(monkeypatch):
    # PyBullet DIRECT only: no ROS graph, robot transport, or hardware commands.
    monkeypatch.setenv('MAGICIAN_TOOL', 'suction_cup')
    validator = PoseValidatorService.__new__(PoseValidatorService)
    validator.enable_collision_check = validator.detect_ground_collision = True
    validator.collision_step_mm = validator.collision_joint_step_deg = 1.
    validator.collision_server = PyBulletCollisionServer()
    validator.dobot_pose = [220., 0., 80., 0.]
    for axis, limits in enumerate([(-120, 120), (-5, 90), (-15, 90), (-140, 140)], 1):
        setattr(validator, f'axis_{axis}_range', dict(min=limits[0], max=limits[1]))
    validator.pose_received_monotonic = time.monotonic()
    response = validator.visual_servo_trajectory_callback(
        SimpleNamespace(target=[221., 0., 80., 0.], motion_type=2), SimpleNamespace())
    assert response.is_valid, response.message
