import inspect
import time

from dobot_calibration.supervised_auto import SupervisedAutoCalibration


def wait(machine):
    machine.worker.join(timeout=2)
    assert not machine.worker.is_alive()
    return machine.snapshot()


def test_dry_run_walks_state_machine_without_motion_or_capture_side_effects():
    machine = SupervisedAutoCalibration(lambda: ([], 'READY'), lambda target: [])
    ok, _ = machine.start([{'pose_index': 1}], dry_run=True)
    assert ok
    status = wait(machine)
    assert status['state'] == 'COMPLETE'
    assert status['dry_run'] is True
    assert status['capture_result'] == 'DRY_RUN_NO_DATASET_MUTATION'
    source = inspect.getsource(SupervisedAutoCalibration)
    for forbidden in ('PTP_action', 'send_goal_async', 'capture_pose_service'):
        assert forbidden not in source


def test_failed_target_enters_fault_and_does_not_continue():
    machine = SupervisedAutoCalibration(
        lambda: ([], 'READY'), lambda target: ['CONSERVATIVE_TABLE_CLEARANCE_FAILED'])
    machine.start([{'pose_index': 2}, {'pose_index': 3}], accepted_count=0)
    status = wait(machine)
    assert status['state'] == 'FAULT'
    assert status['current_pose'] == 1
    assert status['blockers'] == ['CONSERVATIVE_TABLE_CLEARANCE_FAILED']


def test_real_motion_is_disabled_until_separately_commissioned():
    machine = SupervisedAutoCalibration(lambda: ([], 'READY'), lambda target: [])
    ok, reason = machine.start([{'pose_index': 1}], dry_run=False)
    assert not ok
    assert 'disabled' in reason
