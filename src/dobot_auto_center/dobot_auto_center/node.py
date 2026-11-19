"""ROS graph and application lifecycle."""

import argparse
import os
from pathlib import Path
from threading import RLock
import time

from ament_index_python.packages import get_package_share_directory
import cv2
import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from .config import load
from .mock_camera import MockCamera
from .motion import Motion, MockTransport
from .ros_motion import ActionBridge
from .ros_sensors import CameraPublisher, CameraReceiver, RobotReceiver
from .safety import Safety
from .web import Access, serve
from .workflow import Workflow


class AutoCenterNode(Node):
    def __init__(self, config, secret):
        super().__init__('dobot_auto_center')
        self.config = config
        self.lock = RLock()
        self.clock = time.monotonic
        self.access = Access(config['web'], secret)
        self.simulated = config['hardware']['simulation_mode']
        self.robot = None if self.simulated else RobotReceiver(self, config['hardware'], self.clock)
        self.camera = CameraReceiver(self, config['camera'], self.clock)
        transport = MockTransport(config['motion']) if self.simulated else None
        self.motion = Motion(config, Safety(config), transport)
        self.action = ActionBridge(self, self.motion, self.lock, self.clock) if self.simulated else None
        self.workflow = Workflow(config, self.motion, self.action.submit if self.action else None,
                                 self.access.valid)
        if self.action:
            self.action.workflow = self.workflow
            self.mock_camera = MockCamera(config)
            self.mock_publisher = CameraPublisher(self, config['camera'], self.mock_camera,
                                                  lambda: self.motion.transport.pose)
        self.create_timer(0.025, self.tick)

    def tick(self):
        with self.lock:
            now = self.clock()
            if self.robot:
                self.motion.snapshot = self.robot.snapshot()
            observation = self.camera.take(now)
            if observation is not None:
                self.workflow.ingest(observation, now)
            self.workflow.tick(now)
            if self.action:
                self.action.tick()

    def close(self):
        with self.lock:
            self.workflow.stop(self.clock(), 'Controller shutting down')
            if self.action:
                self.action.destroy()


def main():
    share = Path(get_package_share_directory('dobot_auto_center'))
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=share / 'config')
    args = parser.parse_args(remove_ros_args()[1:])
    config = load(args.config)
    cv2.setNumThreads(1)
    rclpy.init()
    node = AutoCenterNode(config, os.environ.get('DOBOT_OPERATOR_TOKEN', ''))
    server = None
    try:
        server = serve(node, share / 'web')
        node.get_logger().info(f'Dashboard at http://{server.server_address[0]}:{server.server_address[1]}')
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if server:
            server.shutdown()
            server.server_close()
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()
