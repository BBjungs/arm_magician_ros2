"""Natural-feature RGB-D registration with independently checked dense geometry."""

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy.spatial import cKDTree

from .geometry import (
    CalibrationError, Limits, apply, checked_transform, finite_cloud, inverse,
    rigid_fit, scene_geometry, table_plane,
)


@dataclass
class Capture:
    stamp: float
    base_T_tool: np.ndarray
    rgb: np.ndarray
    depth: np.ndarray
    intrinsics: np.ndarray
    cloud: np.ndarray
    plane: np.ndarray
    quality: dict = field(default_factory=dict)


@dataclass
class Registration:
    # Camera first_T_second; AX=XB uses A = tool_first_T_tool_second.
    first_T_second: np.ndarray
    source: np.ndarray
    target: np.ndarray
    quality: dict


def depth_points(pixels, depth, intrinsics, limits=Limits()):
    pixels = np.asarray(pixels, dtype=float).reshape(-1, 2)
    indices = np.rint(pixels).astype(int)
    inside = ((indices[:, 0] >= 0) & (indices[:, 0] < depth.shape[1])
              & (indices[:, 1] >= 0) & (indices[:, 1] < depth.shape[0]))
    z = np.full(len(pixels), np.nan)
    z[inside] = depth[indices[inside, 1], indices[inside, 0]]
    valid = inside & np.isfinite(z) & (z >= limits.min_depth_m) & (z <= limits.max_depth_m)
    # Reject depth discontinuities: a 3x3 patch must agree within 12 mm.
    padded = np.pad(depth, 1, mode='constant', constant_values=np.nan)
    for index in np.flatnonzero(valid):
        x, y = indices[index]
        patch = padded[y:y + 3, x:x + 3]
        if not np.isfinite(patch).all() or np.ptp(patch) > 0.012 or np.min(patch) <= 0:
            valid[index] = False
    rays = np.c_[pixels, np.ones(len(pixels))] @ np.linalg.inv(intrinsics).T
    return rays * z[:, None], valid


def make_capture(stamp, base_T_tool, rgb, depth_m, intrinsics, cloud,
                 tool_T_camera_hint, limits=Limits()):
    base_T_tool = checked_transform(base_T_tool)
    intrinsics = np.asarray(intrinsics, dtype=float).reshape(3, 3)
    depth = np.asarray(depth_m, dtype=float)
    rgb = np.asarray(rgb)
    if (depth.ndim != 2 or depth.size == 0 or rgb.shape != (*depth.shape, 3) or rgb.dtype != np.uint8
            or not np.isfinite(intrinsics).all() or min(intrinsics[0, 0], intrinsics[1, 1]) <= 0
            or not np.allclose(intrinsics[2], [0, 0, 1]) or not np.isfinite(stamp)):
        raise CalibrationError('Invalid aligned RGB/depth/CameraInfo observation')
    valid = np.isfinite(depth) & (depth >= limits.min_depth_m) & (depth <= limits.max_depth_m)
    ratio = float(valid.mean())
    if ratio < limits.min_depth_valid_ratio:
        raise CalibrationError('Insufficient depth-valid ratio')
    points = finite_cloud(cloud, limits)
    # The PointCloud2 must describe the same optical frame and aligned depth.
    yy, xx = np.mgrid[0:depth.shape[0]:4, 0:depth.shape[1]:4]
    projected, mask = depth_points(np.c_[xx.ravel(), yy.ravel()], depth, intrinsics, limits)
    if mask.sum() < limits.min_points:
        raise CalibrationError('Insufficient aligned depth geometry')
    distance, _ = cKDTree(points).query(projected[mask])
    if np.mean(distance < limits.correspondence_m) < limits.min_registration_fitness:
        raise CalibrationError('PointCloud2 and aligned depth disagree')
    quality = {'depth_valid_ratio': ratio, **scene_geometry(points, limits)}
    camera_up = (base_T_tool @ tool_T_camera_hint)[:3, :3].T @ np.array([0., 0., 1.])
    plane, plane_quality = table_plane(points, camera_up, limits)
    quality.update(plane_quality)
    return Capture(float(stamp), base_T_tool.copy(), rgb.copy(), depth.copy(),
                   intrinsics.copy(), points, plane, quality)


def cloud_consistency(source, target, value, limits=Limits()):
    """Bidirectional overlap prevents tiny subsets from claiming high fitness."""
    moved = apply(value, source)
    distances, indices = cKDTree(target).query(moved)
    reverse, _ = cKDTree(moved).query(target)
    mask = distances < limits.correspondence_m
    reverse_mask = reverse < limits.correspondence_m
    fitness = float(min(mask.mean(), reverse_mask.mean()))
    rmse = (float(np.sqrt(np.mean(np.r_[distances[mask], reverse[reverse_mask]] ** 2)))
            if mask.any() and reverse_mask.any() else float('inf'))
    return fitness, rmse, mask, indices


def register(first, second, limits=Limits(), seed=0):
    """Map second camera to first using mutual ORB matches, RANSAC and ICP."""
    scene_geometry(first.cloud, limits)
    scene_geometry(second.cloud, limits)
    if first.rgb.shape != second.rgb.shape or not np.allclose(first.intrinsics, second.intrinsics):
        raise CalibrationError('Camera intrinsics/resolution changed during calibration')
    detector = cv2.ORB_create(nfeatures=2500, fastThreshold=12)
    kp1, des1 = detector.detectAndCompute(cv2.cvtColor(first.rgb, cv2.COLOR_BGR2GRAY), None)
    kp2, des2 = detector.detectAndCompute(cv2.cvtColor(second.rgb, cv2.COLOR_BGR2GRAY), None)
    if des1 is None or des2 is None:
        raise CalibrationError('Insufficient natural image features')
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    def good(a, b):
        return {pair[0].queryIdx: pair[0].trainIdx for pair in matcher.knnMatch(a, b, k=2)
                if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance}

    forward, reverse = good(des2, des1), good(des1, des2)
    matches = [(i, j) for i, j in forward.items() if reverse.get(j) == i]
    if len(matches) < limits.min_feature_inliers:
        raise CalibrationError('Insufficient mutual RGB feature matches')
    source, valid2 = depth_points([kp2[i].pt for i, _ in matches], second.depth,
                                  second.intrinsics, limits)
    target, valid1 = depth_points([kp1[j].pt for _, j in matches], first.depth,
                                  first.intrinsics, limits)
    source, target = source[valid1 & valid2], target[valid1 & valid2]
    if len(source) < limits.min_feature_inliers:
        raise CalibrationError('Insufficient RGB matches with valid depth')
    rng = np.random.default_rng(seed)
    best = np.zeros(len(source), dtype=bool)
    for _ in range(500):
        indices = rng.choice(len(source), 3, replace=False)
        try:
            value = rigid_fit(source[indices], target[indices])
        except CalibrationError:
            continue
        mask = np.linalg.norm(apply(value, source) - target, axis=1) < 0.006
        if mask.sum() > best.sum():
            best = mask
    if best.sum() < limits.min_feature_inliers or best.mean() < limits.min_feature_ratio:
        raise CalibrationError('RGB-D registration has insufficient static-scene inliers')
    # Inliers must span 3D geometry as well as the full cloud; texture on one
    # flat patch cannot rescue ambiguous registration of an otherwise rich scene.
    spreads = np.linalg.svd(source[best] - source[best].mean(axis=0), compute_uv=False)
    if spreads[2] / np.sqrt(best.sum()) < limits.min_scene_thickness_m:
        raise CalibrationError('RGB-D inliers do not constrain nonplanar scene geometry')
    feature_value = rigid_fit(source[best], target[best])
    value = feature_value.copy()
    tree = cKDTree(first.cloud)
    for _ in range(25):
        moved = apply(value, second.cloud)
        distances, indices = tree.query(moved)
        mask = distances < limits.correspondence_m
        if mask.sum() < limits.min_points:
            raise CalibrationError('Insufficient ICP overlap')
        # Trim largest errors so moving objects and occlusion edges have less influence.
        mask &= distances <= np.quantile(distances[mask], 0.85)
        delta = rigid_fit(moved[mask], first.cloud[indices[mask]])
        value = delta @ value
        if np.linalg.norm(delta - np.eye(4)) < 1e-6:
            break
    fitness, rmse, _, _ = cloud_consistency(second.cloud, first.cloud, value, limits)
    feature_error = np.linalg.norm(apply(value, source[best]) - target[best], axis=1)
    if (fitness < limits.min_registration_fitness or rmse > limits.max_registration_rmse_m
            or np.sqrt(np.mean(feature_error ** 2)) > 0.006):
        raise CalibrationError('Registration fitness/residual failed')
    quality = {'registration_fitness': fitness, 'registration_rmse_m': rmse,
               'feature_inlier_ratio': float(best.mean()), 'feature_inliers': int(best.sum())}
    return Registration(checked_transform(value), source[best], target[best], quality)


def predicted_camera_motion(first, second, tool_T_camera):
    return inverse(tool_T_camera) @ inverse(first.base_T_tool) @ second.base_T_tool @ tool_T_camera
