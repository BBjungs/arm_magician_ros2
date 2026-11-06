from types import SimpleNamespace
from unittest.mock import Mock
import threading

from fastapi.testclient import TestClient
import pytest

from dobot_web_interface.web_interface import create_app, DobotWebNode


def test_observation_api_can_only_request_a_sensor_proposal():
    node = SimpleNamespace(api_token='',
        workspace_proposal_status=Mock(return_value={'state': 'IDLE'}),
        propose_workspace=Mock(return_value={'accepted': True, 'motion_command_sent': False}))
    client = TestClient(create_app(node))
    assert client.get('/api/workspace/proposal').json() == {'state': 'IDLE'}
    node.propose_workspace.assert_not_called()
    result = client.post('/api/workspace/proposal').json()
    assert result['accepted'] and not result['motion_command_sent']
    node.propose_workspace.assert_called_once_with()


def test_stale_calibration_topic_cannot_display_current_proposal():
    node = Mock()
    node.calibration_runtime_status.return_value = {'age_sec': 3., 'workspace_proposal': {'state': 'PROPOSED'}}
    assert DobotWebNode.workspace_proposal_status(node)['state'] == 'UNAVAILABLE'


@pytest.mark.parametrize('busy', ['operation', 'calibration', 'goal'])
def test_scan_rejects_robot_activity_before_ros_request(busy):
    node = Mock()
    node._operation_is_active.return_value = busy == 'operation'
    node._calibration_is_active.return_value = busy == 'calibration'
    node._goal_lock = threading.Lock()
    node._active_goal_handle = object() if busy == 'goal' else None
    with pytest.raises(RuntimeError):
        DobotWebNode.propose_workspace(node)
    node.workspace_proposal_client.call_async.assert_not_called()


def test_sensor_observation_blocks_manual_movement():
    node = SimpleNamespace(_calibration_status={'workspace_proposal': {'state': 'OBSERVING'}})
    assert DobotWebNode._calibration_is_active(node)
