from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock
import time

import pytest

from dobot_motion.PTP_server import DobotPTPServer
import dobot_motion.PTP_server as ptp


@pytest.fixture
def server(monkeypatch):
    value = object.__new__(DobotPTPServer)
    value._state_lock = Lock()
    value._pose_event = Event()
    value._goal_reserved = True
    value.motion_type = 1
    value.dobot_pose = [200.0, 0.0, 100.0, 0.0]
    value.active_alarms = False
    value._pose_received_at = time.monotonic()
    value._alarms_received_at = time.monotonic()
    value.state_timeout_sec = 1.0
    value.motion_timeout_sec = 1.0
    value.get_logger = Mock(return_value=Mock())
    monkeypatch.setattr(ptp, 'bot', Mock())
    monkeypatch.setattr(ptp.time, 'sleep', lambda seconds: None)
    return value


def goal(cancel=False):
    return SimpleNamespace(
        request=SimpleNamespace(target_pose=[200.0, 0.0, 100.0, 0.0], motion_type=1),
        is_cancel_requested=cancel, canceled=Mock(), abort=Mock(),
        succeed=Mock(), publish_feedback=Mock(),
    )


@pytest.mark.parametrize('field', ['_pose_received_at', '_alarms_received_at'])
@pytest.mark.parametrize('stamp', [None, 0.0])
def test_missing_or_old_state_is_not_fresh(server, field, stamp):
    setattr(server, field, stamp)
    assert not server._state_is_fresh()


def test_fresh_state(server):
    assert server._state_is_fresh()


def test_nonfinite_pose_invalidates_fresh_state(server):
    server.tcp_position_callback(SimpleNamespace(data=[float('nan'), 0.0, 0.1, 0.0]))
    assert not server._state_is_fresh()


def test_cancel_before_dispatch_sends_no_motion(server):
    handle = goal(cancel=True)
    server.execute_callback(handle)
    ptp.bot.set_point_to_point_command.assert_not_called()
    handle.canceled.assert_called_once()
    handle.succeed.assert_not_called()
    assert not server._goal_reserved


@pytest.mark.parametrize('unsafe', ['alarm', 'stale'])
def test_unsafe_state_before_dispatch_sends_no_motion(server, unsafe):
    if unsafe == 'alarm':
        server.active_alarms = True
    else:
        server._alarms_received_at = None
    handle = goal()
    server.execute_callback(handle)
    ptp.bot.set_point_to_point_command.assert_not_called()
    handle.abort.assert_called_once()
    assert not server._goal_reserved


def test_lost_state_aborts_and_stops_queue(server):
    server._state_is_fresh = Mock(side_effect=[True, False])
    handle = goal()
    server.execute_callback(handle)
    ptp.bot.set_point_to_point_command.assert_called_once()
    ptp.bot.stop_queue.assert_called_once_with(force=True)
    ptp.bot.clear_queue.assert_called_once()
    handle.abort.assert_called_once()
    handle.succeed.assert_not_called()


def test_stale_state_cannot_be_reported_as_success(server):
    server._state_is_fresh = Mock(side_effect=[True, True, True, False])
    handle = goal()
    server.execute_callback(handle)
    handle.abort.assert_called_once()
    handle.succeed.assert_not_called()


def test_cancel_takes_priority_over_target_reached(server):
    handle = goal()
    ticks = [False, False, False, True]
    class CancelingGoal:
        request = handle.request
        canceled = handle.canceled
        abort = handle.abort
        succeed = handle.succeed
        publish_feedback = handle.publish_feedback
        @property
        def is_cancel_requested(self):
            return ticks.pop(0)
    server.execute_callback(CancelingGoal())
    handle.canceled.assert_called_once()
    handle.succeed.assert_not_called()
    ptp.bot.stop_queue.assert_called_once_with(force=True)


def test_failed_stop_aborts_instead_of_reporting_canceled(server):
    handle = goal()
    def cancel_after_dispatch(*args):
        handle.is_cancel_requested = True
    ptp.bot.set_point_to_point_command.side_effect = cancel_after_dispatch
    ptp.bot.stop_queue.side_effect = OSError('serial disconnected')
    server.execute_callback(handle)
    handle.abort.assert_called_once()
    handle.canceled.assert_not_called()
    ptp.bot.start_queue.assert_not_called()
