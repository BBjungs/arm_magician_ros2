"""ROS sensor adapters shared by simulation, passive monitoring and readiness."""

from collections import deque
import math

import cv2
from cv_bridge import CvBridge, CvBridgeError
from dobot_msgs.msg import AlarmState, DeviceStatus, ToolState
from geometry_msgs.msg import PoseStamped
import numpy as np
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, JointState

from .motion import Readback
from .vision import Observation


JOINT_NAMES = [f'magician_joint_{index}' for index in range(1, 5)]


def stamp_seconds(header):
    return header.stamp.sec + header.stamp.nanosec / 1e9


def local_stamp(node, header, clock):
    stamp = stamp_seconds(header)
    if not stamp:
        return float('-inf')
    return clock() - (node.get_clock().now().nanoseconds / 1e9 - stamp)


class CameraReceiver:
    def __init__(self, node, config, clock):
        self.node, self.config, self.clock = node, config, clock
        self.bridge = CvBridge()
        self.info = None
        self.info_stamps = deque(maxlen=12)
        self.rgb = deque(maxlen=8)
        self.depth = deque(maxlen=8)
        self.last_stamp = 0.
        for kind, msg, callback in (('rgb', Image, self.on_rgb), ('depth', Image, self.on_depth),
                                    ('info', CameraInfo, self.on_info)):
            node.create_subscription(msg, config[f'{kind}_topic'], callback,
                                     qos_profile_sensor_data)

    def dimensions_match(self, msg):
        return (msg.width == self.config['width'] and msg.height == self.config['height']
                and msg.header.frame_id == self.config['frame'])

    def on_info(self, message):
        calibrated = (self.dimensions_match(message) and all(map(math.isfinite, message.k))
                      and message.k[0] > 0 and message.k[4] > 0)
        self.info = (message.header.frame_id, message.width, message.height) if calibrated else None
        if calibrated:
            self.info_stamps.append(stamp_seconds(message.header))
        else:
            self.info_stamps.clear()

    def on_rgb(self, message):
        if not self.dimensions_match(message):
            return
        stamp = stamp_seconds(message.header)
        if stamp <= self.last_stamp:
            return
        try:
            pixels = self.bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
        except (ValueError, TypeError, CvBridgeError, cv2.error):
            return
        self.rgb.append((stamp, local_stamp(self.node, message.header, self.clock),
                         self.clock(), pixels))

    def on_depth(self, message):
        if not self.dimensions_match(message) or message.encoding not in ('16UC1', '32FC1'):
            return
        try:
            values = self.bridge.imgmsg_to_cv2(message, desired_encoding='passthrough')
        except (ValueError, TypeError, CvBridgeError, cv2.error):
            return
        if message.encoding == '16UC1':
            values = values.astype(np.float32) / 1000.
        self.depth.append((stamp_seconds(message.header),
                           local_stamp(self.node, message.header, self.clock), values))

    def take(self, now):
        if not self.rgb:
            return None
        stamp, local, received, rgb = self.rgb[0]
        nearest = min(self.depth, key=lambda item: abs(item[0] - stamp), default=None)
        synchronized = nearest is not None and abs(nearest[0] - stamp) <= self.config['max_depth_skew']
        calibrated = any(abs(stamp - info_stamp) <= self.config['max_depth_skew']
                         for info_stamp in self.info_stamps)
        if (not synchronized or not calibrated) and now - received < self.config['max_depth_skew']:
            return None
        self.rgb.popleft()
        if stamp <= self.last_stamp:
            return None
        self.last_stamp = stamp
        if not synchronized:
            return Observation(local, received, rgb, None, source_stamp=stamp)
        _, depth_stamp, depth = nearest
        sample = depth[::16, ::16]
        valid = np.mean(np.isfinite(sample) & (sample > 0)) >= self.config['minimum_valid_depth_fraction']
        return Observation(local, received, rgb, depth if valid else None, depth_stamp,
                           calibrated, stamp)


class RobotReceiver:
    def __init__(self, node, config, clock):
        self.node, self.clock = node, clock
        self.timeout = config['telemetry_timeout']
        self.samples = {}
        for key, kind in (('device', DeviceStatus), ('alarms', AlarmState),
                          ('joints', JointState), ('tcp', PoseStamped),
                          ('suction', ToolState), ('gripper', ToolState)):
            node.create_subscription(kind, config['topics'][key],
                                     lambda msg, name=key: self.receive(name, msg), 10)

    def receive(self, key, message):
        self.samples[key] = local_stamp(self.node, message.header, self.clock), message

    def snapshot(self):
        keys = ('device', 'alarms', 'joints', 'tcp')
        if not all(key in self.samples for key in keys):
            return Readback(0.)
        device, alarm, joints, tcp = [self.samples[key][1] for key in keys]
        stamp = min(self.samples[key][0] for key in keys)
        if (len(joints.name) != len(joints.position)
                or any(name not in joints.name for name in JOINT_NAMES)
                or tcp.header.frame_id != 'magician_base_link'):
            return Readback(stamp)
        angles = tuple(math.degrees(joints.position[joints.name.index(name)]) for name in JOINT_NAMES)
        p, q = tcp.pose.position, tcp.pose.orientation
        if not math.isclose(math.hypot(q.x, q.y, q.z, q.w), 1, abs_tol=0.01):
            return Readback(stamp)
        yaw = math.degrees(math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z)))
        pose = (p.x * 1000, p.y * 1000, p.z * 1000, yaw)
        if not all(map(math.isfinite, (*pose, *angles))):
            return Readback(stamp)
        return Readback(stamp, device.connected, alarm.valid, tuple(alarm.codes), pose, angles)


    def device_status(self, now):
        def fresh(topic):
            sample = self.samples.get(topic)
            return sample[1] if sample and 0 <= now - sample[0] <= self.timeout else None

        device = fresh('device')
        connected = bool(device and device.connected)
        alarm = fresh('alarms') if connected else None
        result = {
            'device_connected': connected,
            'device_name': device.device_name if connected else None,
            'firmware_version': list(device.firmware_version) if connected else [],
            'alarms': list(alarm.codes) if alarm and alarm.valid else [],
            'alarm_valid': bool(alarm and alarm.valid),
        }
        for key in ('suction', 'gripper'):
            tool = fresh(key) if connected else None
            result[key] = {'control_enabled': tool.control_enabled, 'active': tool.active} if tool and tool.valid else None
        return result


class CameraPublisher:
    def __init__(self, node, config, camera, pose):
        self.node, self.camera, self.pose = node, camera, pose
        self.config, self.bridge = config, CvBridge()
        self.rgb = node.create_publisher(Image, config['rgb_topic'], qos_profile_sensor_data)
        self.depth = node.create_publisher(Image, config['depth_topic'], qos_profile_sensor_data)
        self.info = node.create_publisher(CameraInfo, config['info_topic'], qos_profile_sensor_data)
        self.enabled = True
        node.create_timer(1 / config['mock_fps'], self.publish)

    def publish(self):
        if not self.enabled:
            return
        bgr, depth = self.camera.render(self.pose())
        color = self.bridge.cv2_to_imgmsg(bgr, encoding='bgr8')
        color.header.stamp = self.node.get_clock().now().to_msg()
        color.header.frame_id = self.config['frame']
        camera_info = CameraInfo(header=color.header, width=color.width, height=color.height)
        camera_info.k = [520., 0., color.width/2, 0., 520., color.height/2, 0., 0., 1.]
        self.info.publish(camera_info)
        if self.camera.depth_enabled:
            depth_msg = self.bridge.cv2_to_imgmsg(depth, encoding='16UC1')
            depth_msg.header = color.header
            self.depth.publish(depth_msg)
        self.rgb.publish(color)
