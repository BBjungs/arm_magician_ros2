"""Plane-free RGB-D object observations and conservative reference tracking.

Detector IDs are per-frame indices, never persistent identities. Selection is
bound to an exposure; subsequent identity is established by RGB-D registration.
"""

from dataclasses import replace
import threading

import cv2
import numpy as np
from scipy.spatial import cKDTree

from .geometry import CalibrationError, Limits, checked_transform, finite_cloud, pose_distance, scene_geometry
from .registration import Capture, register


METHOD = 'object_based'


def is_object_capture(capture):
    return capture.quality.get('calibration_method') == METHOD


def require_same_method(captures, object_only):
    if any(is_object_capture(c) != object_only for c in captures):
        raise CalibrationError('CALIBRATION_METHOD_MISMATCH')


def detection_mask(detection, shape):
    outline = np.asarray(detection.get('calibration_outline', []), dtype=float)
    if (outline.ndim != 2 or outline.shape[1:] != (2,) or len(outline) < 3
            or not np.isfinite(outline).all() or len(outline) > 4096):
        raise CalibrationError('OBJECT_SEGMENTATION_REQUIRED')
    height, width = shape
    if (np.any(outline < 0) or np.any(outline[:, 0] >= width)
            or np.any(outline[:, 1] >= height)):
        raise CalibrationError('OBJECT_SEGMENTATION_OUTSIDE_IMAGE')
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.rint(outline).astype(np.int32)], 1)
    # Silhouette boundaries mix foreground/background depth and are not features.
    return cv2.erode(mask, np.ones((5, 5), np.uint8)).astype(bool)


def make_object_capture(stamp, pose, rgb, depth, intrinsics, mask, limits=Limits(),
                        *, base_T_carrier=None, identity=None):
    """Use only object pixels; never fit or require a scene/table plane."""
    pose = checked_transform(pose)
    carrier = None if base_T_carrier is None else checked_transform(base_T_carrier)
    rgb, depth, mask = np.asarray(rgb), np.asarray(depth, float), np.asarray(mask, bool)
    k = np.asarray(intrinsics, float)
    if (depth.ndim != 2 or rgb.shape != (*depth.shape, 3) or rgb.dtype != np.uint8
            or mask.shape != depth.shape or k.shape != (3, 3) or not np.isfinite(k).all()
            or min(k[0, 0], k[1, 1]) <= 0 or not np.allclose(k[2], [0, 0, 1])
            or not np.isfinite(stamp) or mask.sum() < limits.min_points):
        raise CalibrationError('OBJECT_RGBD_OBSERVATION_INVALID')
    valid = np.isfinite(depth) & (depth >= limits.min_depth_m) & (depth <= limits.max_depth_m)
    ratio = float(valid[mask].mean())
    if float(valid.mean()) < limits.min_depth_valid_ratio or ratio < limits.min_depth_valid_ratio:
        raise CalibrationError('OBJECT_DEPTH_COVERAGE_INSUFFICIENT')
    yy, xx = np.nonzero(mask & valid)
    rays = np.c_[xx, yy, np.ones(len(xx))] @ np.linalg.inv(k).T
    cloud = finite_cloud(rays * depth[yy, xx, None], limits)
    quality = scene_geometry(cloud, limits)  # 3D extent/thickness, not a plane gate.
    centered = cloud - cloud.mean(axis=0)
    _, spread, axes = np.linalg.svd(centered, full_matrices=False)
    # Equal principal axes make shape orientation ambiguous. Textured but
    # symmetric objects are conservatively rejected, not assigned an orientation.
    separation = np.abs(np.diff(spread)) / np.maximum(spread[:-1], 1e-12)
    if np.min(separation) < .08:
        raise CalibrationError('OBJECT_SYMMETRIC_OR_AMBIGUOUS')
    # Distinct axis lengths alone do not rule out half-turn symmetry (e.g.
    # an ellipsoid). Reject observed geometry with competing 180-degree poses.
    tree = cKDTree(centered)
    for signs in ((1, -1, -1), (-1, 1, -1), (-1, -1, 1)):
        rotated = (centered @ axes.T * signs) @ axes
        distances, _ = tree.query(rotated)
        if float(np.mean(distances < limits.max_registration_rmse_m)) >= .90:
            raise CalibrationError('OBJECT_SYMMETRIC_OR_AMBIGUOUS')
    object_rgb = rgb.copy()
    object_rgb[~mask] = 0
    object_depth = depth.copy()
    object_depth[~mask] = 0
    keypoints, descriptors = cv2.ORB_create(nfeatures=2500, fastThreshold=12).detectAndCompute(
        cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY), (mask.astype(np.uint8) * 255))
    if descriptors is None or len(keypoints) < limits.min_feature_inliers:
        raise CalibrationError('OBJECT_TEXTURE_INSUFFICIENT')
    quality.update(calibration_method=METHOD, depth_valid_ratio=ratio,
                   full_depth_valid_ratio=float(valid.mean()),
                   object_centroid_camera_m=np.median(cloud, axis=0).tolist(),
                   object_feature_count=len(keypoints), object_identity=dict(identity or {}),
                   object_axis_separation=separation.tolist())
    return Capture(float(stamp), pose.copy(), object_rgb, object_depth, k.copy(),
                   cloud, np.empty(0), quality, None if carrier is None else carrier.copy(), depth.copy())


def stationary_pair(first, second, limits=Limits(), *, pair=None):
    distance, angle = pose_distance(first.calibration_pose, second.calibration_pose)
    if distance > .001 or angle > .3:
        raise CalibrationError('OBJECT_BURST_ROBOT_MOVED')
    pair = register(first, second, limits) if pair is None else pair
    distance, angle = pose_distance(np.eye(4), pair.first_T_second)
    if distance > .002 or angle > .5:
        raise CalibrationError('REFERENCE_OBJECT_MOVED')
    return pair


def combine_stationary(captures, limits=Limits()):
    """Median aligned depth from distinct stationary exposures, not repeated frames."""
    if len(captures) < 3 or any(b.stamp <= a.stamp for a, b in zip(captures, captures[1:])):
        raise CalibrationError('OBJECT_FRESH_FRAMES_REQUIRED')
    first = captures[0]
    for capture in captures[1:]:
        stationary_pair(first, capture, limits)
    valid = np.stack([np.isfinite(c.depth) & (c.depth >= limits.min_depth_m)
                      & (c.depth <= limits.max_depth_m) for c in captures])
    common = valid.all(axis=0)
    if common.sum() < limits.min_points:
        raise CalibrationError('OBJECT_TEMPORAL_OVERLAP_INSUFFICIENT')
    # Only depth valid in all frames participates; no NaN/zero filling.
    depths = np.stack([c.depth for c in captures])
    noise = float(np.quantile(np.std(depths[:, common], axis=0), .95))
    if noise > limits.max_registration_rmse_m:
        raise CalibrationError('OBJECT_DEPTH_NOISE_EXCESSIVE')
    last = captures[-1]
    depth = last.depth.copy()
    depth[common] = np.median(depths[:, common], axis=0)
    yy, xx = np.nonzero(common)
    rays = np.c_[xx, yy, np.ones(len(xx))] @ np.linalg.inv(last.intrinsics).T
    cloud = finite_cloud(rays * depth[yy, xx, None], limits)
    quality = {**last.quality, **scene_geometry(cloud, limits),
               'object_burst_stamps': [c.stamp for c in captures],
               'object_depth_noise_p95_m': noise, 'object_stationary_verified': True,
               'object_centroid_camera_m': np.median(cloud, axis=0).tolist()}
    rgb = last.rgb.copy(); rgb[~common] = 0; depth[~common] = 0
    sensor_depth = last.sensor_depth.copy()
    sensor_depth[common] = depth[common]
    return replace(last, rgb=rgb, depth=depth, cloud=cloud, quality=quality, sensor_depth=sensor_depth)


class ObjectReference:
    def __init__(self):
        self.lock = threading.RLock()
        self.packet = None
        self.selection = None
        self.last = None

    def update(self, packet):
        import json
        # Reject malformed detector payloads before they can poison status JSON.
        json.dumps(packet, allow_nan=False)
        with self.lock:
            self.packet = packet

    def select(self, request, now):
        with self.lock:
            packet = self.packet or {}
            stamp = float(packet.get('rgb_stamp', -1))
            if not np.isfinite(stamp) or not 0 <= now - stamp <= 1.5:
                raise CalibrationError('OBJECT_DETECTIONS_STALE')
            pixel = request.get('pixel') if request else None
            if pixel is not None:
                p = np.asarray(pixel, float)
                requested_stamp = float(request.get('rgb_stamp', -1))
                if (p.shape != (2,) or not np.isfinite(p).all()
                        or not np.isfinite(requested_stamp)
                        or request.get('image_size') != packet.get('image_size')
                        or abs(requested_stamp - stamp) > .1):
                    raise CalibrationError('OBJECT_SELECTION_IMAGE_CHANGED')
            self.selection = dict(request or {})
            self.last = None
            return {'selected': True, 'selection': self.selection, 'motion_command_sent': False}

    def snapshot(self):
        with self.lock:
            packet = self.packet or {}
            return {'selection': self.selection, 'rgb_stamp': packet.get('rgb_stamp'),
                    'image_size': packet.get('image_size'),
                    'preview_jpeg': packet.get('calibration_preview_jpeg', ''),
                    'candidates': [{k: d.get(k) for k in ('bbox', 'center_pixel', 'shape', 'color',
                                                          'class_name', 'calibration_outline')}
                                   for d in packet.get('detections', [])],
                    'tracked': self.last is not None}

    def exposure_ready(self, stamp):
        with self.lock:
            try:
                stamps = [float((self.packet or {}).get(key, -1)) for key in ('rgb_stamp', 'depth_stamp')]
                return bool(np.isfinite(stamps).all() and all(abs(value - stamp) <= .1 for value in stamps))
            except (TypeError, ValueError):
                return False

    def capture(self, stamp, pose, rgb, depth, intrinsics, frame, limits=Limits(), *, carrier=None):
        with self.lock:
            packet = self.packet or {}
            if (packet.get('registered_depth') is not True or packet.get('error')
                    or packet.get('rgb_frame_id') != frame or packet.get('depth_frame_id') != frame
                    or packet.get('image_size') != [rgb.shape[1], rgb.shape[0]]
                    or not self.exposure_ready(stamp)):
                raise CalibrationError('OBJECT_DETECTION_EXPOSURE_MISMATCH')
            choices, reasons = [], []
            for detection in packet.get('detections', []):
                try:
                    if str(detection.get('shape', '')).lower() in ('circle', 'ellipse', 'sphere', 'cylinder'):
                        raise CalibrationError('OBJECT_SYMMETRIC_OR_AMBIGUOUS')
                    score = float(detection.get('shape_score', detection.get('confidence', 0)))
                    if not np.isfinite(score) or score < .6:
                        raise CalibrationError('OBJECT_DETECTION_CONFIDENCE_LOW')
                    mask = detection_mask(detection, depth.shape)
                    pixel = (self.selection or {}).get('pixel') if self.last is None else None
                    if pixel is not None:
                        x, y = np.rint(pixel).astype(int)
                        if not (0 <= y < mask.shape[0] and 0 <= x < mask.shape[1] and mask[y, x]):
                            continue
                    identity = {k: detection.get(k) for k in ('shape', 'color', 'class_name')}
                    capture = make_object_capture(stamp, pose, rgb, depth, intrinsics, mask,
                        limits, base_T_carrier=carrier, identity=identity)
                    if self.last is not None:
                        if identity != self.last.quality['object_identity']:
                            continue
                        pair = register(self.last, capture, limits)
                        distance, angle = pose_distance(self.last.calibration_pose, capture.calibration_pose)
                        if distance <= .001 and angle <= .3:
                            stationary_pair(self.last, capture, limits, pair=pair)
                        capture.quality['object_tracking'] = pair.quality
                    choices.append(capture)
                except CalibrationError as error:
                    reasons.append(str(error))
            if len(choices) != 1:
                reason = 'OBJECT_SELECTION_AMBIGUOUS' if choices else 'OBJECT_REFERENCE_UNSUITABLE_OR_LOST'
                raise CalibrationError(reason + ': ' + '; '.join(dict.fromkeys(reasons)))
            self.last = choices[0]
            return choices[0]
