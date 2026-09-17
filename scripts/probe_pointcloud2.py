#!/usr/bin/env python3
"""Read-only PointCloud2 transport probe; sends no robot or camera commands."""
import argparse
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud2


def stamp(message):
    return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9


class Probe(Node):
    def __init__(self, topic, duration):
        super().__init__('pointcloud2_probe')
        self.topic, self.duration, self.start = topic, duration, time.monotonic()
        self.samples = []
        self.create_subscription(PointCloud2, topic, self.callback, qos_profile_sensor_data)
        self.create_timer(0.1, self.done)

    def callback(self, message):
        self.samples.append((time.monotonic(), stamp(message), message.header.frame_id,
                             message.width * message.height, message.is_dense))

    def done(self):
        if time.monotonic() - self.start < self.duration:
            return
        info = self.get_publishers_info_by_topic(self.topic)
        stamps = [s[1] for s in self.samples]
        advancing = sum(b > a for a, b in zip(stamps, stamps[1:]))
        elapsed = max(time.monotonic() - self.start, 1e-9)
        print({'topic': self.topic, 'publisher_count': len(info),
               'publishers': [{'node': x.node_name, 'namespace': x.node_namespace,
                               'qos': str(x.qos_profile)} for x in info],
               'callbacks': len(self.samples), 'rate_hz': len(self.samples) / elapsed,
               'timestamp_advancing_transitions': advancing,
               'first_stamp': stamps[0] if stamps else None,
               'last_stamp': stamps[-1] if stamps else None,
               'frame_ids': sorted(set(s[2] for s in self.samples)),
               'point_counts': [s[3] for s in self.samples[-3:]]})
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', default='/camera/depth/points')
    parser.add_argument('--duration', type=float, default=20.0)
    args = parser.parse_args()
    rclpy.init()
    node = Probe(args.topic, args.duration)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()


if __name__ == '__main__':
    main()
