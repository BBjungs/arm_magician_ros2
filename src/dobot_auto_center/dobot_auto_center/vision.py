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

    def fresh(self, now, timeout):
        return 0 <= now - self.stamp <= timeout and 0 <= now - self.received <= timeout

    def registered(self, now, camera):
        return (self.calibrated and self.depth is not None
                and self.depth.shape == self.rgb.shape[:2]
                and self.fresh(now, camera['freshness'])
                and 0 <= now - self.depth_stamp <= camera['freshness']
                and abs(self.depth_stamp - self.stamp) <= camera['max_depth_skew'])


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
    def detect(self, observation: Observation) -> list[Detection]: ...


class ClassicalDetector:
    def __init__(self, config):
        self.config = config

    def detect(self, observation):
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


def make_detector(config) -> DetectionBackend:
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
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError('ROI is outside the image')
    matches = [d for d in detections if left <= d.center[0] <= right
               and top <= d.center[1] <= bottom]
    if len(matches) != 1:
        raise ValueError('Select an ROI containing exactly one object')
    return matches[0]
