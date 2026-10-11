"""HTTP -> typed ROS request contract with no connected motion transport."""

from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from dobot_msgs.srv import AuthorizeCalibration
from dobot_web_interface.web_interface import DobotWebNode, create_app
from dobot_calibration.motion_authorization import ACKNOWLEDGEMENTS


def client_for(result):
    future = Future()
    future.set_result(result)
    client = Mock()
    client.service_is_ready.return_value = True
    client.call_async.return_value = future
    return client


def node_for_api():
    node = object.__new__(DobotWebNode)
    node.api_token = ''
    node._operation_is_active = lambda: False
    node.calibration_automatic_clients = {
        action: client_for(SimpleNamespace(success=True, message='Plan validation requested'))
        for action in ('start', 'commission', 'pause', 'resume', 'abort')}
    node.calibration_automatic_authorize = client_for(SimpleNamespace(
        accepted=True, report='{"message":"Run-specific authorization submitted"}'))
    return node


@pytest.mark.parametrize('action', ('start', 'commission', 'pause', 'resume', 'abort'))
def test_http_controls_route_to_their_autonomous_ros_clients(action):
    node = node_for_api()
    response = TestClient(create_app(node)).post('/api/calibration/autonomous/' + action)
    assert response.status_code == 200
    assert response.json()['accepted']
    node.calibration_automatic_clients[action].call_async.assert_called_once()
    assert all(client.call_async.call_count == int(key == action)
               for key, client in node.calibration_automatic_clients.items())
    node.calibration_automatic_authorize.call_async.assert_not_called()


def test_authorization_missing_checks_never_calls_ros():
    node = node_for_api()
    response = TestClient(create_app(node)).post('/api/calibration/autonomous/authorize', json={
        'plan_fingerprint': 'test-plan', 'operator_confirmed': True})
    assert response.status_code == 400
    node.calibration_automatic_authorize.call_async.assert_not_called()


def test_http_authorization_preserves_the_exact_plan_and_typed_confirmations():
    node = node_for_api()
    body = {**dict.fromkeys(ACKNOWLEDGEMENTS, True), 'plan_fingerprint': 'test-plan'}
    response = TestClient(create_app(node)).post('/api/calibration/autonomous/authorize', json=body)
    assert response.status_code == 200
    request = node.calibration_automatic_authorize.call_async.call_args.args[0]
    assert isinstance(request, AuthorizeCalibration.Request)
    assert request.plan_fingerprint == 'test-plan'
    assert all(getattr(request, key) is True for key in ACKNOWLEDGEMENTS)
    assert not response.json().get('motion_command_sent', False)


def test_ros_rejection_is_not_reported_as_accepted_motion():
    node = node_for_api()
    node.calibration_automatic_clients['start'] = client_for(SimpleNamespace(
        success=False, message='Another operation is active'))
    result = DobotWebNode.automatic_calibration_control(node, 'start')
    assert result['accepted'] is False


def test_active_operator_motion_prevents_authorization():
    node = node_for_api()
    node._operation_is_active = lambda: True
    response = TestClient(create_app(node)).post('/api/calibration/autonomous/authorize', json={})
    assert response.status_code == 409
    node.calibration_automatic_authorize.call_async.assert_not_called()
