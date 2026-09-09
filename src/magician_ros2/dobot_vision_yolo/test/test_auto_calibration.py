import numpy as np

import dobot_vision_yolo.camera_calibration_tool as calibration_module
from dobot_vision_yolo.camera_calibration_tool import CalibrationStore
from dobot_vision_yolo.camera_calibration_tool import auto_calibration_candidate
from dobot_vision_yolo.camera_calibration_tool import default_auto_calibration
from dobot_vision_yolo.camera_calibration_tool import default_calibration
from dobot_vision_yolo.aruco_board import marker_corners_board
from dobot_vision_yolo.aruco_board import transform_from_pose
from dobot_vision_yolo.eye_in_hand_transform import (
    EyeInHandConfigStore,
)
from dobot_vision_yolo.eye_in_hand_transform import (
    aggregate_eye_in_hand_calibration,
)
from dobot_vision_yolo.eye_in_hand_transform import default_eye_in_hand_config


def _robot_to_pixel(points):
    points = np.asarray(points, dtype=np.float64)
    return np.column_stack(
        (
            4.0 * (points[:, 0] - 150.0) + 100.0,
            3.0 * (points[:, 1] + 110.0) + 50.0,
        )
    )


def _synthetic_observations(noise_px=0.15, missing_id=None):
    config = default_auto_calibration()
    board = config["board"]
    t_base_board = transform_from_pose(board["pose_base"])
    observations = []
    for frame_index in range(config["sample_count"]):
        observation = {}
        for marker_id in board["required_ids"]:
            if marker_id == missing_id:
                continue
            local = marker_corners_board(
                board["markers"][str(marker_id)],
                board["marker_length_mm"],
            )
            base = (
                t_base_board
                @ np.column_stack((local, np.ones(len(local)))).T
            ).T[:, :3]
            corners = _robot_to_pixel(base[:, :2])
            pattern = np.array(
                [[1.0, -1.0], [-1.0, -0.5], [0.5, 1.0], [-0.5, 0.5]]
            )
            corners = corners + pattern * noise_px * ((frame_index % 3) - 1)
            observation[marker_id] = corners
        observations.append(observation)
    return observations


def test_fixed_camera_auto_calibration_self_validates_holdout_frames():
    config = default_auto_calibration()
    result = auto_calibration_candidate(
        _synthetic_observations(),
        (720, 1280, 3),
        config,
    )

    assert result["calibration_valid"] is True
    assert result["source"] == "aruco_auto_holdout"
    assert result["quality"]["verification_mean_error_mm"] < 1.0
    assert result["quality"]["cross_validation_max_error_mm"] < 1.0
    assert result["quality"]["frame_count"] == 12


def test_fixed_camera_auto_calibration_rejects_missing_marker():
    result = auto_calibration_candidate(
        _synthetic_observations(missing_id=2),
        (720, 1280, 3),
        default_auto_calibration(),
    )

    assert result["calibration_valid"] is False
    assert result["missing_ids"] == [2]


def test_failed_auto_attempt_preserves_last_valid_calibration(tmp_path, monkeypatch):
    path = tmp_path / "camera_to_robot.yaml"
    store = CalibrationStore(str(path))
    existing = default_calibration()
    existing.update(
        {
            "image_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "robot_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "homography": [1, 0, 0, 0, 1, 0, 0, 0, 1],
            "calibration_valid": True,
            "mean_error_mm": 0.0,
            "max_error_mm": 0.0,
            "calibrated_at": "2026-01-01T00:00:00Z",
            "validation": {
                "mean_error_mm": 0.0,
                "max_error_mm": 0.0,
                "point_errors_mm": [0.0] * 4,
                "calibration_valid": True,
                "calibrated_at": "2026-01-01T00:00:00Z",
                "warning": "",
                "source": "manual",
            },
        }
    )
    store.save(existing)
    monkeypatch.setattr(
        calibration_module,
        "_detect_aruco_observation",
        lambda _frame, _config: {},
    )

    status = store.auto_compute([np.zeros((20, 20, 3), dtype=np.uint8)] * 8)

    assert status["is_complete"] is True
    assert status["homography"] == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    assert status["last_auto_attempt"]["calibration_valid"] is False
    assert status["last_auto_attempt"]["previous_calibration_preserved"] is True


def test_successful_auto_attempt_is_saved_after_holdout_checks(tmp_path, monkeypatch):
    store = CalibrationStore(str(tmp_path / "camera_to_robot.yaml"))
    observations = iter(_synthetic_observations())
    monkeypatch.setattr(
        calibration_module,
        "_detect_aruco_observation",
        lambda _frame, _config: next(observations),
    )

    status = store.auto_compute([np.zeros((720, 1280, 3), dtype=np.uint8)] * 12)
    reloaded = store.load()

    assert status["is_complete"] is True
    assert reloaded["calibration_valid"] is True
    assert reloaded["validation"]["source"] == "aruco_auto_holdout"
    assert reloaded["validation"]["quality"]["verification_mean_error_mm"] < 1.0


def _eye_samples(translation_spread=0.2):
    samples = []
    for index in range(12):
        offset = translation_spread * ((index % 3) - 1)
        samples.append(
            {
                "detected_ids": [0, 1, 2, 3],
                "reprojection_error_px": 0.5 + 0.02 * index,
                "observation_valid": True,
                "missing_ids": [],
                "marker_cross_check_mean_mm": 0.5,
                "marker_cross_check_max_mm": 1.0,
                "measured_camera_mount": {
                    "translation_mm": [offset, -offset, 45.0 + offset],
                    "rotation_rpy_deg": [180.0, 0.05 * offset, -0.05 * offset],
                },
            }
        )
    return samples


def test_eye_in_hand_auto_calibration_accepts_stable_multiframe_mount():
    result = aggregate_eye_in_hand_calibration(
        _eye_samples(),
        default_eye_in_hand_config(),
        [220.0, 0.0, 120.0, 0.0],
    )

    assert result["calibration_valid"] is True
    assert result["quality"]["valid_sample_count"] == 12
    assert result["quality"]["mount_translation_stability_mm"] < 1.0


def test_eye_in_hand_auto_calibration_rejects_unstable_mount():
    result = aggregate_eye_in_hand_calibration(
        _eye_samples(translation_spread=8.0),
        default_eye_in_hand_config(),
        [220.0, 0.0, 120.0, 0.0],
    )

    assert result["calibration_valid"] is False
    assert "stable marker samples" in result["warning"]


def test_eye_in_hand_store_saves_only_stable_multiframe_result(tmp_path, monkeypatch):
    store = EyeInHandConfigStore(str(tmp_path / "eye_in_hand.yaml"))
    samples = iter(_eye_samples())
    monkeypatch.setattr(
        "dobot_vision_yolo.eye_in_hand_transform.calibrate_from_frame",
        lambda *_args, **_kwargs: next(samples),
    )

    status = store.auto_calibrate_from_frames(
        [np.zeros((20, 20, 3), dtype=np.uint8)] * 12,
        [220.0, 0.0, 120.0, 0.0],
        {
            "image_width": 20,
            "image_height": 20,
            "fx": 100.0,
            "fy": 100.0,
            "cx": 10.0,
            "cy": 10.0,
            "distortion_coefficients": [0.0] * 5,
        },
    )

    assert status["is_complete"] is True
    assert status["validation"]["source"] == "aruco_auto_multiframe"
    assert status["validation"]["updated_camera_mount"] is True


def test_failed_single_frame_eye_calibration_preserves_valid_config(
    tmp_path,
    monkeypatch,
):
    store = EyeInHandConfigStore(str(tmp_path / "eye_in_hand.yaml"))
    existing = default_eye_in_hand_config()
    existing["calibration_valid"] = True
    existing["validation"] = {
        "calibration_valid": True,
        "warning": "",
        "source": "known_good",
    }
    store.save(existing)
    monkeypatch.setattr(
        "dobot_vision_yolo.eye_in_hand_transform.calibrate_from_frame",
        lambda *_args, **_kwargs: {
            "calibration_valid": False,
            "warning": "Missing required ArUco marker ids: 1",
        },
    )

    status = store.calibrate_from_frame(
        np.zeros((20, 20, 3), dtype=np.uint8),
        [220.0, 0.0, 120.0, 0.0],
        {
            "image_width": 20,
            "image_height": 20,
            "fx": 100.0,
            "fy": 100.0,
            "cx": 10.0,
            "cy": 10.0,
            "distortion_coefficients": [0.0] * 5,
        },
    )

    assert status["is_complete"] is True
    assert store.load()["validation"]["source"] == "known_good"
    assert status["calibration"]["previous_calibration_preserved"] is True
