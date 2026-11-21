"""Passive inspection of existing ROS topics. This command opens no device."""

import argparse
from collections import deque
import json
import time
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from .config import load
from .ros_sensors import CameraReceiver, RobotReceiver, live_camera_status
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
        stamps = deque(maxlen=60)
        while clock() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            candidate = camera.take(clock())
            if candidate is not None:
                frame = candidate
                if candidate.registered(clock(), config['camera']):
                    stamps.append(candidate.source_stamp)
                else:
                    stamps.clear()
        now = clock()
        readback = robot.snapshot()
        health = 'Fresh, valid and alarm-free'
        try:
            safety.health(readback, now)
        except ValueError as error:
            health = str(error)
        depth = bool(camera.device_name and frame and frame.registered(now, config['camera']))
        rgb = bool(camera.device_name and frame and frame.fresh(now, config['camera']['freshness']))
        device = robot.samples.get('device')
        report = {
            'hardware_motion_enabled': False,
            'camera_status': live_camera_status(rgb, depth),
            'camera_device': camera.device_name,
            'camera_topics': {kind: camera.config[f'{kind}_topic'] for kind in ('rgb', 'depth', 'info')},
            'camera_driver': camera.config['driver_node'] if rgb else None,
            'rgbd_fps': (round((len(stamps) - 1) / (stamps[-1] - stamps[0]), 1)
                         if depth and len(stamps) >= 2 and stamps[-1] > stamps[0] else None),
            'resolution': list(frame.rgb.shape[1::-1]) if rgb else None,
            'rgb_stamp': frame.source_stamp if rgb else None,
            'frame_age_ms': round((now - frame.stamp) * 1000) if rgb else None,
            'depth_skew_ms': round(abs(frame.depth_source_stamp - frame.source_stamp) * 1000, 1) if depth else None,
            'rgb_fresh': rgb, 'aligned_depth_fresh': depth, 'camera_info_valid': bool(rgb and frame.calibrated and frame.info_stamp is not None
                                            and 0 <= now - frame.info_stamp <= camera.config['freshness']),
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
