"""Fail-closed live hardware readiness, independent of calibration quality."""

from collections import deque
from dataclasses import asdict, dataclass


READINESS_STATES = (
    'READY', 'DEPTH_ERROR', 'ROBOT_TELEMETRY_ERROR', 'ROBOT_ALARM',
    'SAFETY_UNVERIFIED', 'SENSOR_ERROR', 'NOT_READY',
)


@dataclass(frozen=True)
class HardwareReadiness:
    state: str
    ready: bool
    reason: str
    blockers: tuple
    depth_fresh: bool
    depth_stable: bool
    tcp_fresh: bool
    joints_fresh: bool
    alarms_fresh: bool
    robot_connected: bool
    safety_supported: bool
    safety_verified: bool
    physical_estop_present: bool
    operator_safety_verified: bool
    software_estop_monitoring: str

    def to_dict(self):
        value = asdict(self)
        value['blockers'] = list(self.blockers)
        return value


def _fresh(now, stamp, ttl):
    return stamp is not None and 0.0 <= now - stamp <= ttl


def evaluate_hardware_readiness(
        *, now, depth_quality, depth_stamp, depth_stable,
        tcp_stamp, joints_stamp, alarm_stamp, alarms, robot_connected,
        safety_supported, safety_verified, sensor_error='',
        physical_estop_present=False, operator_safety_verified=False,
        workspace_valid=True, safe_z_valid=True, depth_ttl_s=0.5,
        robot_ttl_s=0.5, alarm_ttl_s=0.6):
    """Return the single highest-priority readiness state and every blocker.

    Calibration/optimizer state is deliberately not an input. A mathematical
    PASS can therefore never promote live hardware readiness.
    """
    depth_fresh = _fresh(now, depth_stamp, depth_ttl_s)
    tcp_fresh = _fresh(now, tcp_stamp, robot_ttl_s)
    joints_fresh = _fresh(now, joints_stamp, robot_ttl_s)
    alarms_fresh = _fresh(now, alarm_stamp, alarm_ttl_s)
    blockers = []

    if sensor_error:
        blockers.append(sensor_error)
    if depth_quality is None:
        blockers.append('DEPTH_MISSING: no live depth frame has been received')
    elif depth_quality.get('status') != 'VALID_DEPTH':
        code = depth_quality.get('code') or 'DEPTH_INVALID'
        reason = depth_quality.get('reason') or 'live depth is invalid'
        blockers.append(f'{code}: {reason}')
    if not depth_fresh:
        blockers.append('DEPTH_STALE: live depth timestamp is missing or stale')
    if not depth_stable:
        blockers.append('DEPTH_UNSTABLE: insufficient consecutive valid depth frames')
    if not tcp_fresh:
        blockers.append('TCP_MISSING_OR_STALE: TCP telemetry is missing or stale')
    if not joints_fresh:
        blockers.append('JOINTS_MISSING_OR_STALE: joint telemetry is missing or stale')
    if not alarms_fresh:
        blockers.append('ALARMS_MISSING_OR_STALE: alarm telemetry is missing or stale')
    if not robot_connected:
        blockers.append('ROBOT_CONNECTION_UNKNOWN: no fresh hardware response proves the serial connection')
    if alarms_fresh and alarms:
        blockers.append('ROBOT_ALARM: active alarm codes ' + ','.join(map(str, alarms)))
    physical_operator_safe = physical_estop_present and operator_safety_verified
    if not safety_supported and not physical_operator_safe:
        blockers.append('SAFETY_SIGNAL_UNAVAILABLE: the driver exposes no hardware E-stop/safety state')
    elif safety_supported and not safety_verified:
        blockers.append('SAFETY_NOT_SAFE: the live hardware safety signal is not in the safe state')
    if not workspace_valid:
        blockers.append('WORKSPACE_INVALID: current or requested pose is outside the calibration workspace')
    if not safe_z_valid:
        blockers.append('SAFE_Z_INVALID: safe table clearance has not been established')

    if sensor_error:
        state = 'SENSOR_ERROR'
    elif depth_quality is None or depth_quality.get('status') != 'VALID_DEPTH' or not depth_fresh or not depth_stable:
        state = 'DEPTH_ERROR'
    elif not tcp_fresh or not joints_fresh or not alarms_fresh or not robot_connected:
        state = 'ROBOT_TELEMETRY_ERROR'
    elif alarms:
        state = 'ROBOT_ALARM'
    elif (not physical_operator_safe and not safety_supported) or (safety_supported and not safety_verified):
        state = 'SAFETY_UNVERIFIED'
    elif not workspace_valid or not safe_z_valid:
        state = 'NOT_READY'
    else:
        state = 'READY'
    return HardwareReadiness(
        state=state, ready=state == 'READY',
        reason='' if state == 'READY' else blockers[0], blockers=tuple(blockers),
        depth_fresh=depth_fresh, depth_stable=bool(depth_stable),
        tcp_fresh=tcp_fresh, joints_fresh=joints_fresh,
        alarms_fresh=alarms_fresh, robot_connected=bool(robot_connected),
        safety_supported=bool(safety_supported), safety_verified=bool(safety_verified),
        physical_estop_present=bool(physical_estop_present),
        operator_safety_verified=bool(operator_safety_verified),
        software_estop_monitoring=('CONNECTED' if safety_supported else 'NOT CONNECTED'),
    )


class DepthStabilityWindow:
    """Require a short run of consecutive valid, advancing depth frames."""

    def __init__(self, minimum_frames=8, horizon_s=10.0, maximum_gap_s=1.5):
        self.minimum_frames = int(minimum_frames)
        self.horizon_s = float(horizon_s)
        self.maximum_gap_s = float(maximum_gap_s)
        self._samples = deque(maxlen=60)

    def add(self, stamp, quality):
        stamp = float(stamp)
        valid = quality.get('status') == 'VALID_DEPTH'
        if self._samples and stamp < self._samples[-1][0]:
            self._samples.clear()
        elif self._samples and stamp == self._samples[-1][0]:
            previous = self._samples[-1][1]
            self._samples[-1] = (stamp, previous and valid)
            return
        self._samples.append((stamp, valid))

    def stable(self, now):
        samples = [(stamp, valid) for stamp, valid in self._samples
                   if 0.0 <= now - stamp <= self.horizon_s]
        if len(samples) < self.minimum_frames or not all(valid for _, valid in samples):
            return False
        gaps = [b[0] - a[0] for a, b in zip(samples, samples[1:])]
        return bool(gaps) and min(gaps) > 0.0 and max(gaps) <= self.maximum_gap_s
