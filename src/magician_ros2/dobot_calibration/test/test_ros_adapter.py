"""No robot movement: run with a private ROS_DOMAIN_ID for ROS smoke tests."""

from pathlib import Path
from types import SimpleNamespace
import time

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('dobot_msgs.action._point_to_point')
from std_srvs.srv import Trigger
from dobot_calibration.node import CalibrationNode


@pytest.fixture
def node():
    rclpy.init()
    value = CalibrationNode()
    try:
        yield value
    finally:
        value.stop.set()
        if value.worker:
            value.worker.join(timeout=2)
        value.destroy_node()
        rclpy.shutdown()


def test_startup_and_missing_mount_fail_closed_without_motion(node):
    assert not node.is_ready()
    response = node.ready_service(Trigger.Request(), Trigger.Response())
    assert response.success is False
    node.settings['camera_id'] = 'test-only-device'
    node.settings['mount_model'] = str(Path(__file__).resolve().parents[1] / 'config/mount_model.yaml')
    started, _ = node.start_operation(False)
    assert started
    node.worker.join(timeout=3)
    assert node.state == 'FAIL'
    assert 'verified' in node.reason
    assert node.active_goal is None
    assert not node.is_ready()


def test_verify_missing_file_never_moves_and_cancel_blocks(node, tmp_path):
    node.settings['calibration_file'] = str(tmp_path / 'absent.npz')
    response = node.verify_service(Trigger.Request(), Trigger.Response())
    assert response.success is False
    assert node.worker is None
    node.cancel_service(Trigger.Request(), Trigger.Response())
    assert node.stop.is_set()
    assert not node.is_ready()


def test_failed_status_cannot_reuse_an_earlier_pass(node):
    node.workflow = SimpleNamespace(report={'result': 'PASS', 'metrics': {'pose_count': 4}})
    node.status('FAIL', 'Verification expired')
    status = node.status_payload()
    assert status['result'] == 'FAIL'
    assert status['ready'] is False
    assert status['reason'] == 'Verification expired'


def test_verify_service_requests_verification_only(node, tmp_path, monkeypatch):
    path = tmp_path / 'existing.npz'
    path.touch()
    node.settings['calibration_file'] = str(path)
    calls = []
    def start(recalibrate, verify_only=False):
        calls.append((recalibrate, verify_only))
        return True, 'started'
    monkeypatch.setattr(node, 'start_operation', start)
    response = node.verify_service(Trigger.Request(), Trigger.Response())
    assert response.success
    assert calls == [(False, True)]


def test_alarm_during_solving_is_latched(node):
    from dobot_msgs.msg import DobotAlarmCodes
    node.status('SOLVING')
    alarm = DobotAlarmCodes()
    alarm.alarms_list = [1]
    node.on_alarms(alarm)
    alarm.alarms_list = []
    node.on_alarms(alarm)
    assert node.stop.is_set()
    assert node.state == 'FAIL'
    assert not node.is_ready()


def test_telemetry_loss_during_solving_is_latched(node, monkeypatch):
    node.status('SOLVING')
    monkeypatch.setattr(node, 'health_error', lambda: 'Robot telemetry is stale')
    node.supervise()
    assert node.stop.is_set()
    assert node.state == 'FAIL'
    assert node.status_payload()['result'] == 'FAIL'


def test_quality_parameters_cannot_change_during_an_operation(node):
    from rclpy.parameter import Parameter
    result = node.set_parameters_atomically([
        Parameter('quality.max_translation_residual_m', value=0.5)])
    assert not result.successful
    assert node.limits.max_translation_residual_m == 0.004


@pytest.mark.parametrize('state', ['CALIBRATING', 'VERIFYING', 'READY'])
def test_invalid_depth_during_motion_or_verification_is_latched(node, state):
    from cv_bridge import CvBridge
    from sensor_msgs.msg import CameraInfo, PointCloud2
    bridge = CvBridge()
    depth = bridge.cv2_to_imgmsg(np.zeros((48, 64), np.uint16), '16UC1')
    rgb = bridge.cv2_to_imgmsg(np.zeros((48, 64, 3), np.uint8), 'bgr8')
    node.status(state)
    node.on_camera(rgb, depth, CameraInfo(), PointCloud2())
    assert node.stop.is_set()
    assert node.state == 'FAIL'
    assert 'DEPTH_ALL_ZERO' in node.reason
    assert node.status_payload()['depth_quality']['valid_count'] == 0
    assert not node.is_ready()


def test_invalid_depth_stops_calibration_even_without_a_point_cloud(node):
    from cv_bridge import CvBridge
    depth = CvBridge().cv2_to_imgmsg(np.zeros((48, 64), np.uint16), '16UC1')
    node.status('CALIBRATING')
    node.on_depth(depth)
    assert node.bundle is None
    assert node.stop.is_set()
    assert node.state == 'FAIL'
    assert node.live_depth_quality['code'] == 'DEPTH_ALL_ZERO'


def test_mathematical_pass_alone_does_not_authorize_live_picking(node, monkeypatch):
    node.workflow = SimpleNamespace(state='READY', verified_monotonic=time.monotonic(),
                                    report={'result': 'PASS', 'metrics': {}})
    node.status('READY')
    monkeypatch.setattr(node, 'health_error', lambda: '')
    assert not node.is_ready()
    node.supervise()
    assert node.state == 'FAIL'
    assert node.status_payload()['result'] == 'FAIL'
    assert 'LIVE_VALIDATION_NOT_COMPLETED' in node.reason
