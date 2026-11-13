"""Ray-cast textured asymmetric stepped object with independent background."""
import cv2
import numpy as np

from synthetic_scene import K, TRUE_X, MOUNT, START, _texture
from dobot_calibration.object_reference import make_object_capture


def render_object(pose=START, stamp=1., *, shift=0., blank=False, noise=0., value=TRUE_X):
    yy, xx = np.mgrid[:480, :640]
    rays = np.stack([(xx - K[0, 2]) / K[0, 0], (yy - K[1, 2]) / K[1, 1],
                     np.ones_like(xx)], axis=-1)
    camera = pose @ value
    world_rays = rays @ camera[:3, :3].T
    origin = camera[:3, 3]
    depth = (-.25 - origin[2]) / world_rays[:, :, 2]
    mask = np.zeros(depth.shape, bool)
    for z, xmin, xmax, ymin, ymax in [(-.07, .10, .40, -.10, .08),
                                     (-.035, .15, .28, -.08, .03),
                                     (.005, .28, .38, -.08, -.02)]:
        t = (z - origin[2]) / world_rays[:, :, 2]
        world = origin + world_rays * t[:, :, None]
        hit = ((world[:, :, 0] >= xmin + shift) & (world[:, :, 0] <= xmax + shift)
               & (world[:, :, 1] >= ymin) & (world[:, :, 1] <= ymax)
               & (t > 0) & (t < depth))
        depth[hit] = t[hit]; mask |= hit
    world = origin + world_rays * depth[:, :, None]
    map_x = ((world[:, :, 0] - shift + .3) * 1500).astype(np.float32)
    map_y = ((world[:, :, 1] + .5) * 1500).astype(np.float32)
    rgb = cv2.remap(_texture, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if blank:
        rgb[:] = 100
    if noise:
        depth += np.random.default_rng(int(stamp * 100)).normal(0, noise, depth.shape)
    mask = cv2.erode(mask.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    return rgb, depth, mask


def capture(pose=START, stamp=1., **kwargs):
    rgb, depth, mask = render_object(pose, stamp, **kwargs)
    value = make_object_capture(stamp, pose, rgb, depth, K, mask,
                                identity={'shape': 'polygon', 'color': 'mixed', 'class_name': 'reference'})
    value.quality['exposure'] = {'joints': np.zeros(4).tolist(), 'rgb_stamp': stamp,
        'depth_stamp': stamp, 'intrinsics_fingerprint': 'synthetic-object', 'camera_info': {}}
    return value


def packet(rgb, mask, stamp=1.):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    outline = cv2.approxPolyDP(max(contours, key=cv2.contourArea), 1., True).reshape(-1, 2).tolist()
    return {'registered_depth': True, 'error': '', 'rgb_frame_id': 'optical', 'depth_frame_id': 'optical',
            'image_size': [640, 480], 'rgb_stamp': stamp, 'depth_stamp': stamp,
            'detections': [{'shape': 'polygon', 'color': 'mixed', 'class_name': 'reference',
                            'confidence': .95, 'calibration_outline': outline,
                            'pick_eligible': False, 'rejection_reason': 'table_unavailable'}]}
