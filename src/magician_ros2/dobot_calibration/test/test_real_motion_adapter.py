import pytest

from dobot_calibration.real_motion_adapter import RealMotionAdapter, RealMotionRejected
from dobot_calibration.token_lifecycle import TokenLifecycle


def make_adapter(*, token=True, gate='', ptp=None, dispatch=None):
    stopped = []
    if ptp is None:
        ptp = {'velocity_percent': 5, 'acceleration_percent': 5}
    if dispatch is None:
        dispatch = lambda index, target: {'index': index, 'target': target}
    adapter = RealMotionAdapter(
        token_valid=lambda _token, _index: token,
        hard_gates=lambda _index: gate,
        ptp_readback=lambda: ptp,
        dispatch=dispatch,
        safe_stop=lambda: stopped.append(True))
    adapter.enable_authorized_commissioning_run()
    return adapter, stopped


def token(scope='POSE_1_TO_2_ONLY'):
    return {'scope': scope, 'session_id': 's', 'mount_fingerprint': 'm'}


@pytest.mark.parametrize('valid', [False])
def test_invalid_or_expired_token_is_rejected(valid):
    adapter, stopped = make_adapter(token=valid)
    with pytest.raises(RealMotionRejected, match='TOKEN_INVALID'):
        adapter.execute(token(), 1, 'p1')
    assert not stopped


@pytest.mark.parametrize('index', [0, 3, 10])
def test_wrong_index_and_pose_3_are_hard_rejected(index):
    adapter, _ = make_adapter()
    with pytest.raises(RealMotionRejected, match='POSE_SCOPE'):
        adapter.execute(token(), index, 'x')


@pytest.mark.parametrize('gate', ['PREFLIGHT', 'READINESS_LOSS', 'ALARM', 'ABORT'])
def test_preflight_readiness_alarm_and_abort_are_rejected(gate):
    adapter, _ = make_adapter(gate=gate)
    with pytest.raises(RealMotionRejected, match='HARD_GATE'):
        adapter.execute(token(), 1, 'p1')


def test_ptp_readback_mismatch_is_rejected():
    adapter, _ = make_adapter(ptp={'velocity_percent': 10, 'acceleration_percent': 5})
    with pytest.raises(RealMotionRejected, match='PTP_READBACK'):
        adapter.execute(token(), 1, 'p1')


@pytest.mark.parametrize('failure', ['action rejected', 'action timeout', 'capture rejected', 'registration rejected'])
def test_action_and_capture_failures_always_safe_stop(failure):
    def dispatch(_index, _target):
        raise RuntimeError(failure)
    adapter, stopped = make_adapter(dispatch=dispatch)
    with pytest.raises(RuntimeError, match=failure):
        adapter.execute(token(), 1, 'p1')
    assert stopped == [True]


def test_successful_sequence_is_exactly_pose_1_then_pose_2():
    sent = []
    adapter, stopped = make_adapter(dispatch=lambda index, target: sent.append((index, target)) or 'ok')
    assert adapter.execute(token(), 1, 'pose-1').result == 'ok'
    assert adapter.execute(token(), 2, 'pose-2').result == 'ok'
    assert sent == [(1, 'pose-1'), (2, 'pose-2')]
    assert not stopped


def test_uncommissioned_adapter_never_dispatches():
    adapter, _ = make_adapter()
    adapter.disable()
    with pytest.raises(RealMotionRejected, match='NOT_COMMISSIONED'):
        adapter.execute(token(), 1, 'p1')

def test_production_token_lifecycle_survives_100_predispatch_validations():
    for _ in range(100):
        manager = TokenLifecycle(); value = manager.create('session', 'mount', 10)
        assert manager.validate(value, 'session', 'mount', 1) == ''
        assert manager.validate(value, 'session', 'mount', 1) == ''
        manager.activate(value)
        assert manager.validate(value, 'session', 'mount', 1) == ''
        assert manager.validate(value, 'session', 'mount', 2) == ''
        assert manager.validate(value, 'session', 'mount', 3) == 'POSE_NOT_ALLOWED'
