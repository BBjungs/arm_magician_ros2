import math

import numpy as np

from dobot_vision_yolo.eye_in_hand_transform import make_transform
from dobot_vision_yolo.eye_in_hand_transform import rpy_matrix
from dobot_vision_yolo.markerless_hand_eye import depth_health
from dobot_vision_yolo.markerless_hand_eye import MarkerlessThresholds
from dobot_vision_yolo.markerless_hand_eye import rigid_transform
from dobot_vision_yolo.markerless_hand_eye import solve_hand_eye


def _pose(x, y, z, roll, pitch, yaw):
    return make_transform(rpy_matrix([roll, pitch, yaw]), [x, y, z])


def test_zero_depth_is_rejected_before_feature_matching():
    status = depth_health(np.zeros((400, 640), dtype=np.uint16))

    assert status["ok"] is False
    assert status["valid_ratio"] == 0.0
    assert status["reason"] == "invalid_depth"


def test_rigid_transform_recovers_known_motion():
    source = np.array(
        [[0.0, 0.0, 400.0], [50.0, 0.0, 420.0], [0.0, 70.0, 380.0], [40.0, 60.0, 450.0]]
    )
    expected = _pose(12.0, -8.0, 3.0, 2.0, -3.0, 7.0)
    target = (expected[:3, :3] @ source.T).T + expected[:3, 3]

    actual = rigid_transform(source, target)

    assert np.allclose(actual, expected, atol=1e-8)


def test_hand_eye_solver_recovers_mount_with_observable_motion():
    camera_to_tool = _pose(18.0, -12.0, 46.0, 177.0, 2.0, -4.0)
    base_to_target = _pose(240.0, 15.0, -35.0, 0.0, 0.0, 0.0)
    robot = [
        _pose(190.0, -60.0, 125.0, 0.0, 0.0, -20.0),
        _pose(235.0, -45.0, 145.0, 8.0, -5.0, 5.0),
        _pose(260.0, 0.0, 135.0, -7.0, 9.0, 25.0),
        _pose(220.0, 45.0, 155.0, 11.0, 6.0, 45.0),
        _pose(180.0, 35.0, 140.0, -10.0, -8.0, 70.0),
        _pose(205.0, -5.0, 165.0, 6.0, 12.0, 95.0),
    ]
    target_to_camera = [
        np.linalg.inv(camera_to_tool) @ np.linalg.inv(gripper_to_base) @ base_to_target
        for gripper_to_base in robot
    ]

    result = solve_hand_eye(robot, target_to_camera)

    assert result["calibration_valid"] is True
    assert np.allclose(result["transform"], camera_to_tool, atol=1e-5)
    assert result["quality"]["translation_residual_p95_mm"] < 1e-5
    assert result["quality"]["rotation_residual_p95_deg"] < 1e-5


def test_dobot_yaw_only_pose_set_is_rejected_as_degenerate():
    robot = [
        _pose(180.0, -50.0, 120.0, 0.0, 0.0, yaw)
        for yaw in (-30.0, 0.0, 35.0, 70.0)
    ]
    camera = [np.eye(4) for _ in robot]

    result = solve_hand_eye(robot, camera)

    assert result["calibration_valid"] is False
    assert result["observability"]["rotation_axis_rank"] == 1
    assert "robot_rotation_axes_are_degenerate" in result["validation_errors"]


def test_thresholds_never_accept_all_zero_depth():
    permissive = MarkerlessThresholds(min_depth_valid_ratio=0.001)

    assert depth_health(np.zeros((20, 20)), permissive)["ok"] is False
