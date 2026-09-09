"""Geometry in metres; a_T_b maps points from frame b into frame a."""

from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
from scipy.spatial.transform import Rotation
import yaml


class CalibrationError(ValueError):
    """An observation, movement or solution cannot be trusted."""


@dataclass(frozen=True)
class Limits:
    min_depth_m: float = 0.15
    max_depth_m: float = 1.5
    min_depth_valid_ratio: float = 0.35
    min_points: int = 200
    min_scene_thickness_m: float = 0.004
    min_scene_width_m: float = 0.025
    plane_inlier_m: float = 0.004
    min_plane_ratio: float = 0.30
    max_table_tilt_deg: float = 15.0
    min_feature_inliers: int = 24
    min_feature_ratio: float = 0.45
    correspondence_m: float = 0.012
    min_registration_fitness: float = 0.60
    max_registration_rmse_m: float = 0.004
    min_translation_span_m: float = 0.025
    min_yaw_span_deg: float = 15.0
    max_translation_residual_m: float = 0.004
    max_rotation_residual_deg: float = 1.5
    max_plane_offset_m: float = 0.004
    max_plane_angle_deg: float = 1.5
    max_cloud_rmse_m: float = 0.005
    max_mount_sigma_m: float = 0.002
    max_mount_deviation_m: float = 0.020
    max_mount_deviation_deg: float = 15.0


    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
                raise CalibrationError(f'{name} must be finite and positive')
            if ('ratio' in name or name == 'min_registration_fitness') and value > 1:
                raise CalibrationError(f'{name} must be at most one')
        for name in ('min_points', 'min_feature_inliers'):
            if not isinstance(getattr(self, name), (int, np.integer)) or getattr(self, name) < 3:
                raise CalibrationError(f'{name} must be an integer of at least three')
        if self.min_depth_m >= self.max_depth_m:
            raise CalibrationError('Depth range must have positive extent')


def transform(rotation=None, translation=None):
    result = np.eye(4)
    if rotation is not None:
        result[:3, :3] = rotation
    if translation is not None:
        result[:3, 3] = translation
    return result


def checked_transform(value):
    value = np.asarray(value, dtype=float)
    if (value.shape != (4, 4) or not np.isfinite(value).all()
            or not np.allclose(value[3], [0, 0, 0, 1], atol=1e-8)
            or not np.allclose(value[:3, :3].T @ value[:3, :3], np.eye(3), atol=1e-6)
            or not np.isclose(np.linalg.det(value[:3, :3]), 1.0, atol=1e-6)):
        raise CalibrationError('Invalid rigid transform')
    return value


def inverse(value):
    rotation = value[:3, :3].T
    return transform(rotation, -rotation @ value[:3, 3])


def apply(value, points):
    return np.asarray(points) @ value[:3, :3].T + value[:3, 3]


def rotation_deg(rotation):
    return float(np.linalg.norm(Rotation.from_matrix(rotation).as_rotvec()) * 180 / np.pi)


def pose_distance(first, second):
    return (float(np.linalg.norm(first[:3, 3] - second[:3, 3])),
            rotation_deg(first[:3, :3].T @ second[:3, :3]))


def rigid_fit(source, target):
    source, target = np.asarray(source), np.asarray(target)
    if (source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3
            or len(source) < 3 or not np.isfinite([source, target]).all()):
        raise CalibrationError('Invalid 3D correspondences')
    a, b = source.mean(axis=0), target.mean(axis=0)
    u, s, vt = np.linalg.svd((source - a).T @ (target - b))
    if s[1] < 1e-10:
        raise CalibrationError('Collinear correspondences')
    correction = np.diag([1, 1, np.linalg.det(vt.T @ u.T)])
    rotation = vt.T @ correction @ u.T
    return transform(rotation, b - rotation @ a)


def finite_cloud(points, limits=Limits()):
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    points = points[np.isfinite(points).all(axis=1)]
    points = points[(points[:, 2] >= limits.min_depth_m)
                    & (points[:, 2] <= limits.max_depth_m)]
    if len(points) < limits.min_points:
        raise CalibrationError('Insufficient valid point-cloud geometry')
    # Equal weight per voxel limits domination by oversampled near surfaces.
    _, indices = np.unique(np.floor(points / 0.003).astype(np.int64), axis=0,
                           return_index=True)
    points = points[np.sort(indices)]
    if len(points) > 4000:
        points = points[np.linspace(0, len(points) - 1, 4000).astype(int)]
    if len(points) < limits.min_points:
        raise CalibrationError('Insufficient spatially distinct points')
    return points


def scene_geometry(points, limits=Limits()):
    """Reject a flat table, narrow strip and isolated depth outliers."""
    points = finite_cloud(points, limits)
    low, high = np.quantile(points, [0.02, 0.98], axis=0)
    trimmed = points[((points >= low) & (points <= high)).all(axis=1)]
    if len(trimmed) < limits.min_points:
        raise CalibrationError('Insufficient scene geometry after outlier removal')
    singular = np.linalg.svd(trimmed - np.median(trimmed, axis=0), compute_uv=False)
    spread = singular / np.sqrt(len(trimmed))
    if spread[1] < limits.min_scene_width_m or spread[2] < limits.min_scene_thickness_m:
        raise CalibrationError('Insufficient scene geometry: flat, narrow or featureless scene')
    return {'scene_spread_m': spread.tolist(), 'point_count': len(points)}


def table_plane(points, expected_normal, limits=Limits(), seed=0):
    """Orientation-constrained RANSAC followed by an SVD plane fit."""
    points = finite_cloud(points, limits)
    normal_hint = np.asarray(expected_normal, dtype=float)
    if not np.isfinite(normal_hint).all() or np.linalg.norm(normal_hint) < 0.9:
        raise CalibrationError('Invalid table normal constraint')
    normal_hint /= np.linalg.norm(normal_hint)
    rng = np.random.default_rng(seed)
    best = np.zeros(len(points), dtype=bool)
    cosine = np.cos(np.deg2rad(limits.max_table_tilt_deg))
    for _ in range(350):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        length = np.linalg.norm(normal)
        if length < 1e-8:
            continue
        normal /= length
        if abs(normal @ normal_hint) < cosine:
            continue
        mask = np.abs(points @ normal - a @ normal) < limits.plane_inlier_m
        if mask.sum() > best.sum():
            best = mask
    if best.mean() < limits.min_plane_ratio or best.sum() < limits.min_points:
        raise CalibrationError('No sufficiently supported horizontal table plane')
    inliers = points[best]
    center = inliers.mean(axis=0)
    _, s, vt = np.linalg.svd(inliers - center, full_matrices=False)
    normal = vt[-1]
    if normal @ normal_hint < 0:
        normal = -normal
    if normal @ normal_hint < cosine or s[1] / np.sqrt(len(inliers)) < 0.025:
        raise CalibrationError('Table plane is tilted or has inadequate extent')
    return np.r_[normal, -normal @ center], {
        'plane_inlier_ratio': float(best.mean()),
        'plane_rmse_m': float(np.sqrt(np.mean(((inliers - center) @ normal) ** 2))),
    }


def transform_plane(value, plane):
    normal = value[:3, :3] @ plane[:3]
    return np.r_[normal, plane[3] - normal @ value[:3, 3]]


def plane_difference(first, second):
    if first[:3] @ second[:3] < 0:
        second = -second
    angle = np.rad2deg(np.arccos(np.clip(first[:3] @ second[:3], -1, 1)))
    return float(abs(first[3] - second[3])), float(angle)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Mount:
    tool_T_camera: np.ndarray
    axial_sigma_m: float
    envelope_radius_m: float
    source: str
    digest: str

    @classmethod
    def load(cls, path, limits=Limits()):
        with open(path, encoding='utf-8') as stream:
            value = yaml.safe_load(stream)
        if (not isinstance(value, dict) or value.get('geometry_verified') is not True
                or value.get('rigid_to_rotating_tool') is not True
                or not value.get('measurement_source')
                or value.get('translation_units') != 'm'):
            raise CalibrationError('A verified CAD/mount model rigid to the rotating TCP is required')
        matrix = checked_transform(value.get('tool_T_camera_optical'))
        sigma = float(value.get('axial_sigma_m', float('nan')))
        envelope = float(value.get('envelope_radius_m', float('nan')))
        if not np.isfinite([sigma, envelope]).all() or not 0 < sigma <= limits.max_mount_sigma_m:
            raise CalibrationError('Mount axial uncertainty is missing or too large')
        if not np.linalg.norm(matrix[:3, 3]) < envelope < 0.30:
            raise CalibrationError('Mount envelope must enclose the camera, tool and attached hardware')
        return cls(matrix, sigma, envelope, str(value['measurement_source']), fingerprint(value))
