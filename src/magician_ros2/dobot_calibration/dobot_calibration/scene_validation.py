"""Same-viewpoint scene comparison using the existing baseline thresholds."""

import numpy as np


def compare_scene(base, current):
    values = {
        'plane_angle_deg': float(np.rad2deg(np.arccos(np.clip(
            abs(np.dot(base['plane'][:3], current['plane'][:3])), -1., 1.)))),
        'extent_change_m': float(np.max(np.abs(
            np.asarray(base['extent_m']) - current['extent_m']))),
        'depth_histogram_l1': float(np.mean(np.abs(
            np.asarray(base['depth_histogram']) - current['depth_histogram']))),
        'voxel_change_ratio': abs(base['voxel_occupancy'] - current['voxel_occupancy'])
                              / max(base['voxel_occupancy'], 1),
        'feature_change_ratio': abs(base['feature_count'] - current['feature_count'])
                                / max(base['feature_count'], 1),
    }
    thresholds = {'plane_angle_deg': 2., 'extent_change_m': .020, 'depth_histogram_l1': .15,
                  'voxel_change_ratio': .25, 'feature_change_ratio': .40}
    blockers = [key for key, value in values.items()
                if not np.isfinite(value) or value > thresholds[key]]
    return {'passed': not blockers, 'blockers': blockers, **values}
