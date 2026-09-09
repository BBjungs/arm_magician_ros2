import math
import cv2
import numpy as np


def depth_to_mm(depth, encoding, scale_16uc1=1.0):
    if encoding in ('16UC1', 'mono16'):
        return depth.astype(np.float32) * float(scale_16uc1)
    if encoding == '32FC1':
        return depth.astype(np.float32) * 1000.0
    raise ValueError(f'unsupported depth encoding: {encoding}')


def robust_depth(depth_mm, mask, minimum_mm, maximum_mm, min_valid_ratio=0.60, trim=0.10):
    selected = depth_mm[mask > 0]
    if selected.size == 0:
        return {'depth_valid': False, 'depth_mm': None, 'depth_valid_ratio': 0.0, 'depth_stddev': None}
    valid = selected[np.isfinite(selected) & (selected > 0) &
                     (selected >= minimum_mm) & (selected <= maximum_mm)]
    ratio = float(valid.size / selected.size)
    if valid.size == 0:
        return {'depth_valid': False, 'depth_mm': None, 'depth_valid_ratio': round(ratio, 4), 'depth_stddev': None}
    ordered = np.sort(valid)
    cut = int(len(ordered) * trim)
    trimmed = ordered[cut:len(ordered) - cut] if cut and len(ordered) > cut * 2 else ordered
    return {
        'depth_valid': ratio >= min_valid_ratio,
        'depth_mm': round(float(np.median(valid)), 3),
        'depth_trimmed_mean_mm': round(float(np.mean(trimmed)), 3),
        'depth_valid_ratio': round(ratio, 4),
        'depth_stddev': round(float(np.std(valid)), 3),
    }


def contour_mask(shape, contour, erode_px=2):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    if erode_px > 0:
        kernel = np.ones((erode_px * 2 + 1,) * 2, np.uint8)
        mask = cv2.erode(mask, kernel)
    return mask


def deproject_pixel(u, v, depth_mm, intrinsics):
    fx, fy, cx, cy = (float(intrinsics[key]) for key in ('fx', 'fy', 'cx', 'cy'))
    if not all(math.isfinite(value) for value in (u, v, depth_mm, fx, fy, cx, cy)) or fx <= 0 or fy <= 0 or depth_mm <= 0:
        raise ValueError('finite positive depth and focal lengths are required')
    return {'x': (u - cx) * depth_mm / fx, 'y': (v - cy) * depth_mm / fy, 'z': depth_mm}


def physical_size(pixel_width, pixel_height, depth_mm, intrinsics):
    return {
        'width_mm': pixel_width * depth_mm / float(intrinsics['fx']),
        'height_mm': pixel_height * depth_mm / float(intrinsics['fy']),
    }
