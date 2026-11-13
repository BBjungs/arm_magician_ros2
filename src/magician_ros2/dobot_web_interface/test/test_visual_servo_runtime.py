from concurrent.futures import Future
from dataclasses import asdict
from types import MethodType, SimpleNamespace
from unittest.mock import Mock
import threading
import time

import numpy as np
import pytest
import yaml

from dobot_vision_yolo.visual_servo_controller import SafeStop, ServoConfig, TargetTracker
from dobot_web_interface.visual_servo_runtime import VisualServoRuntime
from dobot_web_interface.web_interface import DobotWebNode


def detection(stamp=10., depth=250.):
    return dict(rgb_stamp=stamp, depth_stamp=stamp, registered_depth=True,
                rgb_frame_id='rgb_optical', depth_frame_id='depth_optical', image_size=[640, 480],
                detections=[dict(class_name='black_cap', depth_valid=True, depth_mm=depth,
                    center_pixel=[320., 240.], bbox=[300., 220., 340., 260.], confidence=.95)])


@pytest.fixture
def runtime(tmp_path):
    n = SimpleNamespace(_goal_lock=threading.RLock(), _integration_lock=threading.RLock(),
        _control_lock=threading.RLock(), _vision_lock=threading.RLock(),
        _latest_tcp_pose=[220., 0., 160., 0.], _latest_joints_deg=[0., 30., 30., 0.],
        _latest_tcp_pose_time=time.monotonic(), _latest_joints_time=time.monotonic(),
        _active_goal_handle=None, _homing_confirmed=True, _alarm_codes=[],
        _alarm_time=time.monotonic(), _system_fault='', _startup_action_active=False,
        _control_state='IDLE', _control_owner='', _control_ticket=0, _control_stop_acknowledged=False,
        _vision_cancel_event=threading.Event(), _operator_cancel_event=threading.Event(),
        _vision_detections=detection(), _vision_detections_time=time.monotonic(),
        _calibration_status={'ready': False, 'state': 'FAIL'})
    for name in ('_control_snapshot', '_begin_control_operation', '_mark_control_running',
                 '_request_control_stop', '_acknowledge_control_stop', '_finish_control_operation',
                 '_fault_control_operation'):
        setattr(n, name, MethodType(getattr(DobotWebNode, name), n))
    n._operation_is_active = lambda: bool(n._control_owner)
    n._calibration_is_active = lambda: False
    n.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=10_000_000_000))
    n._safety = lambda: SimpleNamespace(config=SimpleNamespace(allow_real_motion=True,
        workspace=SimpleNamespace(contains=lambda pose: True)))
    n.create_client = Mock(return_value=Mock(service_is_ready=Mock(return_value=True)))
    n.ptp_action = Mock(server_is_ready=Mock(return_value=True))
    config = asdict(ServoConfig())
    config.update(geometry_confirmed=True, free_volume_min_mm=[100., -150., 0.],
                  free_volume_max_mm=[400., 150., 400.], assembly_radius_mm=20.)
    path = tmp_path / 'servo.yaml'
    path.write_text(yaml.safe_dump({'visual_servo': config}))
    return VisualServoRuntime(n, path)


CONFIRM = dict(workspace_clear=True, estop_tested=True, assembly_envelope_confirmed=True)


def test_explicit_enable_does_not_move_or_require_a_calibration_bundle(runtime):
    result = runtime.enable(CONFIRM)
    assert result['accepted'] and not result['motion_command_sent']
    runtime.node.ptp_action.send_goal_async.assert_not_called()
    assert runtime.node._calibration_status == {'ready': False, 'state': 'FAIL'}


@pytest.mark.parametrize('key', CONFIRM)
def test_enable_requires_each_operator_confirmation(runtime, key):
    with pytest.raises(ValueError):
        runtime.enable({**CONFIRM, key: False})
    runtime.node.ptp_action.send_goal_async.assert_not_called()


@pytest.mark.parametrize('attribute,value', [('_alarm_codes', [1]), ('_alarm_time', 0.),
    ('_latest_tcp_pose_time', 0.), ('_latest_joints_time', 0.), ('_latest_tcp_pose', [float('nan')]*4),
    ('_homing_confirmed', False), ('_system_fault', 'hardware failure'),
    ('_active_goal_handle', object()), ('_startup_action_active', True)])
def test_robot_gates_cannot_be_bypassed(runtime, attribute, value):
    setattr(runtime.node, attribute, value)
    with pytest.raises(SafeStop):
        runtime.enable(CONFIRM)
    runtime.node.ptp_action.send_goal_async.assert_not_called()


def test_workspace_permission_is_not_replaced_by_checkbox(runtime):
    runtime.node._safety = lambda: SimpleNamespace(config=SimpleNamespace(allow_real_motion=False))
    with pytest.raises(SafeStop, match='authorize'):
        runtime.enable(CONFIRM)


def test_stop_during_enable_cannot_create_a_new_permit(runtime):
    runtime.health = Mock(side_effect=lambda **kw: runtime.stop())
    with pytest.raises(SafeStop, match='during ENABLE'):
        runtime.enable(CONFIRM)
    assert runtime.enabled_until == 0


def test_stop_during_start_cannot_be_cleared(runtime):
    runtime.enable(CONFIRM)
    runtime.health = Mock(side_effect=lambda **kw: runtime.stop())
    with pytest.raises(SafeStop, match='during START'):
        runtime.start()
    assert runtime.worker is None
    runtime.node.ptp_action.send_goal_async.assert_not_called()


def prepare_motion(runtime):
    runtime.enable(CONFIRM)
    runtime.node._begin_control_operation('visual_servo')
    runtime.validated_start = np.array(runtime.node._latest_tcp_pose)
    runtime.validated_target = runtime.validated_start + [1., 0., 0., 0.]
    runtime.validated_at = time.monotonic()
    return runtime.validated_target.copy()


def test_late_goal_acceptance_after_timeout_is_cancelled_and_faulted(runtime):
    target = prepare_motion(runtime)
    future = Future()
    runtime.node.ptp_action.send_goal_async.return_value = future
    runtime.node._wait_for_future = Mock(side_effect=TimeoutError('send timeout'))
    with pytest.raises(TimeoutError):
        runtime.move(target, .1, .1)
    assert runtime.uncertain_motion
    handle = Mock(accepted=True)
    future.set_result(handle)
    handle.cancel_goal_async.assert_called()
    # Worker finalization latches uncertainty; no retry can obtain control.
    runtime.node._fault_control_operation()
    with pytest.raises(RuntimeError):
        runtime.start()


def test_stop_before_goal_response_cancels_accepted_motion(runtime):
    target = prepare_motion(runtime)
    response = Future()
    runtime.node.ptp_action.send_goal_async.return_value = response
    terminal = Future()
    terminal.set_result(SimpleNamespace(status=5))
    handle = Mock(accepted=True, get_result_async=Mock(return_value=terminal))
    def wait(*args):
        runtime.stop()
        response.set_result(handle)
        return handle
    runtime.node._wait_for_future = wait
    with pytest.raises(SafeStop):
        runtime.move(target, .1, .1)
    handle.cancel_goal_async.assert_called()
    assert not runtime.uncertain_motion


def test_motion_result_exception_retains_uncertainty(runtime):
    target = prepare_motion(runtime)
    terminal = Future()
    terminal.set_exception(RuntimeError('transport lost'))
    handle = Mock(accepted=True, get_result_async=Mock(return_value=terminal))
    response = Future()
    response.set_result(handle)
    runtime.node.ptp_action.send_goal_async.return_value = response
    runtime.node._wait_for_future = lambda *args: handle
    with pytest.raises(RuntimeError, match='transport lost'):
        runtime.move(target, .1, .1)
    assert runtime.uncertain_motion
    assert runtime.node._active_goal_handle is handle


def test_invalid_terminal_result_keeps_handle_for_cancellation(runtime):
    target = prepare_motion(runtime)
    terminal = Future()
    terminal.set_result(SimpleNamespace(status=2))
    handle = Mock(accepted=True, get_result_async=Mock(return_value=terminal))
    response = Future()
    response.set_result(handle)
    runtime.node.ptp_action.send_goal_async.return_value = response
    runtime.node._wait_for_future = lambda *args: handle
    with pytest.raises(SafeStop, match='not terminal'):
        runtime.move(target, .1, .1)
    assert runtime.uncertain_motion
    runtime.cancel()
    handle.cancel_goal_async.assert_called()


@pytest.mark.parametrize('change', ['expired', 'target', 'start', 'speed'])
def test_path_validation_is_bound_to_pose_target_time_and_speed(runtime, change):
    target = prepare_motion(runtime)
    velocity = .1
    if change == 'expired': runtime.validated_at -= 1
    if change == 'target': target[1] += 1
    if change == 'start': runtime.node._latest_tcp_pose[1] += 1
    if change == 'speed': velocity = .2
    with pytest.raises(SafeStop):
        runtime.move(target, velocity, .1)
    runtime.node.ptp_action.send_goal_async.assert_not_called()


def test_post_motion_median_uses_only_fresh_stationary_batch(runtime):
    samples = iter([detection(10.1, 250.), detection(10.2, 251.), detection(10.3, 250.5)])
    poses = iter([(np.array([220., 0., 160., 0.]), stamp) for stamp in (1., 2., 3.)])
    runtime.health = lambda **kw: next(poses)
    runtime.packet = lambda: next(samples)
    runtime.ros_now = lambda: 10.4
    runtime.tracker = TargetTracker(runtime.config)
    observation = runtime.observe(after_stamp=10.)
    assert observation.feature[2] == 250.5
    assert observation.rgb_stamp == observation.depth_stamp == 10.3


def test_moving_tcp_cannot_be_used_for_learning(runtime):
    samples = iter([detection(10.1), detection(10.2)])
    poses = iter([(np.array([220., 0., 160., 0.]), 1.), (np.array([221., 0., 160., 0.]), 2.)])
    runtime.health = lambda **kw: next(poses)
    runtime.packet = lambda: next(samples)
    runtime.ros_now = lambda: 10.4
    with pytest.raises(SafeStop, match='not stationary'):
        runtime.observe(after_stamp=10.)


def test_shutdown_cancels_and_waits_for_worker_before_ros_teardown(runtime):
    runtime.worker = Mock(is_alive=Mock(return_value=True))
    runtime.node._active_goal_handle = Mock()
    runtime.shutdown()
    runtime.node._active_goal_handle.cancel_goal_async.assert_called()
    runtime.worker.join.assert_called_once()
    assert runtime.uncertain_motion
    assert runtime.node._control_snapshot()['state'] == 'FAULT'
