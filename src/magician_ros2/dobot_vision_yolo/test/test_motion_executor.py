import threading

import pytest

from dobot_vision_yolo.vision_pick_place_node import HTTPMotionExecutor


class FakeExecutor(HTTPMotionExecutor):
    def __init__(self, cancel_event):
        super().__init__(
            "http://127.0.0.1:8080",
            cancel_event=cancel_event,
        )
        self.calls = []

    def _post(self, path, payload):
        self.calls.append((path, payload))
        return {"requested": True}

    def _move(self, pose):
        self.calls.append(("move", list(pose)))
        return {"accepted": True}

    def _tool(self, enable):
        self.calls.append(("tool", enable))
        return {"success": True}


def test_cancel_before_sequence_sends_no_motion():
    cancel_event = threading.Event()
    cancel_event.set()
    executor = FakeExecutor(cancel_event)

    with pytest.raises(RuntimeError, match="was canceled"):
        executor.execute(
            [{"step": 1, "command": "move_above_target", "pose": [1, 2, 3, 4]}]
        )

    assert ("move", [1, 2, 3, 4]) not in executor.calls
    assert ("/api/cancel", {}) in executor.calls


def test_cancel_while_waiting_does_not_start_next_step():
    cancel_event = threading.Event()
    executor = FakeExecutor(cancel_event)

    def status_then_cancel(_path):
        cancel_event.set()
        return {"motion": {"active_goal": True}}

    executor._get = status_then_cancel
    sequence = [
        {"step": 1, "command": "move_above_target", "pose": [1, 2, 3, 4]},
        {"step": 2, "command": "suction_on", "pose": [1, 2, 3, 4]},
    ]

    with pytest.raises(RuntimeError, match="was canceled"):
        executor.execute(sequence)

    assert executor.calls.count(("move", [1, 2, 3, 4])) == 1
    assert ("tool", True) not in executor.calls
    assert ("/api/cancel", {}) in executor.calls


def test_cancel_after_tool_on_runs_tool_cleanup():
    cancel_event = threading.Event()
    executor = FakeExecutor(cancel_event)

    def tool_then_cancel(enable):
        executor.calls.append(("tool", enable))
        if enable:
            cancel_event.set()
        return {"success": True}

    executor._tool = tool_then_cancel

    with pytest.raises(RuntimeError, match="was canceled"):
        executor.execute(
            [{"step": 1, "command": "suction_on", "pose": [1, 2, 3, 4]}]
        )

    assert executor.calls.count(("tool", True)) == 1
    assert executor.calls.count(("tool", False)) == 1
