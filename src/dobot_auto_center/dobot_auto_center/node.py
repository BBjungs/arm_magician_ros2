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
from .web import Access, NetworkPolicy, serve
from .workflow import Workflow


class AutoCenterNode(Node):
    def __init__(self, config, secret):
        super().__init__('dobot_auto_center')
        self.config = config
        self.lock = RLock()
        self.clock = time.monotonic
        self.last_tick = None
        self.access = Access(config['web'], secret)
        self.simulated = config['hardware']['simulation_mode']
        self.robot = None if self.simulated else RobotReceiver(self, config['hardware'], self.clock)
        camera = config['camera'].copy()
        if self.simulated:
            for key in ('rgb_topic', 'depth_topic', 'info_topic'):
                camera[key] = '/dobot_auto_center/simulation/' + camera[key].lstrip('/')
        self.camera = CameraReceiver(self, camera, self.clock)
        transport = MockTransport(config['motion']) if self.simulated else None
        self.motion = Motion(config, Safety(config), transport)
        self.action = ActionBridge(self, self.motion, self.lock, self.clock) if self.simulated else None
        self.workflow = Workflow(config, self.motion, self.action.submit if self.action else None,
                                 self.access.valid)
        if self.action:
            self.action.workflow = self.workflow
            self.mock_camera = MockCamera(config)
            self.mock_publisher = CameraPublisher(self, camera, self.mock_camera,
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
            self.last_tick = now

    def dashboard_status(self, now):
        status = self.workflow.status(now)
        frame = self.workflow.frame
        status.update(
            mode='simulation' if self.simulated else 'read-only',
            real_motion_enabled=False, operator_configured=bool(self.access.secret),
            camera_source='mock' if self.simulated else 'orbbec_ros',
            camera_status=('MOCK RGB' if self.simulated else 'LIVE ORBBEC RGB')
            if status['camera'] else ('MOCK CAMERA OFFLINE' if self.simulated else 'CAMERA DISCONNECTED'),
            camera_timestamp=frame.source_stamp if frame and status['camera'] else None,
            camera_age_ms=round((now - frame.stamp) * 1000) if frame and status['camera'] else None,
        )
        if self.robot:
            status.update(self.robot.device_status(now))
            status['robot_status'] = ('ROBOT DISCONNECTED' if not status['device_connected']
                                      else 'READ-ONLY · CONNECTED' if status['connected']
                                      else 'READ-ONLY · TELEMETRY UNAVAILABLE')
        else:
            status.update(robot_status='MOCK ROBOT' if status['connected'] else 'MOCK ROBOT OFFLINE',
                          device_connected=status['connected'], firmware_version=[],
                          suction=None, gripper=None)
        return status

    def close(self):
        with self.lock:
            self.workflow.stop(self.clock(), 'Controller shutting down')
            if self.action:
                self.action.destroy()


def main():
    share = Path(get_package_share_directory('dobot_auto_center'))
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=share / 'config')
    parser.add_argument('--bind')
    parser.add_argument('--port', type=int)
    parser.add_argument('--allow-client', action='append')
    parser.add_argument('--mode', choices=('simulation', 'read-only'))
    args = parser.parse_args(remove_ros_args()[1:])
    try:
        config = load(args.config)
        for option, key in ((args.bind, 'bind'), (args.port, 'port'), (args.allow_client, 'allowed_clients')):
            if option is not None:
                config['web'][key] = option
        if args.mode is not None:
            config['hardware']['simulation_mode'] = args.mode == 'simulation'
        if not 1 <= config['web']['port'] <= 65535:
            raise ValueError('HTTP port must be between 1 and 65535')
        NetworkPolicy(config['web'])
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    cv2.setNumThreads(1)
    rclpy.init()
    node = None
    server = None
    try:
        node = AutoCenterNode(config, os.environ.get('DOBOT_OPERATOR_TOKEN', ''))
        server = serve(node, share / 'web')
        node.get_logger().info(f'Dashboard at http://{server.server_address[0]}:{server.server_address[1]}')
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    except (OSError, ValueError) as error:
        parser.exit(1, f'Dashboard startup failed for {config["web"]["bind"]}:{config["web"]["port"]}: {error}\n')
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if node is not None:
            node.close()
            node.destroy_node()
        rclpy.try_shutdown()
