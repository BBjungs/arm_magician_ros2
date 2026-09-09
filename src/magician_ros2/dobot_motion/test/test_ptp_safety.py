import inspect
from threading import Event, Lock

from dobot_motion.PTP_server import DobotPTPServer


def test_execute_callback_is_synchronous_for_rclpy_executor():
    assert not inspect.iscoroutinefunction(DobotPTPServer.execute_callback)


def test_goal_reached_requires_complete_pose():
    assert not DobotPTPServer.is_goal_reached([1, 2, 3, 4], [], 0.2)


def test_goal_reached_uses_threshold():
    assert DobotPTPServer.is_goal_reached(
        [1.0, 2.0, 3.0, 4.0],
        [1.1, 1.9, 3.1, 3.9],
        0.2,
    )
    assert not DobotPTPServer.is_goal_reached(
        [1.0, 2.0, 3.0, 4.0],
        [1.3, 2.0, 3.0, 4.0],
        0.2,
    )


def test_pose_stability_allows_small_measurement_noise():
    assert DobotPTPServer.is_pose_stable(
        [[1.0, 2.0, 3.0, 4.0], [1.01, 2.01, 2.99, 4.01]],
    )


def test_only_one_goal_can_be_reserved():
    server = object.__new__(DobotPTPServer)
    server._state_lock = Lock()
    server._pose_event = Event()
    server._goal_reserved = False
    server.motion_type = None

    assert server._reserve_goal(1)
    assert not server._reserve_goal(2)

    server._release_goal()
    assert server._reserve_goal(2)
