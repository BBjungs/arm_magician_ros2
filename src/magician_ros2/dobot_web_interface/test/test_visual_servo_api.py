import threading
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from dobot_web_interface.web_interface import create_app, DobotWebNode


def node():
    return SimpleNamespace(api_token='secret', _visual_servo_owns_control=lambda: False,
        visual_servo=SimpleNamespace(status=Mock(return_value={'servo_state': 'IDLE', 'calibration_required': False}),
            enable=Mock(return_value={'accepted': True}), start=Mock(return_value={'accepted': True}),
            stop=Mock(return_value={'requested': True})))


def test_page_assets_and_telemetry_are_available():
    client = TestClient(create_app(node()))
    page = client.get('/visual-servo')
    assert page.status_code == 200
    for text in ('Eye-in-Hand Auto Approach (No Calibration)', 'ENABLE', 'START APPROACH', 'PAUSE', 'STOP'):
        assert text in page.text
    for path in ('/static/visual_servo.js', '/static/visual_servo.css'):
        assert client.get(path).status_code == 200
    assert client.get('/api/visual_servo/status').json()['calibration_required'] is False


@pytest.mark.parametrize('action', ['enable', 'start'])
def test_motion_admission_requires_operator_credentials_and_same_origin(action):
    n = node()
    client = TestClient(create_app(n))
    path = '/api/visual_servo/' + action
    assert client.post(path, json={}).status_code == 401
    headers = {'Authorization': 'Bearer secret', 'Origin': 'https://untrusted.example'}
    assert client.post(path, json={}, headers=headers).status_code == 403
    getattr(n.visual_servo, action).assert_not_called()
    headers['Origin'] = 'http://testserver'
    assert client.post(path, json={}, headers=headers).status_code == 200
    getattr(n.visual_servo, action).assert_called_once()


@pytest.mark.parametrize('action', ['pause', 'stop'])
def test_stop_and_pause_do_not_require_credentials(action):
    n = node()
    client = TestClient(create_app(n))
    assert client.post('/api/visual_servo/' + action).status_code == 200
    n.visual_servo.stop.assert_called_once()


def test_calibration_commands_cannot_take_control_during_servo():
    n = node()
    n._visual_servo_owns_control = lambda: True
    client = TestClient(create_app(n))
    for path in ('/api/calibration/autonomous/start', '/api/system/startup', '/api/workspace/proposal'):
        assert client.post(path, json={}, headers={'Authorization': 'Bearer secret'}).status_code == 409


def test_explicit_home_only_does_not_request_calibrated_observation_motion():
    n = node()
    n.call_homing = Mock(return_value={'success': True})
    client = TestClient(create_app(n))
    assert client.post('/api/homing?move_to_observation=false').status_code == 200
    n.call_homing.assert_called_once_with(move_to_observation=False)


@pytest.mark.parametrize('owner,should_stop', [('', False), ('visual_servo', False), ('operator', True)])
def test_calibration_failure_blocks_auto_pick_without_faking_validity(owner, should_stop):
    n = object.__new__(DobotWebNode)
    n._integration_lock = threading.RLock()
    n._startup_machine = Mock()
    n._operation_is_active = lambda: bool(owner)
    n._control_owner = owner
    n._system_fault = 'existing robot fault'
    n._latch_system_fault = Mock()
    n.get_logger = Mock(return_value=Mock())
    n._calibration_verification_failed('Missing calibration bundle')
    n._startup_machine.fail.assert_called_once()
    assert n._system_fault == 'existing robot fault'
    assert n._latch_system_fault.called == should_stop
