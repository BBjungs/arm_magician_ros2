"""Fail-closed checks for stationary eye-in-hand captures; units mm/deg.

Receipt-time proximity is not exact RGB/TCP synchronization or a motion interlock.
"""

import math


def validate_stationary_capture(reference, records):
    def pose_values(pose):
        if pose is None or len(pose) != 4:
            raise ValueError('Fresh TCP pose is required for every calibration frame')
        values = [float(v) for v in pose]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('TCP pose must be finite')
        return values

    start = pose_values(reference)
    if not records:
        raise ValueError('Calibration capture has no TCP timing evidence')
    for record in records:
        if record.get('motion_active'):
            raise ValueError('A robot motion goal was active during calibration')
        pose = pose_values(record.get('tcp_pose_mm_deg'))
        delta = record.get('frame_to_tcp_receive_delta_ms')
        if delta is None or not math.isfinite(float(delta)) or not 0 <= float(delta) <= 500:
            raise ValueError('TCP/image receive times differ by more than 500 ms; retry')
        distance = math.dist(start[:3], pose[:3])
        rotation = abs((pose[3] - start[3] + 180.0) % 360.0 - 180.0)
        if distance > 0.5 or rotation > 0.2:
            raise ValueError('Robot moved during calibration; keep the arm still and retry')
