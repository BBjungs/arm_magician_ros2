"""Deterministic textured tabletop renderer; no calibration targets."""

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from dobot_calibration.geometry import Mount, apply, inverse, transform
from dobot_calibration.registration import make_capture
from dobot_calibration.workflow import calibration_poses


TRUE_X = transform(Rotation.from_euler('xyz', [180, 5, 7], degrees=True).as_matrix(),
                   [0.035, -0.012, 0.090])
START = transform(translation=[0.19, 0.0, 0.125])
K = np.array([[440., 0, 320.], [0, 440., 240.], [0, 0, 1.]])
HINT = transform(Rotation.from_euler('xyz', [179, 7, 11], degrees=True).as_matrix(),
                 [0.040, -0.015, 0.090])
MOUNT = Mount(HINT, 0.001, 0.105, 'synthetic CAD fixture', 'synthetic-mount-v1')

_rng = np.random.default_rng(123)
_texture = _rng.integers(0, 256, (1500, 1500, 3), dtype=np.uint8)
_texture = cv2.GaussianBlur(_texture, (5, 5), 0.8)
_texture = cv2.convertScaleAbs(_texture, alpha=2, beta=-120)


def render(pose, stamp, value=TRUE_X, blank=False, flat=False):
    yy, xx = np.mgrid[:480, :640]
    rays = np.stack([(xx - K[0, 2]) / K[0, 0], (yy - K[1, 2]) / K[1, 1],
                     np.ones_like(xx)], axis=-1)
    camera = pose @ value
    world_rays = rays @ camera[:3, :3].T
    origin = camera[:3, 3]
    surfaces = [(-0.10, -1, 1, -1, 1)]
    if not flat:
        surfaces += [(-0.085, 0.14, 0.31, -0.10, 0.08),
                     (-0.020, 0.37, 0.43, 0.09, 0.15),
                     (-0.065, 0.24, 0.31, -0.16, -0.11)]
    depth = np.full((480, 640), np.inf)
    for z, xmin, xmax, ymin, ymax in surfaces:
        t = (z - origin[2]) / world_rays[:, :, 2]
        points = origin + world_rays * t[:, :, None]
        mask = ((points[:, :, 0] >= xmin) & (points[:, :, 0] <= xmax)
                & (points[:, :, 1] >= ymin) & (points[:, :, 1] <= ymax)
                & (t > 0) & (t < depth))
        depth[mask] = t[mask]
    points = origin + world_rays * depth[:, :, None]
    map_x = ((points[:, :, 0] + 0.3) * 1500).astype(np.float32)
    map_y = ((points[:, :, 1] + 0.5) * 1500).astype(np.float32)
    rgb = cv2.remap(_texture, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if blank:
        rgb[:] = 100
    cloud = (rays * depth[:, :, None])[::3, ::3].reshape(-1, 3)
    return make_capture(stamp, pose, rgb, depth, K, cloud, MOUNT.tool_T_camera)


def training():
    return [render(pose, 100 + i * 2) for i, pose in enumerate([START, *calibration_poses(START)])]


def held_out():
    return [render(pose, 200 + i * 2) for i, pose in enumerate(calibration_poses(START, True))]
