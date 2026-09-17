"""Monotonic admission gate for authoritative scene baselines."""

REQUIRED = {
    'HARDWARE_READY': 'HARDWARE_NOT_READY',
    'PASSIVE_CAPTURE_READY': 'PASSIVE_CAPTURE_NOT_READY',
    'RGB_FRESH': 'RGB_STALE', 'DEPTH_FRESH': 'DEPTH_STALE',
    'RGB_CAMERAINFO_FRESH': 'RGB_CAMERAINFO_STALE',
    'DEPTH_CAMERAINFO_FRESH': 'DEPTH_CAMERAINFO_STALE',
    'DEPTH_STABLE': 'DEPTH_UNSTABLE',
    'RGB_DEPTH_CAMERAINFO_SYNCHRONIZED': 'RGB_DEPTH_CAMERAINFO_NOT_SYNCHRONIZED',
    'TCP_FRESH': 'TCP_STALE', 'JOINTS_FRESH': 'JOINTS_STALE',
    'ROBOT_STABLE': 'ROBOT_NOT_STABLE', 'ALARM_FREE': 'ALARM_ACTIVE',
    'POINT_CLOUD_USABLE': 'POINT_CLOUD_UNUSABLE',
    'SCENE_GEOMETRY_PASS': 'SCENE_GEOMETRY_FAILED',
    'DOMINANT_PLANE_PASS': 'DOMINANT_PLANE_FAILED',
}


class AuthoritativeBaselineAdmissionGate:
    def __init__(self, required_stable_s=10.0):
        self.required_stable_s = required_stable_s
        self.since = None
        self.blockers = []
        self.last_reset_gate = 'NONE'
        self.last_reset_time = None
        self.reset_count = 0

    def update(self, snapshot, now_monotonic):
        blockers = [gate for key, gate in REQUIRED.items()
                    if not bool(snapshot.get(key, False))]
        if blockers:
            if self.since is not None or blockers != self.blockers:
                self.last_reset_gate = blockers[0]
                self.last_reset_time = now_monotonic
                self.reset_count += 1
            self.since = None
        elif self.since is None:
            self.since = now_monotonic
        self.blockers = blockers
        return self.status(now_monotonic)

    def status(self, now_monotonic):
        stable = 0.0 if self.since is None else max(0.0, now_monotonic - self.since)
        return {
            'eligible': not self.blockers and stable >= self.required_stable_s,
            'stable_for_s': stable,
            'required_stable_s': self.required_stable_s,
            'blockers': list(self.blockers),
            'current_blockers': list(self.blockers),
            'last_reset_gate': self.last_reset_gate,
            'last_reset_time': self.last_reset_time,
            'reset_count': self.reset_count,
        }

    def evaluate_for_baseline(self, now_monotonic):
        value = self.status(now_monotonic)
        if value['blockers']:
            return {'accepted': False, 'exact_gate': value['blockers'][0],
                    'reasons': value['blockers'], **value}
        if not value['eligible']:
            return {'accepted': False, 'exact_gate': 'READINESS_STABILITY_WINDOW_NOT_MET',
                    'reasons': ['READINESS_STABILITY_WINDOW_NOT_MET'], **value}
        return {'accepted': True, 'exact_gate': 'PASS', 'reasons': [], **value}
