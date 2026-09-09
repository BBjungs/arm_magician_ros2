import pytest

from dobot_kinematics.collision_detection_server import PyBulletCollisionServer


def test_zero_distance_path_is_finite():
    waypoints = PyBulletCollisionServer.linear_trajecory_to_discrete_waypoints(
        [200.0, 0.0, 100.0],
        [200.0, 0.0, 100.0],
    )
    assert waypoints == [[200.0, 0.0, 100.0], [200.0, 0.0, 100.0]]


def test_linear_path_includes_both_endpoints():
    waypoints = PyBulletCollisionServer.linear_trajecory_to_discrete_waypoints(
        [0.0, 0.0, 0.0],
        [5.0, 0.0, 0.0],
        step_len=2.0,
    )
    assert waypoints[0] == [0.0, 0.0, 0.0]
    assert waypoints[-1] == [5.0, 0.0, 0.0]
    assert len(waypoints) == 4


def test_linear_path_rejects_invalid_step():
    with pytest.raises(ValueError, match="positive"):
        PyBulletCollisionServer.linear_trajecory_to_discrete_waypoints(
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            step_len=0.0,
        )
