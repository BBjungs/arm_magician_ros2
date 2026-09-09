import numpy as np
import pytest
from dobot_vision_rgbd.depth_geometry import deproject_pixel, physical_size, robust_depth


def test_median_outliers_and_invalid_values():
    depth = np.array([[0, 500, 501], [499, 5000, 500]], np.float32)
    mask = np.full(depth.shape, 255, np.uint8)
    result = robust_depth(depth, mask, 100, 2000, min_valid_ratio=0.5)
    assert result['depth_valid']
    assert result['depth_mm'] == 500.0
    assert result['depth_valid_ratio'] == pytest.approx(4 / 6, abs=1e-4)


def test_nan_zero_depth_invalid():
    depth = np.array([[0, np.nan], [np.inf, 0]], np.float32)
    result = robust_depth(depth, np.full((2, 2), 255, np.uint8), 100, 2000)
    assert not result['depth_valid']
    assert result['depth_mm'] is None


def test_deprojection_and_physical_size():
    intrinsics = {'fx': 600, 'fy': 600, 'cx': 320, 'cy': 240}
    assert deproject_pixel(320, 240, 500, intrinsics) == {'x': 0, 'y': 0, 'z': 500}
    size = physical_size(60, 30, 500, intrinsics)
    assert size == {'width_mm': 50, 'height_mm': 25}
