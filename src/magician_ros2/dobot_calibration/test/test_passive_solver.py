from types import SimpleNamespace

import numpy as np
import pytest

from dobot_calibration.geometry import CalibrationError
from dobot_calibration import passive_solver as module


def samples():
    return [SimpleNamespace(stamp=float(i)) for i in range(10)]


def test_insufficient_real_data_cannot_solve(tmp_path):
    with pytest.raises(CalibrationError, match='1/10'):
        module.solve_session(samples()[:1], None, {}, tmp_path / 'candidate.npz')
    assert not list(tmp_path.iterdir())


def test_timestamps_must_be_ordered(tmp_path):
    data = samples()
    data[-1].stamp = 1.0
    with pytest.raises(CalibrationError, match='strictly increasing'):
        module.solve_session(data, None, {}, tmp_path / 'candidate.npz')


def test_holdout_and_reload_never_authorize_motion(monkeypatch, tmp_path):
    data, fits, checks, writes = samples(), [], [], []
    solution = SimpleNamespace(tool_T_camera=np.eye(4), metrics={}, observability={})
    monkeypatch.setattr(module, 'solve', lambda captures, *args: fits.append(captures) or solution)
    monkeypatch.setattr(module, 'verify', lambda s, a, captures, *args:
                        checks.append(captures) or {'result': 'PASS', 'reason': ''})
    monkeypatch.setattr(module, 'save_bundle', lambda *args: writes.append(args))
    monkeypatch.setattr(module, 'load_bundle', lambda *args: (solution, data[0]))
    result = module.solve_session(data, None, {}, tmp_path / 'candidate.npz')
    assert fits == [data[:7]]
    assert checks == [data[7:], data[7:]]
    assert len(writes) == 1
    assert result['state'] == 'CANDIDATE_VERIFIED'
    assert not result['production_ready']
    assert not result['motion_command_sent']


def test_failed_holdout_is_never_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(module, 'solve', lambda *args: object())
    monkeypatch.setattr(module, 'verify', lambda *args: {'result': 'FAIL', 'reason': 'bad data'})
    monkeypatch.setattr(module, 'save_bundle', lambda *args: pytest.fail('must not save'))
    with pytest.raises(CalibrationError, match='Independent verification failed'):
        module.solve_session(samples(), None, {}, tmp_path / 'candidate.npz')


def test_cancelled_solve_is_not_saved(monkeypatch, tmp_path):
    def cancelled():
        raise CalibrationError('Calibration cancelled')
    monkeypatch.setattr(module, 'solve', lambda *args: pytest.fail('must not fit'))
    with pytest.raises(CalibrationError, match='cancelled'):
        module.solve_session(samples(), None, {}, tmp_path / 'candidate.npz', checkpoint=cancelled)


def test_real_solver_bootstraps_unknown_rotation_on_synthetic_rgbd(tmp_path):
    from dataclasses import replace
    from synthetic_scene import MOUNT, TRUE_X, held_out, training
    from dobot_calibration.geometry import pose_distance, transform
    mount = replace(MOUNT, tool_T_camera=transform(translation=TRUE_X[:3, 3]),
                    rotation_seed_verified=False)
    result = module.solve_session(training() + held_out(), mount, {}, tmp_path / 'candidate.npz')
    distance, angle = pose_distance(TRUE_X, np.asarray(result['tool_T_camera']))
    assert distance < 0.003 and angle < 1.0
    assert result['reload_verification']['result'] == 'PASS'
    assert not result['production_ready']
