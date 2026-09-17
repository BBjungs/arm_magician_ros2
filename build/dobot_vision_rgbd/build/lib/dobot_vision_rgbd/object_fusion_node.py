import json
import time
from pathlib import Path

import cv2
try:
    import message_filters
except ImportError:  # Pure fusion tests do not require the ROS sync dependency.
    message_filters = None
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String

from .color_classifier import ColorClassifier
from .depth_geometry import contour_mask, deproject_pixel, depth_to_mm, physical_size, robust_depth
from .detection_schema import validate_detection
from .rgbd_sync_node import registered_geometry_ok, sync_delta_ms
from .shape_detector import ShapeDetector
from .table_estimator import local_ring_depth
from .visualization import annotate


def load_yaml(path):
    with Path(path).open(encoding='utf-8') as stream:
        return yaml.safe_load(stream) or {}


class ObjectFusion:
    def __init__(self, shape_rules, color_rules, class_rules):
        self.shape_detector = ShapeDetector(shape_rules)
        self.color_classifier = ColorClassifier(color_rules)
        self.class_rules = class_rules
        self.reject = class_rules['rejection']

    def process(self, color, depth_mm, intrinsics):
        detections = []
        debug_masks = []
        for candidate in self.shape_detector.detect(color):
            mask = contour_mask(color.shape, candidate['contour'])
            color_result = self.color_classifier.classify(color, candidate['contour'])
            depth = robust_depth(
                depth_mm, mask, self.reject['depth_minimum_mm'], self.reject['depth_maximum_mm'],
                self.reject['minimum_depth_valid_ratio'], self.reject['trimmed_fraction'])
            table, ring = local_ring_depth(
                depth_mm, mask, int(self.reject['ring_dilate_px']),
                self.reject['depth_minimum_mm'], self.reject['depth_maximum_mm'])
            debug_masks.extend([mask, ring])
            detection = self._fuse(candidate, color_result, depth, table, intrinsics)
            detection.pop('contour', None)
            detection.pop('inner_mask', None)
            validate_detection(detection)
            detections.append(detection)
        for index, detection in enumerate(detections):
            detection['id'] = index
        return detections, debug_masks

    def _fuse(self, shape, color, depth, table, intrinsics):
        x1, y1, x2, y2 = shape['bbox']
        u, v = shape['center_pixel']
        height_mm = None
        size = {'width_mm': None, 'height_mm': None}
        xyz = None
        if depth['depth_valid'] and table['depth_valid']:
            height_mm = table['depth_mm'] - depth['depth_mm']
            size = physical_size(x2 - x1, y2 - y1, depth['depth_mm'], intrinsics)
            xyz = deproject_pixel(u, v, depth['depth_mm'], intrinsics)
        class_name, size_match, height_match = self._classify(
            shape['shape'], color['color'], size['width_mm'], height_mm)
        score_parts = [shape['shape_score'], color['color_score']]
        if depth['depth_valid']:
            score_parts.append(depth['depth_valid_ratio'])
        if size_match is not None:
            score_parts.append(float(size_match))
        if height_match is not None:
            score_parts.append(float(height_match))
        score = sum(score_parts) / len(score_parts)
        reason = ''
        if not depth['depth_valid'] or not table['depth_valid']:
            reason = 'invalid_depth'
        elif height_mm < self.reject['minimum_object_height_mm']:
            reason = 'height_out_of_range'
        elif class_name == 'unknown':
            reason = 'unknown_shape_or_color'
        elif size_match is False:
            reason = 'size_out_of_range'
        elif height_match is False:
            reason = 'height_out_of_range'
        result = {
            **shape, **{key: value for key, value in color.items() if key != 'inner_mask'},
            'id': 0, 'detector': 'rgbd_shape', 'class_name': class_name,
            'classification_score': round(score, 4),
            'confidence': round(score, 4),
            'depth_mm': depth['depth_mm'], 'depth_valid': depth['depth_valid'],
            'depth_valid_ratio': depth['depth_valid_ratio'], 'depth_stddev': depth['depth_stddev'],
            'table_depth_mm': table['depth_mm'],
            'object_height_mm': None if height_mm is None else round(height_mm, 3),
            'width_mm': None if size['width_mm'] is None else round(size['width_mm'], 3),
            'height_mm': None if size['height_mm'] is None else round(size['height_mm'], 3),
            'diameter_mm': None if size['width_mm'] is None else round((size['width_mm'] + size['height_mm']) / 2, 3),
            'camera_xyz_mm': None if xyz is None else {key: round(value, 3) for key, value in xyz.items()},
            'pick_eligible': not bool(reason), 'rejection_reason': reason,
            'rule_score_label': 'rule_score', 'physical_size_approximate': True,
        }
        return result

    def _classify(self, shape, color, diameter, height):
        for name, rule in self.class_rules['classes'].items():
            if rule.get('shape') != shape or rule.get('color') != color:
                continue
            size_match = None if diameter is None else rule['diameter_mm']['min'] <= diameter <= rule['diameter_mm']['max']
            height_match = None if height is None else rule['height_mm']['min'] <= height <= rule['height_mm']['max']
            return name, size_match, height_match
        return 'unknown', None, None


class ObjectFusionNode(Node):
    def __init__(self):
        super().__init__('object_fusion_node')
        if message_filters is None:
            raise RuntimeError('ROS message_filters is required for RGB-D synchronization')
        share = Path(get_package_share_directory('dobot_vision_rgbd'))
        defaults = load_yaml(share / 'config' / 'rgbd_vision.yaml')['object_fusion_node']['ros__parameters']
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        get = lambda name: self.get_parameter(name).value
        shape_path = get('shape_rules_path') or str(share / 'config' / 'shape_rules.yaml')
        color_path = get('color_rules_path') or str(share / 'config' / 'color_rules.yaml')
        classes_path = get('object_classes_path') or str(share / 'config' / 'object_classes.yaml')
        self.fusion = ObjectFusion(load_yaml(shape_path), load_yaml(color_path), load_yaml(classes_path))
        self.bridge = CvBridge()
        self.max_delta = float(get('max_sync_delta_ms'))
        self.scale_16u = float(get('depth_scale_16uc1_to_mm'))
        self.minimum_frame_depth_valid_ratio = float(
            get('minimum_frame_depth_valid_ratio'))
        self.require_registered = bool(get('require_registered_depth'))
        self.debug = bool(get('debug_enabled'))
        self.annotated_path = str(get('annotated_output_path'))
        self.dry_run = bool(get('dry_run'))
        self.allow_real_motion = bool(get('allow_real_motion'))
        if not self.dry_run or self.allow_real_motion:
            raise RuntimeError('RGB-D Vision is detection-only: dry_run=true and allow_real_motion=false are required')
        self.detections_pub = self.create_publisher(String, str(get('detections_topic')), 10)
        self.status_pub = self.create_publisher(String, str(get('status_topic')), 10)
        self.last_rgb = self.last_depth = self.last_sync = None
        self.depth_data_valid = False
        self.depth_frame_valid_ratio = 0.0
        self.count = 0
        queue = int(get('sync_queue_size'))
        self.color_sub = message_filters.Subscriber(self, Image, str(get('color_topic')), qos_profile=qos_profile_sensor_data)
        self.depth_sub = message_filters.Subscriber(self, Image, str(get('depth_topic')), qos_profile=qos_profile_sensor_data)
        self.info_sub = message_filters.Subscriber(self, CameraInfo, str(get('camera_info_topic')), qos_profile=qos_profile_sensor_data)
        self.color_sub.registerCallback(self._mark_rgb)
        self.depth_sub.registerCallback(self._mark_depth)
        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.color_sub, self.depth_sub, self.info_sub], queue, self.max_delta / 1000.0)
        self.sync.registerCallback(self.callback)
        self.create_timer(1.0, self.publish_health)

    def _mark_rgb(self, _message):
        self.last_rgb = time.monotonic()

    def _mark_depth(self, _message):
        self.last_depth = time.monotonic()

    @staticmethod
    def _age_ms(last_seen):
        if last_seen is None:
            return None
        return round(max(0.0, (time.monotonic() - last_seen) * 1000.0), 3)

    def callback(self, color_msg, depth_msg, info_msg):
        now = time.monotonic()
        self.last_sync = now
        delta = sync_delta_ms(color_msg, depth_msg, info_msg)
        registered = registered_geometry_ok(color_msg, depth_msg, info_msg)
        if delta > self.max_delta or (self.require_registered and not registered):
            self._publish([], delta, registered, 'rgb_depth_not_registered_or_synced')
            return
        color_rgb = self.bridge.imgmsg_to_cv2(color_msg, desired_encoding='rgb8')
        color = cv2.cvtColor(color_rgb, cv2.COLOR_RGB2BGR)
        depth = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
        try:
            depth_mm = depth_to_mm(depth, depth_msg.encoding, self.scale_16u)
        except ValueError as exc:
            self._publish([], delta, registered, str(exc))
            return
        valid_depth = (
            np.isfinite(depth_mm)
            & (depth_mm >= float(self.fusion.reject['depth_minimum_mm']))
            & (depth_mm <= float(self.fusion.reject['depth_maximum_mm']))
        )
        self.depth_frame_valid_ratio = float(np.mean(valid_depth))
        self.depth_data_valid = (
            self.depth_frame_valid_ratio >= self.minimum_frame_depth_valid_ratio)
        intrinsics = {'fx': info_msg.k[0], 'fy': info_msg.k[4], 'cx': info_msg.k[2], 'cy': info_msg.k[5]}
        detections, masks = self.fusion.process(color, depth_mm, intrinsics)
        annotated = annotate(color, detections)
        cv2.imwrite(self.annotated_path, annotated)
        if self.debug:
            cv2.imwrite('/tmp/rgbd_debug_rgb.jpg', color)
            cv2.imwrite('/tmp/rgbd_debug_depth.png', np.clip(depth_mm, 0, 65535).astype(np.uint16))
            cv2.imwrite('/tmp/rgbd_debug_annotated.jpg', annotated)
            if masks:
                cv2.imwrite('/tmp/rgbd_debug_masks.jpg', np.maximum.reduce(masks))
        self.count = len(detections)
        self._publish(detections, delta, registered, '')

    def _publish(self, detections, delta, registered, error):
        stamp = self.get_clock().now().nanoseconds / 1e9
        message = String()
        message.data = json.dumps({'stamp': stamp, 'vision_engine': 'rgbd_shape', 'detections': detections}, separators=(',', ':'))
        self.detections_pub.publish(message)
        table_values = [item['table_depth_mm'] for item in detections if item.get('table_depth_mm') is not None]
        rgb_age_ms = self._age_ms(self.last_rgb)
        depth_age_ms = self._age_ms(self.last_depth)
        rgb_fresh = rgb_age_ms is not None and rgb_age_ms <= 1000.0
        depth_fresh = depth_age_ms is not None and depth_age_ms <= 1000.0
        status = {
            'stamp': stamp, 'vision_engine': 'rgbd_shape', 'detector_running': True,
            'rgb_ok': rgb_fresh,
            'depth_stream_ok': depth_fresh,
            'depth_data_valid': bool(self.depth_data_valid and depth_fresh),
            'depth_valid_ratio': round(self.depth_frame_valid_ratio, 4),
            'depth_ok': bool(depth_fresh and self.depth_data_valid),
            'camera_info_ok': self.last_sync is not None, 'sync_ok': bool(
                rgb_fresh and depth_fresh and delta <= self.max_delta and registered),
            'rgb_age_ms': rgb_age_ms,
            'depth_age_ms': depth_age_ms,
            'sync_delta_ms': round(delta, 3), 'registered_depth': registered,
            'detection_count': len(detections),
            'table_depth_mm': round(float(np.median(table_values)), 3) if table_values else None,
            'dry_run': True, 'real_motion': False, 'model_loaded': False,
            'source_ok': rgb_fresh, 'error': error,
            'annotated_image_path': self.annotated_path,
        }
        msg = String(); msg.data = json.dumps(status, separators=(',', ':')); self.status_pub.publish(msg)

    def publish_health(self):
        if self.last_sync is None:
            self._publish([], self.max_delta + 1, False, 'waiting_for_synchronized_rgb_depth_camera_info')


def main(args=None):
    rclpy.init(args=args)
    node = ObjectFusionNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
