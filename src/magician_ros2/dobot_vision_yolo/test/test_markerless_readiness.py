from pathlib import Path

import pytest

from dobot_calibration.geometry import CalibrationError, Mount
from dobot_vision_yolo.safety_guard import SafetyGuard, SafetyConfig, WorkspaceLimits


def test_invalid_mount_geometry_blocks_ready(tmp_path):
    path = tmp_path / "mount.yaml"
    path.write_text("geometry_verified: false\n", encoding="utf-8")
    with pytest.raises(CalibrationError):
        Mount.load(path)


def test_safety_remains_fail_closed_for_unverified_calibration():
    guard = SafetyGuard(SafetyConfig(
        workspace=WorkspaceLimits(150, 320, -180, 180, -45, 120),
        min_confidence=0.7, require_homing=True, homing_policy="reject",
        dry_run_default=True, allow_real_motion=False, camera_timeout_sec=5.0))
    report = guard.validate_pick(
        selected_target=None, camera_status={}, yolo_status={},
        calibration_status={"architecture": "markerless_hand_eye", "ready": False},
        places={}, dry_run=True, robot_homed=False, vision_mode="eye_in_hand",
        tcp_pose=None)
    assert report["ready"] is False
    assert not report["checks"]["calibration"]["ok"]


def test_production_sources_do_not_import_retired_board_pipeline():
    root = Path(__file__).resolve().parents[2]
    active = [
        root / "dobot_vision_yolo" / "target_selector_node.py",
        root / "dobot_vision_yolo" / "pixel_to_robot_node.py",
        root.parent / "launch" / "vision_pick_place.launch.py",
    ]
    forbidden = ("CalibrationStore", "EyeInHandConfigStore", "aruco")
    for path in active:
        text = path.read_text(encoding="utf-8").lower()
        assert not any(item.lower() in text for item in forbidden)
