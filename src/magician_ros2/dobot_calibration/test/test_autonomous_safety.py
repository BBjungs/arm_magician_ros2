"""Regression tests with injected transport; never evidence of real motion."""

from concurrent.futures import Future
from contextlib import nullcontext
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from dobot_calibration.autonomous import AutomaticCalibration
from dobot_calibration.autonomous_backend import AutomaticBackend
from dobot_calibration.geometry import CalibrationError, transform
from dobot_calibration.motion_authorization import ACKNOWLEDGEMENTS, RunAuthorization
from dobot_calibration.node import CalibrationNode
from dobot_calibration.scene_validation import compare_scene
from dobot_calibration.token_lifecycle import TokenLifecycle
from test_automatic_calibration import Backend, load_workspace, workspace_data


def confirmation(plan='test-plan'):
    return {**dict.fromkeys(ACKNOWLEDGEMENTS, True), 'plan_fingerprint': plan}


@pytest.mark.parametrize('field', ACKNOWLEDGEMENTS)
def test_each_on_site_confirmation_is_required(field):
    request = confirmation()
    request[field] = False
    with pytest.raises(CalibrationError, match=field):
        RunAuthorization.issue(request, run_id='r', plan_fingerprint='test-plan',
                               purpose='COMMISSIONING_TWO_POSES', ttl=120)


def test_authorization_binds_plan_run_scope_and_expires_during_active_run():
    token = RunAuthorization.issue(confirmation(), run_id='r', plan_fingerprint='test-plan',
                                  purpose='COMMISSIONING_TWO_POSES', ttl=120, now=10)
    params = dict(run_id='r', plan_fingerprint='test-plan', purpose='COMMISSIONING_TWO_POSES')
    assert token.error(**params, now=129) == ''
    assert token.error(**params, now=130) == 'AUTHORIZATION_EXPIRED'
    for key in params:
        changed = {**params, key: 'different'}
        assert token.error(**changed, now=11) == 'AUTHORIZED_PLAN_MISMATCH'
    assert token.error(**params, abort=True, now=11) == 'ABORT_ACTIVE'
    token.revoked = True
    assert token.error(**params, now=11) == 'AUTHORIZATION_REVOKED'


class WaitingBackend(Backend):
    def wait_for_authorization(self, checkpoint):
        self.engine.update('WAITING_FOR_OPERATOR_AUTHORIZATION', plan_fingerprint='test-plan')
        self.waiting.set()
        self.engine.wait_authorization(checkpoint, 1)


def waiting_engine():
    backend = WaitingBackend()
    backend.waiting = threading.Event()
    backend.engine = engine = AutomaticCalibration(backend)
    return engine, backend


def test_start_validates_then_waits_without_motion_and_rejects_replay():
    engine, backend = waiting_engine()
    assert engine.start()[0]
    assert backend.waiting.wait(2)
    assert 'move' not in backend.events
    assert not engine.start()[0]
    assert not engine.authorize(confirmation('other-plan'))[0]
    assert engine.authorize(confirmation())[0]
    assert not engine.authorize(confirmation())[0]
    engine.worker.join(3)
    assert not engine.worker.is_alive()
    assert engine.snapshot()['state'] == 'CANDIDATE_VERIFIED'


def test_abort_while_waiting_never_dispatches():
    engine, backend = waiting_engine()
    assert engine.start()[0]
    assert backend.waiting.wait(2)
    engine.abort()
    engine.worker.join(2)
    assert engine.snapshot()['state'] == 'SAFE_STOP'
    assert 'move' not in backend.events


def test_expired_operator_wait_fails_without_motion():
    engine, backend = waiting_engine()
    assert engine.start()[0]
    engine.worker.join(3)
    assert engine.snapshot()['state'] == 'FAULT'
    assert 'OPERATOR_AUTHORIZATION_EXPIRED' in engine.snapshot()['reason']
    assert 'move' not in backend.events


def test_commissioning_scope_stops_at_two_poses_and_never_solves_ten():
    engine, backend = waiting_engine()
    records = []
    backend.commissioning_result = lambda: {'state': 'COMMISSIONING_COMPLETE', 'production_ready': False}
    backend.record_commissioning = lambda result: records.append(result)
    assert engine.start('COMMISSIONING_TWO_POSES')[0]
    assert backend.waiting.wait(2)
    assert engine.authorize(confirmation())[0]
    engine.worker.join(3)
    assert engine.snapshot()['state'] == 'COMMISSIONING_COMPLETE'
    assert backend.events.count('move') == 2
    assert backend.events.count('capture') == 2
    assert 'solve' not in backend.events
    assert len(records) == 1


def test_failed_cleanup_cannot_record_commissioning():
    engine, backend = waiting_engine()
    backend.failure = 'close'
    backend.commissioning_result = lambda: {'state': 'COMMISSIONING_COMPLETE'}
    backend.record_commissioning = lambda _: pytest.fail('unverified commissioning recorded')
    engine.start('COMMISSIONING_TWO_POSES')
    assert backend.waiting.wait(2)
    assert engine.authorize(confirmation())[0]
    engine.worker.join(3)
    assert engine.snapshot()['state'] == 'FAULT'


def test_pause_and_abort_at_the_actual_send_boundary():
    engine, backend = waiting_engine()
    sent = []
    engine.pause()
    def dispatch():
        try:
            with engine.dispatch_guard():
                sent.append('send')
        except InterruptedError:
            pass
    worker = threading.Thread(target=dispatch)
    worker.start()
    time.sleep(.1)
    assert not sent
    engine.abort()
    engine.resume()
    worker.join(2)
    assert not worker.is_alive()
    assert not sent


def test_missing_authorization_never_enters_transport():
    node = SimpleNamespace(_execute_guarded_motion=lambda *_: pytest.fail('motion'))
    with pytest.raises(CalibrationError, match='OPERATOR_AUTHORIZATION_REQUIRED'):
        AutomaticBackend(node).move(transform(translation=[.185, 0, .1]))


def test_failed_ptp_restore_latches_uncertainty_and_releases_ownership():
    engine = SimpleNamespace(snapshot=lambda: {'state': 'NEXT_POSE'}, update=lambda *a, **kw: None)
    lock = threading.Lock()
    lock.acquire()
    node = SimpleNamespace(automatic=engine, operation_lock=lock, ptp_param_state_uncertain=False,
                           status=lambda *_: None, _restore_arm_ptp=lambda _: (False, 'bad readback'))
    backend = AutomaticBackend(node)
    backend.owned = True
    backend.ptp_before = {'velocity_percent': 100, 'acceleration_percent': 100}
    with pytest.raises(CalibrationError, match='PTP_RESTORE_FAILED'):
        backend.close()
    assert backend.ptp_restore == 'FAIL'
    assert node.ptp_param_state_uncertain
    assert not backend.owned and not lock.locked()


def test_dry_run_flag_cannot_satisfy_real_commissioning(tmp_path):
    node = SimpleNamespace(automatic_commissioning={'state': 'DRY_RUN_PASS'},
        passive_session=SimpleNamespace(mount_fingerprint='test-mount'),
        settings={'camera_id': 'test-camera'})
    backend = AutomaticBackend(node)
    backend.workspace = load_workspace(tmp_path, workspace_data())
    assert not backend.commissioning_valid()


def test_whole_plan_collision_is_checked_before_dispatch(tmp_path, monkeypatch):
    import dobot_kinematics.collision_detection_server as collision
    calls = []
    class Collision:
        def validate_trajectory(self, motion_type, current, target, ground, **kw):
            calls.append((motion_type, current, target, ground))
            return False
    monkeypatch.setattr(collision, 'PyBulletCollisionServer', Collision)
    backend = AutomaticBackend(SimpleNamespace(
        mount=SimpleNamespace(envelope_radius_m=.03, translation_error_bound_m=.001),
        settings={'planning_soft_margin_deg': 2.}))
    backend.workspace = load_workspace(tmp_path, workspace_data())
    with pytest.raises(CalibrationError, match='NO_FEASIBLE_AUTOMATIC_PLAN'):
        backend.select_plan(transform(translation=[.19, 0, .125]))
    assert len(calls) == 8
    assert all(mode == 2 and ground for mode, _, _, ground in calls)


def test_real_commissioning_token_activation_uses_lifecycle_owner():
    lifecycle = TokenLifecycle()
    token = lifecycle.create('s', 'm', 120)
    lifecycle.activate(token)
    assert token.state == 'ACTIVE_RUN'
    assert not hasattr(token, 'activate')


def test_legacy_token_expiry_still_applies_after_activation(monkeypatch):
    import dobot_calibration.token_lifecycle as module
    monkeypatch.setattr(module.time, 'monotonic', lambda: 10.)
    manager = TokenLifecycle()
    token = manager.create('s', 'm', 120)
    manager.activate(token)
    monkeypatch.setattr(module.time, 'monotonic', lambda: 130.)
    assert manager.validate(token, 's', 'm', 2) == 'TOKEN_EXPIRED'


def motion_node():
    node = object.__new__(CalibrationNode)
    node.motion_dispatch_lock = threading.Lock()
    node.lock = threading.RLock()
    node.stop = threading.Event()
    node.active_goal = None
    node.motion_acceptance_future = None
    node.motion_stop_confirmation_required = False
    node.motion_stop_result = None
    node.motion_stop_terminal_stamp = None
    node.history = [(10., transform(translation=[.15, 0, .1]), np.zeros(4))]
    node.settings = {'motion_timeout_s': .1}
    node.now_s = lambda: 10.
    node.automatic = SimpleNamespace(backend=SimpleNamespace(owned=False))
    node.checkpoint = lambda: None
    node.health_error = lambda: ''
    future = Future()
    future.set_result(SimpleNamespace(is_valid=True))
    node.validator = SimpleNamespace(wait_for_service=lambda **_: True, call_async=lambda _: future)
    return node


def test_delayed_goal_acceptance_after_timeout_is_cancelled_and_send_is_recorded():
    node = motion_node()
    accepted = Future()
    node.motion = SimpleNamespace(wait_for_server=lambda **_: True, send_goal_async=lambda _: accepted)
    def wait(future, timeout):
        if future is accepted:
            raise CalibrationError('injected acceptance timeout')
        return future.result()
    node.wait_future = wait
    with pytest.raises(CalibrationError, match='timeout'):
        node._execute_guarded_motion(node.history[-1][1], transform(translation=[.185, 0, .1]), lambda *_: None)
    cancelled = []
    accepted.set_result(SimpleNamespace(accepted=True, cancel_goal_async=lambda: cancelled.append(True)))
    assert cancelled == [True]
    assert node._atomic_motion_sent is True
    assert node.stop.is_set()
    assert not node.motion_dispatch_lock.locked()


def test_duplicate_transport_goal_is_rejected():
    node = motion_node()
    node.motion_dispatch_lock.acquire()
    with pytest.raises(CalibrationError, match='ALREADY_ACTIVE'):
        node._execute_guarded_motion(None, None, lambda *_: pytest.fail('dispatch'))
    node.motion_dispatch_lock.release()


def test_ptp_restore_requires_verified_physical_stop_not_just_cancel_request():
    node = motion_node()
    node.ptp_param_state_uncertain = False
    node._set_ptp_common_params = lambda *_: pytest.fail('unsafe restore while stop is unproven')
    node._confirm_motion_stopped_before_restore = lambda: (_ for _ in ()).throw(
        CalibrationError('PHYSICAL_STOP_UNVERIFIED'))
    restored, reason = node._restore_arm_ptp({'ptp_before': {'velocity_percent': 100, 'acceleration_percent': 100}})
    assert not restored
    assert 'PHYSICAL_STOP_UNVERIFIED' in reason
    assert node.ptp_param_state_uncertain


def test_cancel_terminal_result_plus_fresh_stationary_feedback_allows_restore():
    node = motion_node()
    node.motion_stop_confirmation_required = True
    node.motion_stop_terminal_stamp = 9.
    node.now_s = lambda: 10.
    node.tcp_stamp = node.joints_stamp = 9.9
    node._table_touchoff_stability = lambda: (True, {}, None)
    node._confirm_motion_stopped_before_restore()
    assert not node.motion_stop_confirmation_required


def test_scene_thresholds_reject_obstacle_change_and_nonfinite_values():
    base = {'plane': [0, 0, 1, 0], 'extent_m': [.2, .2, .1],
            'depth_histogram': [1, 1], 'voxel_occupancy': 100, 'feature_count': 100}
    assert compare_scene(base, base)['passed']
    assert not compare_scene(base, {**base, 'extent_m': [.3, .2, .1]})['passed']
    assert not compare_scene(base, {**base, 'depth_histogram': [np.nan, 1]})['passed']


def test_validator_policy_requires_enabled_collision_and_measured_axis_limits():
    from rcl_interfaces.msg import ParameterValue
    node = motion_node()
    arrays = [[-120, 120], [-5, 90], [-15, 90], [-140, 140]]
    values = [ParameterValue(type=7, integer_array_value=value) for value in arrays]
    values += [ParameterValue(type=1, bool_value=True), ParameterValue(type=1, bool_value=True),
               ParameterValue(type=3, double_value=2.), ParameterValue(type=3, double_value=2.)]
    future = Future()
    future.set_result(SimpleNamespace(values=values))
    node.validator_parameters = SimpleNamespace(wait_for_service=lambda **_: True, call_async=lambda _: future)
    node.wait_future = lambda f, _: f.result()
    assert node._automatic_validator_policy()['axis_3_range'] == [-15, 90]
    for index in (4, 5):
        values[index].bool_value = False
        with pytest.raises(CalibrationError, match='POLICY_UNSAFE'):
            node._automatic_validator_policy()
        values[index].bool_value = True
    values[6].double_value = 10.
    with pytest.raises(CalibrationError, match='POLICY_UNSAFE'):
        node._automatic_validator_policy()


def test_competing_legacy_transaction_cannot_take_autonomous_ownership():
    lock = threading.Lock()
    lock.acquire()
    node = SimpleNamespace(calibration_transaction_lock=lock)
    backend = AutomaticBackend(node)
    with pytest.raises(CalibrationError, match='CALIBRATION_TRANSACTION_ACTIVE'):
        backend.prepare(lambda: None)
    assert not backend.owned
    lock.release()


def test_autonomous_after_commissioning_uses_the_actual_pose_two_viewpoint():
    pose = transform(translation=[.185, 0, .1])
    capture = SimpleNamespace(base_T_tool=pose)
    node = SimpleNamespace(automatic_commissioning_capture=capture,
        scene_baseline={'viewpoint': 'old-pose-one'}, _scene_signature=lambda c: {'viewpoint': 'real-pose-two'})
    backend = AutomaticBackend(node)
    backend.commissioning_valid = lambda: True
    signature, reference = backend.initial_scene_reference(pose)
    assert signature['viewpoint'] == 'real-pose-two'
    np.testing.assert_allclose(reference, pose)
    with pytest.raises(CalibrationError, match='rebaseline required'):
        backend.initial_scene_reference(transform(translation=[.205, 0, .1]))


@pytest.mark.parametrize('blocker', ('DEPTH_STALE', 'DEPTH_UNSTABLE', 'ROBOT_TELEMETRY_ERROR',
                                   'ROBOT_ALARM', 'SAFETY_UNVERIFIED'))
def test_live_hardware_fault_prevents_autonomous_transport(blocker):
    engine = SimpleNamespace(run_id='r', purpose='COMMISSIONING_TWO_POSES',
        abort_event=threading.Event(), snapshot=lambda: {'state': 'MOVING'}, update=lambda *a, **kw: None)
    node = SimpleNamespace(automatic=engine, stop=threading.Event(),
        hardware_readiness=lambda: SimpleNamespace(ready=False, reason=blocker), health_error=lambda: '',
        _execute_guarded_motion=lambda *_: pytest.fail('motion after hardware fault'))
    backend = AutomaticBackend(node)
    backend.owned = True
    backend.plan_fingerprint = 'test-plan'
    backend.authorization = RunAuthorization.issue(confirmation(), run_id='r', plan_fingerprint='test-plan',
        purpose='COMMISSIONING_TWO_POSES', ttl=120)
    backend.diagnostics = lambda: {'blockers': [blocker]}
    with pytest.raises(CalibrationError, match=blocker):
        backend.move(transform(translation=[.185, 0, .1]))
