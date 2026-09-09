"""Exercise the real offline collision model; never import the hardware driver."""

import numpy as np
import pytest

pytest.importorskip('pybullet')
pytest.importorskip('ament_index_python')
from dobot_kinematics.collision_detection_server import PyBulletCollisionServer
from dobot_kinematics import collision_detection_server as collision


@pytest.mark.parametrize('target', [[202., 0., 150., 5.], np.array([202., 0., 150., 5.])])
def test_calibration_movl_accepts_python_and_ros_array_targets(target, monkeypatch):
    monkeypatch.setenv('MAGICIAN_TOOL', 'none')
    server = PyBulletCollisionServer()
    assert server.validate_trajectory(2, [200., 0., 150., 0.], target, True)
    # Every validation must release its physics client.
    assert not collision.pyb.isConnected()


def test_failed_model_load_releases_collision_client(monkeypatch):
    monkeypatch.setenv('MAGICIAN_TOOL', 'unknown')
    with pytest.raises(ValueError, match='MAGICIAN_TOOL'):
        PyBulletCollisionServer().validate_trajectory(2, [200., 0., 150., 0.],
                                                      [202., 0., 150., 5.], True)
    assert not collision.pyb.isConnected()


def test_zero_distance_waypoints_include_both_endpoints():
    point = [200., 0., 150.]
    points = PyBulletCollisionServer.linear_trajecory_to_discrete_waypoints(point, point)
    assert points == [point, point]


def test_synthetic_calibration_poses_pass_real_trajectory_service(monkeypatch):
    rclpy = pytest.importorskip('rclpy')
    pytest.importorskip('dobot_msgs.srv._evaluate_ptp_trajectory')
    from dobot_msgs.srv import EvaluatePTPTrajectory
    from dobot_kinematics.trajectory_validator_server import PoseValidatorService
    from dobot_calibration.workflow import calibration_poses
    from synthetic_scene import START
    import time
    monkeypatch.setenv('MAGICIAN_TOOL', 'none')
    rclpy.init()
    node = PoseValidatorService()
    try:
        node.dobot_pose = [*map(float, START[:3, 3] * 1000), 0.]
        for pose in calibration_poses(START) + calibration_poses(START, True):
            request = EvaluatePTPTrajectory.Request()
            request.motion_type = 2
            request.target = [*map(float, pose[:3, 3] * 1000),
                              float(np.rad2deg(np.arctan2(pose[1, 0], pose[0, 0])))]
            node.pose_received_monotonic = time.monotonic()
            response = node.calibration_trajectory_callback(request, EvaluatePTPTrajectory.Response())
            assert response.is_valid, (request.target, response.message)
            node.dobot_pose = list(request.target)
    finally:
        node.destroy_node()
        rclpy.shutdown()
