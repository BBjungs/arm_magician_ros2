"""Unit contract for the explicit, bounded smoke-start transaction."""

import json
import threading
from types import SimpleNamespace

from dobot_calibration.node import CalibrationNode


def _node(arm_ok=True, token_ok=True, run=None, restore='PASS'):
    node = object.__new__(CalibrationNode)
    node.real_motion_arm = None
    lifecycle = SimpleNamespace(scope=(1, 2), event=lambda *_args, **_kwargs: None,
                                activate=lambda: None)
    node.real_motion_adapter = SimpleNamespace(
        enable_authorized_commissioning_run=lambda: None,
        disable=lambda: None,
        mark_commissioned=lambda: None)
    node.real_motion_adapter_commissioned = False
    node.ptp_param_state_uncertain = False
    node.stop = threading.Event()
    node.active_goal = None
    node.status = lambda *_args: None
    node._get_ptp_common_params = lambda: {'velocity_percent': 5, 'acceleration_percent': 5}
    def arm(_request, response):
        if arm_ok:
            node.real_motion_arm = {'scope': 'SMOKE_TEST_POSE_1_TO_2_ONLY', 'lifecycle': lifecycle}
        response.success = arm_ok
        response.message = json.dumps({'reason': 'PREFLIGHT_OR_PTP_FAILURE'})
        return response
    node.arm_real_motion_service = arm
    node._smoke_token_is_valid = lambda _arm: token_ok
    node._pre_dispatch_forensics = lambda _arm, _pose: ({}, '' if token_ok else 'TOKEN_EXPIRED')
    if run is None:
        run = lambda _arm: [{'pose': 1}, {'pose': 2}]
    node._run_atomic_smoke_test = run
    node._disarm_real_motion = lambda _reason: {'restore': restore}
    return node


def _call(node, confirmed=True):
    response = SimpleNamespace()
    CalibrationNode.start_smoke_test_service(
        node, SimpleNamespace(operator_confirmed=confirmed), response)
    return response, json.loads(response.report)


def test_confirmation_is_required_and_sends_no_motion():
    response, report = _call(_node(), False)
    assert not response.accepted
    assert report['reason'] == 'OPERATOR_CONFIRMATION_REQUIRED'
    assert report['MOTION_SENT'] is False


def test_preflight_set_readback_and_token_creation_fail_before_motion():
    for _case in ('preflight', 'set_readback', 'token_creation'):
        response, report = _call(_node(arm_ok=False))
        assert not response.accepted
        assert report['reason'] == 'PREFLIGHT_OR_PTP_FAILURE'


def test_invalid_token_before_first_motion_cleans_up_without_dispatch():
    response, report = _call(_node(token_ok=False))
    assert not response.accepted
    assert report['MOTION_SENT'] is False
    assert report['PTP_RESTORE'] == 'PASS'


def test_pose_1_pose_2_abort_and_exception_fail_closed():
    for reason in ('POSE_1_REJECTED', 'POSE_2_REJECTED', 'ABORT', 'unexpected'):
        def fail(_arm, message=reason):
            raise RuntimeError(message)
        response, report = _call(_node(run=fail))
        assert not response.accepted
        assert report['MOTION_SENT'] is False
        assert report['PTP_RESTORE'] == 'PASS'


def test_restore_failure_is_reported_and_success_is_limited_to_two_poses():
    response, report = _call(_node(restore='FAIL'))
    assert not response.accepted
    assert report['POSE_SCOPE'] == [1, 2]
    assert report['accepted_pose_count'] == 2
    assert report['PTP_RESTORE'] == 'FAIL'
