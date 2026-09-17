from dobot_calibration.hardware_readiness import (
    DepthStabilityWindow,
    evaluate_hardware_readiness,
)


def valid_depth():
    return {
        'status': 'VALID_DEPTH',
        'code': '',
        'reason': '',
        'depth_valid_ratio': 0.7,
    }


def ready_inputs():
    return dict(
        now=10.0,
        depth_quality=valid_depth(),
        depth_stamp=9.9,
        depth_stable=True,
        tcp_stamp=9.9,
        joints_stamp=9.9,
        alarm_stamp=9.9,
        alarms=[],
        robot_connected=True,
        safety_supported=True,
        safety_verified=True,
    )


def evaluate(**changes):
    values = ready_inputs()
    values.update(changes)
    return evaluate_hardware_readiness(**values)


def test_all_live_gates_can_reach_hardware_ready():
    result = evaluate()
    assert result.state == 'READY'
    assert result.ready
    assert result.blockers == ()


def test_zero_depth_is_a_depth_error():
    result = evaluate(depth_quality={
        'status': 'SENSOR_ERROR',
        'code': 'DEPTH_ALL_ZERO',
        'reason': 'Every depth pixel is zero',
    })
    assert result.state == 'DEPTH_ERROR'
    assert 'DEPTH_ALL_ZERO' in result.reason


def test_stale_depth_revokes_readiness():
    assert evaluate().ready
    result = evaluate(depth_stamp=8.0)
    assert result.state == 'DEPTH_ERROR'
    assert not result.ready
    assert any('DEPTH_STALE' in blocker for blocker in result.blockers)


def test_missing_tcp_is_reported_separately():
    result = evaluate(tcp_stamp=None)
    assert result.state == 'ROBOT_TELEMETRY_ERROR'
    assert any('TCP_MISSING_OR_STALE' in blocker for blocker in result.blockers)


def test_missing_joints_is_reported_separately():
    result = evaluate(joints_stamp=None)
    assert result.state == 'ROBOT_TELEMETRY_ERROR'
    assert any('JOINTS_MISSING_OR_STALE' in blocker for blocker in result.blockers)


def test_missing_alarms_is_reported_separately():
    result = evaluate(alarm_stamp=None)
    assert result.state == 'ROBOT_TELEMETRY_ERROR'
    assert any('ALARMS_MISSING_OR_STALE' in blocker for blocker in result.blockers)


def test_active_alarm_revokes_readiness():
    assert evaluate().ready
    result = evaluate(alarms=[40])
    assert result.state == 'ROBOT_ALARM'
    assert not result.ready


def test_missing_real_safety_signal_blocks_motion():
    result = evaluate(safety_supported=False, safety_verified=False)
    assert result.state == 'SAFETY_UNVERIFIED'
    assert not result.ready
    assert 'driver exposes no hardware E-stop' in result.reason


def test_mathematical_pass_cannot_promote_failed_hardware():
    mathematical_result = {'result': 'PASS'}
    result = evaluate(depth_stamp=None, tcp_stamp=None)
    assert mathematical_result['result'] == 'PASS'
    assert result.state == 'DEPTH_ERROR'
    assert not result.ready


def test_depth_window_requires_consecutive_advancing_valid_frames():
    window = DepthStabilityWindow(minimum_frames=3, horizon_s=0.5)
    for stamp in (9.8, 9.9, 10.0):
        window.add(stamp, valid_depth())
    assert window.stable(10.0)
    window.add(10.1, {'status': 'SENSOR_ERROR'})
    assert not window.stable(10.1)


def test_depth_clock_regression_clears_old_evidence():
    window = DepthStabilityWindow(minimum_frames=3, horizon_s=0.5)
    for stamp in (9.8, 9.9, 10.0):
        window.add(stamp, valid_depth())
    window.add(9.0, valid_depth())
    assert not window.stable(9.0)


def test_operator_verified_physical_estop_allows_missing_ros_feedback():
    result = evaluate(
        safety_supported=False,
        safety_verified=False,
        physical_estop_present=True,
        operator_safety_verified=True,
    )
    assert result.ready
    assert result.physical_estop_present
    assert result.operator_safety_verified
    assert result.software_estop_monitoring == 'NOT CONNECTED'
    assert not any('SAFETY_SIGNAL_UNAVAILABLE' in item for item in result.blockers)


def test_unsafe_connected_software_signal_still_blocks_motion():
    result = evaluate(
        safety_supported=True,
        safety_verified=False,
        physical_estop_present=True,
        operator_safety_verified=True,
    )
    assert result.state == 'SAFETY_UNVERIFIED'
    assert not result.ready
    assert 'SAFETY_NOT_SAFE' in result.reason
