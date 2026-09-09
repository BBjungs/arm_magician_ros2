import pytest

from dobot_web_interface.web_interface import (
    map_web_gripper_payload, map_web_suction_payload, normalize_tool_mapping,
)

def test_gripper_mapping_is_dedicated():
    assert map_web_gripper_payload({"state": "open"}) == ({"state": "open"}, "gripper")
    assert map_web_gripper_payload({"state": "close"}) == ({"state": "close"}, "gripper")

def test_suction_mapping_is_dedicated():
    assert map_web_suction_payload({"enable_suction": True}) == ({"enable_suction": True}, "suction")
    assert map_web_suction_payload({"enable_suction": False}) == ({"enable_suction": False}, "suction")

def test_swapped_mapping_is_rejected():
    with pytest.raises(ValueError, match="tool_mapping"):
        normalize_tool_mapping("swapped")
