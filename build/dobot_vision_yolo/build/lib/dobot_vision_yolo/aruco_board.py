"""Shared ArUco board geometry and transform conventions.

All calibration paths use this module so marker generation, detection, fixed
camera homography, and eye-in-hand PnP cannot silently disagree about marker
IDs or corner ordering.
"""

from copy import deepcopy
import math
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import yaml

try:
    from ament_index_python.packages import PackageNotFoundError
    from ament_index_python.packages import get_package_share_directory
except ImportError:  # pragma: no cover - available in the ROS runtime
    PackageNotFoundError = LookupError
    get_package_share_directory = None


PACKAGE_NAME = "dobot_vision_yolo"
DEFAULT_DICTIONARY = "DICT_4X4_50"
DEFAULT_REQUIRED_IDS = [0, 1, 2, 3]
DEFAULT_MARKER_LENGTH_MM = 30.0
DEFAULT_BOARD_WIDTH_MM = 80.0
DEFAULT_BOARD_HEIGHT_MM = 160.0
OPENCV_CORNER_ORDER = [
    "top_left",
    "top_right",
    "bottom_right",
    "bottom_left",
]
RPY_CONVENTION = (
    "column_vectors; R=Rz(yaw)*Ry(pitch)*Rx(roll); "
    "intrinsic XYZ (equivalent extrinsic ZYX)"
)


def default_aruco_board() -> Dict[str, Any]:
    """Return the canonical 80 x 160 mm board in a board-local frame."""
    return {
        "dictionary": DEFAULT_DICTIONARY,
        "required_ids": list(DEFAULT_REQUIRED_IDS),
        "marker_length_mm": DEFAULT_MARKER_LENGTH_MM,
        "coordinate_frame": "aruco_board",
        "corner_order": list(OPENCV_CORNER_ORDER),
        "width_mm": DEFAULT_BOARD_WIDTH_MM,
        "height_mm": DEFAULT_BOARD_HEIGHT_MM,
        "markers": {
            "0": {"center_mm": [-40.0, -80.0, 0.0], "yaw_deg": 0.0},
            "1": {"center_mm": [40.0, -80.0, 0.0], "yaw_deg": 0.0},
            "2": {"center_mm": [40.0, 80.0, 0.0], "yaw_deg": 0.0},
            "3": {"center_mm": [-40.0, 80.0, 0.0], "yaw_deg": 0.0},
        },
        "pose_base": {
            "anchored": True,
            "translation_mm": [220.0, 0.0, -35.0],
            "rotation_rpy_deg": [0.0, 0.0, 0.0],
            "source": "configured_fixture",
            "parent_frame": "dobot_base",
            "child_frame": "aruco_board",
        },
    }


def _numeric_list(value: Any, name: str, count: int):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f"{name} must contain {count} numeric values")
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numeric values") from exc
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain finite values")
    return result


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
    raise ValueError(f"{name} must be boolean")


def rotation_x(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rotation_y(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rotation_z(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def rpy_matrix(rpy_deg: Sequence[float]) -> np.ndarray:
    """Build a rotation using the explicit convention in ``RPY_CONVENTION``."""
    roll, pitch, yaw = [math.radians(float(item)) for item in rpy_deg]
    return rotation_z(yaw) @ rotation_y(pitch) @ rotation_x(roll)


def matrix_to_rpy_deg(rotation: np.ndarray):
    rotation = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    sy = math.sqrt(rotation[0, 0] ** 2 + rotation[1, 0] ** 2)
    if sy < 1e-9:
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
    transform[:3, :3] = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    transform[:3, 3] = _numeric_list(translation_mm, "translation_mm", 3)
    return transform


def transform_from_pose(pose: Mapping[str, Any]) -> np.ndarray:
    return make_transform(
        rpy_matrix(_numeric_list(pose.get("rotation_rpy_deg"), "rotation_rpy_deg", 3)),
        _numeric_list(pose.get("translation_mm"), "translation_mm", 3),
    )


def transform_summary(
    transform: np.ndarray,
    parent_frame: str,
    child_frame: str,
) -> Dict[str, Any]:
    matrix = np.asarray(transform, dtype=np.float64).reshape(4, 4)
    return {
        "name": f"T_{parent_frame}_{child_frame}",
        "parent_frame": parent_frame,
        "child_frame": child_frame,
        "translation_mm": [round(float(value), 6) for value in matrix[:3, 3]],
        "rotation_rpy_deg": matrix_to_rpy_deg(matrix[:3, :3]),
        "rpy_convention": RPY_CONVENTION,
        "matrix_row_major": [round(float(value), 10) for value in matrix.reshape(-1)],
    }


def marker_corners_board(marker: Mapping[str, Any], marker_length_mm: float) -> np.ndarray:
    """Return corners in OpenCV's canonical TL, TR, BR, BL order.

    The board frame is right-handed: +X points from marker 0 to 1, +Y points
    from marker 0 to 3, and +Z is the board face normal.  Consequently +Y is
    upward on the printable board even though SVG/image pixel Y points down.
    OpenCV's canonical marker top corners therefore have positive board Y.
    """
    center = np.asarray(
        _numeric_list(marker.get("center_mm"), "marker.center_mm", 3),
        dtype=np.float64,
    )
    yaw = math.radians(float(marker.get("yaw_deg", 0.0)))
    half = float(marker_length_mm) / 2.0
    local = np.array(
        [
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ],
        dtype=np.float64,
    )
    return (rotation_z(yaw) @ local.T).T + center


def marker_transform_board(marker: Mapping[str, Any]) -> np.ndarray:
    center = _numeric_list(marker.get("center_mm"), "marker.center_mm", 3)
    yaw = math.radians(float(marker.get("yaw_deg", 0.0)))
    return make_transform(rotation_z(yaw), center)


def board_geometry(board: Mapping[str, Any]) -> Dict[str, Any]:
    markers = board["markers"]
    centers = {
        marker_id: np.asarray(markers[str(marker_id)]["center_mm"], dtype=np.float64)
        for marker_id in board["required_ids"]
    }
    zero, one, two, three = [centers[index] for index in DEFAULT_REQUIRED_IDS]
    widths = [np.linalg.norm(one - zero), np.linalg.norm(two - three)]
    heights = [np.linalg.norm(three - zero), np.linalg.norm(two - one)]
    return {
        "width_mm": round(float(np.mean(widths)), 6),
        "height_mm": round(float(np.mean(heights)), 6),
        "width_edges_mm": [round(float(value), 6) for value in widths],
        "height_edges_mm": [round(float(value), 6) for value in heights],
        "aspect_ratio_width_over_height": round(
            float(np.mean(widths) / np.mean(heights)), 6
        ),
        "id_layout": {
            "top_left": 3,
            "top_right": 2,
            "bottom_right": 1,
            "bottom_left": 0,
        },
        "axis_convention": (
            "+X: ID0->ID1, +Y: ID0->ID3 (up on print), +Z: board face normal"
        ),
    }


def normalize_aruco_board(value: Any) -> Dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("aruco board configuration must be an object")
    board = default_aruco_board()
    board.update(deepcopy(value))
    board["dictionary"] = str(board.get("dictionary", DEFAULT_DICTIONARY))
    board["required_ids"] = [int(item) for item in board.get("required_ids", [])]
    if board["required_ids"] != DEFAULT_REQUIRED_IDS:
        raise ValueError("ArUco board required_ids must be [0, 1, 2, 3]")
    board["marker_length_mm"] = float(board.get("marker_length_mm", 0.0))
    board["width_mm"] = float(board.get("width_mm", 0.0))
    board["height_mm"] = float(board.get("height_mm", 0.0))
    if min(board["marker_length_mm"], board["width_mm"], board["height_mm"]) <= 0.0:
        raise ValueError("ArUco board dimensions must be positive")
    board["coordinate_frame"] = str(board.get("coordinate_frame", "aruco_board"))
    if board["coordinate_frame"] != "aruco_board":
        raise ValueError("ArUco marker centers must use the board-local aruco_board frame")
    board["corner_order"] = list(board.get("corner_order", OPENCV_CORNER_ORDER))
    if board["corner_order"] != OPENCV_CORNER_ORDER:
        raise ValueError("ArUco corner_order must be top_left, top_right, bottom_right, bottom_left")

    raw_markers = board.get("markers", {}) or {}
    markers = {}
    for marker_id in board["required_ids"]:
        raw = raw_markers.get(str(marker_id), raw_markers.get(marker_id))
        if not isinstance(raw, dict):
            raise ValueError(f"ArUco board marker {marker_id} is missing")
        markers[str(marker_id)] = {
            "center_mm": _numeric_list(
                raw.get("center_mm"), f"markers.{marker_id}.center_mm", 3
            ),
            "yaw_deg": float(raw.get("yaw_deg", 0.0)),
        }
    board["markers"] = markers

    default_pose = default_aruco_board()["pose_base"]
    raw_pose = board.get("pose_base", {}) or {}
    pose = dict(default_pose)
    pose.update(raw_pose)
    pose["anchored"] = _as_bool(pose.get("anchored", False), "pose_base.anchored")
    pose["translation_mm"] = _numeric_list(
        pose.get("translation_mm"), "pose_base.translation_mm", 3
    )
    pose["rotation_rpy_deg"] = _numeric_list(
        pose.get("rotation_rpy_deg"), "pose_base.rotation_rpy_deg", 3
    )
    pose["source"] = str(pose.get("source", ""))
    pose["parent_frame"] = "dobot_base"
    pose["child_frame"] = "aruco_board"
    board["pose_base"] = pose

    geometry = board_geometry(board)
    if abs(geometry["width_mm"] - board["width_mm"]) > 1e-6:
        raise ValueError("ArUco marker geometry does not match board width_mm")
    if abs(geometry["height_mm"] - board["height_mm"]) > 1e-6:
        raise ValueError("ArUco marker geometry does not match board height_mm")
    board["geometry"] = geometry
    return board


def resolve_aruco_board_config_path(config_path: str = "") -> Path:
    if config_path:
        return Path(config_path).expanduser()
    env_path = os.environ.get("DOBOT_ARUCO_BOARD_PATH", "")
    if env_path:
        return Path(env_path).expanduser()
    candidates = [
        Path.cwd() / "src" / "magician_ros2" / PACKAGE_NAME / "config" / "aruco_board.yaml",
        Path(__file__).resolve().parents[1] / "config" / "aruco_board.yaml",
    ]
    if get_package_share_directory is not None:
        try:
            candidates.append(
                Path(get_package_share_directory(PACKAGE_NAME))
                / "config"
                / "aruco_board.yaml"
            )
        except PackageNotFoundError:
            pass
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_aruco_board(config_path: str = "") -> Dict[str, Any]:
    path = resolve_aruco_board_config_path(config_path)
    if not path.exists():
        return normalize_aruco_board({})
    with path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream) or {}
    return normalize_aruco_board(raw.get("aruco_board", raw))


def aruco_dictionary(cv2_module, dictionary_name: str):
    if cv2_module is None or not hasattr(cv2_module, "aruco"):
        raise ValueError("OpenCV ArUco support is unavailable")
    dictionary_id = getattr(cv2_module.aruco, str(dictionary_name), None)
    if dictionary_id is None:
        raise ValueError(f"Unknown ArUco dictionary '{dictionary_name}'")
    return cv2_module.aruco.getPredefinedDictionary(dictionary_id)


def detect_markers(cv2_module, frame: np.ndarray, dictionary_name: str) -> Dict[str, Any]:
    """Detect and manually sub-pixel refine corners on legacy OpenCV 4.6."""
    if frame is None:
        raise ValueError("Camera frame is unavailable")
    dictionary = aruco_dictionary(cv2_module, dictionary_name)
    gray = (
        cv2_module.cvtColor(frame, cv2_module.COLOR_BGR2GRAY)
        if frame.ndim == 3
        else frame
    )
    if hasattr(cv2_module.aruco, "ArucoDetector"):
        parameters = cv2_module.aruco.DetectorParameters()
        if hasattr(cv2_module.aruco, "CORNER_REFINE_SUBPIX"):
            parameters.cornerRefinementMethod = cv2_module.aruco.CORNER_REFINE_SUBPIX
        detector = cv2_module.aruco.ArucoDetector(dictionary, parameters)
        corners, ids, rejected = detector.detectMarkers(gray)
    else:  # OpenCV 4.6 on the deployed machine
        # Passing DetectorParameters to this binding has caused native crashes.
        corners, ids, rejected = cv2_module.aruco.detectMarkers(gray, dictionary)
        if ids is not None and hasattr(cv2_module, "cornerSubPix"):
            criteria = (
                cv2_module.TERM_CRITERIA_EPS + cv2_module.TERM_CRITERIA_MAX_ITER,
                30,
                0.01,
            )
            refined = []
            for marker_corners in corners:
                points = np.asarray(marker_corners, dtype=np.float32).reshape(-1, 1, 2)
                cv2_module.cornerSubPix(gray, points, (3, 3), (-1, -1), criteria)
                refined.append(points.reshape(1, 4, 2))
            corners = refined

    detected_ids = [] if ids is None else [int(item[0]) for item in ids]
    marker_map = {
        marker_id: np.asarray(marker_corners, dtype=np.float64).reshape(4, 2)
        for marker_id, marker_corners in zip(detected_ids, corners or [])
    }
    marker_diagnostics = []
    for marker_id in detected_ids:
        points = marker_map[marker_id]
        sides = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
        area = abs(float(cv2_module.contourArea(points.astype(np.float32))))
        center = np.mean(points, axis=0)
        marker_diagnostics.append(
            {
                "id": marker_id,
                "corners_pixel": [
                    [round(float(value), 3) for value in point] for point in points
                ],
                "center_pixel": [round(float(value), 3) for value in center],
                "area_px2": round(area, 3),
                "side_lengths_px": [round(float(value), 3) for value in sides],
                "side_ratio_min_over_max": round(
                    float(np.min(sides) / np.max(sides)) if np.max(sides) > 0.0 else 0.0,
                    4,
                ),
                "quality_type": "corner_geometry_not_detector_confidence",
            }
        )
    blur_score = None
    if hasattr(cv2_module, "Laplacian") and hasattr(cv2_module, "CV_64F"):
        blur_score = round(
            float(cv2_module.Laplacian(gray, cv2_module.CV_64F).var()),
            3,
        )
    return {
        "markers": marker_map,
        "corners": list(corners or []),
        "ids": detected_ids,
        "detected_ids": detected_ids,
        "rejected": list(rejected or []),
        "diagnostics": {
            "dictionary": str(dictionary_name),
            "detected_ids": detected_ids,
            "missing_ids": [],
            "rejected_marker_count": len(rejected or []),
            "blur_laplacian_variance": blur_score,
            "image_resolution": {
                "width": int(gray.shape[1]),
                "height": int(gray.shape[0]),
            },
            "markers": marker_diagnostics,
        },
    }
