"""Read-only pose guidance for operator-positioned markerless captures."""

import numpy as np


XYZ_TOLERANCE_MM = 5.0
J4_TOLERANCE_DEG = 2.0


def calibration_plan(anchor_xyz_mm, anchor_j4_deg=0.0):
    """Ten absolute targets; target 2 is the commissioned translation-only pose."""
    anchor = np.asarray(anchor_xyz_mm, dtype=float)
    offsets = [
        (0.0, 0.0, 0.0, 0.0),
        (34.95935, 0.0, 0.10281, 0.0),  # exactly [185, 0, 100] for commissioned anchor
        (15.0, 30.0, 10.0, 0.0),
        (15.0, -30.0, 15.0, 0.0),
        (30.0, 20.0, 20.0, 15.0),
        (30.0, -20.0, 25.0, -15.0),
        (-5.0, 25.0, 10.0, 10.0),
        (10.0, -25.0, 30.0, -10.0),
        (35.0, 15.0, 15.0, 20.0),
        (-5.0, -25.0, 25.0, -20.0),
    ]
    result = []
    for index, (dx, dy, dz, dj4) in enumerate(offsets, start=1):
        xyz = anchor + [dx, dy, dz]
        result.append({'pose_index': index, 'xyz_mm': xyz.tolist(),
                       'j4_deg': float(anchor_j4_deg + dj4)})
    # User-authoritative commissioned Pose 2 target.
    result[1]['xyz_mm'] = [185.0, 0.0, 100.0]
    result[1]['j4_deg'] = 0.0
    return result


def compute_guidance(current_xyz_mm, current_j4_deg, target, stable, hardware_ready):
    current = np.asarray(current_xyz_mm, dtype=float)
    target_xyz = np.asarray(target['xyz_mm'], dtype=float)
    delta = target_xyz - current
    delta_j4 = float(target['j4_deg']) - float(current_j4_deg)
    axes = ('X', 'Y', 'Z')
    directions = {
        axis: ('OK' if abs(value) <= XYZ_TOLERANCE_MM else f'{"+" if value > 0 else "-"}{axis}')
        for axis, value in zip(axes, delta)
    }
    directions['J4'] = ('OK' if abs(delta_j4) <= J4_TOLERANCE_DEG
                        else ('J4_POSITIVE' if delta_j4 > 0 else 'J4_NEGATIVE'))
    within = bool(np.all(np.abs(delta) <= XYZ_TOLERANCE_MM)
                  and abs(delta_j4) <= J4_TOLERANCE_DEG)
    capture_enabled = bool(within and stable and hardware_ready)
    state = ('TARGET_REACHED' if capture_enabled else
             'WAIT_ROBOT_STABLE' if within and not stable else
             'WAIT_HARDWARE_READY' if within and not hardware_ready else
             'GUIDE_TO_TARGET')
    return {
        'state': state,
        'current': {'xyz_mm': current.tolist(), 'j4_deg': float(current_j4_deg)},
        'target': target,
        'delta': {'xyz_mm': delta.tolist(), 'j4_deg': delta_j4},
        'directions': directions,
        'distance_to_target_mm': float(np.linalg.norm(delta)),
        'xyz_tolerance_mm': XYZ_TOLERANCE_MM,
        'j4_tolerance_deg': J4_TOLERANCE_DEG,
        'robot_stable': bool(stable),
        'hardware_ready': bool(hardware_ready),
        'capture_enabled': capture_enabled,
        'automatic_capture': False,
    }
