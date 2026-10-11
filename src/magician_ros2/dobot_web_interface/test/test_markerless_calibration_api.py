from unittest.mock import Mock
from concurrent.futures import Future
from types import SimpleNamespace
import pytest

from dobot_web_interface.system_integration import calibration_is_ready
from dobot_web_interface.web_interface import DobotWebNode


def test_passive_solve_returns_actual_rejection_not_request_acceptance():
    node = Mock()
    node._operation_is_active.return_value = False
    future = Future()
    future.set_result(SimpleNamespace(success=False, message=
                      '{"accepted":false,"reason":"REAL_POSES_REQUIRED: 1/10"}'))
    client = Mock()
    client.service_is_ready.return_value = True
    client.call_async.return_value = future
    node.calibration_passive_clients = {'solve': client}
    result = DobotWebNode.passive_calibration_control(node, 'solve')
    assert not result['success'] and not result['accepted']
    assert '1/10' in result['reason']
    assert not result['motion_command_sent']


def test_passive_capture_rejects_active_robot_operation():
    node = Mock()
    client = Mock()
    node.calibration_passive_clients = {'capture': client}
    node._operation_is_active.return_value = True
    with pytest.raises(RuntimeError, match='Stop active'):
        DobotWebNode.passive_calibration_control(node, 'capture')
    client.call_async.assert_not_called()


def _ready_status(**updates):
    status = {
        "architecture": "markerless_hand_eye", "ready": True,
        "state": "READY", "result": "PASS", "age_sec": 0.1,
        "bundle_loaded": True, "geometry_verified": True,
        "verification_status": "PASS", "reload_verification_status": "PASS",
        "blockers": [],
    }
    status.update(updates)
    return status


def test_marker_ids_and_zero_detections_do_not_affect_readiness():
    assert calibration_is_ready(_ready_status(
        detected_ids=[], required_ids=[0, 1, 2, 3],
        marker_status={"missing_ids": [0, 1, 2, 3]}))


def test_fake_old_board_status_cannot_produce_ready():
    assert not calibration_is_ready({
        "ready": True, "state": "READY", "result": "PASS", "age_sec": 0.1,
        "calibration_valid": True, "detected_ids": [0, 1, 2, 3],
    })


def test_web_calibration_button_calls_markerless_service():
    node = Mock()
    node._operation_is_active.return_value = False
    node.calibration_recalibrate_client.service_is_ready.return_value = True
    node.calibration_recalibrate_client.call_async.return_value.done.return_value = False
    node.calibration_recalibrate_service = "/calibration/recalibrate"
    node.calibration_status_topic = "/calibration/status"
    result = DobotWebNode.vision_auto_calibrate(node, {})
    node.calibration_recalibrate_client.call_async.assert_called_once()
    assert result["architecture"] == "markerless_hand_eye"
    assert result["status_topic"] == "/calibration/status"


def test_web_status_is_authoritative_topic_snapshot():
    node = Mock()
    node.calibration_runtime_status.return_value = _ready_status()
    assert DobotWebNode.vision_calibration(node) == node.calibration_runtime_status.return_value

