import threading
from unittest.mock import Mock

import pytest

from dobot_web_interface.web_interface import DobotWebNode


def _node():
    node = object.__new__(DobotWebNode)
    node._control_lock = threading.RLock()
    node._control_state = 'IDLE'
    node._control_owner = ''
    node._control_ticket = 0
    node._control_stop_acknowledged = False
    node._vision_cancel_event = threading.Event()
    node._operator_cancel_event = threading.Event()
    return node


def test_stop_during_starting_cannot_be_cleared_by_start():
    node = _node()
    ticket = node._begin_control_operation('operator')

    assert node._request_control_stop() is True
    node._acknowledge_control_stop()

    assert node._control_snapshot()['state'] == 'STOPPING'
    assert node._vision_cancel_event.is_set()
    assert node._operator_cancel_event.is_set()
    assert node._mark_control_running(ticket) is False
    with pytest.raises(RuntimeError):
        node._begin_control_operation('operator')

    node._finish_control_operation(ticket)
    assert node._control_snapshot()['state'] == 'IDLE'


def test_start_is_rejected_until_idle_stop_is_acknowledged():
    node = _node()
    assert node._request_control_stop() is False
    assert node._control_snapshot()['state'] == 'STOPPING'

    with pytest.raises(RuntimeError):
        node._begin_control_operation('vision')

    node._acknowledge_control_stop()
    ticket = node._begin_control_operation('vision')
    assert node._mark_control_running(ticket) is True
    assert node._control_snapshot()['state'] == 'RUNNING'
    node._finish_control_operation(ticket)
    assert node._control_snapshot()['state'] == 'IDLE'


def test_fault_rejects_start_until_explicit_reset():
    node = _node()
    node._fault_control_operation()

    with pytest.raises(RuntimeError):
        node._begin_control_operation('operator')

    node._reset_control_fault()
    ticket = node._begin_control_operation('operator')
    assert ticket == 1


def test_automatic_calibration_uses_guarded_load_verify_or_calibrate_service():
    node = object.__new__(DobotWebNode)
    node.calibration_start_client = Mock()
    node.calibration_start_client.service_is_ready.return_value = True
    future = Mock()
    node.calibration_start_client.call_async.return_value = future

    node._dispatch_calibration_verification()

    node.calibration_start_client.call_async.assert_called_once()
    future.add_done_callback.assert_called_once()
