"""Fail-closed readiness lease for picking clients."""

import json
import math
import time


class ReadinessLease:
    """A saved PASS or stale transient-local message never authorizes picking."""

    def __init__(self, timeout_s=1.0):
        self.timeout_s = timeout_s
        self.received = None
        self.stamp = None
        self.valid = False

    def update(self, payload, ros_now, monotonic_now=None):
        monotonic_now = time.monotonic() if monotonic_now is None else monotonic_now
        self.valid = False
        try:
            status = json.loads(payload)
            stamp = float(status['stamp'])
            if (not math.isfinite(stamp) or not 0 <= ros_now - stamp < self.timeout_s
                    or (self.stamp is not None and stamp <= self.stamp)):
                return
            self.stamp, self.received = stamp, monotonic_now
            self.valid = (status.get('ready') is True and status.get('state') == 'READY'
                          and status.get('result') == 'PASS')
        except (ValueError, TypeError, KeyError):
            return

    def ready(self, ros_now, monotonic_now=None):
        monotonic_now = time.monotonic() if monotonic_now is None else monotonic_now
        return (self.valid and self.received is not None and self.stamp is not None
                and 0 <= monotonic_now - self.received < self.timeout_s
                and 0 <= ros_now - self.stamp < self.timeout_s)


class PickingGuard:
    def __init__(self, node, on_invalidated):
        from rclpy.qos import DurabilityPolicy, QoSProfile
        from std_msgs.msg import String
        self.node, self.on_invalidated = node, on_invalidated
        self.lease, self.started = ReadinessLease(), False
        self.subscription = node.create_subscription(
            String, '/calibration/status', self.on_status,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.timer = node.create_timer(0.2, self.check)

    def now(self):
        return self.node.get_clock().now().nanoseconds * 1e-9

    def ready(self):
        return self.lease.ready(self.now())

    def on_status(self, message):
        self.lease.update(message.data, self.now())
        self.check()

    def check(self):
        if self.started and not self.ready():
            self.on_invalidated()

    def require_ready(self):
        if not self.ready():
            raise RuntimeError('Picking blocked: calibration is missing, failed or stale')
        self.started = True
