import threading
import json
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from dobot_calibration.autonomous import AutomaticCalibration
from dobot_calibration.autonomous_backend import AutomaticBackend
from dobot_calibration.calibration_workspace import CalibrationWorkspace, automatic_plan
from dobot_calibration.geometry import CalibrationError, RetryableCaptureError, transform


class Backend:
    def __init__(self):
        self.events = []
        self.failure = None

    def event(self, name):
        self.events.append(name)
        if name == self.failure:
            raise RuntimeError('injected ' + name)

    def prepare(self, checkpoint):
        self.event('prepare')
        return automatic_plan(transform(translation=[.15, 0, .10]))

    def wait_for_authorization(self, checkpoint):
        # Explicit test double: no hardware transport exists in this backend.
        pass

    def validate(self, first, second):
        self.event('validate')

    def check(self):
        pass

    def move(self, target):
        self.event('move')

    def settle(self, target, checkpoint):
        self.event('settle')

    def capture(self, target):
        self.event('capture')
        return object()

    def accept(self, capture, index):
        self.event('accept')

    def solve(self, checkpoint):
        self.event('solve')
        return {'state': 'CANDIDATE_VERIFIED'}

    def persist_status(self, status):
        pass

    def stop(self):
        self.event('stop')

    def close(self):
        self.event('close')


@pytest.fixture
def observation_backend(tmp_path, monkeypatch):
    from dobot_calibration.baseline_admission import AuthoritativeBaselineAdmissionGate, REQUIRED
    from dobot_calibration.passive_session import PassiveSessionStore
    from dobot_calibration import autonomous_backend as module

    clock = SimpleNamespace(now=0., healthy_after=1., cancelled_at=None, scene_ready=True)
    events = []
    gate = AuthoritativeBaselineAdmissionGate()
    node = SimpleNamespace(
        settings={'capture_timeout_s': 15.}, stop=threading.Event(),
        passive_capture_active=False, passive_session_error='', scene_baseline=None,
        passive_session=PassiveSessionStore(tmp_path, 'mount', 'camera'),
        bundle=(None, None, 'intrinsics'), authoritative_baseline_gate=gate,
        intrinsics_fingerprint=lambda info: info,
        _prepare_passive_capture=lambda: events.append('subscribe'),
        health_error=lambda: '',
        _scene_signature=lambda capture: {'captured_at': clock.now},
    )
    backend = AutomaticBackend(node)
    node.automatic = AutomaticCalibration(backend)
    backend.check = lambda: None
    node.hardware_readiness = lambda: SimpleNamespace(
        ready=clock.now >= clock.healthy_after, reason='DEPTH_UNSTABLE')
    node._authoritative_baseline_snapshot = lambda: {
        key: clock.scene_ready and clock.now >= clock.healthy_after for key in REQUIRED}
    node._scene_baseline_path = lambda: node.passive_session.session_dir / 'scene_baseline.yaml'
    node.capture = lambda: events.append('capture') or object()

    def persist():
        events.append('persist')
        node._scene_baseline_path().write_text(yaml.safe_dump(node.scene_baseline))

    def wait(seconds):
        clock.now += seconds
        if clock.cancelled_at is not None and clock.now >= clock.cancelled_at:
            node.automatic.abort_event.set()

    node._persist_scene_baseline = persist
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock.now)
    monkeypatch.setattr(node.stop, 'wait', wait)
    return backend, node, clock, events


def test_first_automatic_run_warms_inputs_and_creates_measured_baseline(observation_backend):
    backend, node, clock, events = observation_backend
    backend.prepare_observations()
    assert events == ['subscribe', 'capture', 'persist']
    assert clock.now >= 11.  # One second warm-up, then the unchanged ten-second gate.
    assert node.passive_session.manifest['accepted_pose_count'] == 0
    assert node._scene_baseline_path().is_file()
    assert not node.passive_capture_active
    assert not node.automatic.snapshot().get('motion_command_sent', False)


@pytest.mark.parametrize('quality', ['VALID', 'REJECTED', 'INCOMPATIBLE'])
def test_existing_baseline_is_never_replaced_automatically(observation_backend, quality):
    backend, node, clock, events = observation_backend
    node.passive_session.new('intrinsics')
    path = node._scene_baseline_path()
    original = yaml.safe_dump({'quality_status': quality})
    path.write_text(original)
    if quality == 'VALID':
        node.scene_baseline = {'original': True}
    backend.prepare_observations()
    assert events == ['subscribe']
    assert path.read_text() == original
    assert clock.now < 2.


@pytest.mark.parametrize('failure', ['timeout', 'abort', 'lost_readiness', 'capture_abort', 'storage'])
def test_initial_baseline_failure_never_persists_valid_scene(observation_backend, failure):
    backend, node, clock, events = observation_backend
    expected = {
        'timeout': 'OBSERVATION_WARMUP_TIMEOUT', 'abort': 'cancelled',
        'lost_readiness': 'HARDWARE_NOT_READY', 'capture_abort': 'Operator abort',
        'storage': 'disk full',
    }[failure]
    if failure == 'timeout':
        clock.healthy_after = 100.
    elif failure == 'abort':
        clock.cancelled_at = .2
    elif failure == 'lost_readiness':
        node.capture = lambda: setattr(clock, 'scene_ready', False) or object()
    elif failure == 'capture_abort':
        node.capture = lambda: node.automatic.abort_event.set() or object()
    else:
        def fail_write():
            raise OSError('disk full')
        node._persist_scene_baseline = fail_write
    with pytest.raises((CalibrationError, InterruptedError, OSError), match=expected):
        backend.prepare_observations()
    assert node.scene_baseline is None
    assert not node._scene_baseline_path().exists()
    assert not node.passive_capture_active
    assert 'persist' not in events


def test_automatic_observations_preserve_incompatible_session(observation_backend):
    backend, node, _, events = observation_backend
    node.passive_session_error = 'camera changed'
    with pytest.raises(CalibrationError, match='SESSION_INCOMPATIBLE'):
        backend.prepare_observations()
    assert node.passive_session.manifest is None
    assert events == ['subscribe']
    assert not node.passive_capture_active


def test_new_fit_measures_current_view_without_overwriting_passive_baseline(observation_backend):
    backend, node, clock, events = observation_backend
    node.passive_session.new('intrinsics')
    node.scene_baseline = {'old_viewpoint': True}
    path = node._scene_baseline_path()
    path.write_text('old evidence\n')
    backend.commissioning_valid = lambda: False
    pose = transform(translation=[.18725, 0, .13725])
    node.capture = lambda: SimpleNamespace(base_T_tool=pose)
    reference, measured_pose = backend.initial_scene_reference(pose)
    assert reference['captured_at'] >= 11.
    np.testing.assert_array_equal(measured_pose, pose)
    assert node.scene_baseline == {'old_viewpoint': True}
    assert path.read_text() == 'old evidence\n'
    assert node.passive_session.manifest['accepted_pose_count'] == 0
    assert not node.passive_capture_active
    assert not node.automatic.snapshot().get('motion_command_sent', False)


def test_saved_verification_keeps_existing_scene_reference(observation_backend):
    backend, node, _, _ = observation_backend
    backend.commissioning_valid = lambda: False
    backend.reusing_saved = True
    node.scene_baseline = {'existing_reference': True}
    node.capture = lambda: pytest.fail('must not replace saved verification reference')
    pose = transform(translation=[.18725, 0, .13725])
    assert backend.initial_scene_reference(pose)[0] is node.scene_baseline


@pytest.mark.parametrize('failure', ['timeout', 'abort', 'capture_abort', 'lost_readiness', 'moved'])
def test_run_reference_fails_without_changing_existing_evidence(observation_backend, failure):
    backend, node, clock, _ = observation_backend
    node.scene_baseline = {'existing_reference': True}
    pose = transform(translation=[.18725, 0, .13725])

    def capture():
        if failure == 'capture_abort':
            node.automatic.abort_event.set()
        if failure == 'lost_readiness':
            clock.scene_ready = False
        measured = pose.copy()
        if failure == 'moved':
            measured[0, 3] += .002
        return SimpleNamespace(base_T_tool=measured)

    node.capture = capture
    if failure == 'timeout':
        clock.healthy_after = 100.
    if failure == 'abort':
        clock.cancelled_at = .2
    expected = {'timeout': 'OBSERVATION_WARMUP_TIMEOUT', 'abort': 'Operator abort',
                'capture_abort': 'Operator abort', 'lost_readiness': 'HARDWARE_NOT_READY',
                'moved': 'ROBOT_MOVED_SINCE_PLAN_VALIDATION'}[failure]
    with pytest.raises((CalibrationError, InterruptedError), match=expected):
        backend.capture_run_reference(pose)
    assert node.scene_baseline == {'existing_reference': True}
    assert not node.passive_capture_active


@pytest.mark.parametrize('change', ['none', 'scene', 'pose'])
def test_run_reference_requires_independent_same_viewpoint_comparison(observation_backend, change):
    backend, node, _, _ = observation_backend
    pose = transform(translation=[.18725, 0, .13725])
    base = {'plane': [0, 0, 1, 0], 'extent_m': [.2, .2, .1],
            'depth_histogram': [1, 1], 'voxel_occupancy': 100, 'feature_count': 100}
    backend.scene_reference, backend.scene_pose = base, pose
    measured = pose.copy()
    if change == 'pose':
        measured[0, 3] += .003
    node.capture = lambda: SimpleNamespace(base_T_tool=measured)
    node._scene_signature = lambda _: {**base, 'extent_m': [.3, .2, .1]} if change == 'scene' else base
    if change == 'none':
        backend.verify_scene(pose)
    else:
        with pytest.raises(CalibrationError, match='SCENE_VERIFY_FAILED'):
            backend.verify_scene(pose)
    assert not node.passive_capture_active


def test_ten_pose_sequence_needs_no_operator_capture_calls():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    engine.run()
    assert backend.events[:10] == ['prepare'] + ['validate'] * 9
    assert backend.events[10:-2] == ['move', 'settle', 'capture', 'accept'] * 10
    assert backend.events[-2:] == ['solve', 'close']
    assert engine.snapshot()['accepted_pose_count'] == 10
    assert engine.snapshot()['state'] == 'CANDIDATE_VERIFIED'
    assert engine.snapshot()['production_ready'] is False


def test_image_retry_does_not_move_again_or_count_rejected_pose():
    backend = Backend()
    accepted = []
    def accept(capture, index):
        if backend.events.count('capture') < 3:
            raise RetryableCaptureError('blur')
        accepted.append(index)
    backend.accept = accept
    engine = AutomaticCalibration(backend)
    engine.run()
    assert accepted == list(range(1, 11))
    assert backend.events.count('move') == 10
    assert backend.events.count('capture') == 12
    assert engine.snapshot()['accepted_pose_count'] == 10


def test_image_retry_exhaustion_stops_without_next_pose():
    backend = Backend()
    def reject(*args):
        raise RetryableCaptureError('bad RGB-D')
    backend.accept = reject
    engine = AutomaticCalibration(backend)
    engine.run()
    assert 'CAPTURE_RETRIES_EXHAUSTED' in engine.snapshot()['reason']
    assert engine.snapshot()['accepted_pose_count'] == 0
    assert backend.events.count('capture') == 3
    assert backend.events.count('move') == 1
    assert 'solve' not in backend.events


@pytest.mark.parametrize('stop_kind', ['abort', 'sensor', 'authorization'])
def test_live_fault_during_rejected_image_prevents_retry(stop_kind):
    backend = Backend()
    engine = AutomaticCalibration(backend)
    def reject(*args):
        if stop_kind == 'abort':
            engine.abort()
        else:
            def failed_check():
                raise CalibrationError(stop_kind + ' lost')
            backend.check = failed_check
        raise RetryableCaptureError('blur')
    backend.accept = reject
    engine.run()
    assert engine.snapshot()['state'] in ('FAULT', 'SAFE_STOP')
    assert backend.events.count('capture') == 1
    assert backend.events.count('move') == 1


def test_missing_authorization_never_dispatches_motion():
    backend = Backend()
    def denied(checkpoint):
        raise CalibrationError('OPERATOR_AUTHORIZATION_EXPIRED')
    backend.wait_for_authorization = denied
    engine = AutomaticCalibration(backend)
    engine.run()
    assert engine.snapshot()['state'] == 'FAULT'
    assert 'move' not in backend.events


def test_saved_bundle_uses_three_verification_poses_without_ten_pose_collection():
    backend = Backend()
    backend.reusing_saved = True
    backend.prepare = lambda checkpoint: automatic_plan(transform(translation=[.15, 0, .10]))[:3]
    engine = AutomaticCalibration(backend)
    engine.run()
    assert engine.snapshot()['reused_saved']
    assert engine.snapshot()['total_poses'] == 3
    assert backend.events.count('move') == backend.events.count('capture') == 3


def test_verified_geometry_waits_for_live_acceptance_and_cleanup_before_ready():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    pending = []
    def finalize(result, checkpoint):
        checkpoint()
        pending.append(result)
        assert not engine.snapshot()['production_ready']
    def close():
        pending[0].update(state='AWAITING_LIVE_VALIDATION', production_ready=False,
                          reason='LIVE_VALIDATION_NOT_COMPLETED', completed_unix_s=1234)
    backend.finalize, backend.close = finalize, close
    engine.run()
    assert engine.snapshot()['state'] == 'AWAITING_LIVE_VALIDATION'
    assert not engine.snapshot()['production_ready']
    assert engine.snapshot()['last_completed_unix_s'] == 1234


def test_saved_backend_verifies_without_fitting_again(monkeypatch, tmp_path):
    from dobot_calibration import autonomous_backend as module
    phases, checked = [], []
    node = SimpleNamespace(automatic=SimpleNamespace(update=phases.append), mount=object(), limits=object())
    backend = AutomaticBackend(node)
    backend.reusing_saved = True
    backend.saved_solution, backend.saved_anchor = object(), object()
    backend.context = {}
    backend.captures = [SimpleNamespace(base_T_tool=np.eye(4)) for _ in range(3)]
    backend.store = SimpleNamespace(session_dir=tmp_path, manifest={'session_id': 'test'})
    backend.workspace = SimpleNamespace(digest='test-workspace')
    monkeypatch.setattr(module, 'solve_session', lambda *args, **kwargs: pytest.fail('must not refit'))
    monkeypatch.setattr(module, 'verify', lambda solution, anchor, captures, *args:
                        checked.append(captures) or {'result': 'PASS'})
    monkeypatch.setattr(module, 'save_bundle', lambda *args: None)
    monkeypatch.setattr(module, 'load_bundle', lambda *args: (backend.saved_solution, backend.saved_anchor))
    result = backend.solve(lambda: None)
    assert checked == [backend.captures, backend.captures]
    assert phases == ['VERIFYING', 'SAVING', 'VERIFYING']
    assert result['reused_saved'] and not result['production_ready']


@pytest.mark.parametrize('restore_ok', [True, False])
def test_production_bundle_does_not_bypass_live_acceptance_or_ptp_restore(monkeypatch, tmp_path, restore_ok):
    from dobot_calibration import autonomous_backend as module
    candidate = tmp_path / 'candidate.npz'
    np.savez(candidate, metadata=json.dumps({'verification': {'result': 'PASS'}}))
    statuses, phases, writes = [], [], []
    node = SimpleNamespace(settings={'calibration_file': str(tmp_path / 'production.npz')},
        mount=SimpleNamespace(rotation_seed_verified=True), limits=object(), workflow=None,
        stop=threading.Event(), operation_lock=threading.Lock(), ptp_param_state_uncertain=False,
        automatic=SimpleNamespace(update=lambda state, **kw: phases.append(state),
                                  snapshot=lambda: {'state': 'SAVING'}, abort_event=threading.Event()),
        _restore_arm_ptp=lambda value: (restore_ok, 'readback'), health_error=lambda: '',
        status=lambda state, reason: statuses.append((state, reason)))
    node.operation_lock.acquire()
    backend = AutomaticBackend(node)
    backend.owned = True
    backend.ptp_before = {'velocity_percent': 20, 'acceleration_percent': 20}
    backend.context = {}
    monkeypatch.setattr(module, 'load_bundle', lambda *args: (object(), object()))
    monkeypatch.setattr(module, 'save_bundle', lambda *args: writes.append(args))
    result = {'state': 'CANDIDATE_VERIFIED', 'candidate_path': str(candidate), 'production_ready': False}
    backend.finalize(result, lambda: None)
    assert len(writes) == 1 and node.workflow is None
    if restore_ok:
        backend.close()
        assert result['state'] == 'AWAITING_LIVE_VALIDATION'
        assert 'LIVE_VALIDATION_NOT_COMPLETED' in result['reason']
        assert not result['production_ready']
    else:
        with pytest.raises(CalibrationError, match='PTP_RESTORE_FAILED'):
            backend.close()
        assert node.workflow is None
        assert node.ptp_param_state_uncertain
    assert all(state != 'READY' for state, _ in statuses)
    assert not node.operation_lock.locked()


def test_audit_failure_revokes_success():
    backend = Backend()
    failed = []
    def fail_audit(status):
        raise OSError('disk full')
    backend.persist_status = fail_audit
    backend.failed = failed.append
    engine = AutomaticCalibration(backend)
    engine.run()
    assert engine.snapshot()['state'] == 'FAULT'
    assert not engine.snapshot()['production_ready']
    assert failed == ['AUDIT_PERSISTENCE_FAILED: disk full']


@pytest.mark.parametrize('failure', ['prepare', 'validate', 'move', 'settle', 'capture', 'accept', 'solve', 'close'])
def test_every_stage_failure_prevents_success_and_closes(failure):
    backend = Backend()
    backend.failure = failure
    engine = AutomaticCalibration(backend)
    engine.run()
    assert engine.snapshot()['state'] == 'FAULT'
    assert backend.events[-1] == 'close'
    if failure in ('prepare', 'validate'):
        assert 'move' not in backend.events


def test_abort_at_movement_boundary_prevents_capture_and_next_move():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    def move(target):
        backend.events.append('move')
        engine.abort_event.set()
    backend.move = move
    engine.run()
    assert engine.snapshot()['state'] == 'SAFE_STOP'
    assert 'capture' not in backend.events
    assert backend.events.count('move') == 1


def test_pause_resume_and_double_start():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    paused = threading.Event()
    def check():
        if engine.pause_event.is_set():
            paused.set()
    def move(target):
        backend.events.append('move')
        if backend.events.count('move') == 1:
            engine.pause()
    backend.check, backend.move = check, move
    assert engine.start()[0]
    assert paused.wait(2)
    assert not engine.start()[0]
    assert backend.events.count('move') == 1
    engine.resume()
    engine.worker.join(2)
    assert not engine.worker.is_alive()
    assert backend.events.count('capture') == 10


def workspace_data():
    return dict(schema_version=1, installation_verified=True, whole_robot_environment_verified=True,
                measurement_source='synthetic test fixture, never deployed', base_frame='base',
                camera_id='test-camera', mount_fingerprint='test-mount', table_surface_z_m=-.2,
                free_volume_min_m=[-.3, -.4, -.2], free_volume_max_m=[.6, .4, .6],
                minimum_clearance_m=.025)


def load_workspace(tmp_path, data):
    path = tmp_path / 'workspace.yaml'
    path.write_text(yaml.safe_dump(data))
    return CalibrationWorkspace.load(path, base_frame='base', camera_id='test-camera',
                                     mount_fingerprint='test-mount')


@pytest.mark.parametrize('key,value', [
    ('installation_verified', False), ('whole_robot_environment_verified', False),
    ('camera_id', 'wrong'), ('mount_fingerprint', 'wrong'), ('base_frame', 'wrong'),
    ('table_surface_z_m', None), ('table_surface_z_m', float('nan')),
    ('measurement_source', ''), ('minimum_clearance_m', 0),
    ('free_volume_min_m', [0, 0]), ('free_volume_max_m', [-1, -1, -1]),
])
def test_unmeasured_or_mismatched_installation_is_rejected(tmp_path, key, value):
    data = workspace_data()
    data[key] = value
    with pytest.raises(CalibrationError, match='WORKSPACE_INVALID'):
        load_workspace(tmp_path, data)


def test_workspace_does_not_require_camera_rotation_but_checks_swept_sphere(tmp_path):
    workspace = load_workspace(tmp_path, workspace_data())
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001,
                            rotation_seed_verified=False)
    start = transform(translation=[.15, 0, .10])
    target = transform(translation=[.185, 0, .10])
    workspace.check_segment(start, target, mount)
    data = workspace_data()
    data['table_surface_z_m'] = 0.
    workspace = load_workspace(tmp_path, data)
    with pytest.raises(CalibrationError, match='CLEARANCE'):
        workspace.check_segment(start, target, mount)


def test_automatic_plan_tracks_current_pose_not_old_pose_two():
    anchor = transform(translation=[.205, .01, .08])
    plan = automatic_plan(anchor)
    np.testing.assert_allclose(plan[0], anchor)
    np.testing.assert_allclose(plan[1][:3, 3], [.240, .01, .08])


def test_clearance_diagnostics_identify_independent_anchor_blockers(tmp_path):
    data = workspace_data()
    data.update(table_surface_z_m=-.058, free_volume_min_m=[-.0086, -.2486, .0014],
                free_volume_max_m=[.4086, .2486, .3986])
    workspace = load_workspace(tmp_path, data)
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    anchor = transform(translation=[.14993, 0, .09989])
    report = workspace.clearance_diagnostics(anchor, anchor, mount)
    deficits = {v['boundary']: v['deficit_m'] for v in report['violations']}
    assert deficits == pytest.approx({'volume_x_min': .02007, 'volume_z_min': .08011,
                                     'table': .02071})
    assert report['table_min_center_z_m'] == pytest.approx(.1206)
    with pytest.raises(CalibrationError, match='volume_x_min.*volume_z_min.*table'):
        workspace.check_segment(anchor, anchor, mount)


def test_table_correction_does_not_hide_volume_failure(tmp_path):
    data = workspace_data()
    data.update(table_surface_z_m=-.2, free_volume_min_m=[-.0086, -.2486, .0014],
                free_volume_max_m=[.4086, .2486, .3986])
    workspace = load_workspace(tmp_path, data)
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    anchor = transform(translation=[.15, 0, .10])
    report = workspace.clearance_diagnostics(anchor, anchor, mount)
    assert report['signed_margins_m']['table'] > 0
    assert {v['boundary'] for v in report['violations']} == {'volume_x_min', 'volume_z_min'}
    with pytest.raises(CalibrationError, match='CLEARANCE'):
        workspace.check_segment(anchor, anchor, mount)


def test_clearance_diagnostics_cover_both_segment_endpoints(tmp_path):
    data = workspace_data()
    data['free_volume_max_m'] = [.36, .4, .6]
    workspace = load_workspace(tmp_path, data)
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    start = transform(translation=[.15, 0, .1])
    target = transform(translation=[.185, 0, .1])
    workspace.check_segment(start, start, mount)
    forward = workspace.clearance_diagnostics(start, target, mount)
    reverse = workspace.clearance_diagnostics(target, start, mount)
    assert forward == reverse
    assert forward['violations'] == [{'boundary': 'volume_x_max',
                                     'deficit_m': pytest.approx(.0036)}]
    with pytest.raises(CalibrationError, match='volume_x_max deficit_mm=3.600'):
        workspace.check_segment(start, target, mount)


def test_decimal_workspace_accepts_exact_boundary_across_all_plan_segments(tmp_path):
    data = workspace_data()
    data.update(table_surface_z_m=-.058,
                free_volume_min_m=[-.00835, -.2041, -.0541],
                free_volume_max_m=[.38285, .2041, .3286])
    workspace = load_workspace(tmp_path, data)
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    anchor = transform(translation=[.2, 0, .15])
    previous = anchor
    for target in automatic_plan(anchor, x_sign=-1, z_sign=-1, scale=.85):
        workspace.check_segment(previous, target, mount)
        assert workspace.clearance_diagnostics(previous, target, mount)['violations'] == []
        previous = target


@pytest.mark.parametrize('boundary', [
    'volume_x_min', 'volume_y_min', 'volume_z_min',
    'volume_x_max', 'volume_y_max', 'volume_z_max', 'table',
])
def test_boundary_roundoff_tolerance_still_rejects_one_nanometre_violation(tmp_path, boundary):
    data = workspace_data()
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    anchor = transform(translation=[.2, 0, .15])
    padding = mount.envelope_radius_m + mount.translation_error_bound_m + .025
    if boundary == 'table':
        data['table_surface_z_m'] = float(anchor[2, 3] - padding + 1e-9)
    else:
        _, axis, side = boundary.split('_')
        index = 'xyz'.index(axis)
        data[f'free_volume_{side}_m'][index] = float(
            anchor[index, 3] - padding + 1e-9 if side == 'min'
            else anchor[index, 3] + padding - 1e-9)
    workspace = load_workspace(tmp_path, data)
    report = workspace.clearance_diagnostics(anchor, anchor, mount)
    assert {v['boundary'] for v in report['violations']} == {boundary}
    with pytest.raises(CalibrationError, match=boundary):
        workspace.check_segment(anchor, anchor, mount)


def test_planner_selects_feasible_variant_around_joint_limit(tmp_path):
    backend = AutomaticBackend(SimpleNamespace(
        mount=SimpleNamespace(envelope_radius_m=.105, translation_error_bound_m=.001),
        settings={'planning_soft_margin_deg': 2.0}))
    backend.workspace = load_workspace(tmp_path, workspace_data())
    anchor = transform(translation=[.19, 0, .125])
    plan = backend.select_plan(anchor)
    assert len(plan) == 10
    assert not np.allclose(plan[5], automatic_plan(anchor)[5])
    for first, second in zip(plan, plan[1:]):
        backend.validate(first, second)


def tight_workspace(tmp_path):
    data = workspace_data()
    data.update(table_surface_z_m=-.058,
                free_volume_min_m=[-.00835, -.2041, -.0541],
                free_volume_max_m=[.38285, .2041, .3286])
    return load_workspace(tmp_path, data)


@pytest.mark.parametrize('outside', [False, True])
def test_start_pose_report_uses_existing_installation_geometry(tmp_path, outside):
    node = SimpleNamespace(mount=SimpleNamespace(
        envelope_radius_m=.1526, translation_error_bound_m=.001))
    backend = AutomaticBackend(node)
    node.automatic = AutomaticCalibration(backend)
    backend.workspace = tight_workspace(tmp_path)
    anchor = transform(translation=[.057741783, 0, -.01535643] if outside else [.18725, 0, .13725])
    if outside:
        with pytest.raises(CalibrationError, match='START_POSE_OUTSIDE_WORKSPACE'):
            backend.validate_start_pose(anchor)
    else:
        backend.validate_start_pose(anchor)
    report = node.automatic.snapshot()['start_pose_check']
    assert bool(report['violations']) is outside
    np.testing.assert_allclose(report['current_xyz_mm'], anchor[:3, 3] * 1000)
    np.testing.assert_allclose(report['allowed_center_min_m'], [.17025, -.0255, .1245])
    np.testing.assert_allclose(report['allowed_center_max_m'], [.20425, .0255, .15])


def test_plan_translation_preserves_excitation_and_rotation(tmp_path):
    workspace = tight_workspace(tmp_path)
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    anchor = transform(translation=[.18725, 0, .13725])
    original = automatic_plan(anchor, scale=.85)
    before = np.asarray(original).copy()
    translated = workspace.translate_plan_into_volume(original, mount)
    np.testing.assert_array_equal(np.asarray(original), before)
    np.testing.assert_allclose(np.diff(np.asarray(translated)[:, :3, 3], axis=0),
                               np.diff(before[:, :3, 3], axis=0), atol=1e-15)
    np.testing.assert_array_equal(np.asarray(translated)[:, :3, :3], before[:, :3, :3])
    for target in translated:
        workspace.check_segment(target, target, mount)
    with pytest.raises(CalibrationError, match='WORKSPACE_PLAN_VOLUME_TOO_SMALL'):
        workspace.translate_plan_into_volume(automatic_plan(anchor, scale=1.), mount)


def test_planner_fits_surveyed_volume_from_interior_start_with_full_validation(tmp_path, monkeypatch):
    monkeypatch.setenv('MAGICIAN_TOOL', 'suction_cup')
    backend = AutomaticBackend(SimpleNamespace(
        mount=SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001),
        settings={'planning_soft_margin_deg': 2.}))
    backend.workspace = tight_workspace(tmp_path)
    anchor = transform(translation=[.18725, 0, .13725])
    plan = backend.select_plan(anchor)
    assert len(plan) == 10
    assert not np.allclose(plan[0], anchor)
    assert len(backend.validated_segments) >= 10
    backend.validate(anchor, plan[0])
    for first, second in zip(plan, plan[1:]):
        backend.validate(first, second)
    # Measured poses within the existing 2 mm settling tolerance must still
    # fit the unchanged installation envelope, even at the plan extrema.
    for target in plan:
        margins = backend.workspace.clearance_diagnostics(target, target, backend.node.mount)
        assert min(margins['signed_margins_m'].values()) >= .002 - 1e-12
        for axis in range(3):
            for offset in (-.002, .002):
                actual = target.copy()
                actual[axis, 3] += offset
                backend.workspace.check_segment(actual, actual, backend.node.mount)


@pytest.mark.parametrize('reserve', [-.001, float('nan'), float('inf')])
def test_plan_tracking_reserve_cannot_enlarge_measured_volume(tmp_path, reserve):
    workspace = tight_workspace(tmp_path)
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001)
    with pytest.raises(CalibrationError, match='WORKSPACE_PLAN_RESERVE_INVALID'):
        workspace.translate_plan_into_volume(automatic_plan(transform(translation=[.18725, 0, .13725])),
                                             mount, reserve_m=reserve)


def test_translated_plan_cannot_admit_start_outside_surveyed_volume(tmp_path):
    backend = AutomaticBackend(SimpleNamespace(
        mount=SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001),
        settings={'planning_soft_margin_deg': 2.}))
    backend.workspace = tight_workspace(tmp_path)
    with pytest.raises(CalibrationError, match='NO_FEASIBLE_AUTOMATIC_PLAN'):
        backend.select_plan(transform(translation=[.11968, .14549, .05042]))
    assert not backend.validated_segments


def test_settling_uses_bracketed_robot_timestamp():
    pose = transform(translation=[.15, 0, .1])
    history = [(float(t), pose, np.zeros(4)) for t in np.linspace(10, 10.8, 41)]
    node = SimpleNamespace(history=history, lock=threading.RLock(), now_s=lambda: 10.81,
                           after_motion_stamp=9., stop=threading.Event())
    AutomaticBackend(node).settle(pose, lambda: None)
