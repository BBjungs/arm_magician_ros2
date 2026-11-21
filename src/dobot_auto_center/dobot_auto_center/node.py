"""ROS graph and application lifecycle."""

import argparse
from pathlib import Path
from threading import RLock
import time

from ament_index_python.packages import get_package_share_directory
import cv2
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from .config import load
from .mock_camera import MockCamera
from .motion import Motion, MockTransport
from .ros_motion import ActionBridge
from .ros_sensors import CameraPublisher, CameraReceiver, RobotReceiver, live_camera_status
from .safety import Safety
from .web import Access, NetworkPolicy, serve
from .workflow import Workflow
from dobot_driver.state.node import ReadbackNode


class AutoCenterNode(Node):
    def __init__(self, config, *, home_driver=None):
        super().__init__('dobot_auto_center')
        self.config = config
        self.lock = RLock()
        self.clock = time.monotonic
        self.last_tick = None
        self.tick_interval_ms = None
        self.last_camera_state = None
        self.camera_generation = 0
        self.access = Access(config['web'])
        self.simulated = config['hardware']['simulation_mode']
        self.home_driver = home_driver
        self.robot = None if self.simulated else RobotReceiver(
            self, config['hardware'], self.clock, lock=self.lock)
        camera = config['camera'].copy()
        if self.simulated:
            for key in ('rgb_topic', 'depth_topic', 'info_topic'):
                camera[key] = '/dobot_auto_center/simulation/' + camera[key].lstrip('/')
        self.camera = CameraReceiver(self, camera, self.clock, simulated=self.simulated,
                                     trace=not self.simulated)
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
            if not self.simulated and (not self.camera.device_name or
                                       self.camera.source_generation != self.camera_generation):
                self.workflow.camera_offline()
                self.camera_generation = self.camera.source_generation
            if not self.simulated and self.camera.device_name:
                self.workflow.update_preview(self.camera.pending_preview(now))
            if observation is not None:
                self.workflow.ingest(observation, now)
            self.workflow.tick(now)
            if not self.simulated:
                display = self.workflow.display_frame(now)
                camera_state = (display is not None, bool(self.workflow.rgbd(now)))
                if self.last_camera_state != camera_state:
                    previous = self.last_camera_state
                    self.last_camera_state = camera_state
                    reason = (self.camera.offline_reason() if not camera_state[0] else
                              self.camera.depth_issue if not camera_state[1] else 'RGB-D ready')
                    camera = self.camera
                    age = lambda queue: now - max(s[1] for s in queue) if queue else None
                    camera.record('readiness', previous=previous, current=camera_state, reason=reason,
                                  now=now, frame_id=self.workflow.frame_id, last_ingest=self.workflow.last_ingest,
                                  rgb_header_ns=(display.source_ns if display else None),
                                  rgb_received=display.received if display else None,
                                  rgb_age=now-display.stamp if display else None,
                                  depth_age=age(camera.depth), info_age=age(camera.info_stamps),
                                  triplet_age=(now-camera.valid_until+camera.config['freshness']
                                               if camera.valid_until != float('-inf') else None),
                                  pending_rgb=len(camera.rgb), last_emit=camera.last_match)
                    self.get_logger().info(
                        f"Camera RGB fresh={camera_state[0]}, registered depth={camera_state[1]}, "
                        f"frame={self.workflow.frame_id}: {reason}"
                        + (f" match={self.camera.last_match}" if reason == "info_skew" else ""))
            if self.action:
                self.action.tick()
            if self.last_tick is not None:
                self.tick_interval_ms = (now - self.last_tick) * 1000
            self.last_tick = now

    def dashboard_status(self, now):
        if self.robot:
            self.motion.snapshot = self.robot.snapshot()
        status = self.workflow.status(now)
        frame = self.workflow.display_frame(now)
        stamps = self.workflow.frame_stamps
        camera = self.camera.config
        if self.simulated:
            camera_status = 'MOCK RGB' if status['camera'] else 'MOCK CAMERA OFFLINE'
        else:
            camera_status = live_camera_status(status['camera'], status['depth'])
            if not status['camera']:
                status['diagnostic'] = self.camera.offline_reason()
            elif not status['depth']:
                status['diagnostic'] = self.camera.depth_issue
        status.update(
            camera_readiness=('RGBD_READY' if status['depth'] else
                              'WAITING_FOR_DEPTH' if status['camera'] else 'WAITING_FOR_RGB'),
            stream_url='/api/stream.mjpg',
            camera_last_match=self.camera.last_match,
            camera_queue_overflow=dict(self.camera.overflow),
            camera_topics={kind: camera[f'{kind}_topic'] for kind in ('rgb', 'depth', 'info')},
            camera_device=self.camera.device_name,
            camera_fps=(round((len(stamps)-1) / (stamps[-1]-stamps[0]), 1)
                        if status['camera'] and len(stamps) >= 2 and stamps[-1] > stamps[0] else None),
            depth_skew_ms=(round(abs(frame.depth_source_stamp - frame.source_stamp) * 1000, 1)
                           if status['depth'] and frame.depth_source_stamp is not None else None),
            depth_source=('mock' if self.simulated else 'orbbec_ros') if status['depth'] else None,
            mode='hardware-home' if self.home_driver else ('simulation' if self.simulated else 'read-only'),
            real_motion_enabled=self.home_driver is not None,
            camera_source='mock' if self.simulated else 'orbbec_ros',
            camera_status=camera_status,
            camera_timestamp=frame.source_stamp if frame and status['camera'] else None,
            capture_to_receive_ms=(round((frame.received - frame.stamp) * 1000, 1)
                                   if status['camera'] else None),
            camera_age_ms=round((now - frame.stamp) * 1000) if frame and status['camera'] else None,
        )
        if self.robot:
            status.update(self.robot.device_status(now))
            issue = self.home_driver.home_issue if self.home_driver else ''
            if self.access.pending_home is not None:
                issue = 'Waiting for HOME command result'
            status['home_available'] = bool(self.home_driver and status['connected']
                                            and status['alarm_valid'] and not status['alarms'] and not issue)
            if self.home_driver and not status['home_available']:
                status['home_blocked_reason'] = issue or 'Waiting for fresh Dobot telemetry'
            prefix = 'DOBOT' if self.home_driver else 'READ-ONLY'
            status['robot_status'] = (f'{prefix} · TELEMETRY STALE' if status['device_status_stale']
                                      else 'ROBOT DISCONNECTED' if not status['device_connected']
                                      else f'{prefix} · CONNECTED' if status['connected']
                                      else f'{prefix} · TELEMETRY UNAVAILABLE')
        else:
            status.update(home_available=False, robot_status='MOCK ROBOT' if status['connected'] else 'MOCK ROBOT OFFLINE',
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
    parser.add_argument('--mode', choices=('simulation', 'read-only', 'hardware-home'))
    parser.add_argument('--home-port', help='Dedicated Dobot serial port for hardware HOME')
    args = parser.parse_args(remove_ros_args()[1:])
    try:
        config = load(args.config)
        for option, key in ((args.bind, 'bind'), (args.port, 'port'), (args.allow_client, 'allowed_clients')):
            if option is not None:
                config['web'][key] = option
        if args.mode is not None:
            config['hardware']['simulation_mode'] = args.mode == 'simulation'
        if (args.mode == 'hardware-home') != bool(args.home_port):
            raise ValueError('Hardware HOME requires --mode hardware-home and --home-port together')
        if not 1 <= config['web']['port'] <= 65535:
            raise ValueError('HTTP port must be between 1 and 65535')
        NetworkPolicy(config['web'])
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    cv2.setNumThreads(1)
    rclpy.init()
    node = None
    server = None
    driver = None
    executor = None
    try:
        if args.home_port:
            driver = ReadbackNode(home_port=args.home_port)
            executor = MultiThreadedExecutor(num_threads=2)
            executor.add_node(driver)
        node = AutoCenterNode(config, home_driver=driver)
        server = serve(node, share / 'web')
        node.get_logger().info(f'Dashboard at http://{server.server_address[0]}:{server.server_address[1]}')
        rclpy.spin(node, executor=executor)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    except (OSError, ValueError) as error:
        parser.exit(1, f'Dashboard startup failed for {config["web"]["bind"]}:{config["web"]["port"]}: {error}\n')
    finally:
        if server:
            server.shutdown()
            server.server_close()
        if executor:
            executor.shutdown()
        if node is not None:
            node.close()
            node.destroy_node()
        if driver:
            driver.close_device()
            driver.destroy_node()
        rclpy.try_shutdown()
