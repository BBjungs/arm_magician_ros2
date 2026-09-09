from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace

import pytest

from dobot_calibration.geometry import CalibrationError
from dobot_calibration.workflow import Workflow
from synthetic_scene import MOUNT, START, render


class SimulatedBackend:
    def __init__(self):
        self.current = START.copy()
        self.stamp = 1000
        self.states = []
        self.moves = []

    def checkpoint(self):
        pass

    def capture(self):
        self.stamp += 2
        return render(self.current, self.stamp)

    def move(self, target):
        self.moves.append(target.copy())
        self.current = target.copy()

    def status(self, state, reason):
        self.states.append(state)


def test_automatic_calibrate_save_load_verify_ready(tmp_path, monkeypatch):
    path = tmp_path / 'automatic.npz'
    backend = SimulatedBackend()
    context = {'camera_id': 'synthetic-camera', 'mount_digest': MOUNT.digest}
    workflow = Workflow(backend, MOUNT, path, context)
    report = workflow.run()
    assert report['result'] == 'PASS', report
    assert workflow.state == 'READY'
    assert path.is_file()
    assert len(backend.moves) == 9
    assert backend.states.index('VERIFYING') < backend.states.index('READY')
    assert workflow.verified_monotonic is not None

    def forbid_fit(*args, **kwargs):
        raise AssertionError('Reload must verify the persisted transform without refitting')

    monkeypatch.setattr('dobot_calibration.workflow.solve', forbid_fit)
    restored = Workflow(backend, MOUNT, path, context)
    report = restored.run()
    assert report['result'] == 'PASS', report
    assert restored.state == 'READY'
    assert len(backend.moves) == 12
    assert 'LOADING' in backend.states


def test_motion_failure_blocks_readiness_and_does_not_save(tmp_path):
    class FailingBackend(SimulatedBackend):
        def move(self, target):
            raise CalibrationError('Injected motion timeout')

    backend = FailingBackend()
    path = tmp_path / 'failed.npz'
    workflow = Workflow(backend, MOUNT, path, {})
    report = workflow.run()
    assert report['result'] == 'FAIL'
    assert 'timeout' in report['reason']
    assert workflow.state == 'FAIL'
    assert workflow.verified_monotonic is None
    assert not path.exists()
    assert 'READY' not in backend.states


def test_corrupt_reload_never_commands_motion(tmp_path):
    backend = SimulatedBackend()
    path = tmp_path / 'corrupt.npz'
    path.write_bytes(b'not a calibration bundle')
    workflow = Workflow(backend, MOUNT, path, {})
    assert workflow.run()['result'] == 'FAIL'
    assert not backend.moves
    assert workflow.verified_monotonic is None


@pytest.fixture
def controlled_workflow(tmp_path, monkeypatch):
    # State-machine faults use a fake solver; the automatic workflow test
    # above separately exercises real RGB-D registration and refinement.
    reference = render(START, 1000)
    class Backend(SimulatedBackend):
        cancelled = False

        def checkpoint(self):
            if self.cancelled:
                raise CalibrationError('Injected cancellation')

        def capture(self):
            self.stamp += 2
            return replace(reference, stamp=self.stamp, base_T_tool=self.current.copy())

    backend = Backend()
    workflow = Workflow(backend, MOUNT, tmp_path / 'controlled.npz', {})
    monkeypatch.setattr('dobot_calibration.workflow.check_path', lambda *a: None)
    monkeypatch.setattr('dobot_calibration.workflow.solve', lambda *a: SimpleNamespace(
        training_poses=[START], tool_T_camera=MOUNT.tool_T_camera))
    monkeypatch.setattr('dobot_calibration.workflow.verify', lambda *a: {
        'result': 'PASS', 'metrics': {'translation_residual_m': 0.001}, 'reason': ''})
    monkeypatch.setattr('dobot_calibration.workflow.save_bundle', lambda *a: None)
    return workflow, backend


def test_failed_verification_preserves_evidence(controlled_workflow, monkeypatch):
    workflow, backend = controlled_workflow
    metrics = {'translation_residual_m': 0.02, 'registration_fitness': 0.8}
    monkeypatch.setattr('dobot_calibration.workflow.verify', lambda *a: {
        'result': 'FAIL', 'metrics': metrics, 'reason': 'translation residual too large'})
    report = workflow.run()
    assert report['result'] == 'FAIL'
    assert report['metrics'] == metrics
    assert 'READY' not in backend.states
    assert not workflow.path.exists()


def test_cancellation_during_solver_prevents_verification_motion(controlled_workflow, monkeypatch):
    workflow, backend = controlled_workflow
    def cancel_during_solve(*args):
        backend.cancelled = True
        return SimpleNamespace(training_poses=[START])
    monkeypatch.setattr('dobot_calibration.workflow.solve', cancel_during_solve)
    assert workflow.run()['result'] == 'FAIL'
    assert len(backend.moves) == 6
    assert 'VERIFYING' not in backend.states
    assert workflow.verified_monotonic is None


def test_cancellation_during_save_never_becomes_ready(controlled_workflow, monkeypatch):
    workflow, backend = controlled_workflow
    def cancel_during_save(*args):
        backend.cancelled = True
    monkeypatch.setattr('dobot_calibration.workflow.save_bundle', cancel_during_save)
    assert workflow.run()['result'] == 'FAIL'
    assert 'READY' not in backend.states
    assert workflow.verified_monotonic is None


def test_settled_capture_must_match_motion_target(controlled_workflow, monkeypatch):
    workflow, backend = controlled_workflow
    monkeypatch.setattr(backend, 'move', lambda target: None)
    assert workflow.run()['result'] == 'FAIL'
    assert 'commanded pose' in workflow.reason
    assert 'SOLVING' not in backend.states


def test_verify_only_missing_file_does_not_calibrate(controlled_workflow):
    workflow, backend = controlled_workflow
    assert workflow.run(verify_only=True)['result'] == 'FAIL'
    assert backend.stamp == 1000
    assert not backend.moves
