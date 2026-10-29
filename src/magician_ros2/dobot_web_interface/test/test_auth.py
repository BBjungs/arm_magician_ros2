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
