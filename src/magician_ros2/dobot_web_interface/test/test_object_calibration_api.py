from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
from fastapi.testclient import TestClient

from dobot_web_interface.web_interface import DobotWebNode, create_app


def web_node(result):
    node = Mock()
    node._operation_is_active.return_value = False
    node._calibration_is_active.return_value = False
    future = Future(); future.set_result(result)
    node.object_calibration_select.service_is_ready.return_value = True
    node.object_calibration_select.call_async.return_value = future
    node.object_calibration_clients = {'start': node.object_calibration_select,
                                       'dry_run': node.object_calibration_select}
    node._wait_for_future.side_effect = lambda f, timeout: f.result()
    return node


def test_selection_round_trip_preserves_exposure_and_rejection():
    node = web_node(SimpleNamespace(accepted=False, report='{"reason":"OBJECT_SELECTION_IMAGE_CHANGED"}'))
    payload = {'pixel': [200, 150], 'image_size': [640, 480], 'rgb_stamp': 42.}
    result = DobotWebNode.object_calibration_control(node, 'select', payload)
    assert not result['accepted'] and not result['motion_command_sent']
    request = node.object_calibration_select.call_async.call_args.args[0]
    assert json.loads(request.selection_json) == payload


@pytest.mark.parametrize('action', ['start', 'dry_run'])
def test_start_and_dry_run_wait_for_actual_service_result(action):
    node = web_node(SimpleNamespace(success=False, message='Another calibration operation is active'))
    result = DobotWebNode.object_calibration_control(node, action)
    assert not result['accepted']
    assert result['dry_run'] == (action == 'dry_run')


def test_selection_and_start_cannot_overlap_motion():
    node = web_node(None); node._operation_is_active.return_value = True
    with pytest.raises(RuntimeError):
        DobotWebNode.object_calibration_control(node, 'select', {})
    node.object_calibration_select.call_async.assert_not_called()


def test_api_requires_existing_auth_and_forwards_only_explicit_actions():
    node = SimpleNamespace(api_token='test-secret',
        object_calibration_control=Mock(return_value={'accepted': True, 'motion_command_sent': False}))
    with TestClient(create_app(node)) as client:
        for action in ('select', 'start', 'dry_run'):
            assert client.post('/api/calibration/object/' + action, json={}).status_code == 401
            response = client.post('/api/calibration/object/' + action, json={},
                                   auth=('maintenance', 'test-secret'))
            assert response.status_code == 200 and response.json()['accepted']
    assert node.object_calibration_control.call_count == 3
