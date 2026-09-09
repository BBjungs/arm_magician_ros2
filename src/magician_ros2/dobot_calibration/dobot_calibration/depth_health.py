"""Per-frame depth evidence used before and throughout calibration motion."""
import numpy as np
from .geometry import Limits


def depth_quality(values, encoding, limits=Limits()):
    array = np.asarray(values, dtype=float)
    report = {'status': 'SENSOR_ERROR', 'code': '', 'reason': '',
              'pixel_count': int(array.size), 'valid_count': 0,
              'depth_valid_ratio': 0., 'median_m': None, 'mad_m': None,
              'stddev_m': None, 'minimum_m': None, 'maximum_m': None}
    if encoding not in ('16UC1', '32FC1'):
        report.update(code='DEPTH_ENCODING_UNSUPPORTED', reason='Depth must be 16UC1 millimetres or 32FC1 metres')
        return report
    if array.ndim != 2 or array.size == 0:
        report.update(code='DEPTH_SHAPE_INVALID', reason='Depth image is empty or not two-dimensional')
        return report
    if encoding == '16UC1':
        array = array * .001
    finite = np.isfinite(array)
    valid = finite & (array >= limits.min_depth_m) & (array <= limits.max_depth_m)
    report.update(valid_count=int(valid.sum()), depth_valid_ratio=float(valid.mean()),
                  zero_count=int(np.count_nonzero(array == 0)),
                  nonfinite_count=int(np.count_nonzero(~finite)),
                  outside_range_count=int(np.count_nonzero(finite & ~valid)))
    if valid.any():
        selected = array[valid]
        median = float(np.median(selected))
        report.update(median_m=median, mad_m=float(1.4826 * np.median(np.abs(selected - median))),
                      stddev_m=float(np.std(selected)), minimum_m=float(np.min(selected)),
                      maximum_m=float(np.max(selected)))
    if report['zero_count'] == array.size:
        report.update(code='DEPTH_ALL_ZERO', reason='Every depth pixel is zero; no measured distance is available')
    elif report['depth_valid_ratio'] < limits.min_depth_valid_ratio:
        report.update(code='DEPTH_INSUFFICIENT_VALID_PIXELS',
                      reason='Depth-valid ratio is below the configured calibration threshold')
    else:
        # This establishes sensor depth support, not a stable table or calibration PASS.
        report.update(status='VALID_DEPTH', code='', reason='')
    return report
