"""Passive inspection of existing ROS topics. This command opens no device."""

import argparse
import json
import time
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from .config import load
from .ros_sensors import CameraReceiver, RobotReceiver
from .safety import Safety


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(
        get_package_share_directory('dobot_auto_center')) / 'config')
    parser.add_argument('--seconds', type=float, default=4.)
    args = parser.parse_args(remove_ros_args()[1:])
    if not 0 < args.seconds <= 60:
        parser.error('--seconds must be in (0, 60]')
    config = load(args.config)
    clock = time.monotonic
    rclpy.init()
    node = Node('dobot_readiness_passive')
    try:
        camera = CameraReceiver(node, config['camera'], clock)
        robot = RobotReceiver(node, config['hardware'], clock)
        safety = Safety(config)
        deadline = clock() + args.seconds
        frame = None
        while clock() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            candidate = camera.take(clock())
            if candidate is not None:
                frame = candidate
        now = clock()
        readback = robot.snapshot()
        health = 'Fresh, valid and alarm-free'
        try:
            safety.health(readback, now)
        except ValueError as error:
            health = str(error)
        depth = bool(frame and frame.registered(now, config['camera']))
        rgb = bool(frame and frame.fresh(now, config['camera']['freshness']))
        device = robot.samples.get('device')
        report = {
            'hardware_motion_enabled': False,
            'scene': 'Passive ROS topic inspection. Source provenance requires operator verification.',
            'rgb_fresh': rgb, 'aligned_depth_fresh': depth, 'camera_info_valid': camera.info is not None,
            'robot_readback': health, 'tcp_mm_deg': readback.pose if readback.connected else None,
            'joint_deg': readback.joints if readback.connected else None,
            'alarm_codes': readback.alarms if readback.alarm_valid else None,
            'firmware_version': list(device[1].firmware_version) if device else None,
            'required_on_site': ['camera/tool mount and depth alignment', 'physical E-stop',
                                 'workspace and swept collision model', 'HOME/observation behavior',
                                 'controller stop/cancel and recovery'],
        }
        print(json.dumps(report, indent=2))
        return 0 if rgb and depth and health == 'Fresh, valid and alarm-free' else 1
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
