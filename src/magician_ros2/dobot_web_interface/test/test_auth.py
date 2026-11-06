from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from dobot_web_interface.web_interface import create_app


@pytest.mark.parametrize('legacy_token', ['', 'previously-configured-token'])
def test_web_and_api_are_accessible_without_credentials(legacy_token):
    node = SimpleNamespace(
        api_token=legacy_token,
        operator_status=Mock(return_value={'state': 'IDLE'}),
        operator_stop=Mock(return_value={'accepted': True}),
    )
    with TestClient(create_app(node)) as client:
        for path in ('/', '/static/operator.html', '/api/operator/status'):
            response = client.get(path)
            assert response.status_code == 200
            assert 'www-authenticate' not in response.headers
        response = client.post('/api/operator/stop')
        assert response.status_code == 200
        assert response.json() == {'accepted': True}
        assert 'www-authenticate' not in response.headers

    node.operator_status.assert_called_once_with({'job': 'black', 'place_id': 'Zone A'})
    node.operator_stop.assert_called_once_with()


@pytest.mark.parametrize('path', ['/maintenance', '/static/maintenance.html', '/static/maintenance.js',
                                  '/static/%2e/maintenance.html', '/static//maintenance.js'])
def test_maintenance_page_and_assets_require_credentials(path):
    node = SimpleNamespace(api_token='test-secret')
    client = TestClient(create_app(node))
    assert client.get(path).status_code == 401
    assert client.get(path, auth=('maintenance', 'wrong')).status_code == 401
    assert client.get(path, auth=('maintenance', 'test-secret')).status_code == 200


@pytest.mark.parametrize('path', ['/api/calibration/autonomous/start',
    '/api/calibration/autonomous/authorize', '/api/calibration/passive/capture',
    '/api/calibration/auto/start', '/api/system/startup', '/api/move'])
def test_maintenance_commands_fail_closed_without_access(path):
    client = TestClient(create_app(SimpleNamespace(api_token='test-secret')))
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, auth=('maintenance', 'wrong')).status_code == 401
    assert client.post(path, json={}, auth=('maintenance', 'test-secret'),
                       headers={'Origin': 'https://untrusted.example'}).status_code == 403
    unconfigured = TestClient(create_app(SimpleNamespace(api_token='')))
    assert unconfigured.post(path, json={}).status_code == 503


@pytest.mark.parametrize('token', ['', 'test-secret'])
def test_operator_home_needs_no_maintenance_credentials(token):
    node = SimpleNamespace(api_token=token, call_homing=Mock(return_value={'success': True}))
    with TestClient(create_app(node)) as client:
        response = client.post('/api/homing', headers={'Origin': 'http://testserver'})
        assert response.status_code == 200
        assert response.json() == {'success': True}
        assert 'www-authenticate' not in response.headers
        node.call_homing.assert_called_once_with()
        response = client.post('/api/homing', headers={'Origin': 'https://untrusted.example'})
        assert response.status_code == 403
        node.call_homing.assert_called_once_with()


def test_internal_motion_executor_credential_is_limited_to_existing_motion_api():
    from dobot_vision_yolo.vision_pick_place_node import HTTPMotionExecutor
    node = SimpleNamespace(api_token='', internal_api_token='private-in-process',
                           call_web_suction=Mock(return_value={'success': True}))
    executor = HTTPMotionExecutor('http://testserver', api_token=node.internal_api_token)
    client = TestClient(create_app(node), headers=executor._headers())
    assert client.post('/api/suction', json={'enable_suction': False}).status_code == 200
    node.call_web_suction.assert_called_once()
    assert client.get('/maintenance').status_code == 503
    assert client.post('/api/calibration/autonomous/authorize', json={}).status_code == 503
