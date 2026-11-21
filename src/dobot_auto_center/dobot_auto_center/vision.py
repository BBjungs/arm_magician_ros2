"""Registered RGB-D validation, a detector interface and conservative tracking."""

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np


@dataclass
class Observation:
    stamp: float
    received: float
    rgb: np.ndarray
    depth: np.ndarray | None
    depth_stamp: float = 0.0
    calibrated: bool = False
    source_stamp: float | None = None
    depth_source_stamp: float | None = None
    info_stamp: float | None = None

    header_skew_ns: int | None = None

    source_ns: int | None = None

    def fresh(self, now, timeout):
        return 0 <= now - self.stamp <= timeout and 0 <= now - self.received <= timeout

    def registered(self, now, camera):
        return (self.calibrated and self.depth is not None
                and self.depth.shape == self.rgb.shape[:2]
                and self.fresh(now, camera['freshness'])
                and (self.info_stamp is None or 0 <= now - self.info_stamp <= camera['freshness'])
                and 0 <= now - self.depth_stamp <= camera['freshness']
                and (self.header_skew_ns <= round(camera['max_depth_skew'] * 1e9)
                     if self.header_skew_ns is not None else
                     abs(self.depth_stamp - self.stamp) <= camera['max_depth_skew']))


@dataclass(frozen=True)
class Detection:
    box: tuple[int, int, int, int]
    center: tuple[float, float]
    confidence: float
    area: float
    hue: float
    depth: float | None

    def error(self, width, height):
        return self.center[0] - width / 2, self.center[1] - height / 2


class DetectionBackend(Protocol):
    def detect(self, observation: Observation, *, registered_depth=False) -> list[Detection]: ...


class ClassicalDetector:
    def __init__(self, config):
        self.config = config

    def detect(self, observation, *, registered_depth=False):
        config = self.config
        hsv = cv2.cvtColor(observation.rgb, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, tuple(config['hsv_lower']), tuple(config['hsv_upper']))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
        height, width = mask.shape
        border = config['border_pixels']
        results = []
        for i in range(1, count):
            x, y, w, h, area = map(int, stats[i])
            if area < config['minimum_area'] or min(x, y, width - x - w, height - y - h) < border:
                continue
            confidence = area / (w * h)
            if confidence < config['minimum_confidence']:
                continue
            u, v = map(float, centers[i])
            hue = float(np.median(hsv[y:y+h, x:x+w, 0][mask[y:y+h, x:x+w] > 0]))
            results.append(Detection((x, y, w, h), (u, v), confidence, area,
                                     hue, self.sample_depth(observation, u, v)))
        return results

    def sample_depth(self, observation, u, v):
        if observation.depth is None:
            return None
        r = self.config['depth_sample_radius']
        x, y = round(u), round(v)
        values = observation.depth[max(0, y-r):y+r+1, max(0, x-r):x+r+1]
        valid = values[np.isfinite(values) & (values > 0)]
        if not valid.size or valid.size / values.size < self.config['depth_minimum_fraction']:
            return None
        return float(np.median(valid))


class RoundDetector(ClassicalDetector):
    def detect(self, observation, *, registered_depth=False):
        # Multichannel gradients retain edges between colors of similar brightness.
        edges = cv2.Canny(cv2.GaussianBlur(observation.rgb, (5, 5), 0), 30, 70)
        results = self.circle_contours(observation, edges)
        if registered_depth and observation.depth is not None:
            depth = observation.depth
            valid = np.isfinite(depth) & (depth > 0)
            threshold = self.config.get('depth_edge_m', 0.01)
            # A nearer pixel marks an edge only if a measured neighbour is farther.
            measured = np.where(valid, depth, 0).astype(np.float32, copy=False)
            cross = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
            step = cv2.dilate(measured, cross) - measured
            depth_edges = (valid & (step >= threshold)).astype(np.uint8)
            for candidate in self.circle_contours(observation, depth_edges):
                if candidate.depth is None:
                    continue
                x, y, w, h = candidate.box
                if any(x <= obj.center[0] < x+w and y <= obj.center[1] < y+h for obj in results):
                    continue
                # A raised target has a farther background outside its rim.
                # Reject holes, including circular patches of missing depth.
                u, v = candidate.center
                radius = max(w, h) / 2
                left, top = max(0, x-5), max(0, y-5)
                patch = depth[top:y+h+5, left:x+w+5]
                yy, xx = np.ogrid[top:top+patch.shape[0], left:left+patch.shape[1]]
                distance2 = (xx-u)**2 + (yy-v)**2
                ring = (distance2 >= (radius+2)**2) & (distance2 <= (radius+5)**2)
                background = patch[ring & valid[top:y+h+5, left:x+w+5]]
                if (background.size and background.size >= self.config['depth_minimum_fraction'] * ring.sum()
                        and np.median(background) - candidate.depth >= threshold):
                    results.append(candidate)
        return sorted(results, key=lambda item: item.center)

    def circle_contours(self, observation, edges):
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        height, width = edges.shape
        accepted = set()
        results = []
        for index, contour in enumerate(contours):
            parent = hierarchy[0, index, 3]
            if parent in accepted:
                accepted.add(index)
                continue
            area = cv2.contourArea(contour)
            if area < self.config['minimum_area']:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if min(x, y, width-x-w, height-y-h) < self.config['border_pixels']:
                continue
            (u, v), radius = cv2.minEnclosingCircle(contour)
            fill = area / (np.pi * radius**2)
            if fill < self.config['minimum_circle_fill']:
                continue
            mask = np.zeros((h, w), np.uint8)
            cv2.drawContours(mask, [contour], 0, 255, -1, offset=(-x, -y))
            roi = observation.rgb[y:y+h, x:x+w]
            hue = float(np.median(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 0][mask != 0]))
            results.append(Detection((x, y, w, h), (u, v), fill, area, hue,
                                     self.sample_depth(observation, u, v)))
            accepted.add(index)
        return results


def make_detector(config) -> DetectionBackend:
    if config['backend'] == 'round':
        return RoundDetector(config)
    if config['backend'] == 'hsv':
        return ClassicalDetector(config)
    raise ValueError('Unknown detection backend')


class Tracker:
    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.target = None

    def lock(self, detection):
        self.target = detection

    def update(self, detections):
        if self.target is None:
            return None
        previous = self.target
        candidates = []
        for detection in detections:
            distance = np.linalg.norm(np.subtract(detection.center, previous.center))
            ratio = max(detection.area, previous.area) / min(detection.area, previous.area)
            if (distance <= self.config['tracking_radius_pixels']
                    and ratio <= self.config['tracking_area_ratio']
                    and abs(detection.hue - previous.hue) <= self.config['tracking_hue_tolerance']):
                candidates.append(detection)
        if len(candidates) != 1:
            self.reset()
            return None
        self.target = candidates[0]
        return self.target


def select_roi(detections, roi, width, height):
    if len(roi) != 4 or any(not np.isfinite(value) for value in roi):
        raise ValueError('Invalid ROI')
    left, top, right, bottom = roi
    if not (0 <= left <= width and 0 <= right <= width and 0 <= top <= height and 0 <= bottom <= height):
        raise ValueError('ROI is outside the image')
    if left >= right or top >= bottom:
        raise ValueError('ROI must have positive width and height')
    matches = [d for d in detections if left <= d.center[0] < right
               and top <= d.center[1] < bottom]
    if len(matches) != 1:
        raise ValueError('Select an ROI containing exactly one object')
    return matches[0]
