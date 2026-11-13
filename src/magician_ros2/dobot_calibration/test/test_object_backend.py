"""Object workflow integration with synthetic sensors and a forbidden real transport."""
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import numpy as np
import pytest
import yaml

from dobot_calibration.autonomous import AutomaticCalibration
from dobot_calibration.object_backend import ObjectBackend
from dobot_calibration.object_reference import ObjectReference
from dobot_calibration.geometry import CalibrationError, Limits, fingerprint, pose_distance
from dobot_calibration.calibration_workspace import CalibrationWorkspace, automatic_plan
from dobot_calibration.motion_authorization import ACKNOWLEDGEMENTS
from dobot_calibration.workflow import calibration_poses, save_bundle, load_bundle
from dobot_calibration.solver import solve, verify
from object_scene import START, MOUNT, capture


@pytest.fixture
def backend(tmp_path):
    config = {'physical_attachment': {'exact_parent_frame_verified': True,
        'candidate_parent_frame': 'TCP', 'rotates_with_joint_4': True}}
    path = tmp_path / 'mount.yaml'; path.write_text(yaml.safe_dump(config))
    events = []
    node = SimpleNamespace(settings={
        'mount_model': str(path), 'camera_id': 'synthetic', 'carrier_frame': '', 'tool_frame': 'TCP',
        'capture_timeout_s': 15., 'real_motion_arm_ttl_s': 300., 'planning_soft_margin_deg': 2.,
        'passive_session_root': str(tmp_path / 'sessions'), 'calibration_file': str(tmp_path / 'saved.npz')},
        mount=MOUNT, limits=Limits(), calibration_context={'camera_id': 'synthetic'},
        object_reference=ObjectReference(), object_capture_active=False,
        calibration_transaction_lock=threading.RLock(), operation_lock=threading.Lock(), lock=threading.Lock(),
        real_motion_arm=None, supervised_auto=SimpleNamespace(worker=None), stop=threading.Event(),
        ptp_param_state_uncertain=False, passive_capture_active=False,
        passive_session=SimpleNamespace(mount_fingerprint=fingerprint(config)),
        history=[(1., START.copy(), np.zeros(4))], bundle=(None, None, 'K'),
        health_error=lambda: '', _resolve_camera_identity=lambda: SimpleNamespace(resolution='PASS'),
        hardware_readiness=lambda: SimpleNamespace(ready=True, reason='', to_dict=lambda: {'blockers': []}),
        _prepare_passive_capture=lambda: None, intrinsics_fingerprint=lambda info: 'synthetic-object',
        _automatic_validator_policy=lambda: {f'axis_{i}_range': [-180, 180] for i in range(1, 5)},
        status=lambda state, reason='': events.append(('status', state)),
        _adapter_safe_stop=lambda: events.append(('stop',)),
    )
    def forbidden(*args, **kwargs):
        pytest.fail('No robot/PTP transport is allowed in this test')
    node._execute_guarded_motion = node._get_ptp_common_params = node._set_ptp_common_params = forbidden
    node._scene_signature = node._authoritative_baseline_record = forbidden
    node._scene_baseline_path = node._persist_scene_baseline = forbidden
    clock = [10.]
    def sensor():
        clock[0] += 1.
        return capture(node.history[-1][1], clock[0])
    node.capture = sensor
    value = ObjectBackend(node)
    workspace = CalibrationWorkspace(np.array([-1., -1., -.5]), np.array([1., 1., 1.]), -.5, .025, 'surveyed-test-only')
    value.load_workspace = lambda: workspace
    value.select_plan = lambda anchor: automatic_plan(anchor)
    # This injected validator tests the state machine, not physical collision certification.
    value.validate = lambda first, second: workspace.check_segment(first, second, MOUNT)
    node.automatic = AutomaticCalibration(value)
    return value, node, events


def wait(controller):
    controller.worker.join(300)
    if controller.worker.is_alive():
        controller.abort()
        controller.worker.join(30)
        pytest.fail('Synthetic calibration worker exceeded test timeout')
    return controller.snapshot()


def test_object_dry_run_uses_real_rgbd_without_scene_plane_or_motion(backend):
    value, node, events = backend
    previously_selected = capture(stamp=5.)
    node.object_reference.last = previously_selected
    assert node.automatic.start(dry_run=True)[0]
    status = wait(node.automatic)
    assert status['state'] == 'DRY_RUN_COMPLETE', status
    assert not status['production_ready'] and not status['motion_command_sent']
    assert status['result']['planned_pose_count'] == 10
    assert not node.operation_lock.locked()
    assert not node.object_capture_active
    assert not Path(node.settings['calibration_file']).exists()
    # The test sensor is injected; prepare itself must not discard identity
    # and fall back to a screen pixel from a previous camera viewpoint.
    assert node.object_reference.last is previously_selected


def test_object_real_run_waits_for_explicit_authorization_then_abort_does_not_move(backend):
    value, node, events = backend
    assert node.automatic.start()[0]
    deadline = time.monotonic() + 45
    while node.automatic.snapshot()['state'] not in ('WAITING_FOR_OPERATOR_AUTHORIZATION', 'FAULT'):
        assert time.monotonic() < deadline
        time.sleep(.02)
    status = node.automatic.snapshot()
    assert status['state'] == 'WAITING_FOR_OPERATOR_AUTHORIZATION', status
    assert not node.automatic.authorize({'plan_fingerprint': status['plan_fingerprint']})[0]
    node.automatic.abort()
    status = wait(node.automatic)
    assert not status['motion_command_sent']
    assert not status['production_ready']
    assert not node.operation_lock.locked()


@pytest.mark.parametrize('field,value', [('exact_parent_frame_verified', False),
                                       ('candidate_parent_frame', 'wrong_link'),
                                       ('rotates_with_joint_4', False)])
def test_unverified_or_wrong_camera_parent_never_plans_motion(backend, field, value):
    runner, node, _ = backend
    path = Path(node.settings['mount_model'])
    config = yaml.safe_load(path.read_text()); config['physical_attachment'][field] = value
    path.write_text(yaml.safe_dump(config))
    node.automatic.start(dry_run=True)
    status = wait(node.automatic)
    assert status['state'] == 'FAULT'
    assert 'CAMERA_' in status['reason']
    assert not status['motion_command_sent']


def test_workspace_and_collision_rejection_are_not_replaced_by_object_quality(backend):
    runner, node, _ = backend
    def reject(first, second):
        raise CalibrationError('AUTOMATIC_COLLISION_TRAJECTORY_REJECTED')
    runner.validate = reject
    node.automatic.start(dry_run=True)
    status = wait(node.automatic)
    assert status['state'] == 'FAULT' and 'COLLISION' in status['reason']
    assert not status['motion_command_sent']


def test_saved_object_bundle_loads_and_checks_current_data_without_new_fit_or_motion(backend, monkeypatch):
    runner, node, _ = backend
    observations = [capture(p, 1. + i) for i, p in enumerate([START, *calibration_poses(START)])]
    solution = solve(observations, MOUNT, object_only=True)
    fresh = [capture(p, 100. + i) for i, p in enumerate(calibration_poses(START, True))]
    report = verify(solution, observations[0], fresh, MOUNT, object_only=True)
    assert report['result'] == 'PASS'
    report['calibration_method'] = 'object_based'
    save_bundle(node.settings['calibration_file'], solution, observations[0], node.calibration_context, report)
    def forbidden(*args, **kwargs):
        pytest.fail('Loading an accepted calibration must not fit again or move')
    monkeypatch.setattr('dobot_calibration.object_backend.solve_session', forbidden)
    runner.wait_for_authorization = runner.move = runner.select_plan = forbidden
    node.automatic.start()
    status = wait(node.automatic)
    assert status['state'] == 'AWAITING_LIVE_VALIDATION', status.get('reason')
    assert status['reused_saved'] and not status['motion_command_sent']
    assert not status['production_ready']
    assert node.workflow.bundle_loaded and node.workflow.reload_verified
    restored, _ = load_bundle(node.settings['calibration_file'], node.calibration_context, MOUNT)
    np.testing.assert_allclose(restored.tool_T_camera, solution.tool_T_camera)


def test_ten_pose_object_pipeline_with_simulated_transport_saves_but_never_admits_picking(backend):
    runner, node, events = backend
    params = {'velocity_percent': 20, 'acceleration_percent': 20}
    node._get_ptp_common_params = lambda: dict(params)
    def set_params(v, a):
        params.update(velocity_percent=v, acceleration_percent=a)
    node._set_ptp_common_params = set_params
    def restore(arm):
        params.update(arm['ptp_before']); return True, dict(params)
    node._restore_arm_ptp = restore
    node.automatic_commissioning = {'state': 'COMMISSIONING_COMPLETE',
        'workspace_fingerprint': 'surveyed-test-only', 'mount_fingerprint': node.passive_session.mount_fingerprint,
        'camera_id': 'synthetic', 'PTP_RESTORE': 'PASS', 'motion_command_sent': True,
        'stop_tested_by_operator': True}
    def simulated_dispatch(current, target, guard):
        guard(current, target)
        assert runner.authorization_error() == ''
        assert params == {'velocity_percent': 5, 'acceleration_percent': 5}
        events.append(('simulated_dispatch', target.tolist()))
        node.history[-1] = (1., target.copy(), np.zeros(4))
    node._execute_guarded_motion = simulated_dispatch
    runner.settle = lambda target, checkpoint: checkpoint()
    node.automatic.start(force_recalibrate=True)
    deadline = time.monotonic() + 45
    while node.automatic.snapshot()['state'] not in ('WAITING_FOR_OPERATOR_AUTHORIZATION', 'FAULT'):
        assert time.monotonic() < deadline
        time.sleep(.02)
    status = node.automatic.snapshot()
    assert status['state'] == 'WAITING_FOR_OPERATOR_AUTHORIZATION', status
    assert node.automatic.authorize({**dict.fromkeys(ACKNOWLEDGEMENTS, True),
                                    'plan_fingerprint': status['plan_fingerprint']})[0]
    status = wait(node.automatic)
    assert status['state'] == 'AWAITING_LIVE_VALIDATION', status.get('reason')
    assert status['accepted_pose_count'] == 10
    assert not status['production_ready']
    assert params == {'velocity_percent': 20, 'acceleration_percent': 20}
    assert runner.authorization.revoked
    assert Path(node.settings['calibration_file']).is_file()
    restored, anchor = load_bundle(node.settings['calibration_file'], node.calibration_context, MOUNT)
    assert anchor.plane.size == 0
    assert len(restored.training_poses) == 7
