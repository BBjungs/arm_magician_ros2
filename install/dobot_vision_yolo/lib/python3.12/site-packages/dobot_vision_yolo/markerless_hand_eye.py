"""Markerless RGB-D hand-eye calibration primitives.

This module deliberately contains no robot command code.  Callers must collect
synchronised RGB, registered depth, CameraInfo and TCP poses through the guarded
motion path, then pass the observations here.  A result is only marked valid
when depth, feature matching, robot-motion observability and AX=XB residual
checks all pass.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

import cv2
import numpy as np

from dobot_vision_yolo.eye_in_hand_transform import (
    make_transform,
    matrix_to_rpy_deg,
    normalize_intrinsics,
    rotation_error_deg,
)


class MarkerlessCalibrationError(ValueError):
    """Raised when an RGB-D observation cannot safely be used."""


@dataclass(frozen=True)
class MarkerlessThresholds:
    min_depth_mm: float = 150.0
    max_depth_mm: float = 2000.0
    min_depth_valid_ratio: float = 0.05
    min_pair_matches: int = 40
    min_pair_inliers: int = 24
    min_pair_inlier_ratio: float = 0.45
    max_pair_residual_mm: float = 6.0
    min_translation_span_mm: float = 35.0
    min_rotation_span_deg: float = 12.0
    min_rotation_axis_rank: int = 2
    max_hand_eye_translation_residual_mm: float = 8.0
    max_hand_eye_rotation_residual_deg: float = 3.0


def _as_transform(value: Any, name: str) -> np.ndarray:
    transform = np.asarray(value, dtype=np.float64)
    if transform.shape != (4, 4) or not np.all(np.isfinite(transform)):
        raise MarkerlessCalibrationError(f"{name} must be a finite 4x4 transform")
    if not np.allclose(transform[3], [0.0, 0.0, 0.0, 1.0], atol=1e-6):
        raise MarkerlessCalibrationError(f"{name} has an invalid homogeneous row")
    rotation = transform[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-4):
        raise MarkerlessCalibrationError(f"{name} rotation is not orthonormal")
    if float(np.linalg.det(rotation)) < 0.999:
        raise MarkerlessCalibrationError(f"{name} rotation is not right-handed")
    return transform


def depth_health(
    depth_mm: np.ndarray,
    thresholds: MarkerlessThresholds = MarkerlessThresholds(),
) -> Dict[str, Any]:
    depth = np.asarray(depth_mm)
    if depth.ndim != 2:
        raise MarkerlessCalibrationError("registered depth must be a 2-D image")
    finite = np.isfinite(depth)
    valid = finite & (depth >= thresholds.min_depth_mm) & (
        depth <= thresholds.max_depth_mm
    )
    ratio = float(np.count_nonzero(valid)) / float(max(depth.size, 1))
    return {
        "ok": ratio >= thresholds.min_depth_valid_ratio,
        "valid_ratio": round(ratio, 6),
        "valid_count": int(np.count_nonzero(valid)),
        "pixel_count": int(depth.size),
        "minimum_required_ratio": thresholds.min_depth_valid_ratio,
        "reason": "" if ratio >= thresholds.min_depth_valid_ratio else "invalid_depth",
    }


def _points_from_registered_depth(
    pixels: np.ndarray,
    depth_mm: np.ndarray,
    intrinsics: Dict[str, Any],
    thresholds: MarkerlessThresholds,
) -> Tuple[np.ndarray, np.ndarray]:
    intrinsics = normalize_intrinsics(intrinsics)
    pixels = np.asarray(pixels, dtype=np.float64).reshape(-1, 2)
    rounded = np.rint(pixels).astype(np.int64)
    height, width = depth_mm.shape
    inside = (
        (rounded[:, 0] >= 0)
        & (rounded[:, 0] < width)
        & (rounded[:, 1] >= 0)
        & (rounded[:, 1] < height)
    )
    depths = np.zeros(len(pixels), dtype=np.float64)
    depths[inside] = depth_mm[rounded[inside, 1], rounded[inside, 0]]
    valid = (
        inside
        & np.isfinite(depths)
        & (depths >= thresholds.min_depth_mm)
        & (depths <= thresholds.max_depth_mm)
    )
    z = depths[valid]
    u = pixels[valid, 0]
    v = pixels[valid, 1]
    points = np.column_stack(
        (
            (u - intrinsics["cx"]) * z / intrinsics["fx"],
            (v - intrinsics["cy"]) * z / intrinsics["fy"],
            z,
        )
    )
    return points, valid


def rigid_transform(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return the least-squares transform mapping source points to target."""
    source = np.asarray(source, dtype=np.float64).reshape(-1, 3)
    target = np.asarray(target, dtype=np.float64).reshape(-1, 3)
    if len(source) != len(target) or len(source) < 3:
        raise MarkerlessCalibrationError("at least 3 paired 3-D points are required")
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    left, _values, right = np.linalg.svd(covariance)
    rotation = right.T @ left.T
    if np.linalg.det(rotation) < 0.0:
        right[-1, :] *= -1.0
        rotation = right.T @ left.T
    translation = target_center - rotation @ source_center
    return make_transform(rotation, translation)


def estimate_rgbd_motion(
    first_rgb: np.ndarray,
    first_depth_mm: np.ndarray,
    second_rgb: np.ndarray,
    second_depth_mm: np.ndarray,
    intrinsics: Dict[str, Any],
    thresholds: MarkerlessThresholds = MarkerlessThresholds(),
    random_seed: int = 0,
) -> Dict[str, Any]:
    """Estimate ``second_camera_T_first_camera`` from natural RGB-D features."""
    first_health = depth_health(first_depth_mm, thresholds)
    second_health = depth_health(second_depth_mm, thresholds)
    if not first_health["ok"] or not second_health["ok"]:
        raise MarkerlessCalibrationError("invalid_depth")
    if first_rgb.shape[:2] != first_depth_mm.shape:
        raise MarkerlessCalibrationError("first RGB/depth images are not registered")
    if second_rgb.shape[:2] != second_depth_mm.shape:
        raise MarkerlessCalibrationError("second RGB/depth images are not registered")

    def gray(image):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    detector = cv2.ORB_create(nfeatures=1800, fastThreshold=10)
    first_keypoints, first_descriptors = detector.detectAndCompute(gray(first_rgb), None)
    second_keypoints, second_descriptors = detector.detectAndCompute(gray(second_rgb), None)
    if first_descriptors is None or second_descriptors is None:
        raise MarkerlessCalibrationError("insufficient_rgb_features")
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(
        first_descriptors, second_descriptors, k=2
    )
    matches = [
        pair[0]
        for pair in pairs
        if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
    ]
    if len(matches) < thresholds.min_pair_matches:
        raise MarkerlessCalibrationError(
            f"insufficient_feature_matches:{len(matches)}<{thresholds.min_pair_matches}"
        )
    first_pixels = np.array([first_keypoints[m.queryIdx].pt for m in matches])
    second_pixels = np.array([second_keypoints[m.trainIdx].pt for m in matches])
    _first_points, first_valid = _points_from_registered_depth(
        first_pixels, first_depth_mm, intrinsics, thresholds
    )
    _second_points, second_valid = _points_from_registered_depth(
        second_pixels, second_depth_mm, intrinsics, thresholds
    )
    both_valid = first_valid & second_valid
    source, _ = _points_from_registered_depth(
        first_pixels[both_valid], first_depth_mm, intrinsics, thresholds
    )
    target, _ = _points_from_registered_depth(
        second_pixels[both_valid], second_depth_mm, intrinsics, thresholds
    )
    if len(source) < thresholds.min_pair_inliers:
        raise MarkerlessCalibrationError("insufficient_matches_with_valid_depth")

    rng = np.random.default_rng(random_seed)
    best_mask = np.zeros(len(source), dtype=bool)
    for _ in range(250):
        indices = rng.choice(len(source), size=3, replace=False)
        try:
            candidate = rigid_transform(source[indices], target[indices])
        except MarkerlessCalibrationError:
            continue
        predicted = (candidate[:3, :3] @ source.T).T + candidate[:3, 3]
        residuals = np.linalg.norm(predicted - target, axis=1)
        mask = residuals <= thresholds.max_pair_residual_mm
        if np.count_nonzero(mask) > np.count_nonzero(best_mask):
            best_mask = mask
    inlier_count = int(np.count_nonzero(best_mask))
    inlier_ratio = float(inlier_count) / float(len(source))
    if inlier_count < thresholds.min_pair_inliers or inlier_ratio < thresholds.min_pair_inlier_ratio:
        raise MarkerlessCalibrationError("rgbd_registration_quality_below_threshold")
    transform = rigid_transform(source[best_mask], target[best_mask])
    predicted = (transform[:3, :3] @ source[best_mask].T).T + transform[:3, 3]
    residuals = np.linalg.norm(predicted - target[best_mask], axis=1)
    return {
        "transform": transform,
        "match_count": len(matches),
        "depth_match_count": len(source),
        "inlier_count": inlier_count,
        "inlier_ratio": round(inlier_ratio, 6),
        "residual_mean_mm": round(float(np.mean(residuals)), 6),
        "residual_max_mm": round(float(np.max(residuals)), 6),
        "depth_health": [first_health, second_health],
    }


def _rotation_vector(transform: np.ndarray) -> np.ndarray:
    vector, _ = cv2.Rodrigues(transform[:3, :3])
    return vector.reshape(3)


def motion_observability(
    gripper2base: Sequence[np.ndarray],
) -> Dict[str, Any]:
    poses = [_as_transform(value, f"gripper2base[{index}]") for index, value in enumerate(gripper2base)]
    if len(poses) < 4:
        raise MarkerlessCalibrationError("at least 4 robot poses are required")
    translations = np.stack([pose[:3, 3] for pose in poses])
    centered = translations - np.mean(translations, axis=0)
    translation_rank = int(np.linalg.matrix_rank(centered, tol=1e-3))
    translation_span = float(np.max(np.linalg.norm(centered, axis=1)) * 2.0)
    axes = []
    angles = []
    for first, second in zip(poses, poses[1:]):
        vector = _rotation_vector(np.linalg.inv(second) @ first)
        angle = float(np.linalg.norm(vector))
        if angle > math.radians(0.5):
            axes.append(vector / angle)
            angles.append(math.degrees(angle))
    axis_rank = int(np.linalg.matrix_rank(np.asarray(axes), tol=1e-3)) if axes else 0
    return {
        "translation_rank": translation_rank,
        "translation_span_mm": round(translation_span, 6),
        "rotation_axis_rank": axis_rank,
        "rotation_span_deg": round(float(sum(angles)), 6),
    }


def solve_hand_eye(
    gripper2base: Sequence[np.ndarray],
    target2camera: Sequence[np.ndarray],
    thresholds: MarkerlessThresholds = MarkerlessThresholds(),
) -> Dict[str, Any]:
    """Solve and validate camera-to-tool from absolute robot/camera poses."""
    robot = [_as_transform(value, f"gripper2base[{i}]") for i, value in enumerate(gripper2base)]
    camera = [_as_transform(value, f"target2camera[{i}]") for i, value in enumerate(target2camera)]
    if len(robot) != len(camera) or len(robot) < 4:
        raise MarkerlessCalibrationError("matching sets of at least 4 poses are required")
    observable = motion_observability(robot)
    reasons = []
    if observable["translation_span_mm"] < thresholds.min_translation_span_mm:
        reasons.append("robot_translation_span_too_small")
    if observable["rotation_span_deg"] < thresholds.min_rotation_span_deg:
        reasons.append("robot_rotation_span_too_small")
    if observable["rotation_axis_rank"] < thresholds.min_rotation_axis_rank:
        reasons.append("robot_rotation_axes_are_degenerate")
    if reasons:
        return {
            "ok": False,
            "calibration_valid": False,
            "source": "markerless_rgbd_hand_eye",
            "observability": observable,
            "validation_errors": reasons,
            "warning": "; ".join(reasons),
        }

    rotation, translation = cv2.calibrateHandEye(
        [pose[:3, :3] for pose in robot],
        [pose[:3, 3] for pose in robot],
        [pose[:3, :3] for pose in camera],
        [pose[:3, 3] for pose in camera],
        method=cv2.CALIB_HAND_EYE_DANIILIDIS,
    )
    tool_camera = make_transform(rotation, np.asarray(translation).reshape(3))
    translation_residuals = []
    rotation_residuals = []
    for index in range(len(robot) - 1):
        a_motion = np.linalg.inv(robot[index + 1]) @ robot[index]
        b_motion = camera[index + 1] @ np.linalg.inv(camera[index])
        delta = np.linalg.inv(a_motion @ tool_camera) @ (tool_camera @ b_motion)
        translation_residuals.append(float(np.linalg.norm(delta[:3, 3])))
        rotation_residuals.append(rotation_error_deg(np.eye(4), delta))
    translation_residual = float(np.percentile(translation_residuals, 95))
    rotation_residual = float(np.percentile(rotation_residuals, 95))
    valid = (
        np.all(np.isfinite(tool_camera))
        and translation_residual <= thresholds.max_hand_eye_translation_residual_mm
        and rotation_residual <= thresholds.max_hand_eye_rotation_residual_deg
    )
    validation_errors = []
    if translation_residual > thresholds.max_hand_eye_translation_residual_mm:
        validation_errors.append("hand_eye_translation_residual_too_large")
    if rotation_residual > thresholds.max_hand_eye_rotation_residual_deg:
        validation_errors.append("hand_eye_rotation_residual_too_large")
    return {
        "ok": valid,
        "calibration_valid": valid,
        "source": "markerless_rgbd_hand_eye",
        "camera_mount": {
            "translation_mm": [round(float(value), 6) for value in tool_camera[:3, 3]],
            "rotation_rpy_deg": matrix_to_rpy_deg(tool_camera[:3, :3]),
        },
        "transform": tool_camera,
        "observability": observable,
        "quality": {
            "pose_count": len(robot),
            "translation_residual_p95_mm": round(translation_residual, 6),
            "rotation_residual_p95_deg": round(rotation_residual, 6),
        },
        "validation_errors": validation_errors,
        "warning": "; ".join(validation_errors),
    }


def solve_markerless_observations(
    observations: Sequence[Dict[str, Any]],
    intrinsics: Dict[str, Any],
    thresholds: MarkerlessThresholds = MarkerlessThresholds(),
) -> Dict[str, Any]:
    """Estimate camera poses from RGB-D observations, then solve hand-eye."""
    if len(observations) < 4:
        raise MarkerlessCalibrationError("at least 4 synchronized RGB-D/TCP observations are required")
    robot = [_as_transform(item["gripper2base"], f"observations[{i}].gripper2base") for i, item in enumerate(observations)]
    camera = [np.eye(4, dtype=np.float64)]
    pair_quality = []
    for index, (first, second) in enumerate(zip(observations, observations[1:])):
        estimate = estimate_rgbd_motion(
            first["rgb"], first["depth_mm"], second["rgb"], second["depth_mm"],
            intrinsics, thresholds, random_seed=index,
        )
        camera.append(estimate["transform"] @ camera[-1])
        pair_quality.append({key: value for key, value in estimate.items() if key != "transform"})
    result = solve_hand_eye(robot, camera, thresholds)
    result["pair_quality"] = pair_quality
    return result
