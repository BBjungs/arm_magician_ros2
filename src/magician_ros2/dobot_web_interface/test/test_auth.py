import base64
from types import SimpleNamespace

from dobot_web_interface.web_interface import _basic_auth_valid


def request_with_credentials(username, password):
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return SimpleNamespace(headers={"authorization": f"Basic {encoded}"})


def test_basic_auth_accepts_expected_credentials():
    assert _basic_auth_valid(request_with_credentials("dobot", "secret"), "secret")


def test_basic_auth_rejects_wrong_user_or_token():
    assert not _basic_auth_valid(request_with_credentials("admin", "secret"), "secret")
    assert not _basic_auth_valid(request_with_credentials("dobot", "wrong"), "secret")


def test_basic_auth_rejects_missing_header():
    assert not _basic_auth_valid(SimpleNamespace(headers={}), "secret")
