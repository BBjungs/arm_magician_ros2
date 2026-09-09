import cv2
import numpy as np
from .depth_geometry import robust_depth


def local_ring_depth(depth_mm, object_mask, dilate_px, minimum_mm, maximum_mm, min_valid_ratio=0.30):
    kernel = np.ones((dilate_px * 2 + 1,) * 2, np.uint8)
    outer = cv2.dilate(object_mask, kernel)
    ring = cv2.subtract(outer, object_mask)
    result = robust_depth(depth_mm, ring, minimum_mm, maximum_mm, min_valid_ratio, trim=0.10)
    return result, ring
