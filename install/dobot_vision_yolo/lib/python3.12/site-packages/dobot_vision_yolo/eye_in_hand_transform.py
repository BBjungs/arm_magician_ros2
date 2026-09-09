import math
import os
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml
from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory

from dobot_vision_yolo.aruco_board import RPY_CONVENTION
from dobot_vision_yolo.aruco_board import aruco_dictionary
from dobot_vision_yolo.aruco_board import default_aruco_board
from dobot_vision_yolo.aruco_board import detect_markers
from dobot_vision_yolo.aruco_board import load_aruco_board
from dobot_vision_yolo.aruco_board import marker_corners_board
from dobot_vision_yolo.aruco_board import marker_transform_board
from dobot_vision_yolo.aruco_board import normalize_aruco_board
from dobot_vision_yolo.aruco_board import transform_from_pose
from dobot_vision_yolo.aruco_board import transform_summary

try:
    import cv2
except ImportError:  # pragma: no cover - depends on target image
    cv2 = None


PACKAGE_NAME = "dobot_vision_yolo"


class EyeInHandError(ValueError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _source_config_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "config" / filename


def _workspace_config_path(filename: str) -> Path:
    return Path.cwd() / "src" / "magician_ros2" / PACKAGE_NAME / "config" / filename


def _share_config_path(filename: str) -> Optional[Path]:
    try:
        return Path(get_package_share_directory(PACKAGE_NAME)) / "config" / filename
    except PackageNotFoundError:
        return None


def _resolve_config_path(filename: str, config_path: str, env_var: str) -> Path:
    if config_path:
        return Path(config_path).expanduser()

    env_path = os.environ.get(env_var, "")
    if env_path:
        return Path(env_path).expanduser()

    candidates = [_workspace_config_path(filename), _source_config_path(filename)]
    share_path = _share_config_path(filename)
    if share_path is not None:
        candidates.append(share_path)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_eye_in_hand_config_path(config_path: str = "") -> Path:
    return _resolve_config_path(
        "eye_in_hand.yaml",
        config_path,
        "DOBOT_VISION_EYE_IN_HAND_PATH",
    )


def resolve_camera_intrinsics_path(config_path: str = "") -> Path:
    return _resolve_config_path(
        "camera_intrinsics.yaml",
        config_path,
        "DOBOT_VISION_CAMERA_INTRINSICS_PATH",
    )


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream) or {}
    if not isinstance(loaded, dict):
        raise EyeInHandError(f"{path} root must be an object")
    return loaded


def _as_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise EyeInHandError(f"{name} must be numeric") from exc


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
    raise EyeInHandError(f"{name} must be boolean")


def _as_list(value: Any, name: str, count: int) -> List[float]:
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise EyeInHandError(f"{name} must contain {count} numeric values")
    return [_as_float(item, f"{name}[{index}]") for index, item in enumerate(value)]


def normalize_tcp_pose(
    value: Any,
    name: str = "tcp_pose",
    xyz_unit: str = "auto",
) -> List[float]:
    """Return ``[x, y, z, r]`` in millimetres/degrees.

    ``dobot_pose_raw`` is explicitly metres/degrees.  ``auto`` remains for
    compatibility with Web/API payloads, but ROS subscribers must pass ``m``
    so a valid near-origin pose can never be misclassified by magnitude.
    """
    if isinstance(value, dict):
        if all(key in value for key in ("x", "y", "z", "r")):
            value = [value["x"], value["y"], value["z"], value["r"]]
        elif "pose" in value:
            value = value["pose"]
        elif "current_pose" in value:
            value = value["current_pose"]
    pose = _as_list(value, name, 4)
    unit = str(xyz_unit).strip().lower()
    if unit not in ("auto", "m", "mm"):
        raise EyeInHandError(f"{name} xyz_unit must be auto, m, or mm")
    xyz_abs = [abs(item) for item in pose[:3]]
    if unit == "m" or (
        unit == "auto"
        and any(item > 1e-9 for item in xyz_abs)
        and max(xyz_abs) <= 2.0
    ):
        pose[:3] = [item * 1000.0 for item in pose[:3]]
    return pose


def extract_tcp_pose_from_status(status: Dict[str, Any]) -> Optional[List[float]]:
    if not isinstance(status, dict):
        return None

    candidates = [
        status.get("tcp_pose"),
        status.get("current_tcp_pose"),
        status.get("pose"),
        status.get("current_pose"),
    ]
    motion = status.get("motion")
    if isinstance(motion, dict):
        candidates.extend(
            [
                motion.get("current_tcp_pose"),
                motion.get("tcp_pose"),
                motion.get("last_feedback"),
            ]
        )
        last_result = motion.get("last_result")
        if isinstance(last_result, dict):
            candidates.append(last_result.get("achieved_pose"))

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return normalize_tcp_pose(candidate)
        except EyeInHandError:
            continue
    return None


def default_camera_intrinsics() -> Dict[str, Any]:
    return {
        "image_width": 640,
        "image_height": 480,
        "fx": 900.0,
        "fy": 900.0,
        "cx": 320.0,
        "cy": 240.0,
        "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
    }


def normalize_intrinsics(data: Dict[str, Any]) -> Dict[str, Any]:
    raw = data.get("camera_intrinsics", data)
    if not isinstance(raw, dict):
        raise EyeInHandError("camera_intrinsics must be an object")
    defaults = default_camera_intrinsics()
    normalized = {
        "image_width": int(raw.get("image_width", defaults["image_width"])),
        "image_height": int(raw.get("image_height", defaults["image_height"])),
        "fx": _as_float(raw.get("fx", defaults["fx"]), "camera_intrinsics.fx"),
        "fy": _as_float(raw.get("fy", defaults["fy"]), "camera_intrinsics.fy"),
        "cx": _as_float(raw.get("cx", defaults["cx"]), "camera_intrinsics.cx"),
        "cy": _as_float(raw.get("cy", defaults["cy"]), "camera_intrinsics.cy"),
        "distortion_coefficients": list(
            raw.get(
                "distortion_coefficients",
                defaults["distortion_coefficients"],
            )
        ),
    }
    normalized["distortion_coefficients"] = [
        _as_float(value, f"camera_intrinsics.distortion_coefficients[{index}]")
        for index, value in enumerate(normalized["distortion_coefficients"])
    ]
    if normalized["fx"] <= 0.0 or normalized["fy"] <= 0.0:
        raise EyeInHandError("camera intrinsics fx/fy must be positive")
    return normalized


def camera_matrix(intrinsics: Dict[str, Any]) -> np.ndarray:
    intrinsics = normalize_intrinsics(intrinsics)
    return np.array(
        [
            [intrinsics["fx"], 0.0, intrinsics["cx"]],
            [0.0, intrinsics["fy"], intrinsics["cy"]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def distortion_coefficients(intrinsics: Dict[str, Any]) -> np.ndarray:
    values = normalize_intrinsics(intrinsics)["distortion_coefficients"]
    return np.array(values, dtype=np.float64).reshape(-1, 1)


def intrinsics_for_image_size(
    intrinsics: Dict[str, Any],
    image_shape: Sequence[int],
) -> Dict[str, Any]:
    normalized = normalize_intrinsics(intrinsics)
    if len(image_shape) < 2:
        return normalized
    height = int(image_shape[0])
    width = int(image_shape[1])
    source_width = int(normalized.get("image_width", width))
    source_height = int(normalized.get("image_height", height))
    if source_width <= 0 or source_height <= 0:
        return normalized
    if width == source_width and height == source_height:
        return normalized
    scale_x = float(width) / float(source_width)
    scale_y = float(height) / float(source_height)
    scaled = dict(normalized)
    scaled["image_width"] = width
    scaled["image_height"] = height
    scaled["fx"] = float(normalized["fx"]) * scale_x
    scaled["fy"] = float(normalized["fy"]) * scale_y
    scaled["cx"] = float(normalized["cx"]) * scale_x
    scaled["cy"] = float(normalized["cy"]) * scale_y
    return scaled


def default_eye_in_hand_config() -> Dict[str, Any]:
    return {
        "mode": "eye_in_hand",
        "camera_device": "/dev/video0",
        "tcp_pose_source": "api_status",
        "tcp_pose_topic": "dobot_pose_raw",
        "fallback_tcp_pose_topic": "",
        "api_status_url": "http://127.0.0.1:8080/api/status",
        "camera_mount": {
            "translation_mm": [0.0, 0.0, 45.0],
            "rotation_rpy_deg": [180.0, 0.0, 0.0],
            "transform_direction": "T_tcp_camera",
            "parent_frame": "tcp",
            "child_frame": "camera_optical",
            "rpy_convention": RPY_CONVENTION,
            "max_look_down_tilt_deg": 25.0,
        },
        "table_plane": {"z_mm": -35.0},
        "aruco": {
            "board_config_path": "",
            "board": default_aruco_board(),
            "min_markers": 4,
            "max_reprojection_error_px": 3.0,
            "max_mount_translation_error_mm": 10.0,
            "max_mount_rotation_error_deg": 8.0,
            "max_marker_cross_check_mean_mm": 5.0,
            "max_marker_cross_check_max_mm": 10.0,
            "update_camera_mount": False,
            "auto_sample_count": 12,
            "auto_capture_timeout_sec": 5.0,
            "auto_min_valid_samples": 10,
            "min_valid_frame_ratio": 0.8,
            "min_blur_laplacian_variance": 40.0,
            "min_marker_side_px": 12.0,
            "min_marker_side_ratio": 0.35,
            "max_mount_stability_translation_mm": 2.5,
            "max_mount_stability_rotation_deg": 2.0,
            "max_camera_mount_distance_mm": 250.0,
        },
        "auto_position": {
            "enabled": False,
            "source": "configured_mount",
            "warning": (
                "ArUco calibration is not valid; using configured camera mount "
                "for automatic position estimate."
            ),
        },
        "safe_z": 60.0,
        "pick_z": -35.0,
        "calibration_valid": False,
        "calibrated_at": None,
        "validation": {
            "calibration_valid": False,
            "detected_ids": [],
            "missing_ids": [0, 1, 2, 3],
            "reprojection_error_px": None,
            "mount_translation_error_mm": None,
            "mount_rotation_error_deg": None,
            "warning": "Eye-in-hand calibration has not been validated.",
        },
    }


def normalize_eye_in_hand_config(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = default_eye_in_hand_config()
    normalized.update(data or {})

    mount = default_eye_in_hand_config()["camera_mount"]
    mount.update((data or {}).get("camera_mount", {}) or {})
    mount["translation_mm"] = _as_list(
        mount.get("translation_mm"),
        "camera_mount.translation_mm",
        3,
    )
    mount["rotation_rpy_deg"] = _as_list(
        mount.get("rotation_rpy_deg"),
        "camera_mount.rotation_rpy_deg",
        3,
    )
    mount["max_look_down_tilt_deg"] = _as_float(
        mount.get("max_look_down_tilt_deg", 25.0),
        "camera_mount.max_look_down_tilt_deg",
    )
    mount["transform_direction"] = str(
        mount.get("transform_direction", "T_tcp_camera")
    )
    mount["parent_frame"] = str(mount.get("parent_frame", "tcp"))
    mount["child_frame"] = str(mount.get("child_frame", "camera_optical"))
    mount["rpy_convention"] = str(mount.get("rpy_convention", RPY_CONVENTION))
    if mount["transform_direction"] != "T_tcp_camera":
        raise EyeInHandError("camera_mount.transform_direction must be T_tcp_camera")
    if mount["parent_frame"] != "tcp" or mount["child_frame"] != "camera_optical":
        raise EyeInHandError("camera_mount must map tcp -> camera_optical")
    if mount["rpy_convention"] != RPY_CONVENTION:
        raise EyeInHandError(
            "camera_mount.rpy_convention does not match the implemented convention"
        )
    normalized["camera_mount"] = mount

    table = default_eye_in_hand_config()["table_plane"]
    table.update((data or {}).get("table_plane", {}) or {})
    table["z_mm"] = _as_float(table.get("z_mm", -35.0), "table_plane.z_mm")
    normalized["table_plane"] = table

    aruco = default_eye_in_hand_config()["aruco"]
    raw_aruco = (data or {}).get("aruco", {}) or {}
    aruco.update(raw_aruco)
    aruco["board_config_path"] = str(aruco.get("board_config_path", ""))
    board_value = raw_aruco.get("board")
    legacy_keys = ("dictionary", "marker_length_mm", "required_ids", "markers")
    if board_value is None and any(key in raw_aruco for key in legacy_keys):
        board_value = default_aruco_board()
        board_value["dictionary"] = str(
            raw_aruco.get("dictionary", board_value["dictionary"])
        )
        board_value["marker_length_mm"] = _as_float(
            raw_aruco.get("marker_length_mm", board_value["marker_length_mm"]),
            "aruco.marker_length_mm",
        )
        board_value["required_ids"] = [
            int(item)
            for item in raw_aruco.get("required_ids", board_value["required_ids"])
        ]
        legacy_markers = raw_aruco.get("markers", {}) or {}
        if legacy_markers:
            t_board_base = np.linalg.inv(transform_from_pose(board_value["pose_base"]))
            converted = {}
            for marker_id in board_value["required_ids"]:
                marker = legacy_markers.get(str(marker_id), legacy_markers.get(marker_id))
                if marker is None:
                    continue
                center = _as_list(
                    marker.get("center_mm"),
                    f"aruco.markers.{marker_id}.center_mm",
                    3,
                )
                local = t_board_base @ np.array([*center, 1.0], dtype=np.float64)
                converted[str(marker_id)] = {
                    "center_mm": local[:3].tolist(),
                    "yaw_deg": _as_float(
                        marker.get("yaw_deg", 0.0),
                        f"aruco.markers.{marker_id}.yaw_deg",
                    ),
                }
            board_value["markers"] = converted
    try:
        aruco["board"] = normalize_aruco_board(board_value or aruco.get("board"))
    except ValueError as exc:
        raise EyeInHandError(str(exc)) from exc
    for legacy_key in legacy_keys:
        aruco.pop(legacy_key, None)
    required_ids = aruco["board"]["required_ids"]
    aruco["min_markers"] = int(aruco.get("min_markers", len(required_ids)))
    aruco["max_reprojection_error_px"] = _as_float(
        aruco.get("max_reprojection_error_px", 3.0),
        "aruco.max_reprojection_error_px",
    )
    aruco["max_mount_translation_error_mm"] = _as_float(
        aruco.get("max_mount_translation_error_mm", 10.0),
        "aruco.max_mount_translation_error_mm",
    )
    aruco["max_mount_rotation_error_deg"] = _as_float(
        aruco.get("max_mount_rotation_error_deg", 8.0),
        "aruco.max_mount_rotation_error_deg",
    )
    aruco["max_marker_cross_check_mean_mm"] = _as_float(
        aruco.get("max_marker_cross_check_mean_mm", 5.0),
        "aruco.max_marker_cross_check_mean_mm",
    )
    aruco["max_marker_cross_check_max_mm"] = _as_float(
        aruco.get("max_marker_cross_check_max_mm", 10.0),
        "aruco.max_marker_cross_check_max_mm",
    )
    aruco["update_camera_mount"] = _as_bool(
        aruco.get("update_camera_mount", False),
        "aruco.update_camera_mount",
    )
    aruco["auto_sample_count"] = int(aruco.get("auto_sample_count", 12))
    aruco["auto_capture_timeout_sec"] = _as_float(
        aruco.get("auto_capture_timeout_sec", 5.0),
        "aruco.auto_capture_timeout_sec",
    )
    aruco["auto_min_valid_samples"] = int(
        aruco.get("auto_min_valid_samples", 10)
    )
    for key, default in (
        ("min_valid_frame_ratio", 0.8),
        ("min_blur_laplacian_variance", 40.0),
        ("min_marker_side_px", 12.0),
        ("min_marker_side_ratio", 0.35),
    ):
        aruco[key] = _as_float(aruco.get(key, default), f"aruco.{key}")
    aruco["max_mount_stability_translation_mm"] = _as_float(
        aruco.get("max_mount_stability_translation_mm", 2.5),
        "aruco.max_mount_stability_translation_mm",
    )
    aruco["max_mount_stability_rotation_deg"] = _as_float(
        aruco.get("max_mount_stability_rotation_deg", 2.0),
        "aruco.max_mount_stability_rotation_deg",
    )
    aruco["max_camera_mount_distance_mm"] = _as_float(
        aruco.get("max_camera_mount_distance_mm", 250.0),
        "aruco.max_camera_mount_distance_mm",
    )
    if aruco["auto_sample_count"] < 8:
        raise EyeInHandError("aruco.auto_sample_count must be at least 8")
    if not 0.8 <= aruco["min_valid_frame_ratio"] <= 1.0:
        raise EyeInHandError("aruco.min_valid_frame_ratio must be 0.8..1.0")
    required_valid = int(
        math.ceil(aruco["auto_sample_count"] * aruco["min_valid_frame_ratio"])
    )
    if aruco["auto_min_valid_samples"] < required_valid:
        raise EyeInHandError(
            f"aruco.auto_min_valid_samples must be at least {required_valid} "
            "to preserve the 80% valid-frame criterion"
        )
    if aruco["auto_min_valid_samples"] > aruco["auto_sample_count"]:
        raise EyeInHandError(
            "aruco.auto_min_valid_samples cannot exceed aruco.auto_sample_count"
        )
    if aruco["min_markers"] != len(required_ids):
        raise EyeInHandError("eye-in-hand calibration requires every configured marker")
    normalized["aruco"] = aruco

    auto_position = default_eye_in_hand_config()["auto_position"]
    raw_auto_position = (data or {}).get("auto_position", {}) or {}
    if not isinstance(raw_auto_position, dict):
        raise EyeInHandError("auto_position must be an object")
    auto_position.update(raw_auto_position)
    auto_position["enabled"] = _as_bool(
        auto_position.get("enabled", False),
        "auto_position.enabled",
    )
    auto_position["source"] = str(auto_position.get("source", "configured_mount"))
    if auto_position["source"] != "configured_mount":
        raise EyeInHandError("auto_position.source must be configured_mount")
    auto_position["warning"] = str(
        auto_position.get(
            "warning",
            default_eye_in_hand_config()["auto_position"]["warning"],
        )
    )
    normalized["auto_position"] = auto_position

    normalized["mode"] = str(normalized.get("mode", "eye_in_hand"))
    normalized["camera_device"] = str(normalized.get("camera_device", "/dev/video0"))
    normalized["safe_z"] = _as_float(normalized.get("safe_z", 60.0), "safe_z")
    normalized["pick_z"] = _as_float(normalized.get("pick_z", -35.0), "pick_z")
    normalized["calibration_valid"] = _as_bool(
        normalized.get("calibration_valid", False),
        "calibration_valid",
    )
    validation = default_eye_in_hand_config()["validation"]
    raw_validation = normalized.get("validation", {}) or {}
    if isinstance(raw_validation, dict):
        validation.update(raw_validation)
    validation["calibration_valid"] = bool(normalized["calibration_valid"])
    normalized["validation"] = validation
    return normalized


def _rotation_x(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _rotation_y(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _rotation_z(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def rpy_matrix(rpy_deg: Sequence[float]) -> np.ndarray:
    roll, pitch, yaw = [math.radians(float(item)) for item in rpy_deg]
    return _rotation_z(yaw) @ _rotation_y(pitch) @ _rotation_x(roll)


def matrix_to_rpy_deg(rotation: np.ndarray) -> List[float]:
    sy = math.sqrt(rotation[0, 0] * rotation[0, 0] + rotation[1, 0] * rotation[1, 0])
    singular = sy < 1e-9
    if singular:
        roll = math.atan2(-rotation[1, 2], rotation[1, 1])
        pitch = math.atan2(-rotation[2, 0], sy)
        yaw = 0.0
    else:
        roll = math.atan2(rotation[2, 1], rotation[2, 2])
        pitch = math.atan2(-rotation[2, 0], sy)
        yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    return [round(math.degrees(value), 6) for value in (roll, pitch, yaw)]


def make_transform(rotation: np.ndarray, translation_mm: Sequence[float]) -> np.ndarray:
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    transform[:3, 3] = np.array(translation_mm, dtype=np.float64)
    return transform


def transform_from_tcp_pose(tcp_pose: Sequence[float]) -> np.ndarray:
    x, y, z, r = normalize_tcp_pose(tcp_pose)
    return make_transform(_rotation_z(math.radians(r)), [x, y, z])


def transform_from_mount(camera_mount: Dict[str, Any]) -> np.ndarray:
    translation = _as_list(
        camera_mount.get("translation_mm", [0.0, 0.0, 0.0]),
        "camera_mount.translation_mm",
        3,
    )
    rotation = rpy_matrix(
        _as_list(
            camera_mount.get("rotation_rpy_deg", [180.0, 0.0, 0.0]),
            "camera_mount.rotation_rpy_deg",
            3,
        )
    )
    return make_transform(rotation, translation)


def rotation_error_deg(a: np.ndarray, b: np.ndarray) -> float:
    delta = a[:3, :3].T @ b[:3, :3]
    value = (float(np.trace(delta)) - 1.0) / 2.0
    value = max(-1.0, min(1.0, value))
    return math.degrees(math.acos(value))


def _normalized_pixel_ray(
    center_pixel: Sequence[float],
    intrinsics: Dict[str, Any],
) -> np.ndarray:
    u, v = _as_list(center_pixel, "center_pixel", 2)
    intrinsics = normalize_intrinsics(intrinsics)
    if cv2 is not None and any(abs(value) > 1e-12 for value in intrinsics["distortion_coefficients"]):
        points = np.array([[[u, v]]], dtype=np.float64)
        undistorted = cv2.undistortPoints(
            points,
            camera_matrix(intrinsics),
            distortion_coefficients(intrinsics),
        )
        x = float(undistorted[0, 0, 0])
        y = float(undistorted[0, 0, 1])
    else:
        x = (u - intrinsics["cx"]) / intrinsics["fx"]
        y = (v - intrinsics["cy"]) / intrinsics["fy"]
    ray = np.array([x, y, 1.0], dtype=np.float64)
    return ray / np.linalg.norm(ray)


def camera_optical_axis_base(
    tcp_pose: Sequence[float],
    eye_config: Dict[str, Any],
) -> np.ndarray:
    config = normalize_eye_in_hand_config(eye_config)
    t_base_tool = transform_from_tcp_pose(tcp_pose)
    t_tool_camera = transform_from_mount(config["camera_mount"])
    axis = t_base_tool[:3, :3] @ t_tool_camera[:3, :3] @ np.array([0.0, 0.0, 1.0])
    return axis / np.linalg.norm(axis)


def look_down_status(
    tcp_pose: Optional[Sequence[float]],
    eye_config: Dict[str, Any],
) -> Dict[str, Any]:
    if tcp_pose is None:
        return {
            "ok": False,
            "warning": "TCP pose is unavailable; eye-in-hand look-down pose cannot be checked.",
            "tilt_deg": None,
        }
    config = normalize_eye_in_hand_config(eye_config)
    axis = camera_optical_axis_base(tcp_pose, config)
    down = np.array([0.0, 0.0, -1.0], dtype=np.float64)
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(axis, down))))))
    max_tilt = float(config["camera_mount"].get("max_look_down_tilt_deg", 25.0))
    warning = ""
    if tilt > max_tilt:
        warning = (
            f"Camera optical axis is {tilt:.1f} deg from table-normal down; "
            f"expected <= {max_tilt:g} deg."
        )
    return {
        "ok": not warning,
        "warning": warning,
        "tilt_deg": round(tilt, 3),
        "optical_axis_base": [round(float(item), 6) for item in axis],
    }


def _workspace_check(workspace: Any, pick_pose: Sequence[float]) -> Tuple[bool, str]:
    if workspace is None:
        return True, "workspace check not configured"
    if hasattr(workspace, "contains"):
        ok = bool(workspace.contains(pick_pose))
        if ok:
            return True, "pick_pose is inside workspace"
        if hasattr(workspace, "violation_reason"):
            return False, workspace.violation_reason(pick_pose, "pick_pose")
        return False, "pick_pose is outside workspace"
    if isinstance(workspace, dict):
        names = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
        if all(name in workspace for name in names):
            x, y, z = [float(item) for item in pick_pose[:3]]
            ok = (
                float(workspace["x_min"]) <= x <= float(workspace["x_max"])
                and float(workspace["y_min"]) <= y <= float(workspace["y_max"])
                and float(workspace["z_min"]) <= z <= float(workspace["z_max"])
            )
            return (ok, "pick_pose is inside workspace" if ok else "pick_pose is outside workspace")
    return True, "workspace check format not recognized"


def pixel_to_robot_xy(
    center_pixel: Sequence[float],
    tcp_pose: Sequence[float],
    intrinsics: Dict[str, Any],
    eye_config: Dict[str, Any],
    workspace: Any = None,
    require_calibration: bool = True,
) -> Dict[str, Any]:
    config = normalize_eye_in_hand_config(eye_config)
    calibration_valid = bool(config.get("calibration_valid", False))
    auto_position = config.get("auto_position", {}) or {}
    auto_position_enabled = bool(auto_position.get("enabled", False))
    if require_calibration and not calibration_valid and not auto_position_enabled:
        raise EyeInHandError("Eye-in-hand calibration_valid=false")

    tcp_pose = normalize_tcp_pose(tcp_pose)
    ray_camera = _normalized_pixel_ray(center_pixel, intrinsics)
    t_base_tool = transform_from_tcp_pose(tcp_pose)
    t_tool_camera = transform_from_mount(config["camera_mount"])
    t_base_camera = t_base_tool @ t_tool_camera

    origin = t_base_camera[:3, 3]
    direction = t_base_camera[:3, :3] @ ray_camera
    if abs(float(direction[2])) < 1e-9:
        raise EyeInHandError("Pixel ray is parallel to the configured table plane")

    table_z = float(config["table_plane"]["z_mm"])
    scale = (table_z - float(origin[2])) / float(direction[2])
    if scale <= 0.0:
        raise EyeInHandError("Pixel ray does not intersect the table in front of the camera")

    point = origin + scale * direction
    robot_xy = [round(float(point[0]), 3), round(float(point[1]), 3)]
    pick_pose = [robot_xy[0], robot_xy[1], float(config["pick_z"]), 0.0]
    workspace_ok, workspace_reason = _workspace_check(workspace, pick_pose)
    if not workspace_ok:
        raise EyeInHandError(workspace_reason)

    look_down = look_down_status(tcp_pose, config)
    position_estimate = not calibration_valid
    position_source = (
        "aruco_calibration" if calibration_valid else "configured_mount_estimate"
    )
    validation = dict(config.get("validation", {}) or {})
    warning = ""
    if position_estimate:
        warning = str(auto_position.get("warning", ""))
        validation_warnings = [
            str(value)
            for value in (validation.get("warning", ""), warning)
            if str(value)
        ]
        validation["warning"] = "; ".join(validation_warnings)
        validation["position_estimate"] = True
        validation["position_source"] = position_source

    return {
        "ok": True,
        "vision_mode": "eye_in_hand",
        "calibration_valid": calibration_valid,
        "position_available": True,
        "position_estimate": position_estimate,
        "position_source": position_source,
        "auto_position": auto_position,
        "warning": warning,
        "center_pixel": _as_list(center_pixel, "center_pixel", 2),
        "tcp_pose": tcp_pose,
        "robot_xy": robot_xy,
        "safe_z": float(config["safe_z"]),
        "pick_z": float(config["pick_z"]),
        "pick_pose": pick_pose,
        "table_z": table_z,
        "camera_origin_base": [round(float(item), 3) for item in origin],
        "ray_base": [round(float(item), 6) for item in direction],
        "look_down": look_down,
        "workspace": {
            "ok": workspace_ok,
            "reason": workspace_reason,
        },
        "validation": validation,
    }


def _aruco_dictionary(name: str):
    try:
        return aruco_dictionary(cv2, name)
    except ValueError as exc:
        raise EyeInHandError(str(exc)) from exc


def detect_aruco_markers(
    frame: np.ndarray,
    eye_config: Dict[str, Any],
) -> Dict[str, Any]:
    if frame is None:
        raise EyeInHandError("Camera frame is unavailable")
    config = normalize_eye_in_hand_config(eye_config)
    board = config["aruco"]["board"]
    try:
        detection = detect_markers(cv2, frame, board["dictionary"])
    except ValueError as exc:
        raise EyeInHandError(str(exc)) from exc
    detection["diagnostics"]["missing_ids"] = [
        marker_id
        for marker_id in board["required_ids"]
        if marker_id not in detection["detected_ids"]
    ]
    return detection


def _marker_detection_positions(
    detection: Dict[str, Any],
    eye_config: Dict[str, Any],
    tcp_pose: Optional[Sequence[float]] = None,
    intrinsics: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    config = normalize_eye_in_hand_config(eye_config)
    markers = config["aruco"]["board"]["markers"]
    table_z = float(config["table_plane"]["z_mm"])
    positions = []

    for marker_id, corners in zip(detection["ids"], detection["corners"]):
        marker_id = int(marker_id)
        corner_points = np.asarray(corners, dtype=np.float64).reshape(4, 2)
        center_pixel = np.mean(corner_points, axis=0)
        marker = markers.get(str(marker_id), markers.get(marker_id))
        item = {
            "id": marker_id,
            "center_pixel": [
                round(float(center_pixel[0]), 3),
                round(float(center_pixel[1]), 3),
            ],
            "corners_pixel": [
                [round(float(point[0]), 3), round(float(point[1]), 3)]
                for point in corner_points
            ],
            "configured": marker is not None,
        }

        yaw_deg = 0.0
        if marker is not None:
            configured_center_board = _as_list(
                marker.get("center_mm"),
                "aruco.markers.*.center_mm",
                3,
            )
            expected_center_base = (
                transform_from_pose(config["aruco"]["board"]["pose_base"])
                @ np.array([*configured_center_board, 1.0], dtype=np.float64)
            )[:3]
            yaw_deg = _as_float(
                marker.get("yaw_deg", 0.0),
                "aruco.markers.*.yaw_deg",
            )
            item["configured_center_mm"] = [
                round(float(value), 3) for value in expected_center_base
            ]
            item["configured_center_board_mm"] = [
                round(float(value), 3) for value in configured_center_board
            ]
            item["configured_yaw_deg"] = round(float(yaw_deg), 3)

        if tcp_pose is not None and intrinsics is not None:
            try:
                estimate = pixel_to_robot_xy(
                    item["center_pixel"],
                    tcp_pose,
                    intrinsics,
                    config,
                    require_calibration=False,
                )
                suggested_marker = {
                    "center_mm": [
                        estimate["robot_xy"][0],
                        estimate["robot_xy"][1],
                        table_z,
                    ],
                    "yaw_deg": round(float(yaw_deg), 3),
                }
                item["robot_xy_estimate"] = estimate["robot_xy"]
                item["suggested_marker"] = suggested_marker
                item["suggestion_source"] = estimate.get("position_source")
                item["suggestion_used_for_calibration"] = False
            except EyeInHandError as exc:
                item["position_error"] = str(exc)

        positions.append(item)

    return positions


def _marker_object_corners(marker: Dict[str, Any], marker_length_mm: float) -> np.ndarray:
    try:
        return marker_corners_board(marker, marker_length_mm)
    except ValueError as exc:
        raise EyeInHandError(str(exc)) from exc


def _project_base_points_to_image(
    object_points: np.ndarray,
    tcp_pose: Sequence[float],
    eye_config: Dict[str, Any],
    intrinsics: Dict[str, Any],
) -> np.ndarray:
    config = normalize_eye_in_hand_config(eye_config)
    t_base_tool = transform_from_tcp_pose(tcp_pose)
    t_tool_camera = transform_from_mount(config["camera_mount"])
    t_camera_base = np.linalg.inv(t_base_tool @ t_tool_camera)
    rotation = t_camera_base[:3, :3]
    translation = t_camera_base[:3, 3]
    camera_points = (rotation @ object_points.T).T + translation
    if np.any(camera_points[:, 2] <= 1e-6):
        raise EyeInHandError("Configured marker projects behind the camera")
    rvec, _ = cv2.Rodrigues(rotation)
    projected, _ = cv2.projectPoints(
        object_points.astype(np.float64),
        rvec,
        translation.reshape(3, 1),
        camera_matrix(intrinsics),
        distortion_coefficients(intrinsics),
    )
    return projected.reshape(-1, 2)


def render_aruco_overlay(
    frame: np.ndarray,
    eye_config: Dict[str, Any],
    intrinsics: Dict[str, Any],
    tcp_pose: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    if frame is None:
        raise EyeInHandError("Camera frame is unavailable")
    if cv2 is None:
        raise EyeInHandError("OpenCV is not available")

    config = normalize_eye_in_hand_config(eye_config)
    scaled_intrinsics = intrinsics_for_image_size(intrinsics, frame.shape)
    detection = detect_aruco_markers(frame, config)
    detected_ids = [int(item) for item in detection["detected_ids"]]
    detected_set = set(detected_ids)
    aruco = config["aruco"]
    board = aruco["board"]
    markers = board["markers"]
    required_ids = [int(item) for item in board["required_ids"]]
    marker_length = float(board["marker_length_mm"])
    output = frame.copy()
    green = (52, 199, 89)
    red = (60, 60, 240)
    white = (245, 245, 245)
    black = (0, 0, 0)

    def draw_label(text: str, origin: Sequence[float], color):
        x = int(round(float(origin[0])))
        y = int(round(float(origin[1])))
        y = max(18, y)
        cv2.putText(output, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.65, black, 3, cv2.LINE_AA)
        cv2.putText(output, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)

    markers_detected = _marker_detection_positions(
        detection,
        config,
        tcp_pose=tcp_pose,
        intrinsics=scaled_intrinsics,
    )
    detected_by_id = {int(item["id"]): item for item in markers_detected}

    for rejected in detection.get("rejected", []):
        points = np.asarray(rejected, dtype=np.float64).reshape(4, 2)
        cv2.polylines(
            output,
            [np.round(points).astype(np.int32)],
            True,
            red,
            2,
            cv2.LINE_AA,
        )
        draw_label("not decoded", np.mean(points, axis=0), red)

    for marker_id, corners in zip(detection["ids"], detection["corners"]):
        marker_id = int(marker_id)
        points = np.asarray(corners, dtype=np.float64).reshape(4, 2)
        cv2.polylines(
            output,
            [np.round(points).astype(np.int32)],
            True,
            green,
            3,
            cv2.LINE_AA,
        )
        center = np.mean(points, axis=0)
        marker_info = detected_by_id.get(marker_id, {})
        xy = marker_info.get("robot_xy_estimate")
        suffix = f" X={xy[0]:.1f} Y={xy[1]:.1f}" if isinstance(xy, list) and len(xy) >= 2 else ""
        draw_label(f"id {marker_id} found{suffix}", center, green)

    missing_ids = []
    projected_missing = []
    if tcp_pose is not None:
        for marker_id in required_ids:
            if marker_id in detected_set:
                continue
            marker = markers.get(str(marker_id), markers.get(marker_id))
            if marker is None:
                missing_ids.append(marker_id)
                continue
            missing_ids.append(marker_id)
            try:
                object_corners = _marker_object_corners(marker, marker_length)
                t_base_board = transform_from_pose(board["pose_base"])
                homogeneous = np.column_stack(
                    (object_corners, np.ones(len(object_corners), dtype=np.float64))
                )
                object_corners = (t_base_board @ homogeneous.T).T[:, :3]
                projected = _project_base_points_to_image(
                    object_corners,
                    tcp_pose,
                    config,
                    scaled_intrinsics,
                )
                cv2.polylines(
                    output,
                    [np.round(projected).astype(np.int32)],
                    True,
                    red,
                    3,
                    cv2.LINE_AA,
                )
                center = np.mean(projected, axis=0)
                configured = _as_list(marker.get("center_mm"), "aruco.markers.*.center_mm", 3)
                draw_label(
                    f"id {marker_id} missing X={configured[0]:.1f} Y={configured[1]:.1f}",
                    center,
                    red,
                )
                projected_missing.append(marker_id)
            except EyeInHandError:
                continue
    else:
        missing_ids = [marker_id for marker_id in required_ids if marker_id not in detected_set]

    legend_lines = [
        "GREEN: detected ArUco",
        "RED: not detected / not decoded",
    ]
    if missing_ids:
        legend_lines.append("missing: " + ", ".join(str(item) for item in missing_ids))
    y = 28
    for line in legend_lines:
        cv2.putText(output, line, (14, y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.72, black, 3, cv2.LINE_AA)
        cv2.putText(output, line, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, white, 2, cv2.LINE_AA)
        y += 30

    return {
        "image": output,
        "detected_ids": detected_ids,
        "missing_ids": missing_ids,
        "projected_missing_ids": projected_missing,
        "markers_detected": markers_detected,
    }


def _configured_marker_points(
    detection: Dict[str, Any],
    eye_config: Dict[str, Any],
    excluded_ids: Sequence[int] = (),
) -> Tuple[np.ndarray, np.ndarray, List[int], List[int]]:
    config = normalize_eye_in_hand_config(eye_config)
    board = config["aruco"]["board"]
    markers = board["markers"]
    required_ids = [int(item) for item in board["required_ids"]]
    marker_length = float(board["marker_length_mm"])

    object_points = []
    image_points = []
    used_ids = []
    excluded = {int(item) for item in excluded_ids}
    for marker_id, corners in zip(detection["ids"], detection["corners"]):
        if int(marker_id) in excluded:
            continue
        marker = markers.get(str(marker_id), markers.get(marker_id))
        if marker is None:
            continue
        marker_object = _marker_object_corners(marker, marker_length)
        object_points.extend(marker_object.tolist())
        image_points.extend(np.asarray(corners, dtype=np.float64).reshape(4, 2).tolist())
        used_ids.append(int(marker_id))

    missing = [marker_id for marker_id in required_ids if marker_id not in used_ids]
    return (
        np.asarray(object_points, dtype=np.float64),
        np.asarray(image_points, dtype=np.float64),
        used_ids,
        missing,
    )


def _eye_detection_quality_reasons(
    detection: Dict[str, Any],
    config: Dict[str, Any],
) -> List[str]:
    aruco = config["aruco"]
    diagnostics = detection.get("diagnostics", {}) or {}
    reasons = []
    blur = diagnostics.get("blur_laplacian_variance")
    if (
        blur is not None
        and float(blur) < float(aruco["min_blur_laplacian_variance"])
    ):
        reasons.append(f"blur score {float(blur):.1f} is too low")
    for marker in diagnostics.get("markers", []):
        sides = marker.get("side_lengths_px", [])
        if sides and min(float(value) for value in sides) < float(
            aruco["min_marker_side_px"]
        ):
            reasons.append(f"marker {marker['id']} is too small")
        ratio = marker.get("side_ratio_min_over_max")
        if ratio is not None and float(ratio) < float(aruco["min_marker_side_ratio"]):
            reasons.append(f"marker {marker['id']} corner geometry is distorted")
    return reasons


def _solve_camera_t_board(
    object_points: np.ndarray,
    image_points: np.ndarray,
    intrinsics: Dict[str, Any],
):
    ok, rvec, tvec = cv2.solvePnP(
        object_points,
        image_points,
        camera_matrix(intrinsics),
        distortion_coefficients(intrinsics),
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not ok:
        raise EyeInHandError("OpenCV solvePnP failed")
    rotation, _ = cv2.Rodrigues(rvec)
    return make_transform(rotation, tvec.reshape(3)), rvec, tvec


def _eye_marker_cross_validation(
    detection: Dict[str, Any],
    config: Dict[str, Any],
    intrinsics: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[float]]:
    board = config["aruco"]["board"]
    t_base_board = transform_from_pose(board["pose_base"])
    rows = []
    errors = []
    corners_by_id = {
        int(marker_id): np.asarray(corners, dtype=np.float64).reshape(4, 2)
        for marker_id, corners in zip(detection["ids"], detection["corners"])
    }
    for marker_id in board["required_ids"]:
        expected_local = np.asarray(
            board["markers"][str(marker_id)]["center_mm"],
            dtype=np.float64,
        )
        expected_base = (
            t_base_board @ np.array([*expected_local, 1.0], dtype=np.float64)
        )[:3]
        row = {
            "id": int(marker_id),
            "expected_xyz_mm": [round(float(value), 3) for value in expected_base],
            "predicted_xyz_mm": None,
            "delta_xyz_mm": None,
            "error_norm_mm": None,
        }
        try:
            partial_object, partial_image, _used, _missing = _configured_marker_points(
                detection,
                config,
                excluded_ids=[marker_id],
            )
            if len(partial_object) < 8:
                raise EyeInHandError("not enough independent markers for cross-check")
            t_camera_board, _rvec, _tvec = _solve_camera_t_board(
                partial_object,
                partial_image,
                intrinsics,
            )
            t_board_camera = np.linalg.inv(t_camera_board)
            center_pixel = np.mean(corners_by_id[marker_id], axis=0)
            ray_camera = _normalized_pixel_ray(center_pixel.tolist(), intrinsics)
            origin_board = t_board_camera[:3, 3]
            direction_board = t_board_camera[:3, :3] @ ray_camera
            if abs(float(direction_board[2])) < 1e-9:
                raise EyeInHandError("held-out marker ray is parallel to board")
            distance = -float(origin_board[2]) / float(direction_board[2])
            if distance <= 0.0:
                raise EyeInHandError("held-out marker lies behind camera")
            predicted_local = origin_board + distance * direction_board
            predicted_base = (
                t_base_board
                @ np.array([*predicted_local, 1.0], dtype=np.float64)
            )[:3]
            delta = predicted_base - expected_base
            error = float(np.linalg.norm(delta))
            row.update(
                {
                    "predicted_xyz_mm": [
                        round(float(value), 3) for value in predicted_base
                    ],
                    "delta_xyz_mm": [round(float(value), 3) for value in delta],
                    "error_norm_mm": round(error, 3),
                }
            )
            errors.append(error)
        except (EyeInHandError, KeyError, ValueError) as exc:
            row["warning"] = str(exc)
            errors.append(float("inf"))
        rows.append(row)
    return rows, errors


def calibrate_from_frame(
    frame: np.ndarray,
    tcp_pose: Sequence[float],
    eye_config: Dict[str, Any],
    intrinsics: Dict[str, Any],
    update_mount: Optional[bool] = None,
) -> Dict[str, Any]:
    if cv2 is None:
        raise EyeInHandError("OpenCV is not available")
    config = normalize_eye_in_hand_config(eye_config)
    tcp_pose = normalize_tcp_pose(tcp_pose)
    intrinsics = intrinsics_for_image_size(intrinsics, frame.shape)
    detection = detect_aruco_markers(frame, config)
    markers_detected = _marker_detection_positions(
        detection,
        config,
        tcp_pose=tcp_pose,
        intrinsics=intrinsics,
    )
    suggested_markers = {
        str(item["id"]): item["suggested_marker"]
        for item in markers_detected
        if "suggested_marker" in item
    }
    object_points, image_points, used_ids, missing = _configured_marker_points(
        detection,
        config,
    )

    aruco = config["aruco"]
    board = aruco["board"]
    warning = ""
    quality_reasons = _eye_detection_quality_reasons(detection, config)
    if not bool(board["pose_base"].get("anchored", False)):
        warning = (
            "Board pose in Dobot base is not anchored; a single robot pose "
            "cannot solve both board pose and T_tcp_camera"
        )
    elif missing:
        warning = "Missing required ArUco marker ids: " + ", ".join(str(item) for item in missing)
    elif len(used_ids) < int(aruco["min_markers"]):
        warning = f"Detected {len(used_ids)} configured markers; need {aruco['min_markers']}"
    elif len(object_points) < 4:
        warning = "Not enough configured ArUco corner points for solvePnP"
    elif quality_reasons:
        warning = "; ".join(quality_reasons)

    result = {
        "ok": False,
        "calibration_valid": False,
        "detected_ids": detection["detected_ids"],
        "used_ids": used_ids,
        "missing_ids": missing,
        "markers_detected": markers_detected,
        "suggested_markers": suggested_markers,
        "estimated_marker_ids": [],
        "dictionary": board["dictionary"],
        "required_ids": board["required_ids"],
        "board": board,
        "frame_diagnostics": detection.get("diagnostics", {}),
        "warning": warning,
    }
    if warning:
        return result

    try:
        t_camera_board, rvec, tvec = _solve_camera_t_board(
            object_points,
            image_points,
            intrinsics,
        )
    except EyeInHandError as exc:
        result["warning"] = str(exc)
        return result

    projected, _jacobian = cv2.projectPoints(
        object_points,
        rvec,
        tvec,
        camera_matrix(intrinsics),
        distortion_coefficients(intrinsics),
    )
    reprojection = np.linalg.norm(
        projected.reshape(-1, 2) - image_points.reshape(-1, 2),
        axis=1,
    )
    reprojection_error = float(np.mean(reprojection))
    t_base_board = transform_from_pose(board["pose_base"])
    t_base_camera = t_base_board @ np.linalg.inv(t_camera_board)
    t_base_tcp = transform_from_tcp_pose(tcp_pose)
    measured_t_tcp_camera = np.linalg.inv(t_base_tcp) @ t_base_camera
    configured_t_tcp_camera = transform_from_mount(config["camera_mount"])

    translation_error = float(
        np.linalg.norm(
            measured_t_tcp_camera[:3, 3] - configured_t_tcp_camera[:3, 3]
        )
    )
    rotation_error = rotation_error_deg(measured_t_tcp_camera, configured_t_tcp_camera)

    warnings = []
    if reprojection_error > float(aruco["max_reprojection_error_px"]):
        warnings.append(f"reprojection error {reprojection_error:.3f}px is too high")
    if translation_error > float(aruco["max_mount_translation_error_mm"]):
        warnings.append(f"mount translation error {translation_error:.3f}mm is too high")
    if rotation_error > float(aruco["max_mount_rotation_error_deg"]):
        warnings.append(f"mount rotation error {rotation_error:.3f}deg is too high")
    marker_validation, marker_errors = _eye_marker_cross_validation(
        detection,
        config,
        intrinsics,
    )
    marker_cross_mean = float(np.mean(marker_errors))
    marker_cross_max = float(np.max(marker_errors))
    if marker_cross_mean > float(aruco["max_marker_cross_check_mean_mm"]):
        warnings.append(
            f"marker cross-check mean error is {marker_cross_mean:.2f}mm"
        )
    if marker_cross_max > float(aruco["max_marker_cross_check_max_mm"]):
        warnings.append(
            f"marker cross-check maximum error is {marker_cross_max:.2f}mm"
        )

    measured_translation = [
        round(float(item), 6) for item in measured_t_tcp_camera[:3, 3].tolist()
    ]
    measured_rpy = matrix_to_rpy_deg(measured_t_tcp_camera[:3, :3])
    candidate_config = normalize_eye_in_hand_config(config)
    candidate_config["camera_mount"]["translation_mm"] = measured_translation
    candidate_config["camera_mount"]["rotation_rpy_deg"] = measured_rpy
    look_down = look_down_status(tcp_pose, candidate_config)
    if not look_down.get("ok", False):
        warnings.append(look_down.get("warning") or "camera is not looking down")
    valid = not warnings
    should_update_mount = bool(aruco.get("update_camera_mount", False))
    if update_mount is not None:
        should_update_mount = bool(update_mount)
    if should_update_mount and valid:
        config["camera_mount"]["translation_mm"] = measured_translation
        config["camera_mount"]["rotation_rpy_deg"] = measured_rpy
    transforms = {
        "T_camera_board": transform_summary(
            t_camera_board,
            "camera_optical",
            "aruco_board",
        ),
        "T_base_tcp": transform_summary(t_base_tcp, "base", "tcp"),
        "T_tcp_camera": transform_summary(
            measured_t_tcp_camera,
            "tcp",
            "camera_optical",
        ),
        "T_base_camera": transform_summary(
            t_base_camera,
            "base",
            "camera_optical",
        ),
        "T_base_board": transform_summary(t_base_board, "base", "aruco_board"),
        "markers": [],
    }
    for marker_id in board["required_ids"]:
        t_board_marker = marker_transform_board(board["markers"][str(marker_id)])
        transforms["markers"].append(
            {
                "id": int(marker_id),
                "T_camera_marker": transform_summary(
                    t_camera_board @ t_board_marker,
                    "camera_optical",
                    f"marker_{marker_id}",
                ),
                "T_base_marker": transform_summary(
                    t_base_board @ t_board_marker,
                    "base",
                    f"marker_{marker_id}",
                ),
            }
        )
    return {
        "ok": valid,
        "calibration_valid": valid,
        "detected_ids": detection["detected_ids"],
        "used_ids": used_ids,
        "missing_ids": missing,
        "markers_detected": markers_detected,
        "suggested_markers": suggested_markers,
        "reprojection_error_px": round(reprojection_error, 3),
        "mount_translation_error_mm": round(translation_error, 3),
        "mount_rotation_error_deg": round(rotation_error, 3),
        "measured_camera_mount": {
            "translation_mm": measured_translation,
            "rotation_rpy_deg": measured_rpy,
            "transform_direction": "T_tcp_camera",
            "parent_frame": "tcp",
            "child_frame": "camera_optical",
            "rpy_convention": RPY_CONVENTION,
        },
        "observation_valid": (
            reprojection_error <= float(aruco["max_reprojection_error_px"])
            and marker_cross_mean
            <= float(aruco["max_marker_cross_check_mean_mm"])
            and marker_cross_max
            <= float(aruco["max_marker_cross_check_max_mm"])
            and not quality_reasons
        ),
        "marker_validation": marker_validation,
        "marker_cross_check_mean_mm": round(marker_cross_mean, 3),
        "marker_cross_check_max_mm": round(marker_cross_max, 3),
        "transforms": transforms,
        "updated_camera_mount": bool(should_update_mount and valid),
        "look_down": look_down,
        "warning": "; ".join(warnings),
        "config": config,
    }


def _average_rotation(rotations: Sequence[np.ndarray]) -> np.ndarray:
    mean_rotation = np.sum(np.stack(rotations, axis=0), axis=0)
    left, _singular_values, right = np.linalg.svd(mean_rotation)
    averaged = left @ right
    if np.linalg.det(averaged) < 0.0:
        left[:, -1] *= -1.0
        averaged = left @ right
    return averaged


def aggregate_eye_in_hand_calibration(
    samples: Sequence[Dict[str, Any]],
    eye_config: Dict[str, Any],
    tcp_pose: Sequence[float],
) -> Dict[str, Any]:
    """Reject unstable measurements and return one robust camera mount."""
    config = normalize_eye_in_hand_config(eye_config)
    aruco = config["aruco"]
    board = aruco["board"]
    detection_usable_flags = [
        (
            isinstance(sample.get("measured_camera_mount"), dict)
            and sample.get("reprojection_error_px") is not None
            and bool(sample.get("observation_valid", True))
            and not sample.get("missing_ids", [])
        )
        for sample in samples
    ]
    detection_usable = [
        sample
        for sample, is_usable in zip(samples, detection_usable_flags)
        if is_usable
    ]
    detected_ids = sorted(
        {
            int(marker_id)
            for sample in samples
            for marker_id in sample.get("detected_ids", [])
        }
    )
    quality = {
        "frame_count": len(samples),
        "detection_valid_sample_count": len(detection_usable),
        "valid_sample_count": len(detection_usable),
        "valid_frame_ratio": (
            round(float(len(detection_usable)) / float(len(samples)), 4)
            if samples
            else 0.0
        ),
        "required_valid_samples": max(
            int(aruco["auto_min_valid_samples"]),
            int(math.ceil(len(samples) * float(aruco["min_valid_frame_ratio"]))),
        ),
        "rejected_frame_count": len(samples) - len(detection_usable),
        "robust_outlier_count": 0,
        "robust_outlier_indices": [],
        "robust_estimator": "median translation + rotation medoid + SVD mean",
        "rejection_reasons": [
            str(sample.get("warning") or "invalid observation")
            for sample, is_usable in zip(samples, detection_usable_flags)
            if not is_usable
        ],
        "reprojection_mean_px": None,
        "reprojection_max_px": None,
        "mount_translation_stability_mm": None,
        "mount_rotation_stability_deg": None,
        "prior_translation_offset_mm": None,
        "prior_rotation_offset_deg": None,
        "marker_cross_check_mean_mm": None,
        "marker_cross_check_max_mm": None,
    }
    result = {
        "ok": False,
        "calibration_valid": False,
        "source": "aruco_auto_multiframe",
        "quality": quality,
        "detected_ids": detected_ids,
        "required_ids": board["required_ids"],
        "estimated_marker_ids": [],
        "dictionary": board["dictionary"],
        "board": board,
        "board_coordinate_convention": (
            "marker centers are board-local; pose_base maps aruco_board to dobot_base"
        ),
        "markers_detected": [],
        "missing_ids": [
            marker_id
            for marker_id in board["required_ids"]
            if marker_id not in detected_ids
        ],
        "measured_camera_mount": None,
        "marker_validation": [],
        "transforms": {},
        "frame_diagnostics": [
            {
                **dict(sample.get("frame_diagnostics", {}) or {}),
                "frame_index": index,
                "valid_for_solve": bool(detection_usable_flags[index]),
                "rejection_reasons": (
                    []
                    if detection_usable_flags[index]
                    else [str(sample.get("warning") or "invalid observation")]
                ),
            }
            for index, sample in enumerate(samples)
        ],
        "look_down": {},
        "warning": "",
    }
    minimum = int(quality["required_valid_samples"])
    if len(detection_usable) < minimum:
        result["warning"] = (
            f"Only {len(detection_usable)} complete, quality-valid marker samples "
            f"were available; need {minimum}"
        )
        return result

    candidate_transforms = []
    for sample in detection_usable:
        mount = sample["measured_camera_mount"]
        candidate_transforms.append(
            make_transform(
                rpy_matrix(mount["rotation_rpy_deg"]),
                mount["translation_mm"],
            )
        )

    candidate_translations = np.stack(
        [transform[:3, 3] for transform in candidate_transforms]
    )
    provisional_translation = np.median(candidate_translations, axis=0)
    pairwise_rotation_errors = np.array(
        [
            [
                rotation_error_deg(left, right)
                for right in candidate_transforms
            ]
            for left in candidate_transforms
        ],
        dtype=np.float64,
    )
    rotation_medoid_index = int(
        np.argmin(np.median(pairwise_rotation_errors, axis=1))
    )
    rotation_medoid = candidate_transforms[rotation_medoid_index]
    provisional_translation_deviations = np.linalg.norm(
        candidate_translations - provisional_translation[None, :],
        axis=1,
    )
    provisional_rotation_deviations = np.asarray(
        [
            rotation_error_deg(transform, rotation_medoid)
            for transform in candidate_transforms
        ],
        dtype=np.float64,
    )
    stable_flags = (
        provisional_translation_deviations
        <= float(aruco["max_mount_stability_translation_mm"])
    ) & (
        provisional_rotation_deviations
        <= float(aruco["max_mount_stability_rotation_deg"])
    )
    stable_samples = [
        sample
        for sample, is_stable in zip(detection_usable, stable_flags)
        if bool(is_stable)
    ]
    transforms = [
        transform
        for transform, is_stable in zip(candidate_transforms, stable_flags)
        if bool(is_stable)
    ]
    stable_iterator = iter(bool(value) for value in stable_flags)
    outlier_indices = []
    for index, is_detection_usable in enumerate(detection_usable_flags):
        if is_detection_usable and not next(stable_iterator):
            outlier_indices.append(index)
    quality.update(
        {
            "valid_sample_count": len(stable_samples),
            "valid_frame_ratio": round(
                float(len(stable_samples)) / float(len(samples)), 4
            ),
            "rejected_frame_count": len(samples) - len(stable_samples),
            "robust_outlier_count": len(outlier_indices),
            "robust_outlier_indices": outlier_indices,
        }
    )
    quality["rejection_reasons"].extend(
        f"frame {index}: camera mount estimate is a robust outlier"
        for index in outlier_indices
    )
    for index in outlier_indices:
        result["frame_diagnostics"][index]["valid_for_solve"] = False
        result["frame_diagnostics"][index]["rejection_reasons"].append(
            "camera mount estimate is a robust outlier"
        )
    if len(stable_samples) < minimum:
        result["warning"] = (
            f"Only {len(stable_samples)} stable marker samples remained after "
            f"robust outlier rejection; need {minimum}"
        )
        return result

    translations = np.stack([transform[:3, 3] for transform in transforms])
    median_translation = np.median(translations, axis=0)
    averaged_rotation = _average_rotation(
        [transform[:3, :3] for transform in transforms]
    )
    averaged_transform = make_transform(averaged_rotation, median_translation)
    translation_deviations = np.linalg.norm(
        translations - median_translation[None, :],
        axis=1,
    )
    rotation_deviations = [
        rotation_error_deg(transform, averaged_transform) for transform in transforms
    ]
    translation_stability = float(np.percentile(translation_deviations, 95))
    rotation_stability = float(np.percentile(rotation_deviations, 95))
    reprojection_errors = [
        float(sample["reprojection_error_px"]) for sample in stable_samples
    ]
    reprojection_mean = float(np.mean(reprojection_errors))
    reprojection_max = float(np.max(reprojection_errors))
    marker_cross_values = [
        float(sample["marker_cross_check_mean_mm"])
        for sample in stable_samples
        if sample.get("marker_cross_check_mean_mm") is not None
    ]
    marker_cross_max_values = [
        float(sample["marker_cross_check_max_mm"])
        for sample in stable_samples
        if sample.get("marker_cross_check_max_mm") is not None
    ]
    marker_cross_mean = (
        float(np.median(marker_cross_values)) if marker_cross_values else None
    )
    marker_cross_max = (
        float(np.max(marker_cross_max_values)) if marker_cross_max_values else None
    )
    representative = min(
        stable_samples,
        key=lambda sample: np.linalg.norm(
            np.asarray(
                sample["measured_camera_mount"]["translation_mm"],
                dtype=np.float64,
            )
            - median_translation
        ),
    )
    result["markers_detected"] = representative.get("markers_detected", [])
    result["marker_validation"] = representative.get("marker_validation", [])
    result["transforms"] = representative.get("transforms", {})
    configured_transform = transform_from_mount(config["camera_mount"])
    prior_translation_offset = float(
        np.linalg.norm(median_translation - configured_transform[:3, 3])
    )
    prior_rotation_offset = rotation_error_deg(
        configured_transform,
        averaged_transform,
    )
    quality.update(
        {
            "reprojection_mean_px": round(reprojection_mean, 3),
            "reprojection_max_px": round(reprojection_max, 3),
            "mount_translation_stability_mm": round(translation_stability, 3),
            "mount_rotation_stability_deg": round(rotation_stability, 3),
            "prior_translation_offset_mm": round(prior_translation_offset, 3),
            "prior_rotation_offset_deg": round(prior_rotation_offset, 3),
            "marker_cross_check_mean_mm": (
                round(marker_cross_mean, 3) if marker_cross_mean is not None else None
            ),
            "marker_cross_check_max_mm": (
                round(marker_cross_max, 3) if marker_cross_max is not None else None
            ),
        }
    )
    measured_mount = {
        "translation_mm": [
            round(float(value), 6) for value in median_translation.tolist()
        ],
        "rotation_rpy_deg": matrix_to_rpy_deg(averaged_rotation),
        "transform_direction": "T_tcp_camera",
        "parent_frame": "tcp",
        "child_frame": "camera_optical",
        "rpy_convention": RPY_CONVENTION,
    }
    candidate_config = normalize_eye_in_hand_config(config)
    candidate_config["camera_mount"]["translation_mm"] = measured_mount[
        "translation_mm"
    ]
    candidate_config["camera_mount"]["rotation_rpy_deg"] = measured_mount[
        "rotation_rpy_deg"
    ]
    look_down = look_down_status(tcp_pose, candidate_config)

    warnings = []
    max_reprojection = float(aruco["max_reprojection_error_px"])
    if reprojection_mean > max_reprojection:
        warnings.append(f"mean reprojection error is {reprojection_mean:.2f}px")
    if reprojection_max > max_reprojection * 1.5:
        warnings.append(f"maximum reprojection error is {reprojection_max:.2f}px")
    if marker_cross_mean is None or marker_cross_max is None:
        warnings.append("marker leave-one-out cross-check is unavailable")
    else:
        if marker_cross_mean > float(aruco["max_marker_cross_check_mean_mm"]):
            warnings.append(
                f"marker cross-check mean error is {marker_cross_mean:.2f}mm"
            )
        if marker_cross_max > float(aruco["max_marker_cross_check_max_mm"]):
            warnings.append(
                f"marker cross-check maximum error is {marker_cross_max:.2f}mm"
            )
    if translation_stability > float(
        aruco["max_mount_stability_translation_mm"]
    ):
        warnings.append(
            f"camera mount varies by {translation_stability:.2f}mm between frames"
        )
    if rotation_stability > float(aruco["max_mount_stability_rotation_deg"]):
        warnings.append(
            f"camera mount varies by {rotation_stability:.2f}deg between frames"
        )
    mount_distance = float(np.linalg.norm(median_translation))
    if mount_distance > float(aruco["max_camera_mount_distance_mm"]):
        warnings.append(f"camera mount distance {mount_distance:.2f}mm is implausible")
    if not look_down.get("ok", False):
        warnings.append(look_down.get("warning") or "camera is not looking down")

    valid = not warnings
    result.update(
        {
            "ok": valid,
            "calibration_valid": valid,
            "measured_camera_mount": measured_mount,
            "look_down": look_down,
            "warning": "; ".join(warnings),
        }
    )
    return result


class CameraIntrinsicsStore:
    def __init__(self, config_path: str = ""):
        self.path = resolve_camera_intrinsics_path(config_path)

    def load(self) -> Dict[str, Any]:
        data = default_camera_intrinsics()
        data.update(normalize_intrinsics(_load_yaml(self.path) or {}))
        return data

    def status(self) -> Dict[str, Any]:
        data = self.load()
        data["config_path"] = str(self.path)
        return data

    def save(self, intrinsics: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_intrinsics(intrinsics)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(
                {"camera_intrinsics": normalized},
                stream,
                sort_keys=False,
            )
        return normalized


class EyeInHandConfigStore:
    def __init__(self, config_path: str = ""):
        self.path = resolve_eye_in_hand_config_path(config_path)
        self._attempt_lock = threading.Lock()
        self._last_auto_attempt = None

    def load(self) -> Dict[str, Any]:
        data = default_eye_in_hand_config()
        loaded = _load_yaml(self.path)
        data.update(loaded)
        aruco = data.get("aruco", {}) or {}
        legacy_keys = ("dictionary", "marker_length_mm", "required_ids", "markers")
        if isinstance(aruco, dict) and "board" not in aruco and not any(
            key in aruco for key in legacy_keys
        ):
            aruco = dict(aruco)
            try:
                aruco["board"] = load_aruco_board(
                    aruco.get("board_config_path", "")
                )
            except ValueError as exc:
                raise EyeInHandError(str(exc)) from exc
            data["aruco"] = aruco
        return normalize_eye_in_hand_config(data)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_eye_in_hand_config(data)
        persisted = deepcopy(normalized)
        persisted["aruco"].pop("board", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(persisted, stream, sort_keys=False)
        return normalized

    def status(
        self,
        tcp_pose: Optional[Sequence[float]] = None,
        intrinsics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = self.load()
        validation = data.get("validation", {}) or {}
        warning = validation.get("warning", "")
        auto_position = data.get("auto_position", {}) or {}
        auto_position_enabled = bool(auto_position.get("enabled", False))
        calibration_valid = bool(data.get("calibration_valid", False))
        position_available = calibration_valid or auto_position_enabled
        data["config_path"] = str(self.path)
        data["is_complete"] = calibration_valid and not warning
        data["calibration_valid"] = calibration_valid
        data["auto_position_enabled"] = auto_position_enabled
        data["position_available"] = position_available
        data["can_estimate_position"] = position_available
        data["position_estimate"] = bool(position_available and not calibration_valid)
        data["position_source"] = (
            "aruco_calibration"
            if calibration_valid
            else "configured_mount_estimate"
            if auto_position_enabled
            else "unavailable"
        )
        if tcp_pose is not None:
            data["tcp_pose"] = normalize_tcp_pose(tcp_pose)
            data["look_down"] = look_down_status(tcp_pose, data)
        else:
            data["tcp_pose"] = None
            data["look_down"] = look_down_status(None, data)
        if intrinsics is not None:
            data["intrinsics"] = normalize_intrinsics(intrinsics)
        with self._attempt_lock:
            data["last_auto_attempt"] = self._last_auto_attempt
        return data

    def auto_calibrate_from_frames(
        self,
        frames: Sequence[np.ndarray],
        tcp_pose: Sequence[float],
        intrinsics: Dict[str, Any],
    ) -> Dict[str, Any]:
        if len(frames) < 8:
            raise EyeInHandError("At least 8 fresh camera frames are required")
        config = self.load()
        samples = []
        for frame in frames:
            try:
                samples.append(
                    calibrate_from_frame(
                        frame,
                        tcp_pose,
                        config,
                        intrinsics,
                        update_mount=False,
                    )
                )
            except EyeInHandError as exc:
                samples.append(
                    {
                        "ok": False,
                        "calibration_valid": False,
                        "warning": str(exc),
                    }
                )

        previous_status = self.status(tcp_pose=tcp_pose, intrinsics=intrinsics)
        attempt = aggregate_eye_in_hand_calibration(samples, config, tcp_pose)
        attempt["attempted_at"] = _utc_now_iso()
        attempt["previous_calibration_preserved"] = bool(
            previous_status.get("is_complete", False)
            and not attempt["calibration_valid"]
        )
        with self._attempt_lock:
            self._last_auto_attempt = attempt

        if attempt["calibration_valid"]:
            calibrated_at = _utc_now_iso()
            config["camera_mount"] = attempt["measured_camera_mount"]
            config["calibration_valid"] = True
            config["calibrated_at"] = calibrated_at
            config["validation"] = {
                "calibration_valid": True,
                "source": attempt["source"],
                "detected_ids": attempt["detected_ids"],
                "used_ids": attempt["detected_ids"],
                "missing_ids": attempt["missing_ids"],
                "markers_detected": attempt["markers_detected"],
                "reprojection_error_px": attempt["quality"][
                    "reprojection_mean_px"
                ],
                "mount_translation_error_mm": attempt["quality"][
                    "prior_translation_offset_mm"
                ],
                "mount_rotation_error_deg": attempt["quality"][
                    "prior_rotation_offset_deg"
                ],
                "measured_camera_mount": attempt["measured_camera_mount"],
                "updated_camera_mount": True,
                "look_down": attempt["look_down"],
                "quality": attempt["quality"],
                "dictionary": attempt["dictionary"],
                "required_ids": attempt["required_ids"],
                "board": attempt["board"],
                "board_coordinate_convention": attempt[
                    "board_coordinate_convention"
                ],
                "marker_validation": attempt["marker_validation"],
                "transforms": attempt["transforms"],
                "frame_diagnostics": attempt["frame_diagnostics"],
                "warning": "",
            }
            self.save(config)

        status = self.status(tcp_pose=tcp_pose, intrinsics=intrinsics)
        status["dry_run"] = True
        status["calibration_attempt"] = attempt
        return status

    def save_calibration_result(self, calibration: Dict[str, Any]) -> Dict[str, Any]:
        data = calibration.get("config") or self.load()
        # Estimated marker positions are visualization hints only.  The shared
        # board definition is authoritative and may not be learned from the
        # same camera mount estimate that calibration is trying to solve.
        created_marker_ids = []
        calibration["created_marker_ids"] = created_marker_ids
        calibration["estimated_markers_used_for_calibration"] = False

        validation = {
            "calibration_valid": bool(calibration.get("calibration_valid", False)),
            "detected_ids": calibration.get("detected_ids", []),
            "used_ids": calibration.get("used_ids", []),
            "missing_ids": calibration.get("missing_ids", []),
            "markers_detected": calibration.get("markers_detected", []),
            "suggested_markers": calibration.get("suggested_markers", {}),
            "created_marker_ids": created_marker_ids,
            "reprojection_error_px": calibration.get("reprojection_error_px"),
            "mount_translation_error_mm": calibration.get("mount_translation_error_mm"),
            "mount_rotation_error_deg": calibration.get("mount_rotation_error_deg"),
            "measured_camera_mount": calibration.get("measured_camera_mount"),
            "updated_camera_mount": bool(calibration.get("updated_camera_mount", False)),
            "look_down": calibration.get("look_down", {}),
            "warning": calibration.get("warning", ""),
        }
        data["calibration_valid"] = bool(calibration.get("calibration_valid", False))
        data["calibrated_at"] = _utc_now_iso()
        data["validation"] = validation
        return self.save(data)

    def calibrate_from_frame(
        self,
        frame: np.ndarray,
        tcp_pose: Sequence[float],
        intrinsics: Dict[str, Any],
        update_mount: Optional[bool] = None,
        save_detected_markers: bool = False,
    ) -> Dict[str, Any]:
        started = time.monotonic()
        previous_status = self.status(tcp_pose=tcp_pose, intrinsics=intrinsics)
        calibration = calibrate_from_frame(
            frame,
            tcp_pose,
            self.load(),
            intrinsics,
            update_mount=update_mount,
        )
        calibration["save_detected_markers"] = bool(save_detected_markers)
        calibration["previous_calibration_preserved"] = bool(
            previous_status.get("is_complete", False)
            and not calibration.get("calibration_valid", False)
        )
        saved = (
            self.save_calibration_result(calibration)
            if calibration.get("calibration_valid", False)
            else self.load()
        )
        status = self.status(tcp_pose=tcp_pose, intrinsics=intrinsics)
        status["calibration"] = calibration
        status["elapsed_sec"] = round(time.monotonic() - started, 3)
        status["saved_config"] = saved
        return status

    def test_pixel(
        self,
        center_pixel: Sequence[float],
        tcp_pose: Sequence[float],
        intrinsics: Dict[str, Any],
        workspace: Any = None,
    ) -> Dict[str, Any]:
        return pixel_to_robot_xy(
            center_pixel,
            tcp_pose,
            intrinsics,
            self.load(),
            workspace=workspace,
            require_calibration=True,
        )
