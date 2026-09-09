"""Rendered metric disks on a slanted table; exact camera-space ground truth."""
import cv2
import numpy as np
from dobot_object_vision.detector import rays

K = np.array([[600., 0., 320.], [0., 600., 240.], [0., 0., 1.]])
COLORS = {'black': (25, 25, 25), 'white': (225, 225, 225), 'yellow': (10, 210, 230)}


def scene(tilt=0., noise=0.0002, objects=None, background=125):
    objects = objects if objects is not None else [
        ('black', (150, 230), 0.022, 0.012),
        ('white', (320, 240), 0.019, 0.015),
        ('yellow', (485, 245), 0.026, 0.020)]
    theta = np.deg2rad(tilt)
    plane = np.array([np.sin(theta), 0., -np.cos(theta), 0.6 * np.cos(theta)])
    yy, xx = np.indices((480, 640))
    ray = rays(np.c_[xx.ravel(), yy.ravel()], K).reshape(480, 640, 3)
    depth = -plane[3] / (ray @ plane[:3])
    bgr = np.full((480, 640, 3), background, dtype=np.uint8)
    truth = []
    for label, uv, radius, height in objects:
        center_ray = rays([uv], K)[0]
        center = center_ray * ((height - plane[3]) / (center_ray @ plane[:3]))
        top_depth = (height - plane[3]) / (ray @ plane[:3])
        points = ray * top_depth[:, :, None]
        mask = np.linalg.norm(points - center, axis=2) <= radius
        bgr[mask] = COLORS.get(label, (200, 40, 20))
        depth[mask] = top_depth[mask]
        truth.append({'class_name': label, 'center': center, 'uv': uv,
                      'diameter': radius * 2, 'height': height, 'mask': mask})
    rng = np.random.default_rng(14)
    depth += rng.normal(0, noise, depth.shape)
    return bgr, depth, truth, plane
