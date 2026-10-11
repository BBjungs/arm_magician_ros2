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


def test_startup_and_missing_mount_fail_closed_without_motion(node, monkeypatch):
    from dobot_calibration.camera_identity import CameraIdentity
    assert not node.is_ready()
    response = node.ready_service(Trigger.Request(), Trigger.Response())
    assert response.success is False
    node.settings['camera_id'] = 'test-only-device'
    node.camera_identity = CameraIdentity('test-only-device', 'YAML', True, 'PASS', '')
    monkeypatch.setattr(node, '_resolve_camera_identity', lambda: node.camera_identity)
    node.settings['mount_model'] = str(Path(__file__).resolve().parents[1] / 'config/mount_model.yaml')
    started, _ = node.start_operation(False)
    assert started
    node.worker.join(timeout=3)
    assert node.state == 'FAIL'
    assert ('verified' in node.reason or 'factory camera TF unavailable' in node.reason)
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


def test_passive_capture_services_have_no_motion_calls(node):
    import inspect
    capture_source = inspect.getsource(node.capture_pose_service)
    prepare_source = inspect.getsource(node._prepare_passive_capture)
    for forbidden in ('self.move(', 'PTP_action', 'send_goal', 'publish('):
        assert forbidden not in capture_source
        assert forbidden not in prepare_source
    assert node.status_payload()['geometry_verified'] is False


def test_passive_solve_requires_ten_real_poses_and_releases_lock(node):
    response = node.solve_passive_service(Trigger.Request(), Trigger.Response())
    assert not response.success
    assert '0/10' in response.message
    assert not node.operation_lock.locked()
    assert node.active_goal is None
    assert not node.is_ready()


def test_baseline_rejection_preserves_gate_diagnostics(node):
    import json
    response = node.scene_baseline_service(Trigger.Request(), Trigger.Response())
    payload = json.loads(response.message)
    assert not response.success
    assert payload['accepted'] is False
    assert payload['quality_status'] == 'REJECTED'
    assert payload['eligible_for_preflight'] is False
    assert not node.operation_lock.locked()


def test_automatic_start_without_workspace_never_dispatches(node, tmp_path, monkeypatch):
    node.settings['automatic_workspace_file'] = str(tmp_path / 'not-surveyed.yaml')
    monkeypatch.setattr(node, '_execute_guarded_motion', lambda *args: pytest.fail('must not move'))
    count = len(node.passive_captures)
    response = node.automatic_start_service(Trigger.Request(), Trigger.Response())
    assert response.success
    node.automatic.worker.join(3)
    assert not node.automatic.worker.is_alive()
    status = node.automatic.snapshot()
    assert status['state'] == 'FAULT'
    assert 'WORKSPACE_NOT_CONFIGURED' in status['reason']
    assert len(node.passive_captures) == count
    assert not node.operation_lock.locked()


def test_automatic_start_cannot_overlap_operation(node):
    node.operation_lock.acquire()
    try:
        response = node.automatic_start_service(Trigger.Request(), Trigger.Response())
        assert not response.success
        assert node.automatic.worker is None
    finally:
        node.operation_lock.release()


def test_passive_solve_cannot_overlap_another_operation(node):
    node.operation_lock.acquire()
    try:
        response = node.solve_passive_service(Trigger.Request(), Trigger.Response())
        assert not response.success
        assert node.operation_lock.locked()
    finally:
        node.operation_lock.release()


def test_first_passive_pose_creates_plan_and_saves_exact_exposure(node, tmp_path, monkeypatch):
    from test_passive_session import sample_capture
    from dobot_calibration.passive_session import PassiveSessionStore
    capture = sample_capture()
    capture.quality.update({
        'point_cloud_source': 'DEPTH_DEPROJECTION', 'filtered_cloud_points': 3,
        'cloud_frame_id': 'optical', 'cloud_timestamp': 123.494,
        'native_cross_validation': {},
        'exposure': {'rgb_stamp': 123.49, 'depth_stamp': 123.494,
                     'joints': [0., 0., 0., 0.], 'tcp_span_mm': 0., 'joint_span_deg': 0.,
                     'intrinsics_fingerprint': 'exact-exposure', 'camera_info': {'width': 5}},
    })
    node.passive_captures, node.passive_capture_metadata = [], []
    node.passive_session = PassiveSessionStore(tmp_path, 'mount', 'camera')
    monkeypatch.setattr(node, '_prepare_passive_capture', lambda: None)
    monkeypatch.setattr(node, 'capture', lambda: capture)
    monkeypatch.setattr(node, 'passive_guidance', lambda: {})
    monkeypatch.setattr('dobot_calibration.node.cv2.Laplacian', lambda *args: np.array([-100., 100.]))
    response = node.capture_pose_service(Trigger.Request(), Trigger.Response())
    assert response.success, response.message
    assert len(node.passive_session.manifest['target_poses']) == 10
    with np.load(node.passive_session.session_dir / 'pose_001.npz') as data:
        assert float(data['rgb_timestamp']) == 123.49
        assert str(data['intrinsics_fingerprint']) == 'exact-exposure'
        assert float(data['rgb_depth_sync_skew_ms']) == pytest.approx(4.)
    assert not node.operation_lock.locked()


def test_failed_status_cannot_reuse_an_earlier_pass(node):
    node.workflow = SimpleNamespace(report={'result': 'PASS', 'metrics': {'pose_count': 4}},
                                    bundle_loaded=False, context={}, samples_collected=0,
                                    samples_accepted=0, samples_rejected=0, reload_verified=False)
    node.status('FAIL', 'Verification expired')
    status = node.status_payload()
    assert status['result'] == 'FAIL'
    assert status['ready'] is False
    assert status['reason'] == 'Verification expired'
    node.cancel_service(Trigger.Request(), Trigger.Response())
    assert node.status_payload()['reason'] == 'Verification expired'


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
    node.depth_quality_worker.join(timeout=2)
    assert not node.depth_quality_worker.is_alive()
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
    node.depth_quality_worker.join(timeout=2)
    assert not node.depth_quality_worker.is_alive()
    assert node.stop.is_set()
    assert node.state == 'FAIL'
    assert node.live_depth_quality['code'] == 'DEPTH_ALL_ZERO'


def test_duplicate_depth_stamp_is_decoded_once(node, monkeypatch):
    from cv_bridge import CvBridge
    depth = CvBridge().cv2_to_imgmsg(np.zeros((48, 64), np.uint16), '16UC1')
    calls = []

    def decode(*args):
        calls.append(args)
        return np.zeros((48, 64), np.uint16)

    monkeypatch.setattr(node.bridge, 'imgmsg_to_cv2', decode)
    node.on_depth(depth)
    node.on_depth(depth)
    node.depth_quality_worker.join(timeout=1)
    assert len(calls) == 1


def _payload(node, stamp):
    from sensor_msgs.msg import Image
    value = Image()
    value.header.frame_id = node.settings['camera_frame']
    value.header.stamp.sec = int(stamp)
    value.header.stamp.nanosec = int(round((stamp - int(stamp)) * 1e9))
    return value


def _cached_info(node, stamp=10.0):
    from sensor_msgs.msg import CameraInfo
    value = CameraInfo()
    value.header.frame_id = node.settings['camera_frame']
    value.header.stamp.sec = int(stamp)
    value.header.stamp.nanosec = int(round((stamp - int(stamp)) * 1e9))
    node.on_camera_info(value)


def test_unmatched_new_rgb_retains_previous_valid_synchronized_payload(node):
    _cached_info(node)
    rgb1, depth1, rgb2 = _payload(node, 10.000), _payload(node, 10.012), _payload(node, 10.033)
    node.on_rgb_payload(rgb1)
    node._pair_raw_payload('depth', depth1)
    assert node.bundle[:2] == (rgb1, depth1)
    node.on_rgb_payload(rgb2)  # readiness may sample in this callback gap
    assert node.bundle[:2] == (rgb1, depth1)
    assert node.last_sync_pairing_reason == 'NO_DEPTH_SAMPLE'


def test_nearest_queue_pairing_avoids_crossing_pairs(node):
    _cached_info(node)
    rgb1, rgb2, depth2 = _payload(node, 10.000), _payload(node, 10.033), _payload(node, 10.043)
    node.on_rgb_payload(rgb1)
    node.on_rgb_payload(rgb2)
    node._pair_raw_payload('depth', depth2)
    assert node.bundle[:2] == (rgb2, depth2)
    assert node.last_sync_pair_skew_ms == pytest.approx(10.0)


@pytest.mark.parametrize('skew,accepted', [(0.099, True), (0.101, False)])
def test_raw_payload_pairing_keeps_the_100ms_contract(node, skew, accepted):
    _cached_info(node)
    node.on_rgb_payload(_payload(node, 10.0))
    node._pair_raw_payload('depth', _payload(node, 10.0 + skew))
    assert (node.bundle is not None) is accepted
    if not accepted:
        assert node.last_sync_pairing_reason == 'PAIR_SKEW_OVER_100MS'


def test_invalid_candidate_cannot_overwrite_an_accepted_payload(node):
    _cached_info(node)
    rgb, depth = _payload(node, 10.0), _payload(node, 10.012)
    node.on_rgb_payload(rgb)
    node._pair_raw_payload('depth', depth)
    node.on_rgb_payload(_payload(node, 20.0))
    node._pair_raw_payload('depth', _payload(node, 20.101))
    assert node.bundle[:2] == (rgb, depth)
    assert node.last_sync_pairing_reason == 'PAIR_SKEW_OVER_100MS'


def test_valid_pair_commit_advances_generation_and_refreshes_monotonic_age(node):
    _cached_info(node)
    node.on_rgb_payload(_payload(node, 10.000))
    node._pair_raw_payload('depth', _payload(node, 10.020))
    assert node.sync_pair_success_count == 1
    assert node.sync_payload_generation == 1
    assert node.last_sync_commit_monotonic is not None
    assert node.last_valid_synchronized_capture_monotonic == node.last_sync_commit_monotonic
    assert node.last_sync_commit_rgb_stamp == pytest.approx(10.000)
    assert node.last_sync_commit_depth_stamp == pytest.approx(10.020)
    assert node.last_sync_commit_skew_ms == pytest.approx(20.0)


def test_impossible_pair_is_consumed_once_not_retried_indefinitely(node):
    _cached_info(node)
    node.on_rgb_payload(_payload(node, 10.000))
    node._pair_raw_payload('depth', _payload(node, 10.500))
    assert node.sync_pair_reject_count == 1
    assert node.rgb_dropped_too_old_count == 1
    assert not node.rgb_payload_queue
    assert len(node.depth_payload_queue) == 1
    node._pair_raw_payload('depth', _payload(node, 10.533))
    assert node.sync_pair_reject_count == 1


def test_explicit_activation_clears_stale_sync_state(node, monkeypatch):
    node.bundle = (_payload(node, 1.0), _payload(node, 1.01), object())
    node.last_valid_synchronized_capture_monotonic = time.monotonic()
    node.sync_pair_success_count = 9
    node.sync_payload_generation = 9
    node.rgb_payload_queue.append(_payload(node, 1.0))
    node.depth_payload_queue.append(_payload(node, 1.0))
    monkeypatch.setattr(node, 'create_subscription', lambda *args, **kwargs: object())
    node.ensure_camera_sync('passive_capture')
    assert node.bundle is None
    assert node.last_valid_synchronized_capture_monotonic is None
    assert node.sync_pair_success_count == 0
    assert node.sync_payload_generation == 0
    assert not node.rgb_payload_queue and not node.depth_payload_queue


@pytest.mark.parametrize('service', [
    'capture_pose_service', 'passive_capture_test_service',
    'scene_baseline_service', 'scene_verify_service',
])
def test_passive_requests_cannot_change_an_active_operation(node, service, monkeypatch):
    monkeypatch.setattr(node, 'capture', lambda: pytest.fail('Unexpected capture'))
    node.stop.set()
    node.operation_lock.acquire()
    try:
        response = getattr(node, service)(Trigger.Request(), Trigger.Response())
        assert not response.success
        assert 'already running' in response.message
        assert not node.passive_capture_active
        assert node.stop.is_set()
        assert node.operation_lock.locked()
    finally:
        node.operation_lock.release()


def test_passive_failure_releases_operation_and_allows_explicit_retry(node, monkeypatch):
    from dobot_calibration.geometry import CalibrationError

    def fail_capture():
        assert node.operation_lock.locked()
        assert node.passive_capture_active
        assert not node.stop.is_set()
        accepted, reason = node.start_operation(False)
        assert not accepted and 'already running' in reason
        raise CalibrationError('No fresh exposure')

    monkeypatch.setattr(node, '_prepare_passive_capture', fail_capture)
    monkeypatch.setattr(node, '_scene_geometry_diagnostic', lambda: {})
    node.stop.set()
    response = node.passive_capture_test_service(Trigger.Request(), Trigger.Response())
    assert not response.success
    assert 'No fresh exposure' in response.message
    assert not node.passive_capture_active
    assert not node.operation_lock.locked()


def test_plan_dry_run_does_not_require_real_motion_commissioning(node, monkeypatch):
    calls = []

    def preflight(*, include_full_auto_commissioning=True):
        calls.append(include_full_auto_commissioning)
        return (['FULL_AUTO_CALIBRATION_NOT_COMMISSIONED']
                if include_full_auto_commissioning else []), 'READY'

    monkeypatch.setattr(node, 'auto_preflight', preflight)
    node.supervised_auto.validate_target = lambda target: []
    assert node.supervised_auto.start([{'pose_index': 1}], dry_run=True)[0]
    node.supervised_auto.worker.join(timeout=2)
    assert node.supervised_auto.snapshot()['state'] == 'COMPLETE'
    assert calls == [False]
    assert not node.full_auto_calibration_commissioned
    assert not node.supervised_auto.start([{'pose_index': 1}], dry_run=False)[0]


def test_mathematical_pass_alone_does_not_authorize_live_picking(node, monkeypatch):
    node.workflow = SimpleNamespace(state='READY', verified_monotonic=time.monotonic(),
                                    report={'result': 'PASS', 'metrics': {}},
                                    bundle_loaded=False, context={}, samples_collected=0,
                                    samples_accepted=0, samples_rejected=0, reload_verified=False)
    node.status('READY')
    monkeypatch.setattr(node, 'health_error', lambda: '')
    assert not node.is_ready()
    node.supervise()
    assert node.state == 'FAIL'
    assert node.status_payload()['result'] == 'FAIL'
    assert 'LIVE_VALIDATION_NOT_COMPLETED' in node.reason


def test_carrier_lookup_uses_exposure_time_and_selected_frame(node, monkeypatch):
    from geometry_msgs.msg import TransformStamped
    node.settings['carrier_frame'] = 'measured_bracket'
    calls = []
    item = TransformStamped()
    item.transform.translation.x = 0.21
    item.transform.rotation.w = 1.
    def lookup(target, source, stamp):
        calls.append((target, source, stamp.nanoseconds))
        return item
    monkeypatch.setattr(node.carrier_tf, 'lookup_transform', lookup)
    matrix = node.carrier_pose_at(123.25)
    assert calls == [('magician_base_link', 'measured_bracket', 123250000000)]
    assert matrix[0, 3] == 0.21


def test_factory_camera_transform_uses_configured_reference_and_optical_frames(node, monkeypatch):
    from geometry_msgs.msg import TransformStamped
    calls = []
    item = TransformStamped()
    item.transform.translation.x = 0.012
    item.transform.translation.z = -0.004
    item.transform.rotation.w = 1.0

    def lookup(target, source, stamp):
        calls.append((target, source, stamp.nanoseconds))
        return item

    monkeypatch.setattr(node.carrier_tf, 'lookup_transform', lookup)
    value = node.camera_reference_to_optical()
    assert calls == [('camera_link', 'camera_color_optical_frame', 0)]
    np.testing.assert_allclose(value[:3, 3], [0.012, 0.0, -0.004])


def test_missing_carrier_transform_has_no_tcp_fallback(node, monkeypatch):
    from tf2_ros import LookupException
    from dobot_calibration.geometry import CalibrationError
    node.settings['carrier_frame'] = 'missing_bracket'
    def missing(*args):
        raise LookupException('absent')
    monkeypatch.setattr(node.carrier_tf, 'lookup_transform', missing)
    with pytest.raises(CalibrationError, match='TF unavailable at exposure'):
        node.carrier_pose_at(100.)


def test_stale_carrier_transform_fails_health_even_when_hardware_ready(node, monkeypatch):
    from geometry_msgs.msg import TransformStamped
    node.settings['carrier_frame'] = 'bracket'
    monkeypatch.setattr(node, 'hardware_readiness', lambda: SimpleNamespace(ready=True))
    monkeypatch.setattr(node, 'now_s', lambda: 100.)
    item = TransformStamped()
    item.header.stamp.sec = 98
    item.transform.rotation.w = 1.
    monkeypatch.setattr(node.carrier_tf, 'lookup_transform', lambda *args: item)
    assert 'TF is stale' in node.health_error()


@pytest.mark.parametrize('age_ms,expected_fresh', [
    (50.0, True), (600.0, True), (None, False),
    (-1.0, False), (float('nan'), False),
])
def test_health_heartbeat_does_not_refresh_old_depth(node, monkeypatch, age_ms, expected_fresh):
    import json
    from std_msgs.msg import String
    monkeypatch.setattr(node, 'now_s', lambda: 100.0)
    node.on_camera_health(String(data=json.dumps({'streams': {'depth': {
        'fresh': True, 'rate_ok': True, 'timestamp_valid': True, 'valid': True,
        'fps': 30, 'max_stamp_gap_ms': 34, 'valid_ratio': 0.5,
        'age_ms': age_ms,
    }}})))
    assert node.hardware_readiness().depth_fresh is expected_fresh
    if expected_fresh:
        assert node.live_depth_stamp == pytest.approx(100.0 - age_ms / 1000.0)
        monkeypatch.setattr(node, 'now_s', lambda: 101.6)
        assert not node.hardware_readiness().depth_fresh
