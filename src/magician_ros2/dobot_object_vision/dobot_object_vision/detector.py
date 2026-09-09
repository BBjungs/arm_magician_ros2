"""Pure RGB-D geometry. Lengths are metres; images are rectified aligned BGR8."""

from dataclasses import asdict, dataclass

import cv2
import numpy as np
from scipy.optimize import least_squares


class VisionError(ValueError):
    pass


@dataclass(frozen=True)
class Rules:
    min_depth: float = 0.15
    max_depth: float = 1.5
    min_frame_depth_ratio: float = 0.35
    min_diameter: float = 0.015
    max_diameter: float = 0.080
    min_height: float = 0.003
    max_height: float = 0.060
    plane_tolerance: float = 0.002
    min_plane_ratio: float = 0.35
    max_table_tilt_deg: float = 50.0
    min_circularity: float = 0.70
    max_circle_error_ratio: float = 0.12
    min_color_ratio: float = 0.70
    min_object_depth_ratio: float = 0.30
    pick_depth_ratio: float = 0.80
    max_top_mad: float = 0.002
    suction_radius: float = 0.004
    min_confidence: float = 0.75
    black_max_value: int = 85
    white_min_value: int = 155
    white_max_saturation: int = 65
    yellow_min_hue: int = 18
    yellow_max_hue: int = 40
    yellow_min_saturation: int = 80
    yellow_min_value: int = 85

    def __post_init__(self):
        for key, value in asdict(self).items():
            if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
                raise VisionError(f'{key} must be finite and positive')
            if (key.endswith('_ratio') or key in ('min_confidence', 'min_circularity')) and value > 1:
                raise VisionError(f'{key} must be at most one')
        for low, high in [('min_depth', 'max_depth'), ('min_diameter', 'max_diameter'),
                          ('min_height', 'max_height'), ('yellow_min_hue', 'yellow_max_hue')]:
            if getattr(self, low) >= getattr(self, high):
                raise VisionError(f'{low} must be below {high}')
        if self.max_table_tilt_deg >= 80:
            raise VisionError('Table normal must remain directed towards the camera')
        if self.suction_radius * 2 >= self.max_diameter:
            raise VisionError('Suction footprint exceeds target diameter range')
        if self.min_object_depth_ratio > self.pick_depth_ratio:
            raise VisionError('Picking must require at least the detection depth support')
        for key in ('black_max_value', 'white_min_value', 'white_max_saturation',
                    'yellow_min_saturation', 'yellow_min_value', 'yellow_min_hue', 'yellow_max_hue'):
            value = getattr(self, key)
            if not isinstance(value, int) or value > (179 if 'hue' in key else 255):
                raise VisionError(f'{key} is outside the OpenCV HSV range')


@dataclass
class Detection:
    id: int
    class_name: str
    center_uv: tuple
    camera_xyz: tuple
    depth: float
    size: float
    confidence: float
    pickable: bool
    top_height: float
    depth_valid_ratio: float
    depth_mad: float
    rejection_reason: str


@dataclass
class Result:
    detections: list
    annotated: np.ndarray
    table_plane: np.ndarray
    table_inlier_ratio: float
    table_rmse: float
    rejected: dict


def rays(pixels, k):
    pixels = np.asarray(pixels, dtype=float).reshape(-1, 2)
    return np.c_[pixels, np.ones(len(pixels))] @ np.linalg.inv(k).T


def robust_values(values, floor=0.001):
    median = float(np.median(values))
    mad = float(1.4826 * np.median(np.abs(values - median)))
    mask = np.abs(values - median) <= max(floor, 3 * mad)
    return float(np.median(values[mask])), mad, mask


def estimate_table(depth, k, rules):
    """RANSAC/SVD on spatially sampled depth, with broad boundary support."""
    step = max(2, int(np.sqrt(depth.size / 3500)))
    yy, xx = np.mgrid[0:depth.shape[0]:step, 0:depth.shape[1]:step]
    z = depth[yy, xx].ravel()
    uv = np.c_[xx.ravel(), yy.ravel()]
    valid = np.isfinite(z) & (z >= rules.min_depth) & (z <= rules.max_depth)
    uv, z = uv[valid], z[valid]
    if len(z) < 150:
        raise VisionError('Insufficient depth for the table plane')
    points = rays(uv, k) * z[:, None]
    edge = ((uv[:, 0] < depth.shape[1] * 0.15) | (uv[:, 0] > depth.shape[1] * 0.85)
            | (uv[:, 1] < depth.shape[0] * 0.15) | (uv[:, 1] > depth.shape[0] * 0.85))
    rng = np.random.default_rng(17)
    best = np.zeros(len(z), dtype=bool)
    cosine = np.cos(np.deg2rad(rules.max_table_tilt_deg))
    for _ in range(180):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        n = np.cross(b - a, c - a)
        if np.linalg.norm(n) < 1e-8:
            continue
        n /= np.linalg.norm(n)
        if abs(n[2]) < cosine:
            continue
        mask = np.abs(points @ n - a @ n) < rules.plane_tolerance
        if np.count_nonzero(mask & edge) < max(30, 0.25 * edge.sum()):
            continue
        if mask.sum() > best.sum():
            best = mask
    if best.mean() < rules.min_plane_ratio or best.sum() < 150:
        raise VisionError('No broad supported table plane')
    for _ in range(3):
        center = np.mean(points[best], axis=0)
        _, singular, vt = np.linalg.svd(points[best] - center, full_matrices=False)
        n = vt[-1]
        if n[2] > 0:
            n = -n
        d = -n @ center
        best = np.abs(points @ n + d) < rules.plane_tolerance
        if best.sum() < 150:
            raise VisionError('Table plane refinement lost support')
    if (best.mean() < rules.min_plane_ratio or -n[2] < cosine
            or singular[1] / np.sqrt(best.sum()) < 0.03):
        raise VisionError('Table geometry is narrow, tilted or insufficient')
    error = float(np.sqrt(np.mean((points[best] @ n + d) ** 2)))
    return np.r_[n, d], float(best.mean()), error


def fit_metric_circle(contour, k, plane, height):
    uv = contour.reshape(-1, 2)[::max(1, len(contour) // 250)]
    ray = rays(uv, k)
    denominator = ray @ plane[:3]
    if np.any(denominator >= -0.05):
        raise VisionError('Top plane is grazing the viewing rays')
    points = ray * ((height - plane[3]) / denominator)[:, None]
    n = plane[:3]
    e1 = np.cross(n, [0., 1., 0.])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    xy = np.c_[points @ e1, points @ e2]
    origin = np.mean(xy, axis=0)
    local = xy - origin
    fit, _, _, _ = np.linalg.lstsq(np.c_[2 * local, np.ones(len(local))],
                                  np.sum(local ** 2, axis=1), rcond=None)
    radius = np.sqrt(max(1e-10, fit[2] + fit[:2] @ fit[:2]))
    result = least_squares(lambda p: np.linalg.norm(local - p[:2], axis=1) - p[2],
                           np.r_[fit[:2], radius], loss='soft_l1', f_scale=0.0007,
                           max_nfev=40)
    radius = float(result.x[2])
    if not result.success or radius <= 0:
        raise VisionError('Circle fit failed')
    error = float(np.quantile(np.abs(result.fun), 0.95) / radius)
    center_xy = origin + result.x[:2]
    center = e1 * center_xy[0] + e2 * center_xy[1] + n * (height - plane[3])
    pixel = k @ center
    return center, pixel[:2] / pixel[2], 2 * radius, error


class Detector:
    def __init__(self, rules=Rules()):
        self.rules = rules

    def process(self, bgr, depth, k):
        rules = self.rules
        bgr, depth, k = np.asarray(bgr), np.asarray(depth, dtype=float), np.asarray(k, dtype=float)
        if (depth.ndim != 2 or min(depth.shape, default=0) < 20
                or bgr.shape != (*depth.shape, 3) or bgr.dtype != np.uint8
                or k.shape != (3, 3) or not np.isfinite(k).all()
                or min(k[0, 0], k[1, 1]) <= 0 or not np.allclose(k[2], [0, 0, 1])
                or abs(np.linalg.det(k)) < 1e-10):
            raise VisionError('Invalid aligned RGB/depth/intrinsics')
        valid = np.isfinite(depth) & (depth >= rules.min_depth) & (depth <= rules.max_depth)
        if valid.mean() < rules.min_frame_depth_ratio:
            raise VisionError('Frame depth-valid ratio is too low')
        plane, plane_ratio, plane_rmse = estimate_table(depth, k, rules)
        yy, xx = np.indices(depth.shape)
        ray = rays(np.c_[xx.ravel(), yy.ravel()], k).reshape(*depth.shape, 3)
        heights = depth * (ray @ plane[:3]) + plane[3]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        colors = {'black': v <= rules.black_max_value,
                  'white': (v >= rules.white_min_value) & (s <= rules.white_max_saturation),
                  'yellow': (h >= rules.yellow_min_hue) & (h <= rules.yellow_max_hue)
                            & (s >= rules.yellow_min_saturation) & (v >= rules.yellow_min_value)}
        # Raised geometry separates white-on-white and black-on-black targets.
        # Missing depth may join a candidate, but cannot establish its geometry.
        raised = (~valid) | ((heights >= rules.min_height) & (heights <= rules.max_height))
        annotated, detections, rejected = bgr.copy(), [], {}
        kernel = np.ones((3, 3), np.uint8)
        for label, color in colors.items():
            mask = (color & raised).astype(np.uint8) * 255
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            for contour in contours:
                if cv2.contourArea(contour) < 40:
                    continue
                try:
                    detection = self._candidate(contour, color, valid, heights, depth, k, plane)
                    detection.class_name = label
                    detections.append(detection)
                except VisionError as error:
                    reason = str(error)
                    rejected[reason] = rejected.get(reason, 0) + 1
                    cv2.drawContours(annotated, [contour], -1, (70, 70, 200), 1)
        detections.sort(key=lambda item: (item.center_uv[0], item.center_uv[1], item.class_name))
        for index, detection in enumerate(detections):
            detection.id = index
            center = tuple(int(round(x)) for x in detection.center_uv)
            color = (40, 210, 40) if detection.pickable else (0, 140, 255)
            radius = int(round(detection.size * k[0, 0] / detection.depth / 2))
            cv2.circle(annotated, center, max(2, radius), color, 2)
            cv2.drawMarker(annotated, center, color, cv2.MARKER_CROSS, 10, 1)
            text = f'{index} {detection.class_name} {detection.size * 1000:.0f}mm {detection.depth:.3f}m'
            cv2.putText(annotated, text, (max(0, center[0] - radius), max(15, center[1] - radius - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
            if not detection.pickable:
                cv2.putText(annotated, detection.rejection_reason, (max(0, center[0] - radius), center[1] + radius + 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
        return Result(detections, annotated, plane, plane_ratio, plane_rmse, rejected)

    def _candidate(self, contour, color, valid, heights, depth, k, plane):
        r = self.rules
        x, y, w, h = cv2.boundingRect(contour)
        if x < 2 or y < 2 or x + w >= depth.shape[1] - 2 or y + h >= depth.shape[0] - 2:
            raise VisionError('clipped contour')
        area, perimeter = cv2.contourArea(contour), cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / max(perimeter ** 2, 1)
        vertices = len(cv2.approxPolyDP(contour, 0.025 * perimeter, True))
        if circularity < r.min_circularity or vertices < 6:
            raise VisionError('noncircular contour')
        mask = np.zeros(depth.shape, np.uint8)
        cv2.drawContours(mask, [contour], -1, 1, cv2.FILLED)
        distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        interior = distance >= max(2, 0.35 * distance.max())
        support = interior & valid
        ratio = float(support.sum() / max(1, interior.sum()))
        color_ratio = float(np.mean(color[interior])) if interior.any() else 0.
        if color_ratio < r.min_color_ratio:
            raise VisionError('mixed or unsupported color')
        if support.sum() < 20 or ratio < r.min_object_depth_ratio:
            raise VisionError('insufficient interior depth')
        height, mad, keep = robust_values(heights[support])
        # Median plane-relative depth handles a slanted table without taking
        # the median Z of an asymmetric collection of valid pixels.
        if not r.min_height <= height <= r.max_height:
            raise VisionError('height out of range')
        xyz, uv, diameter, circle_error = fit_metric_circle(contour, k, plane, height)
        if not np.isfinite(np.r_[xyz, uv, diameter]).all() or not r.min_depth <= xyz[2] <= r.max_depth:
            raise VisionError('invalid camera XYZ')
        if circle_error > r.max_circle_error_ratio:
            raise VisionError('noncircular metric geometry')
        if not r.min_diameter <= diameter <= r.max_diameter:
            raise VisionError('diameter out of range')
        cx, cy = np.rint(uv).astype(int)
        patch_radius = max(2, int(np.ceil(r.suction_radius * max(k[0, 0], k[1, 1]) / xyz[2])))
        yy, xx = np.ogrid[:depth.shape[0], :depth.shape[1]]
        patch = (xx - uv[0]) ** 2 + (yy - uv[1]) ** 2 <= patch_radius ** 2
        if not (0 <= cx < depth.shape[1] and 0 <= cy < depth.shape[0]) or distance[cy, cx] < patch_radius + 1:
            raise VisionError('no interior suction footprint')
        patch_valid = patch & valid
        patch_ratio = float(patch_valid.sum() / max(1, patch.sum()))
        if patch_valid.sum() < 5:
            raise VisionError('no center depth support')
        top_support = np.abs(heights[patch_valid] - height) <= max(0.002, 3 * mad)
        if top_support.mean() < 0.8 or np.mean(color[patch]) < r.min_color_ratio:
            raise VisionError('center is a hole or another surface')
        confidence = float(np.clip(0.25 * min(1, circularity / 0.9) + 0.25 * color_ratio
                                   + 0.25 * ratio * keep.mean()
                                   + 0.25 * max(0, 1 - circle_error), 0, 1))
        reason = ''
        if ratio < r.pick_depth_ratio or patch_ratio < r.pick_depth_ratio:
            reason = 'insufficient suction depth coverage'
        elif mad > r.max_top_mad:
            reason = 'top surface is not flat enough'
        elif confidence < r.min_confidence:
            reason = 'low confidence'
        return Detection(0, '', tuple(map(float, uv)), tuple(map(float, xyz)), float(xyz[2]),
                         float(diameter), confidence, not reason, height, ratio, mad, reason)
