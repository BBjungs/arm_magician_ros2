#!/usr/bin/env python3
"""Read-only live passive-calibration gate monitor; it never sends motion."""

import argparse
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class PassiveDiagnostic(Node):
    def __init__(self):
        super().__init__('passive_calibration_diagnostic')
        self.status = None
        self.received_at = None
        self.create_subscription(String, '/calibration/status', self._status, 10)

    def _status(self, message):
        try:
            self.status = json.loads(message.data)
            self.received_at = time.monotonic()
        except (TypeError, ValueError, json.JSONDecodeError):
            return

    def report(self, elapsed):
        value = self.status or {}
        readiness = value.get('readiness', {})
        hardware = value.get('hardware_readiness', {})
        metrics = value.get('depth_quality', {})
        gate = value.get('AUTHORITATIVE_BASELINE_EXACT_GATE', 'STATUS_MISSING')
        print('[%05.1f] RGB=%s DEPTH=%s RGB_INFO=%s DEPTH_INFO=%s SYNC=%s' % (
            elapsed, value.get('RGB_FRESH'), value.get('DEPTH_FRESH'),
            value.get('RGB_CAMERAINFO_FRESH'), value.get('DEPTH_CAMERAINFO_FRESH'),
            value.get('RGB_DEPTH_CAMERAINFO_SYNCHRONIZED')))
        print('         TCP=%s JOINTS=%s ROBOT_STABLE=%s ALARM_FREE=%s POINT_CLOUD=%s' % (
            hardware.get('tcp_fresh'), hardware.get('joints_fresh'),
            readiness.get('robot_stability', {}).get('reason', '') == '',
            not bool(value.get('alarm_state', {}).get('codes')),
            readiness.get('point_cloud_source_usable')))
        print('         depth=%s stable=%0.2f/%0.2f exact=%s blockers=%s reset=%s' % (
            metrics.get('status'), value.get('AUTHORITATIVE_BASELINE_STABLE_FOR_S', 0.0),
            value.get('AUTHORITATIVE_BASELINE_REQUIRED_STABLE_S', 10.0), gate,
            value.get('AUTHORITATIVE_BASELINE_CURRENT_BLOCKERS', []),
            value.get('AUTHORITATIVE_BASELINE_LAST_RESET_GATE', 'NONE')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=20.0)
    args = parser.parse_args()
    rclpy.init()
    node = PassiveDiagnostic()
    start = time.monotonic(); next_report = start
    try:
        while rclpy.ok() and time.monotonic() - start < args.duration:
            rclpy.spin_once(node, timeout_sec=0.2)
            if time.monotonic() >= next_report:
                node.report(time.monotonic() - start)
                next_report += 1.0
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
