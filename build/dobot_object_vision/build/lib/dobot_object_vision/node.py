"""ROS adapter for detection only; it imports no robot driver or motion client."""

from dataclasses import asdict
import threading
import time

import cv2
import message_filters
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Header
from dobot_msgs.msg import CircleTarget, CircleTargetArray

from .detector import Detector, Rules, VisionError


def seconds(header):
    return header.stamp.sec + header.stamp.nanosec * 1e-9


def convert_bundle(bundle, bridge, now, frame, max_age, max_skew, input_rectified=True):
    rgb, depth, info = bundle
    stamps = [seconds(m.header) for m in bundle]
    if any(t <= 0 or not 0 <= now - t < max_age for t in stamps):
        raise VisionError('Stale or invalid exposure timestamp')
    if max(stamps) - min(stamps) > max_skew:
        raise VisionError('RGB-D synchronization error')
    if any(m.header.frame_id != frame for m in bundle):
        raise VisionError('Images and intrinsics must share the registered optical frame')
    if (info.width != rgb.width or info.height != rgb.height
            or info.width != depth.width or info.height != depth.height):
        raise VisionError('RGB-D/CameraInfo dimensions disagree')
    if (info.binning_x not in (0, 1) or info.binning_y not in (0, 1)
            or info.roi.x_offset or info.roi.y_offset
            or info.roi.width not in (0, info.width) or info.roi.height not in (0, info.height)):
        raise VisionError('Cropped/binned intrinsics require an adjusted full-frame CameraInfo')
    projection = np.asarray(info.p).reshape(3, 4)
    if projection[0, 0] > 0:
        if not np.allclose(projection[:, 3], 0):
            raise VisionError('Nonzero projection baseline is unsupported')
        k = projection[:, :3]
    else:
        if not np.isfinite(info.d).all() or np.any(np.abs(info.d) > 1e-8):
            raise VisionError('Rectified RGB-D and projection intrinsics are required')
        k = np.asarray(info.k).reshape(3, 3)
    if depth.encoding not in ('16UC1', '32FC1'):
        raise VisionError('Depth encoding must be 16UC1 millimetres or 32FC1 metres')
    values = np.asarray(bridge.imgmsg_to_cv2(depth, 'passthrough'), dtype=float)
    if depth.encoding == '16UC1':
        values *= 0.001
    image = bridge.imgmsg_to_cv2(rgb, 'bgr8')
    if not input_rectified:
        raw_k = np.asarray(info.k).reshape(3, 3)
        rotation = np.asarray(info.r).reshape(3, 3)
        if (not np.isfinite(raw_k).all() or min(raw_k[0, 0], raw_k[1, 1]) <= 0
                or not np.isfinite(info.d).all() or not np.isfinite(k).all()):
            raise VisionError('Invalid raw camera intrinsics')
        if info.distortion_model not in ('', 'plumb_bob', 'rational_polynomial'):
            raise VisionError('Unsupported distortion model')
        if not (np.allclose(rotation, 0) or np.allclose(rotation, np.eye(3))):
            raise VisionError('Rotated rectification requires depth XYZ reprojection')
        # Input depth must already be registered into the RAW color raster.
        # Nearest-neighbour depth remapping never blends object and table Z.
        map_x, map_y = cv2.initUndistortRectifyMap(raw_k, np.asarray(info.d), np.eye(3),
                                                 k, (info.width, info.height), cv2.CV_32FC1)
        image = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR)
        values = cv2.remap(values, map_x, map_y, cv2.INTER_NEAREST)
    return image, values, k


def detection_message(result, header):
    msg = CircleTargetArray()
    msg.header = header
    msg.valid = True
    msg.table_plane = result.table_plane.tolist()
    msg.table_inlier_ratio = result.table_inlier_ratio
    msg.table_rmse = result.table_rmse
    for detection in result.detections:
        target = CircleTarget()
        for name in ('id', 'class_name', 'depth', 'size', 'confidence', 'pickable',
                     'top_height', 'depth_valid_ratio', 'depth_mad', 'rejection_reason'):
            setattr(target, name, getattr(detection, name))
        target.center_uv = list(detection.center_uv)
        target.camera_xyz.x, target.camera_xyz.y, target.camera_xyz.z = detection.camera_xyz
        msg.detections.append(target)
    return msg


class ObjectVisionNode(Node):
    def __init__(self):
        super().__init__('circle_targets')
        defaults = {'rgb_topic': '/camera/color/image_rect',
                    'depth_topic': '/camera/aligned_depth_to_color/image_raw',
                    'camera_info_topic': '/camera/color/camera_info',
                    'camera_frame': 'camera_color_optical_frame',
                    'detections_topic': '/object_vision/detections',
                    'annotated_topic': '/object_vision/annotated',
                    'max_age_s': 0.5, 'max_skew_s': 0.05, 'process_hz': 5.0,
                    'input_rectified': True}
        for name, value in defaults.items():
            self.declare_parameter(name, value, ParameterDescriptor(read_only=True))
        self.settings = {name: self.get_parameter(name).value for name in defaults}
        for name in ('max_age_s', 'max_skew_s', 'process_hz'):
            if not np.isfinite(self.settings[name]) or self.settings[name] <= 0:
                raise VisionError(f'{name} must be finite and positive')
        if self.settings['max_skew_s'] >= self.settings['max_age_s']:
            raise VisionError('Synchronization skew must be smaller than frame freshness limit')
        for name, value in asdict(Rules()).items():
            self.declare_parameter('rules.' + name, value, ParameterDescriptor(read_only=True))
        self.detector = Detector(Rules(**{name: self.get_parameter('rules.' + name).value
                                         for name in asdict(Rules())}))
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.latest = None
        self.received = None
        self.processed_stamp = None
        self.output = self.create_publisher(CircleTargetArray, self.settings['detections_topic'], 1)
        self.annotated = self.create_publisher(Image, self.settings['annotated_topic'], qos_profile_sensor_data)
        self.subscribers = [message_filters.Subscriber(self, cls, self.settings[topic],
                                                       qos_profile=qos_profile_sensor_data)
                            for cls, topic in [(Image, 'rgb_topic'), (Image, 'depth_topic'),
                                               (CameraInfo, 'camera_info_topic')]]
        self.sync = message_filters.ApproximateTimeSynchronizer(self.subscribers, 8,
                                                                self.settings['max_skew_s'])
        self.sync.registerCallback(self.on_bundle)
        self.process_group = MutuallyExclusiveCallbackGroup()
        self.health_group = ReentrantCallbackGroup()
        self.create_timer(1 / self.settings['process_hz'], self.process_latest,
                          callback_group=self.process_group)
        self.create_timer(0.2, self.watchdog, callback_group=self.health_group)

    def now_s(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_bundle(self, rgb, depth, info):
        with self.lock:
            self.latest = (rgb, depth, info)
            self.received = time.monotonic()

    def invalid(self, reason, header=None, image=None):
        message = CircleTargetArray()
        message.header = header if header is not None else Header()
        if header is None:
            message.header.stamp = self.get_clock().now().to_msg()
            message.header.frame_id = self.settings['camera_frame']
        message.valid = False
        message.reason = reason
        self.output.publish(message)
        if image is not None:
            annotated = image.copy()
            cv2.putText(annotated, reason[:85], (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 0, 255), 1, cv2.LINE_AA)
            msg = self.bridge.cv2_to_imgmsg(annotated, 'bgr8')
            msg.header = message.header
            self.annotated.publish(msg)

    def watchdog(self):
        with self.lock:
            latest, received = self.latest, self.received
        if latest is None:
            self.invalid('Waiting for synchronized RGB-D and CameraInfo')
        elif (time.monotonic() - received >= self.settings['max_age_s']
              or any(not 0 <= self.now_s() - seconds(m.header) < self.settings['max_age_s']
                     for m in latest)):
            self.invalid('RGB-D source is stale')

    def process_latest(self):
        with self.lock:
            bundle = self.latest
        if bundle is None:
            return
        stamp = seconds(bundle[0].header)
        if stamp == self.processed_stamp:
            return
        self.processed_stamp = stamp
        image = None
        try:
            image, depth, k = convert_bundle(bundle, self.bridge, self.now_s(),
                                             self.settings['camera_frame'], self.settings['max_age_s'],
                                             self.settings['max_skew_s'], self.settings['input_rectified'])
            result = self.detector.process(image, depth, k)
            # A slow frame must never republish targets after the watchdog cleared them.
            if any(not 0 <= self.now_s() - seconds(m.header) < self.settings['max_age_s'] for m in bundle):
                raise VisionError('Processing exceeded exposure freshness limit')
            with self.lock:
                if self.received is None or time.monotonic() - self.received >= self.settings['max_age_s']:
                    raise VisionError('RGB-D source stopped during processing')
            self.output.publish(detection_message(result, bundle[0].header))
            annotated = self.bridge.cv2_to_imgmsg(result.annotated, 'bgr8')
            annotated.header = bundle[0].header
            self.annotated.publish(annotated)
        except Exception as error:
            self.invalid(str(error), bundle[0].header, image)


def main(args=None):
    rclpy.init(args=args)
    node = ObjectVisionNode()
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
