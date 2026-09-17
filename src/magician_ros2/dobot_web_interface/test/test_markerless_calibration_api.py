from unittest.mock import Mock

from dobot_web_interface.system_integration import calibration_is_ready
from dobot_web_interface.web_interface import DobotWebNode


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

