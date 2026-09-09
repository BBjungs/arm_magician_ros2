import argparse
from copy import deepcopy
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib.request import urlopen

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from dobot_vision_yolo.aruco_board import default_aruco_board
from dobot_vision_yolo.aruco_board import detect_markers
from dobot_vision_yolo.aruco_board import load_aruco_board
from dobot_vision_yolo.aruco_board import marker_corners_board
from dobot_vision_yolo.aruco_board import normalize_aruco_board
from dobot_vision_yolo.aruco_board import transform_from_pose


PACKAGE_NAME = "dobot_vision_yolo"
MEAN_ERROR_THRESHOLD_MM = 5.0
MAX_ERROR_THRESHOLD_MM = 10.0
CLI_COMMANDS = {"status", "add-point", "compute", "test-point", "click-snapshot"}


class CalibrationError(ValueError):
    pass


def default_auto_calibration() -> Dict[str, Any]:
    """Settings for one-click, self-validating fixed-camera calibration."""
    return {
        "enabled": True,
        "board_config_path": "",
        "board": default_aruco_board(),
        "min_samples_per_marker": 3,
        "sample_count": 12,
        "capture_timeout_sec": 5.0,
        "min_valid_frame_ratio": 0.8,
        "min_blur_laplacian_variance": 40.0,
        "min_marker_side_px": 12.0,
        "min_marker_side_ratio": 0.35,
        "max_corner_jitter_px": 3.0,
        "min_coverage_ratio": 0.08,
        "min_inlier_ratio": 0.8,
        "ransac_threshold_mm": 3.0,
        "max_mean_error_mm": MEAN_ERROR_THRESHOLD_MM,
        "max_error_mm": MAX_ERROR_THRESHOLD_MM,
    }


def resolve_calibration_config_path(config_path: str = "") -> Path:
    if config_path:
        return Path(config_path).expanduser()

    env_path = os.environ.get("DOBOT_VISION_CALIBRATION_PATH", "")
    if env_path:
        return Path(env_path).expanduser()

    candidates = []
    candidates.append(
        Path.cwd()
        / "src"
        / "magician_ros2"
        / PACKAGE_NAME
        / "config"
        / "camera_to_robot.yaml"
    )
    candidates.append(
        Path(__file__).resolve().parents[1] / "config" / "camera_to_robot.yaml"
    )

    try:
        candidates.append(
            Path(get_package_share_directory(PACKAGE_NAME))
            / "config"
            / "camera_to_robot.yaml"
        )
    except PackageNotFoundError:
        pass

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def default_calibration() -> Dict[str, Any]:
    return {
        "image_points": [],
        "robot_points": [],
        "safe_z": 60.0,
        "pick_z": -35.0,
        "homography": [],
        "calibration_valid": False,
        "mean_error_mm": None,
        "max_error_mm": None,
        "calibrated_at": None,
        "auto_calibration": default_auto_calibration(),
        "validation": {
            "mean_error_mm": None,
            "max_error_mm": None,
            "point_errors_mm": [],
            "calibration_valid": False,
            "calibrated_at": None,
            "warning": "",
            "source": "manual",
        },
    }


def _as_point(value: Any, name: str) -> List[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise CalibrationError(f"{name} must be [x, y]")
    try:
        return [float(value[0]), float(value[1])]
    except (TypeError, ValueError) as exc:
        raise CalibrationError(f"{name} must contain numeric values") from exc


def _as_points(value: Any, name: str) -> List[List[float]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CalibrationError(f"{name} must be a list of [x, y] points")
    return [_as_point(point, f"{name}[{index}]") for index, point in enumerate(value)]


def _as_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CalibrationError(f"{name} must be numeric") from exc


def _as_optional_float(value: Any, name: str):
    if value is None:
        return None
    return _as_float(value, name)


def _as_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise CalibrationError(f"{name} must be boolean")


def _normalize_auto_calibration(value: Any) -> Dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise CalibrationError("auto_calibration must be an object")

    raw = dict(value)
    config = default_auto_calibration()
    config.update(raw)
    config["enabled"] = _as_bool(config.get("enabled", True), "auto_calibration.enabled")
    config["board_config_path"] = str(config.get("board_config_path", ""))
    board_value = raw.get("board")
    if board_value is None and any(
        key in raw for key in ("dictionary", "marker_length_mm", "required_ids", "markers")
    ):
        # Migrate the original absolute-base marker schema into board-local
        # coordinates. New saves use only the shared board schema.
        board_value = default_aruco_board()
        board_value["dictionary"] = str(raw.get("dictionary", board_value["dictionary"]))
        board_value["marker_length_mm"] = _as_float(
            raw.get("marker_length_mm", board_value["marker_length_mm"]),
            "auto_calibration.marker_length_mm",
        )
        board_value["required_ids"] = [
            int(marker_id)
            for marker_id in raw.get("required_ids", board_value["required_ids"])
        ]
        legacy_markers = raw.get("markers", {}) or {}
        if legacy_markers:
            t_board_base = np.linalg.inv(transform_from_pose(board_value["pose_base"]))
            converted = {}
            for marker_id in board_value["required_ids"]:
                marker = legacy_markers.get(str(marker_id), legacy_markers.get(marker_id))
                if marker is None:
                    continue
                center = list(marker.get("center_mm", []))
                if len(center) == 2:
                    center.append(board_value["pose_base"]["translation_mm"][2])
                local = t_board_base @ np.array([*center, 1.0], dtype=np.float64)
                converted[str(marker_id)] = {
                    "center_mm": local[:3].tolist(),
                    "yaw_deg": float(marker.get("yaw_deg", 0.0)),
                }
            board_value["markers"] = converted
    try:
        config["board"] = normalize_aruco_board(board_value or config.get("board"))
    except ValueError as exc:
        raise CalibrationError(str(exc)) from exc
    for legacy_key in ("dictionary", "marker_length_mm", "required_ids", "markers"):
        config.pop(legacy_key, None)
    config["min_samples_per_marker"] = int(
        config.get("min_samples_per_marker", 3)
    )
    config["sample_count"] = int(config.get("sample_count", 12))
    for key, default in (
        ("capture_timeout_sec", 5.0),
        ("min_valid_frame_ratio", 0.8),
        ("min_blur_laplacian_variance", 40.0),
        ("min_marker_side_px", 12.0),
        ("min_marker_side_ratio", 0.35),
        ("max_corner_jitter_px", 3.0),
        ("min_coverage_ratio", 0.08),
        ("min_inlier_ratio", 0.8),
        ("ransac_threshold_mm", 3.0),
        ("max_mean_error_mm", MEAN_ERROR_THRESHOLD_MM),
        ("max_error_mm", MAX_ERROR_THRESHOLD_MM),
    ):
        config[key] = _as_float(
            config.get(key, default),
            f"auto_calibration.{key}",
        )

    if config["sample_count"] < 8:
        raise CalibrationError("auto_calibration.sample_count must be at least 8")
    if config["min_samples_per_marker"] < 2:
        raise CalibrationError(
            "auto_calibration.min_samples_per_marker must be at least 2"
        )
    if not 0.8 <= config["min_valid_frame_ratio"] <= 1.0:
        raise CalibrationError("auto_calibration.min_valid_frame_ratio must be 0.8..1.0")
    return config


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _error_within_thresholds(mean_error, max_error) -> bool:
    if mean_error is None or max_error is None:
        return False
    return (
        float(mean_error) <= MEAN_ERROR_THRESHOLD_MM
        and float(max_error) <= MAX_ERROR_THRESHOLD_MM
    )


def _as_homography_values(value: Any) -> List[float]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        raise CalibrationError("homography must be a list of 9 numeric values")
    if len(value) != 9:
        raise CalibrationError("homography must contain 9 numeric values")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise CalibrationError("homography must contain numeric values") from exc


def _homography_matrix(value: Any) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 9:
        raise CalibrationError("Homography is not computed yet")
    try:
        matrix = np.array(value, dtype=np.float64).reshape(3, 3)
    except (TypeError, ValueError) as exc:
        raise CalibrationError("Homography contains invalid numeric values") from exc
    if abs(float(matrix[2, 2])) < 1e-9:
        raise CalibrationError("Homography is invalid: bottom-right value is zero")
    return matrix


def transform_pixel(homography: Sequence[float], image_point: Sequence[float]):
    matrix = _homography_matrix(list(homography))
    point = _as_point(image_point, "image_point")
    src = np.array([[[point[0], point[1]]]], dtype=np.float64)
    dst = cv2.perspectiveTransform(src, matrix)[0][0]
    return [round(float(dst[0]), 3), round(float(dst[1]), 3)]


class ArucoObservation(dict):
    """Marker map with capture diagnostics while retaining dict compatibility."""

    def __init__(self, markers=None, diagnostics=None):
        super().__init__(markers or {})
        self.diagnostics = diagnostics or {}


def _detect_aruco_observation(
    frame: np.ndarray,
    config: Dict[str, Any],
) -> Dict[int, np.ndarray]:
    if frame is None:
        return ArucoObservation()
    board = config.get("board", config)
    try:
        detection = detect_markers(cv2, frame, board["dictionary"])
    except ValueError as exc:
        raise CalibrationError(str(exc)) from exc
    required = [int(item) for item in board.get("required_ids", [])]
    detection["diagnostics"]["missing_ids"] = [
        marker_id for marker_id in required if marker_id not in detection["markers"]
    ]
    return ArucoObservation(
        detection["markers"],
        diagnostics=detection["diagnostics"],
    )


def _marker_robot_corners(
    marker: Dict[str, Any],
    marker_length_mm: float,
    board_pose_base: Dict[str, Any],
) -> np.ndarray:
    local = marker_corners_board(marker, marker_length_mm)
    t_base_board = transform_from_pose(board_pose_base)
    homogeneous = np.column_stack((local, np.ones(len(local), dtype=np.float64)))
    base = (t_base_board @ homogeneous.T).T
    return base[:, :2]


def _aggregate_marker_observations(
    observations: Sequence[Dict[int, np.ndarray]],
    config: Dict[str, Any],
) -> Tuple[Dict[int, np.ndarray], Dict[int, int], List[int], float]:
    aggregated = {}
    counts = {}
    missing = []
    jitter_values = []
    minimum = int(config["min_samples_per_marker"])
    for marker_id in config["board"]["required_ids"]:
        samples = [
            np.asarray(observation[marker_id], dtype=np.float64).reshape(4, 2)
            for observation in observations
            if marker_id in observation
        ]
        counts[marker_id] = len(samples)
        if len(samples) < minimum:
            missing.append(marker_id)
            continue
        stack = np.stack(samples, axis=0)
        median = np.median(stack, axis=0)
        aggregated[marker_id] = median
        jitter_values.extend(
            np.linalg.norm(stack - median[None, :, :], axis=2).reshape(-1).tolist()
        )
    jitter_p95 = (
        float(np.percentile(jitter_values, 95)) if jitter_values else float("inf")
    )
    return aggregated, counts, missing, jitter_p95


def _calibration_points(
    aggregated: Dict[int, np.ndarray],
    config: Dict[str, Any],
    included_ids: Sequence[int] = (),
) -> Tuple[np.ndarray, np.ndarray]:
    board = config["board"]
    marker_ids = list(included_ids) or list(board["required_ids"])
    image_points = []
    robot_points = []
    for marker_id in marker_ids:
        image_points.extend(aggregated[marker_id].tolist())
        robot_points.extend(
            _marker_robot_corners(
                board["markers"][str(marker_id)],
                board["marker_length_mm"],
                board["pose_base"],
            ).tolist()
        )
    return (
        np.asarray(image_points, dtype=np.float64),
        np.asarray(robot_points, dtype=np.float64),
    )


def _homography_errors(
    homography: np.ndarray,
    image_points: np.ndarray,
    robot_points: np.ndarray,
) -> np.ndarray:
    projected = cv2.perspectiveTransform(
        image_points.reshape(-1, 1, 2),
        homography,
    ).reshape(-1, 2)
    return np.linalg.norm(projected - robot_points, axis=1)


def _frame_diagnostics(
    observation: Dict[int, np.ndarray],
    frame_index: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    board = config["board"]
    required = [int(item) for item in board["required_ids"]]
    detected = sorted(int(item) for item in observation)
    missing = [marker_id for marker_id in required if marker_id not in observation]
    diagnostics = dict(getattr(observation, "diagnostics", {}) or {})
    diagnostics.update(
        {
            "frame_index": int(frame_index),
            "detected_ids": detected,
            "missing_ids": missing,
            "dictionary": board["dictionary"],
        }
    )
    marker_rows = []
    geometry_reasons = []
    centers = {}
    for marker_id in detected:
        points = np.asarray(observation[marker_id], dtype=np.float64).reshape(4, 2)
        center = np.mean(points, axis=0)
        centers[marker_id] = center
        sides = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
        minimum = float(np.min(sides))
        maximum = float(np.max(sides))
        side_ratio = minimum / maximum if maximum > 0.0 else 0.0
        area = abs(float(cv2.contourArea(points.astype(np.float32))))
        marker_rows.append(
            {
                "id": marker_id,
                "corners_pixel": [
                    [round(float(value), 3) for value in point] for point in points
                ],
                "center_pixel": [round(float(value), 3) for value in center],
                "area_px2": round(area, 3),
                "side_lengths_px": [round(float(value), 3) for value in sides],
                "side_ratio_min_over_max": round(side_ratio, 4),
                "quality_type": "corner_geometry_not_detector_confidence",
            }
        )
        if not np.all(np.isfinite(points)) or area <= 1.0:
            geometry_reasons.append(f"marker {marker_id} has invalid corners")
        elif minimum < float(config["min_marker_side_px"]):
            geometry_reasons.append(
                f"marker {marker_id} is too small ({minimum:.1f}px side)"
            )
        elif side_ratio < float(config["min_marker_side_ratio"]):
            geometry_reasons.append(
                f"marker {marker_id} corner geometry is distorted ({side_ratio:.2f})"
            )
    diagnostics["markers"] = marker_rows

    if all(marker_id in centers for marker_id in required):
        p0, p1, p2, p3 = [centers[marker_id] for marker_id in required]
        widths = [np.linalg.norm(p1 - p0), np.linalg.norm(p2 - p3)]
        heights = [np.linalg.norm(p3 - p0), np.linalg.norm(p2 - p1)]
        mean_width = float(np.mean(widths))
        mean_height = float(np.mean(heights))
        signed_area = 0.5 * float(
            sum(
                point[0] * next_point[1] - next_point[0] * point[1]
                for point, next_point in zip(
                    (p0, p1, p2, p3),
                    (p1, p2, p3, p0),
                )
            )
        )
        diagnostics["detected_board_geometry"] = {
            "width_edges_px": [round(float(value), 3) for value in widths],
            "height_edges_px": [round(float(value), 3) for value in heights],
            "mean_width_px": round(mean_width, 3),
            "mean_height_px": round(mean_height, 3),
            "aspect_ratio_width_over_height": (
                round(mean_width / mean_height, 4) if mean_height > 0.0 else None
            ),
            "id_winding_signed_area_px2": round(signed_area, 3),
            "id_layout": board["geometry"]["id_layout"],
        }

    reasons = []
    if missing:
        reasons.append("missing required marker ids: " + ", ".join(map(str, missing)))
    blur = diagnostics.get("blur_laplacian_variance")
    if (
        blur is not None
        and float(blur) < float(config["min_blur_laplacian_variance"])
    ):
        reasons.append(f"blur score {float(blur):.1f} is too low")
    reasons.extend(geometry_reasons)
    diagnostics["valid_for_solve"] = not reasons
    diagnostics["rejection_reasons"] = reasons
    return diagnostics


def _filter_valid_observations(
    observations: Sequence[Dict[int, np.ndarray]],
    config: Dict[str, Any],
) -> Tuple[List[Dict[int, np.ndarray]], List[Dict[str, Any]], Dict[str, int]]:
    valid = []
    diagnostics = []
    rejection_counts = {
        "missing_marker": 0,
        "blur": 0,
        "marker_geometry": 0,
    }
    for index, observation in enumerate(observations):
        frame = _frame_diagnostics(observation, index, config)
        diagnostics.append(frame)
        if frame["valid_for_solve"]:
            valid.append(observation)
            continue
        reasons = frame["rejection_reasons"]
        if any(reason.startswith("missing required") for reason in reasons):
            rejection_counts["missing_marker"] += 1
        if any(reason.startswith("blur score") for reason in reasons):
            rejection_counts["blur"] += 1
        if any("marker " in reason and not reason.startswith("missing") for reason in reasons):
            rejection_counts["marker_geometry"] += 1
    return valid, diagnostics, rejection_counts


def _marker_center_base(config: Dict[str, Any], marker_id: int) -> np.ndarray:
    board = config["board"]
    marker = board["markers"][str(marker_id)]
    center = np.array([*marker["center_mm"], 1.0], dtype=np.float64)
    return (transform_from_pose(board["pose_base"]) @ center)[:3]


def _cross_check_marker_row(
    marker_id: int,
    partial_homography: np.ndarray,
    verify_markers: Dict[int, np.ndarray],
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[float]]:
    held_image, held_robot = _calibration_points(
        verify_markers,
        config,
        [marker_id],
    )
    predicted = cv2.perspectiveTransform(
        held_image.reshape(-1, 1, 2),
        partial_homography,
    ).reshape(-1, 2)
    corner_errors = np.linalg.norm(predicted - held_robot, axis=1)
    expected_center = _marker_center_base(config, marker_id)
    predicted_center_xy = np.mean(predicted, axis=0)
    predicted_center = np.array(
        [predicted_center_xy[0], predicted_center_xy[1], expected_center[2]],
        dtype=np.float64,
    )
    delta = predicted_center - expected_center
    return (
        {
            "id": int(marker_id),
            "expected_xyz_mm": [
                round(float(value), 3) for value in expected_center
            ],
            "predicted_xyz_mm": [
                round(float(value), 3) for value in predicted_center
            ],
            "delta_xyz_mm": [round(float(value), 3) for value in delta],
            "error_norm_mm": round(float(np.linalg.norm(delta)), 3),
            "corner_mean_error_mm": round(float(np.mean(corner_errors)), 3),
            "corner_max_error_mm": round(float(np.max(corner_errors)), 3),
        },
        corner_errors.tolist(),
    )


def auto_calibration_candidate(
    observations: Sequence[Dict[int, np.ndarray]],
    image_shape: Sequence[int],
    auto_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Fit on half the frames and verify on untouched frames."""
    config = _normalize_auto_calibration(auto_config)
    if len(observations) < 8:
        raise CalibrationError("At least 8 fresh camera frames are required")
    if len(image_shape) < 2 or int(image_shape[0]) <= 0 or int(image_shape[1]) <= 0:
        raise CalibrationError("Camera image size is invalid")

    board = config["board"]
    required_ids = [int(item) for item in board["required_ids"]]
    valid_observations, frame_diagnostics, rejection_counts = (
        _filter_valid_observations(observations, config)
    )
    valid_ratio = float(len(valid_observations)) / float(len(observations))
    minimum_valid = max(
        8,
        int(np.ceil(float(config["min_valid_frame_ratio"]) * len(observations))),
    )
    training = list(valid_observations[::2])
    verification = list(valid_observations[1::2])
    train_markers, train_counts, train_missing, train_jitter = (
        _aggregate_marker_observations(training, config)
    )
    verify_markers, verify_counts, verify_missing, verify_jitter = (
        _aggregate_marker_observations(verification, config)
    )
    detected_ids = sorted(
        {
            int(marker_id)
            for observation in observations
            for marker_id in observation
        }
    )
    missing_ids = sorted(
        set(train_missing + verify_missing)
        & (set(required_ids) - set(detected_ids))
    )
    quality = {
        "frame_count": len(observations),
        "valid_frame_count": len(valid_observations),
        "valid_frame_ratio": round(valid_ratio, 4),
        "required_valid_frame_count": minimum_valid,
        "rejected_frame_count": len(observations) - len(valid_observations),
        "rejection_counts": rejection_counts,
        "training_frame_count": len(training),
        "verification_frame_count": len(verification),
        "training_detection_counts": train_counts,
        "verification_detection_counts": verify_counts,
        "missing_ids": missing_ids,
        "corner_jitter_px": None,
        "coverage_ratio": None,
        "inlier_ratio": None,
        "verification_mean_error_mm": None,
        "verification_max_error_mm": None,
        "cross_validation_mean_error_mm": None,
        "cross_validation_max_error_mm": None,
        "expected_board_geometry": board["geometry"],
        "detected_board_geometry": None,
    }
    result = {
        "ok": False,
        "calibration_valid": False,
        "source": "aruco_auto_holdout",
        "detected_ids": detected_ids,
        "missing_ids": missing_ids,
        "required_ids": required_ids,
        "estimated_marker_ids": [],
        "dictionary": board["dictionary"],
        "board": board,
        "board_coordinate_convention": (
            "marker centers are board-local; pose_base maps aruco_board to dobot_base"
        ),
        "frame_diagnostics": frame_diagnostics,
        "quality": quality,
        "warning": "",
        "homography": [],
        "image_points": [],
        "robot_points": [],
        "point_errors_mm": [],
        "marker_validation": [],
    }
    if not bool(board["pose_base"].get("anchored", False)):
        result["warning"] = (
            "Board pose in Dobot base is not anchored; configure a measured fixture "
            "or use a multi-pose hand-eye workflow"
        )
        return result
    if len(valid_observations) < minimum_valid:
        result["warning"] = (
            f"Only {len(valid_observations)}/{len(observations)} frames contained "
            "all required markers with valid quality; "
            f"need at least {minimum_valid} ({config['min_valid_frame_ratio'] * 100:.0f}%)"
        )
        return result
    if len(training) < int(config["min_samples_per_marker"]) or len(verification) < int(
        config["min_samples_per_marker"]
    ):
        result["warning"] = "Not enough complete frames in both fit and hold-out sets"
        return result
    if missing_ids:
        result["warning"] = (
            "Markers were not detected consistently in both capture sets: "
            + ", ".join(str(marker_id) for marker_id in missing_ids)
        )
        return result

    image_points, robot_points = _calibration_points(train_markers, config)
    verify_image_points, verify_robot_points = _calibration_points(
        verify_markers,
        config,
    )
    jitter = max(train_jitter, verify_jitter)
    hull = cv2.convexHull(image_points.astype(np.float32))
    image_area = float(int(image_shape[0]) * int(image_shape[1]))
    coverage = float(abs(cv2.contourArea(hull))) / image_area

    homography, inlier_mask = cv2.findHomography(
        image_points,
        robot_points,
        cv2.RANSAC,
        float(config["ransac_threshold_mm"]),
    )
    if homography is None:
        result["warning"] = "OpenCV could not compute a stable homography"
        return result
    if abs(float(homography[2, 2])) < 1e-9:
        result["warning"] = "Computed homography is singular"
        return result
    homography = homography / float(homography[2, 2])
    inlier_ratio = (
        float(np.mean(inlier_mask.reshape(-1) > 0))
        if inlier_mask is not None
        else 0.0
    )
    verification_errors = _homography_errors(
        homography,
        verify_image_points,
        verify_robot_points,
    )

    cross_errors = []
    marker_validation = []
    for held_out_id in required_ids:
        included_ids = [
            marker_id
            for marker_id in required_ids
            if marker_id != held_out_id
        ]
        partial_image, partial_robot = _calibration_points(
            train_markers,
            config,
            included_ids,
        )
        partial_homography, _mask = cv2.findHomography(
            partial_image,
            partial_robot,
            cv2.RANSAC,
            float(config["ransac_threshold_mm"]),
        )
        if partial_homography is None:
            cross_errors.append(float("inf"))
            marker_validation.append(
                {
                    "id": int(held_out_id),
                    "expected_xyz_mm": [
                        round(float(value), 3)
                        for value in _marker_center_base(config, held_out_id)
                    ],
                    "predicted_xyz_mm": None,
                    "delta_xyz_mm": None,
                    "error_norm_mm": None,
                    "corner_mean_error_mm": None,
                    "corner_max_error_mm": None,
                    "warning": "leave-one-marker-out homography failed",
                }
            )
            continue
        row, held_errors = _cross_check_marker_row(
            held_out_id,
            partial_homography,
            verify_markers,
            config,
        )
        marker_validation.append(row)
        cross_errors.extend(held_errors)

    verification_mean = float(np.mean(verification_errors))
    verification_max = float(np.max(verification_errors))
    cross_mean = float(np.mean(cross_errors)) if cross_errors else float("inf")
    cross_max = float(np.max(cross_errors)) if cross_errors else float("inf")
    quality.update(
        {
            "corner_jitter_px": round(jitter, 3),
            "coverage_ratio": round(coverage, 4),
            "inlier_ratio": round(inlier_ratio, 4),
            "verification_mean_error_mm": round(verification_mean, 3),
            "verification_max_error_mm": round(verification_max, 3),
            "cross_validation_mean_error_mm": round(cross_mean, 3),
            "cross_validation_max_error_mm": round(cross_max, 3),
            "detected_board_geometry": frame_diagnostics[
                next(
                    index
                    for index, item in enumerate(frame_diagnostics)
                    if item["valid_for_solve"]
                )
            ].get("detected_board_geometry"),
        }
    )

    warnings = []
    if jitter > float(config["max_corner_jitter_px"]):
        warnings.append(
            f"camera or calibration board moved ({jitter:.2f}px corner jitter)"
        )
    if coverage < float(config["min_coverage_ratio"]):
        warnings.append(
            f"markers cover only {coverage * 100.0:.1f}% of the image"
        )
    if inlier_ratio < float(config["min_inlier_ratio"]):
        warnings.append(f"only {inlier_ratio * 100.0:.1f}% of points are inliers")
    if verification_mean > float(config["max_mean_error_mm"]):
        warnings.append(
            f"held-out mean error is {verification_mean:.2f}mm"
        )
    if verification_max > float(config["max_error_mm"]):
        warnings.append(f"held-out maximum error is {verification_max:.2f}mm")
    if cross_mean > float(config["max_mean_error_mm"]):
        warnings.append(f"marker cross-check mean error is {cross_mean:.2f}mm")
    if cross_max > float(config["max_error_mm"]):
        warnings.append(f"marker cross-check maximum error is {cross_max:.2f}mm")

    valid = not warnings
    result.update(
        {
            "ok": valid,
            "calibration_valid": valid,
            "warning": "; ".join(warnings),
            "homography": [
                round(float(value), 10) for value in homography.reshape(-1)
            ],
            "image_points": [
                [round(float(value), 3) for value in point]
                for point in image_points.tolist()
            ],
            "robot_points": [
                [round(float(value), 3) for value in point]
                for point in robot_points.tolist()
            ],
            "point_errors_mm": [
                round(float(value), 3) for value in verification_errors.tolist()
            ],
            "marker_validation": marker_validation,
        }
    )
    return result


class CalibrationStore:
    def __init__(self, config_path: str = ""):
        self.path = resolve_calibration_config_path(config_path)
        self._attempt_lock = threading.Lock()
        self._last_auto_attempt = None

    def load(self) -> Dict[str, Any]:
        data = default_calibration()
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as stream:
                loaded = yaml.safe_load(stream) or {}
            if not isinstance(loaded, dict):
                raise CalibrationError("Calibration YAML root must be an object")
            data.update(loaded)
        auto = data.get("auto_calibration", {}) or {}
        legacy_keys = ("dictionary", "marker_length_mm", "required_ids", "markers")
        if isinstance(auto, dict) and "board" not in auto and not any(
            key in auto for key in legacy_keys
        ):
            auto = dict(auto)
            try:
                auto["board"] = load_aruco_board(auto.get("board_config_path", ""))
            except ValueError as exc:
                raise CalibrationError(str(exc)) from exc
            data["auto_calibration"] = auto
        return self._normalize(data)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize(data)
        persisted = deepcopy(normalized)
        persisted["auto_calibration"].pop("board", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(persisted, stream, sort_keys=False)
        return normalized

    def status(self) -> Dict[str, Any]:
        data = self.load()
        errors = self.validation_errors(data)
        data["config_path"] = str(self.path)
        data["point_count"] = len(data["image_points"])
        data["calibration_valid"] = (
            bool(data.get("calibration_valid", False))
            and not errors
            and len(data["homography"]) == 9
            and not data.get("validation", {}).get("warning")
        )
        data["is_complete"] = data["calibration_valid"]
        data["validation_errors"] = errors
        with self._attempt_lock:
            data["last_auto_attempt"] = self._last_auto_attempt
        return data

    def auto_compute(self, frames: Sequence[np.ndarray]):
        data = self.load()
        config = data["auto_calibration"]
        if not config.get("enabled", True):
            raise CalibrationError("Automatic calibration is disabled")
        if not frames:
            raise CalibrationError("Camera frames are unavailable")
        first_shape = frames[0].shape
        if any(frame is None or frame.shape[:2] != first_shape[:2] for frame in frames):
            raise CalibrationError("Calibration frames have inconsistent image sizes")

        observations = [
            _detect_aruco_observation(frame, config)
            for frame in frames
        ]
        previous_valid = bool(self.status().get("is_complete", False))
        candidate = auto_calibration_candidate(
            observations,
            first_shape,
            config,
        )
        candidate["attempted_at"] = _utc_now_iso()
        candidate["previous_calibration_preserved"] = bool(
            previous_valid and not candidate["calibration_valid"]
        )
        with self._attempt_lock:
            self._last_auto_attempt = candidate

        if candidate["calibration_valid"]:
            quality = candidate["quality"]
            calibrated_at = _utc_now_iso()
            data["image_points"] = candidate["image_points"]
            data["robot_points"] = candidate["robot_points"]
            data["homography"] = candidate["homography"]
            data["calibration_valid"] = True
            data["mean_error_mm"] = quality["verification_mean_error_mm"]
            data["max_error_mm"] = quality["verification_max_error_mm"]
            data["calibrated_at"] = calibrated_at
            data["validation"] = {
                "mean_error_mm": quality["verification_mean_error_mm"],
                "max_error_mm": quality["verification_max_error_mm"],
                "point_errors_mm": candidate["point_errors_mm"],
                "calibration_valid": True,
                "calibrated_at": calibrated_at,
                "warning": "",
                "source": candidate["source"],
                "quality": quality,
                "dictionary": candidate["dictionary"],
                "required_ids": candidate["required_ids"],
                "board": candidate["board"],
                "board_coordinate_convention": candidate[
                    "board_coordinate_convention"
                ],
                "marker_validation": candidate["marker_validation"],
                "frame_diagnostics": candidate["frame_diagnostics"],
            }
            self.save(data)
        return self.status()

    def add_point(self, image_point: Sequence[float], robot_point: Sequence[float]):
        data = self.load()
        data["image_points"].append(_as_point(image_point, "image_point"))
        data["robot_points"].append(_as_point(robot_point, "robot_point"))
        self._invalidate_solution(data)
        self.save(data)
        return self.status()

    def remove_point(self, index: int):
        data = self.load()
        try:
            point_index = int(index)
        except (TypeError, ValueError) as exc:
            raise CalibrationError("index must be an integer") from exc

        if point_index < 0 or point_index >= len(data["image_points"]):
            raise CalibrationError(
                f"index {point_index} is outside calibration point range"
            )

        del data["image_points"][point_index]
        del data["robot_points"][point_index]
        self._invalidate_solution(data)
        self.save(data)
        return self.status()

    @staticmethod
    def _invalidate_solution(data: Dict[str, Any]):
        data["homography"] = []
        data["calibration_valid"] = False
        data["mean_error_mm"] = None
        data["max_error_mm"] = None
        data["calibrated_at"] = None
        data["validation"] = default_calibration()["validation"]

    def compute(self):
        data = self.load()
        errors = self.validation_errors(data, require_homography=False)
        if errors:
            raise CalibrationError("; ".join(errors))

        image_points = np.array(data["image_points"], dtype=np.float64)
        robot_points = np.array(data["robot_points"], dtype=np.float64)
        homography, _mask = cv2.findHomography(image_points, robot_points, 0)
        if homography is None:
            raise CalibrationError("OpenCV could not compute homography")

        data["homography"] = [round(float(value), 10) for value in homography.reshape(-1)]
        data["validation"] = self._validation_result(data)
        data["calibration_valid"] = bool(data["validation"]["calibration_valid"])
        data["mean_error_mm"] = data["validation"]["mean_error_mm"]
        data["max_error_mm"] = data["validation"]["max_error_mm"]
        data["calibrated_at"] = _utc_now_iso()
        data["validation"]["calibrated_at"] = data["calibrated_at"]
        self.save(data)
        return self.status()

    def test_point(self, image_point: Sequence[float]):
        data = self.load()
        errors = self.validation_errors(data)
        if errors:
            raise CalibrationError("; ".join(errors))

        robot_xy = transform_pixel(data["homography"], image_point)
        return {
            "ok": True,
            "image_point": _as_point(image_point, "image_point"),
            "robot_xy": robot_xy,
            "safe_z": float(data["safe_z"]),
            "pick_z": float(data["pick_z"]),
            "calibration_valid": bool(data.get("calibration_valid", False)),
            "mean_error_mm": data.get("mean_error_mm"),
            "max_error_mm": data.get("max_error_mm"),
            "validation": data.get("validation", {}),
        }

    def validation_errors(self, data: Dict[str, Any], require_homography: bool = True):
        errors = []
        try:
            image_points = _as_points(data.get("image_points", []), "image_points")
        except CalibrationError as exc:
            errors.append(str(exc))
            image_points = []
        try:
            robot_points = _as_points(data.get("robot_points", []), "robot_points")
        except CalibrationError as exc:
            errors.append(str(exc))
            robot_points = []

        if len(image_points) != len(robot_points):
            errors.append("image_points and robot_points must have the same length")
        if len(image_points) < 4:
            errors.append("At least 4 calibration points are required")

        for index, point in enumerate(image_points):
            try:
                _as_point(point, f"image_points[{index}]")
            except CalibrationError as exc:
                errors.append(str(exc))
        for index, point in enumerate(robot_points):
            try:
                _as_point(point, f"robot_points[{index}]")
            except CalibrationError as exc:
                errors.append(str(exc))

        for key, default in (("safe_z", 60.0), ("pick_z", -35.0)):
            try:
                _as_float(data.get(key, default), key)
            except CalibrationError as exc:
                errors.append(str(exc))

        if require_homography:
            try:
                _homography_matrix(_as_homography_values(data.get("homography", [])))
            except CalibrationError as exc:
                errors.append(str(exc))

        return errors

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = default_calibration()
        normalized.update(data)
        raw_validation = data.get("validation") if isinstance(data, dict) else {}
        if not isinstance(raw_validation, dict):
            raw_validation = {}
        normalized["image_points"] = _as_points(
            normalized.get("image_points", []),
            "image_points",
        )
        normalized["robot_points"] = _as_points(
            normalized.get("robot_points", []),
            "robot_points",
        )
        normalized["safe_z"] = _as_float(normalized.get("safe_z", 60.0), "safe_z")
        normalized["pick_z"] = _as_float(normalized.get("pick_z", -35.0), "pick_z")
        normalized["homography"] = _as_homography_values(
            normalized.get("homography", [])
        )
        normalized["auto_calibration"] = _normalize_auto_calibration(
            normalized.get("auto_calibration", {})
        )
        if not isinstance(normalized.get("validation"), dict):
            normalized["validation"] = default_calibration()["validation"]
        validation = default_calibration()["validation"]
        validation.update(normalized.get("validation", {}))

        mean_error = normalized.get("mean_error_mm", raw_validation.get("mean_error_mm"))
        max_error = normalized.get("max_error_mm", raw_validation.get("max_error_mm"))
        normalized["mean_error_mm"] = _as_optional_float(mean_error, "mean_error_mm")
        normalized["max_error_mm"] = _as_optional_float(max_error, "max_error_mm")

        calibrated_at = normalized.get(
            "calibrated_at",
            raw_validation.get("calibrated_at"),
        )
        if calibrated_at is not None and not isinstance(calibrated_at, str):
            raise CalibrationError("calibrated_at must be a string or null")
        normalized["calibrated_at"] = calibrated_at

        has_valid_field = "calibration_valid" in data or "calibration_valid" in raw_validation
        calibration_valid = normalized.get(
            "calibration_valid",
            raw_validation.get("calibration_valid", False),
        )
        normalized["calibration_valid"] = _as_bool(
            calibration_valid,
            "calibration_valid",
        )
        if not has_valid_field and normalized["homography"]:
            normalized["calibration_valid"] = _error_within_thresholds(
                normalized["mean_error_mm"],
                normalized["max_error_mm"],
            ) and not validation.get("warning")

        validation["mean_error_mm"] = normalized["mean_error_mm"]
        validation["max_error_mm"] = normalized["max_error_mm"]
        validation["calibration_valid"] = normalized["calibration_valid"]
        validation["calibrated_at"] = normalized["calibrated_at"]
        if not isinstance(validation.get("point_errors_mm"), list):
            validation["point_errors_mm"] = []
        if not isinstance(validation.get("warning", ""), str):
            raise CalibrationError("validation.warning must be a string")
        normalized["validation"] = validation
        return normalized

    def _validation_result(self, data: Dict[str, Any]):
        errors = []
        for image_point, robot_point in zip(data["image_points"], data["robot_points"]):
            projected = transform_pixel(data["homography"], image_point)
            target = _as_point(robot_point, "robot_point")
            errors.append(float(np.linalg.norm(np.array(projected) - np.array(target))))

        point_errors = [round(value, 3) for value in errors]
        mean_error = round(float(np.mean(errors)), 3) if errors else None
        max_error = round(float(np.max(errors)), 3) if errors else None
        warning = ""
        if mean_error is not None and mean_error > MEAN_ERROR_THRESHOLD_MM:
            warning = (
                f"Average calibration error {mean_error} mm exceeds "
                f"{MEAN_ERROR_THRESHOLD_MM:g} mm"
            )
        elif max_error is not None and max_error > MAX_ERROR_THRESHOLD_MM:
            warning = (
                f"Maximum calibration error {max_error} mm exceeds "
                f"{MAX_ERROR_THRESHOLD_MM:g} mm"
            )
        return {
            "mean_error_mm": mean_error,
            "max_error_mm": max_error,
            "point_errors_mm": point_errors,
            "calibration_valid": _error_within_thresholds(mean_error, max_error),
            "calibrated_at": None,
            "warning": warning,
            "source": "manual",
        }


class CameraCalibrationTool(Node):
    def __init__(self):
        super().__init__("camera_calibration_tool")
        self.declare_parameter("dry_run", True)
        self.declare_parameter("image_topic", "/camera/color/image_raw")
        self.declare_parameter("calibration_config_path", "")
        self.declare_parameter("status_period_sec", 5.0)

        self.dry_run = bool(self.get_parameter("dry_run").value)
        self.image_topic = str(self.get_parameter("image_topic").value)
        self.store = CalibrationStore(
            str(self.get_parameter("calibration_config_path").value)
        )

        period = float(self.get_parameter("status_period_sec").value)
        self.create_timer(max(period, 1.0), self._log_status)
        self.get_logger().info(
            "Camera calibration tool ready. dry_run=%s, image_topic=%s, config=%s"
            % (self.dry_run, self.image_topic, self.store.path)
        )

    def _log_status(self):
        status = self.store.status()
        self.get_logger().info(
            "Calibration points=%d complete=%s mean_error_mm=%s"
            % (
                status["point_count"],
                status["is_complete"],
                status.get("validation", {}).get("mean_error_mm"),
            )
        )


def _print_json(payload: Dict[str, Any]) -> int:
    print(json.dumps(payload, indent=2, sort_keys=False))
    return 0


def _store_from_args(args) -> CalibrationStore:
    return CalibrationStore(str(getattr(args, "config", "") or ""))


def _cli_status(args) -> int:
    return _print_json(_store_from_args(args).status())


def _cli_add_point(args) -> int:
    image_point = args.image_point if args.image_point is not None else args.pixel
    if image_point is None:
        raise CalibrationError("--image-point or --pixel is required")
    return _print_json(_store_from_args(args).add_point(image_point, args.robot_point))


def _cli_compute(args) -> int:
    return _print_json(_store_from_args(args).compute())


def _cli_test_point(args) -> int:
    image_point = args.image_point if args.image_point is not None else args.pixel
    if image_point is None:
        raise CalibrationError("--image-point or --pixel is required")
    return _print_json(_store_from_args(args).test_point(image_point))


def _load_snapshot_bytes(args) -> bytes:
    if args.file:
        return Path(args.file).expanduser().read_bytes()
    with urlopen(args.url, timeout=float(args.timeout_sec)) as response:
        return response.read()


def _cli_click_snapshot(args) -> int:
    data = np.frombuffer(_load_snapshot_bytes(args), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise CalibrationError("Snapshot could not be decoded as an image")

    points: List[List[int]] = []
    window_name = "Dobot calibration snapshot"

    def on_mouse(event, x, y, _flags, _userdata):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        points.append([int(x), int(y)])
        cv2.circle(image, (int(x), int(y)), 5, (0, 255, 255), -1)
        cv2.putText(
            image,
            str(len(points)),
            (int(x) + 8, int(y) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    print("Click calibration markers. Press Enter when done, Esc to cancel.")
    while True:
        cv2.imshow(window_name, image)
        key = cv2.waitKey(20) & 0xFF
        if key in (13, 10):
            break
        if key == 27:
            points = []
            break
        if args.count and len(points) >= int(args.count):
            break
    cv2.destroyWindow(window_name)

    result = {"image_points": points, "point_count": len(points)}
    if args.output:
        output_path = Path(args.output).expanduser()
        with output_path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(result, stream, sort_keys=False)
        result["output"] = str(output_path)
    return _print_json(result)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Dobot camera-to-robot homography calibration.",
    )
    parser.add_argument(
        "--config",
        default="",
        help="Calibration YAML path. Defaults to DOBOT_VISION_CALIBRATION_PATH or package config.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Print calibration status as JSON.")
    status.set_defaults(func=_cli_status)

    add_point = subparsers.add_parser(
        "add-point",
        help="Append one matching image/robot calibration point.",
    )
    add_point.add_argument("--image-point", nargs=2, type=float, metavar=("U", "V"))
    add_point.add_argument("--pixel", nargs=2, type=float, metavar=("U", "V"))
    add_point.add_argument(
        "--robot-point",
        nargs=2,
        type=float,
        required=True,
        metavar=("X", "Y"),
    )
    add_point.set_defaults(func=_cli_add_point)

    compute = subparsers.add_parser(
        "compute",
        help="Compute homography and validation error from saved points.",
    )
    compute.set_defaults(func=_cli_compute)

    test_point = subparsers.add_parser(
        "test-point",
        help="Transform one pixel into Dobot X/Y using the saved homography.",
    )
    test_point.add_argument("--image-point", nargs=2, type=float, metavar=("U", "V"))
    test_point.add_argument("--pixel", nargs=2, type=float, metavar=("U", "V"))
    test_point.set_defaults(func=_cli_test_point)

    click_snapshot = subparsers.add_parser(
        "click-snapshot",
        help="Click pixels from a snapshot image without moving the robot.",
    )
    click_snapshot.add_argument(
        "--url",
        default="http://127.0.0.1:8080/api/snapshot",
        help="Snapshot URL to load when --file is not provided.",
    )
    click_snapshot.add_argument("--file", default="", help="Local snapshot image path.")
    click_snapshot.add_argument("--count", type=int, default=4)
    click_snapshot.add_argument("--output", default="", help="Optional YAML output path.")
    click_snapshot.add_argument("--timeout-sec", type=float, default=3.0)
    click_snapshot.set_defaults(func=_cli_click_snapshot)

    return parser


def _run_cli(argv: Sequence[str]) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CalibrationError as exc:
        parser.exit(2, f"error: {exc}\n")


def main(args=None):
    argv = list(sys.argv[1:] if args is None else args)
    if argv and (
        any(item in CLI_COMMANDS for item in argv)
        or any(item in ("-h", "--help") for item in argv)
    ):
        raise SystemExit(_run_cli(argv))

    rclpy.init(args=args)
    node = CameraCalibrationTool()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
