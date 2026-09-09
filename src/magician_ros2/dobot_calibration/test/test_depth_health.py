import json
import numpy as np
import pytest
from dobot_calibration.depth_health import depth_quality


def test_zero_depth_is_sensor_error_with_no_invented_range():
    result = depth_quality(np.zeros((480, 640), np.uint16), '16UC1')
    assert result['status'] == 'SENSOR_ERROR'
    assert result['code'] == 'DEPTH_ALL_ZERO'
    assert result['pixel_count'] == result['zero_count'] == 307200
    assert result['median_m'] is None
    json.dumps(result, allow_nan=False)


def test_nan_and_out_of_range_depth_are_not_valid_samples():
    result = depth_quality(np.array([[np.nan, np.inf], [-1., 2.]]), '32FC1')
    assert result['valid_count'] == 0
    assert result['status'] == 'SENSOR_ERROR'
    assert result['median_m'] is None


def test_depth_units_share_the_existing_calibration_thresholds():
    metric = depth_quality(np.full((20, 20), .4), '32FC1')
    millimetres = depth_quality(np.full((20, 20), 400, np.uint16), '16UC1')
    assert metric == millimetres
    assert metric['status'] == 'VALID_DEPTH'
    assert metric['median_m'] == .4
