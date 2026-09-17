from dobot_web_interface.system_integration import StartupState
from dobot_web_interface.system_integration import StartupStateMachine
from dobot_web_interface.system_integration import aggregate_system_readiness


def _ready_snapshot(**components):
    base = {
        'robot': True,
        'camera': True,
        'vision': True,
        'calibration': True,
        'home': True,
        'observation': True,
        'motion_idle': True,
        'real_motion': True,
    }
    base.update(components)
    return {'components': base}


def test_readiness_is_fail_closed_for_a_stale_calibration_or_camera():
    result = aggregate_system_readiness(
        status={
            'ros': {
                'ptp_action_ready': True,
                'homing_ready': True,
                'suction_ready': True,
                'alarm_state_fresh': True,
                'no_critical_alarm': True,
            },
            'camera': {'has_frame': True, 'frame_age_sec': 2.1},
            'motion': {'joints_age_sec': 0.1, 'current_tcp_pose_age_sec': 0.1},
        },
        vision={
            'ok': True, 'source_ok': True, 'rgb_ok': True,
            'depth_stream_ok': True, 'depth_data_valid': True, 'sync_ok': True,
        },
        calibration={'ready': True, 'state': 'READY', 'result': 'PASS', 'age_sec': 2.1},
        homed=True,
        at_observation=True,
        camera_health={
            'ready': True,
            'age_sec': 0.1,
            'usb': {'identity_valid': True},
        },
    )

    assert result['ready'] is False
    assert set(result['blockers']) >= {'CAMERA_NOT_READY', 'CALIBRATION_NOT_READY'}
    assert result['runtime']['calibration_available'] is False


def test_camera_heartbeat_is_reported_separately_from_quality_readiness():
    result = aggregate_system_readiness(
        status={
            'ros': {},
            'camera': {'has_frame': True, 'frame_age_sec': 0.1},
            'motion': {},
        },
        vision={
            'ok': True, 'source_ok': True, 'rgb_ok': True,
            'depth_stream_ok': True, 'depth_data_valid': True, 'sync_ok': True,
        },
        calibration={}, homed=False, at_observation=False,
        camera_health={
            'ready': False, 'age_sec': 0.1,
            'blockers': ['cloud_rate_unverified_or_degraded'],
            'usb': {'identity_valid': True},
        },
    )

    assert result['runtime']['camera_health_fresh'] is True
    assert result['runtime']['rgb_fresh'] is True
    assert result['runtime']['depth_fresh'] is True
    assert result['runtime']['depth_valid'] is True
    assert result['runtime']['camera_connected'] is False


def test_startup_actions_follow_the_fixed_order_once_each():
    machine = StartupStateMachine(auto_home=True, auto_observation=True)
    assert machine.advance(_ready_snapshot(robot=False)).state is StartupState.WAITING_FOR_ROBOT
    assert machine.advance(_ready_snapshot(camera=False)).state is StartupState.WAITING_FOR_CAMERA
    assert machine.advance(_ready_snapshot(vision=False)).state is StartupState.WAITING_FOR_VISION

    calibration = machine.advance(_ready_snapshot(calibration=False))
    assert calibration.state is StartupState.VERIFYING_CALIBRATION
    assert calibration.action == 'verify_calibration'
    machine.mark_dispatched(calibration.action)
    assert machine.advance(_ready_snapshot(calibration=False)).action is None

    home = machine.advance(_ready_snapshot(home=False))
    assert home.state is StartupState.WAITING_FOR_HOME
    assert home.action == 'home'
    machine.mark_dispatched(home.action)

    observation = machine.advance(_ready_snapshot(observation=False))
    assert observation.state is StartupState.MOVING_TO_OBSERVATION
    assert observation.action == 'move_observation'
    machine.mark_dispatched(observation.action)
    assert machine.advance(_ready_snapshot()).state is StartupState.READY


def test_startup_fault_latches_until_explicit_reset():
    machine = StartupStateMachine(auto_home=True)
    machine.fail('calibration verification failed')

    assert machine.advance(_ready_snapshot()).state is StartupState.FAULT
    machine.reset()
    assert machine.advance(_ready_snapshot()).state is StartupState.READY
