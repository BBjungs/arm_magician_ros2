"""ROS adapter for guarded markerless calibration; no hardware access on import."""

from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
import threading
import time

import message_filters
import cv2
import numpy as np
import yaml
from scipy.spatial.transform import Rotation
import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from action_msgs.msg import GoalStatus
from rcl_interfaces.msg import ParameterDescriptor
from cv_bridge import CvBridge
from dobot_msgs.action import PointToPoint
from dobot_msgs.msg import DobotAlarmCodes
from dobot_msgs.srv import EvaluatePTPTrajectory
from geometry_msgs.msg import PoseStamped, TransformStamped
from sensor_msgs.msg import CameraInfo, Image, JointState, PointCloud2
from sensor_msgs_py import point_cloud2
from scipy.spatial import cKDTree
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformBroadcaster, TransformListener, TransformException

from .depth_health import depth_quality
from .geometry import CalibrationError, Limits, Mount, fingerprint, pose_distance, transform
from .hardware_readiness import DepthStabilityWindow, evaluate_hardware_readiness
from .registration import make_capture, register
from .passive_session import PassiveSessionStore
from .passive_guidance import calibration_plan, compute_guidance
from .supervised_auto import SupervisedAutoCalibration
from .table_touchoff import TableTouchoff
from .workflow import Workflow, check_path, settled_pose
from .validation_status import live_acceptance_error
from dobot_kinematics.dobot_inv_kin import calc_inv_kin
from dobot_kinematics.collision_detection_server import PyBulletCollisionServer


# Calibration consumes large RGB-D and point-cloud messages. A backlog is
# never useful for a safety decision or synchronized capture; the synchronizer
# below keeps its own timestamp queue once the newest DDS samples arrive.
CALIBRATION_SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)


def stamp_seconds(message):
    return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9


class CalibrationNode(Node):
    def __init__(self):
        super().__init__('markerless_calibration')
        defaults = {
            'rgb_topic': '/camera/color/image_raw',
            'depth_topic': '/camera/depth/image_raw',
            'camera_info_topic': '/camera/color/camera_info',
            'cloud_topic': '/camera/depth/points',
            # AUTO never changes a selected source during a capture.  The
            # depth deprojection path is the production-safe fallback when a
            # driver cloud is absent, old, or from a different exposure.
            'point_cloud_source': 'AUTO',
            'planning_soft_margin_deg': 2.0,
            'tcp_topic': '/dobot_TCP', 'joints_topic': '/dobot_joint_states',
            'alarms_topic': '/dobot_alarms', 'safety_state_topic': '',
            'physical_estop_present': False,
            'operator_safety_verified': False,
            'base_frame': 'magician_base_link', 'tool_frame': 'TCP',
            'carrier_frame': '',
            'camera_reference_frame': 'camera_link',
            'camera_frame': 'camera_color_optical_frame',
            'calibrated_frame': 'calibrated_camera_optical_frame',
            'camera_id': '', 'mount_model': '',
            'calibration_file': '~/.ros/dobot/markerless_calibration.npz',
            'auto_start': False, 'recalibrate_on_failure': False,
            'ready_ttl_s': 600.0, 'capture_timeout_s': 15.0,
            'motion_timeout_s': 25.0,
            'passive_session_root': '~/.ros/dobot/calibration_sessions',
            'auto_real_motion_enabled': False,
            'calibration_linear_speed_ratio': 0.10,
            'calibration_acceleration_ratio': 0.10,
            # No controller/URDF datum establishes the tabletop.  A finite value
            # is required before automatic-motion preflight may use table clearance.
            'calibration_table_height_m': float('nan'),
            'calibration_minimum_clearance_m': 0.025,
            'table_touchoff_gauge_height_mm': 0.0,
            'table_reference_status': 'operator_confirmed',
            'table_reference_source': 'physical_operator_confirmation',
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value, ParameterDescriptor(read_only=True))
        self.settings = {name: self.get_parameter(name).value for name in defaults}
        if self.settings['carrier_frame'] in (self.settings['base_frame'], self.settings['tool_frame']):
            raise CalibrationError('Camera carrier must be a distinct moving bracket frame')
        for name in ('ready_ttl_s', 'capture_timeout_s', 'motion_timeout_s'):
            if not np.isfinite(self.settings[name]) or self.settings[name] <= 0:
                raise CalibrationError(f'{name} must be finite and positive')
        for name, value in asdict(Limits()).items():
            self.declare_parameter('quality.' + name, value, ParameterDescriptor(read_only=True))
        self.limits = Limits(**{name: self.get_parameter('quality.' + name).value
                               for name in asdict(Limits())})
        # Quality limits are deployment configuration, not dynamically mutable
        # while a solution is being collected or used.
        self.group = ReentrantCallbackGroup()
        self.lock, self.operation_lock = threading.Lock(), threading.Lock()
        self.stop = threading.Event()
        self.history = deque(maxlen=400)
        self.table_touchoff = TableTouchoff(self.settings['table_touchoff_gauge_height_mm'])
        self.bundle = None
        self.live_depth_quality = None
        self.camera_health = None
        self.live_depth_stamp = None
        self.live_depth_receive_stamp = None
        self.last_depth_processed_stamp = None
        self.last_depth_processed_monotonic = 0.0
        self.depth_window = DepthStabilityWindow()
        self.delegated_depth_stable = False
        self.tcp_stamp = None
        self.joints_stamp = None
        self.robot_response_seen = False
        self.safety_stamp = None
        self.safety_verified = False
        self.alarm_stamp = 0.0
        self.alarms = [255]
        self.after_motion_stamp = self.now_s()
        self.last_capture_stamp = 0.0
        self.last_capture = None
        self.active_goal = None
        self.worker = None
        self.workflow = None
        self.passive_captures = []
        self.passive_capture_metadata = []
        self.passive_capture_active = False
        self.scene_baseline = None
        self.last_native_cloud = None
        self.last_native_cloud_receive_monotonic = None
        try:
            if self.settings['mount_model']:
                with open(self.settings['mount_model'], encoding='utf-8') as stream:
                    mount_config_fingerprint = fingerprint(yaml.safe_load(stream))
            else:
                mount_config_fingerprint = fingerprint({'mount_model': 'unconfigured'})
        except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
            raise CalibrationError('Cannot fingerprint mount configuration: ' + str(error)) from error
        self.passive_session = PassiveSessionStore(
            self.settings['passive_session_root'], mount_config_fingerprint,
            self.settings['camera_id'])
        self.passive_session_error = ''
        try:
            self.passive_captures, self.passive_capture_metadata = self.passive_session.restore()
            if self.passive_captures:
                anchor_xyz = self.passive_captures[0].base_T_tool[:3, 3] * 1000.0
                anchor_j4 = float(self.passive_capture_metadata[0].get('J4_yaw_deg', 0.0))
                self.passive_session.ensure_plan(calibration_plan(anchor_xyz, anchor_j4))
        except CalibrationError as error:
            self.passive_session_error = str(error)
        self.supervised_auto = SupervisedAutoCalibration(
            self.auto_preflight, self.auto_validate_target,
            real_motion_enabled=bool(self.settings['auto_real_motion_enabled']))
        self.mount = None
        self.calibration_context = None
        self.state, self.reason = 'UNCALIBRATED', 'Calibration has not been verified'
        try:
            self.mount = Mount.load(self.settings['mount_model'], self.limits,
                                    carrier_frame=self.settings['carrier_frame'])
        except (CalibrationError, OSError, TypeError, ValueError) as error:
            try:
                blockers = Mount.translation_constraint_blockers(
                    self.settings['mount_model'], self.limits,
                    carrier_frame=self.settings['carrier_frame'])
            except (OSError, TypeError, ValueError, yaml.YAMLError):
                blockers = []
            self.reason = ('Mount calibration prerequisites incomplete: '
                           + '; '.join(blockers)) if blockers else f'Mount geometry unverified: {error}'
        self.carrier_tf = Buffer()
        self.carrier_listener = TransformListener(self.carrier_tf, self)
        self.bridge = CvBridge()
        self.broadcaster = TransformBroadcaster(self)
        self.publisher = self.create_publisher(
            String, '/calibration/status',
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(String, '/camera/health', self.on_camera_health, 10)
        self.create_subscription(DobotAlarmCodes, self.settings['alarms_topic'], self.on_alarms, 10)
        self.create_subscription(PoseStamped, self.settings['tcp_topic'], self.on_tcp_health, 10)
        self.create_subscription(JointState, self.settings['joints_topic'], self.on_joints_health, 10)
        if self.settings['safety_state_topic']:
            self.create_subscription(Bool, self.settings['safety_state_topic'], self.on_safety, 10)
        self.robot_subscribers = [
            message_filters.Subscriber(self, PoseStamped, self.settings['tcp_topic']),
            message_filters.Subscriber(self, JointState, self.settings['joints_topic']),
        ]
        self.robot_sync = message_filters.ApproximateTimeSynchronizer(
            self.robot_subscribers, queue_size=30, slop=0.06)
        self.robot_sync.registerCallback(self.on_robot)
        # Full RGB-D + point-cloud DDS deserialization is expensive in Python.
        # Keep it lazy until a mount-validated calibration/verification run is
        # actually requested.  The direct depth subscription below continues
        # to enforce live sensor health while the node is idle.
        self.camera_subscribers = []
        self.camera_sync = None
        # The direct depth guard is activated together with the synchronized
        # capture inputs, after the immutable mount model has passed. An idle,
        # uncommissioned node must not deserialize a full depth stream forever.
        self.depth_subscription = None
        # Supervised transfers are MOVJ/PTP, not Cartesian MOVL.  Use the
        # controller validator that accepts and samples the requested PTP path;
        # the calibration-specific endpoint deliberately rejects non-MOVL.
        self.validator = self.create_client(EvaluatePTPTrajectory,
                                            '/dobot_PTP_validation_service',
                                             callback_group=self.group)
        self.motion = ActionClient(self, PointToPoint, '/PTP_action', callback_group=self.group)
        self.create_service(Trigger, '/calibration/start', self.start_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/recalibrate', self.recalibrate_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/verify', self.verify_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/ready', self.ready_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/cancel', self.cancel_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/capture_pose', self.capture_pose_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/passive_capture_test',
                            self.passive_capture_test_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/auto/validate_plan',
                            self.validate_plan_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/scene/baseline',
                            self.scene_baseline_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/scene/verify',
                            self.scene_verify_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/delete_last_pose',
                            self.delete_last_pose_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/clear_poses', self.clear_poses_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/session/status', self.session_status_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/session/new', self.session_new_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/session/resume', self.session_resume_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/session/discard', self.session_discard_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/auto/start', self.auto_start_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/auto/pause', self.auto_pause_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/auto/resume', self.auto_resume_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/auto/abort', self.auto_abort_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/auto/status', self.auto_status_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/table_touchoff/capture',
                            self.table_touchoff_capture_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/table_touchoff/status',
                            self.table_touchoff_status_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/table_touchoff/clear',
                            self.table_touchoff_clear_service, callback_group=self.group)
        self.create_timer(0.2, self.supervise, callback_group=self.group)
        self.auto_pending = self.settings['auto_start']

    def ensure_camera_sync(self):
        if self.camera_sync is not None:
            return
        self.delegated_depth_stable = False
        self.depth_subscription = self.create_subscription(
            Image, self.settings['depth_topic'], self.on_depth,
            CALIBRATION_SENSOR_QOS)
        self.camera_subscribers = [message_filters.Subscriber(
            self, kind, self.settings[name], qos_profile=CALIBRATION_SENSOR_QOS)
            for kind, name in [(Image, 'rgb_topic'), (Image, 'depth_topic'),
                               (CameraInfo, 'camera_info_topic')]]
        # Native cloud is deliberately not a member of RGB-D synchronization:
        # it may stop without invalidating aligned depth and intrinsics.
        self.create_subscription(PointCloud2, self.settings['cloud_topic'],
                                 self.on_native_cloud, CALIBRATION_SENSOR_QOS)
        self.camera_sync = message_filters.ApproximateTimeSynchronizer(
            self.camera_subscribers, queue_size=30, slop=0.5)
        self.camera_sync.registerCallback(self.on_camera)

    def now_s(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_alarms(self, message):
        with self.lock:
            self.alarms, self.alarm_stamp = list(message.alarms_list), stamp_seconds(message)
            self.robot_response_seen = True
        if self.alarms and self.state not in ('UNCALIBRATED', 'STARTING', 'FAIL'):
            self.stop.set()
            self.status('FAIL', 'Active robot alarms')

    def on_tcp_health(self, message):
        p, q = message.pose.position, message.pose.orientation
        values = np.array([p.x, p.y, p.z, q.x, q.y, q.z, q.w], dtype=float)
        if (message.header.frame_id == self.settings['base_frame']
                and np.isfinite(values).all()
                and np.isclose(np.linalg.norm(values[3:]), 1.0, atol=1e-3)):
            with self.lock:
                self.tcp_stamp = stamp_seconds(message)
                self.robot_response_seen = True

    def on_joints_health(self, message):
        required = [f'magician_joint_{i}' for i in range(1, 5)]
        try:
            values = [message.position[message.name.index(name)] for name in required]
        except (ValueError, IndexError):
            return
        if np.isfinite(values).all():
            with self.lock:
                self.joints_stamp = stamp_seconds(message)
                self.robot_response_seen = True

    def on_safety(self, message):
        # The configured topic must be backed by a real workcell safety device.
        # An empty topic name deliberately leaves safety unsupported.
        with self.lock:
            self.safety_verified = bool(message.data)
            self.safety_stamp = self.now_s()

    def on_camera_health(self, message):
        """Use the independent live monitor while raw capture is still lazy."""
        try:
            payload = json.loads(message.data)
            depth = payload.get('streams', {}).get('depth', {})
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            return
        self.camera_health = payload
        # During a passive/automatic capture the direct depth callback owns the
        # safety lease, but retain the independent stream-rate diagnostics.
        if self.depth_subscription is not None:
            return
        try:
            depth_age_s = float(depth.get('age_ms')) / 1000.0
            age_valid = bool(np.isfinite(depth_age_s) and depth_age_s >= 0.0)
        except (TypeError, ValueError):
            depth_age_s, age_valid = 0.0, False
        valid = bool(depth.get('fresh') and depth.get('timestamp_valid')
                     and depth.get('valid') and age_valid)
        try:
            median_gap_ms = float(depth.get('median_timestamp_delta_ms', 0.0) or 0.0)
            maximum_gap_ms = float(depth.get('max_stamp_gap_ms', 1e9))
            stable = bool(valid and int(depth.get('frames', 0)) >= 8
                          and int(depth.get('duplicate_timestamps', 0)) == 0
                          and int(depth.get('regressed_timestamps', 0)) == 0
                          and 0.0 < median_gap_ms <= 1500.0
                          and maximum_gap_ms <= 1500.0)
        except (TypeError, ValueError):
            stable = False
        quality = {
            'status': 'VALID_DEPTH' if valid else 'SENSOR_ERROR',
            'code': '' if valid else 'DEPTH_HEALTH_REJECTED',
            'reason': '' if valid else 'Independent camera health rejected live depth',
            'depth_valid_ratio': float(depth.get('valid_ratio', 0.0) or 0.0),
            'source': '/camera/health',
        }
        # A forwarded heartbeat must not make the underlying image younger.
        stamp = self.now_s() - depth_age_s if age_valid else None
        with self.lock:
            self.live_depth_quality = quality
            self.live_depth_stamp = stamp
            self.live_depth_receive_stamp = stamp
            self.delegated_depth_stable = stable
            if stamp is not None:
                self.depth_window.add(stamp, quality)

    def on_robot(self, pose, joints):
        try:
            if pose.header.frame_id != self.settings['base_frame']:
                raise CalibrationError('TCP frame does not match configured base frame')
            names = [f'magician_joint_{i}' for i in range(1, 5)]
            angles = np.array([joints.position[joints.name.index(name)] for name in names])
            q = pose.pose.orientation
            quaternion = np.array([q.x, q.y, q.z, q.w])
            if not np.isclose(np.linalg.norm(quaternion), 1.0, atol=1e-3):
                raise CalibrationError('Invalid TCP quaternion')
            p = pose.pose.position
            matrix = transform(Rotation.from_quat(quaternion).as_matrix(), [p.x, p.y, p.z])
            stamp = stamp_seconds(pose)
            if not np.isfinite(matrix).all() or not np.isfinite(angles).all():
                raise CalibrationError('Nonfinite robot telemetry')
            with self.lock:
                if self.history and stamp <= self.history[-1][0]:
                    self.history.clear()
                    raise CalibrationError('Robot clock moved backwards or repeated')
                self.history.append((stamp, matrix, angles))
        except (CalibrationError, ValueError, IndexError) as error:
            self.status('FAIL', str(error))
            self.stop.set()

    def on_camera(self, rgb, depth, info):
        self.on_depth(depth)
        with self.lock:
            self.bundle = (rgb, depth, info)

    def on_native_cloud(self, cloud):
        """Keep only the newest native sample; decoding happens at capture."""
        with self.lock:
            self.last_native_cloud = cloud
            self.last_native_cloud_receive_monotonic = time.monotonic()

    def on_depth(self, depth):
        stamp = stamp_seconds(depth)
        now = time.monotonic()
        with self.lock:
            if stamp == self.last_depth_processed_stamp:
                return
            # Full-frame robust statistics include medians and MAD. Ten live
            # checks per second retains a 100 ms fail-closed response while
            # avoiding CPU starvation of the 30 Hz camera transport.
            if now - self.last_depth_processed_monotonic < 0.1:
                return
            self.last_depth_processed_stamp = stamp
            self.last_depth_processed_monotonic = now
        try:
            quality = depth_quality(self.bridge.imgmsg_to_cv2(depth, 'passthrough'),
                                    depth.encoding, self.limits)
        except Exception as error:
            quality = {'status': 'SENSOR_ERROR', 'code': 'DEPTH_DECODE_FAILED',
                       'reason': str(error), 'depth_valid_ratio': 0.}
        with self.lock:
            self.live_depth_quality = quality
            self.live_depth_stamp = stamp
            self.live_depth_receive_stamp = self.now_s()
            self.depth_window.add(stamp, quality)
        # Invalid depth must stop active calibration immediately, including
        # motion between captures. A fresh timestamp alone is insufficient.
        if quality['status'] != 'VALID_DEPTH' and self.state not in ('UNCALIBRATED', 'STARTING', 'FAIL'):
            self.stop.set()
            self.status('FAIL', quality['code'] + ': ' + quality['reason'])

    def hardware_readiness(self):
        now = self.now_s()
        with self.lock:
            recent_response = any(
                stamp is not None and 0 <= now - stamp <= 0.6
                for stamp in (self.tcp_stamp, self.joints_stamp,
                              self.alarm_stamp if self.alarm_stamp else None))
            safety_supported = bool(self.settings['safety_state_topic'])
            safety_verified = (safety_supported and self.safety_verified
                               and self.safety_stamp is not None
                               and 0 <= now - self.safety_stamp <= 0.6)
            return evaluate_hardware_readiness(
                now=now, depth_quality=self.live_depth_quality,
                # Freshness is about arrival at this node; sensor timestamp is
                # validated separately and must keep advancing.
                depth_stamp=self.live_depth_receive_stamp,
                depth_stable=(self.depth_window.stable(now)
                              or self.delegated_depth_stable),
                tcp_stamp=self.tcp_stamp, joints_stamp=self.joints_stamp,
                alarm_stamp=self.alarm_stamp if self.alarm_stamp else None,
                alarms=list(self.alarms),
                robot_connected=self.robot_response_seen and recent_response,
                safety_supported=safety_supported,
                safety_verified=safety_verified,
                physical_estop_present=bool(self.settings['physical_estop_present']),
                operator_safety_verified=bool(self.settings['operator_safety_verified']),
                # Probe evidence: median depth period is ~0.566 s and healthy
                # gaps can exceed the old 0.5 s lease. 1.5 s is the validated
                # stability-window maximum, not a point-cloud-derived timeout.
                depth_ttl_s=1.5)

    def health_error(self):
        if self.passive_capture_active:
            return self.passive_health_error()
        now = self.now_s()
        readiness = self.hardware_readiness()
        if not readiness.ready:
            return readiness.reason
        if self.settings['carrier_frame']:
            try:
                latest = self.carrier_tf.lookup_transform(
                    self.settings['base_frame'], self.settings['carrier_frame'], rclpy.time.Time())
                if not 0 <= now - stamp_seconds(latest) < 0.5:
                    return 'Camera-carrier TF is stale or not a dynamic kinematic frame'
            except TransformException as error:
                return 'Camera-carrier TF unavailable: ' + str(error)
        with self.lock:
            if self.bundle is None:
                return 'Waiting for synchronized RGB, depth and CameraInfo'
            if self.live_depth_quality is None:
                return 'Depth quality has not been established'
            if self.live_depth_quality['status'] != 'VALID_DEPTH':
                return self.live_depth_quality['code'] + ': ' + self.live_depth_quality['reason']
            stamps = [stamp_seconds(message) for message in self.bundle]
            if any(not 0 <= now - stamp < 0.5 for stamp in stamps):
                return 'RGB-D telemetry is stale'
            if any(message.header.frame_id != self.settings['camera_frame'] for message in self.bundle):
                return 'RGB-D frames must all be the registered optical frame'
            if self.calibration_context is not None and self.camera_context(self.bundle[2]) != self.calibration_context:
                return 'Camera identity or intrinsics changed'
        return ''

    def passive_health_error(self):
        """Capture-only health gate; never authorizes or accompanies motion."""
        now = self.now_s()
        with self.lock:
            if self.alarms:
                return 'Active robot alarms'
            if self.tcp_stamp is None or not 0 <= now - self.tcp_stamp < 0.6:
                return 'TCP telemetry is stale'
            if self.joints_stamp is None or not 0 <= now - self.joints_stamp < 0.6:
                return 'Joint telemetry is stale'
            if self.bundle is None:
                return 'Waiting for synchronized RGB, depth and CameraInfo'
            rgb, depth, info = self.bundle
            stamps = [stamp_seconds(message) for message in self.bundle]
            if any(not 0 <= now - stamp < 1.5 for stamp in stamps):
                return 'RGB-D telemetry is stale'
            if abs(stamps[0] - stamps[1]) * 1000.0 > 100.0:
                return 'RGB/Depth synchronization skew exceeds 100 ms'
            if any(message.header.frame_id != self.settings['camera_frame']
                   for message in self.bundle):
                return 'RGB-D frames must all be the registered optical frame'
            if self.live_depth_quality is None:
                return 'Depth quality has not been established'
            if self.live_depth_quality['status'] != 'VALID_DEPTH':
                return self.live_depth_quality['code'] + ': ' + self.live_depth_quality['reason']
            if self.live_depth_quality.get('depth_valid_ratio', 0.0) < self.limits.min_depth_valid_ratio:
                return 'Depth valid ratio is below the markerless threshold'
            if self.calibration_context is not None and self.camera_context(info) != self.calibration_context:
                return 'Camera identity or intrinsics changed'
        return ''

    def camera_context(self, info):
        return {
            'camera_id': self.settings['camera_id'], 'camera_frame': info.header.frame_id,
            'base_frame': self.settings['base_frame'], 'tool_frame': self.settings['tool_frame'],
            'carrier_frame': self.settings['carrier_frame'],
            'width': int(info.width), 'height': int(info.height),
            'k': list(info.k), 'p': list(info.p), 'd': list(info.d),
            'distortion_model': info.distortion_model,
            'binning': [info.binning_x, info.binning_y],
            'roi': [info.roi.x_offset, info.roi.y_offset, info.roi.width, info.roi.height],
            'mount_digest': self.mount.digest if self.mount else '',
        }

    def intrinsics_fingerprint(self, info):
        return fingerprint({
            'width': int(info.width), 'height': int(info.height),
            'k': list(info.k), 'p': list(info.p), 'd': list(info.d),
            'distortion_model': info.distortion_model,
            'binning': [info.binning_x, info.binning_y],
            'roi': [info.roi.x_offset, info.roi.y_offset,
                    info.roi.width, info.roi.height],
        })

    def status(self, state, reason=''):
        self.state, self.reason = state, reason

    def is_ready(self):
        """REAL_MOTION_READY: verified calibration plus all live safety gates."""
        workflow = self.workflow
        return (self.state == 'READY' and workflow is not None
                and workflow.state == 'READY'
                and workflow.verified_monotonic is not None
                and time.monotonic() - workflow.verified_monotonic < self.settings['ready_ttl_s']
                and not live_acceptance_error(workflow.report)
                and not self.health_error() and not self.stop.is_set())

    def passive_capture_readiness(self):
        """Readiness to observe a stationary pose; never grants robot motion."""
        hardware = self.hardware_readiness()
        blockers = list(hardware.blockers)
        with self.lock:
            bundle = self.bundle
        if bundle is None:
            blockers.append('RGB_DEPTH_CAMERAINFO_NOT_SYNCHRONIZED')
        else:
            rgb, depth, info = bundle
            if any(message.header.frame_id != self.settings['camera_frame']
                   for message in bundle):
                blockers.append('RGB_DEPTH_CAMERAINFO_FRAME_MISMATCH')
            native, native_state = self._native_cloud_for(stamp_seconds(depth))
            # Aligned metric depth is itself a usable point-cloud source.
            if self.settings['point_cloud_source'] == 'ORBBEC_TOPIC' and native is None:
                blockers.append('ORBBEC_POINT_CLOUD_' + native_state.upper())
        try:
            mount_blockers = Mount.translation_constraint_blockers(
                self.settings['mount_model'], self.limits,
                carrier_frame=self.settings['carrier_frame'])
            blockers.extend('MOUNT_' + item for item in mount_blockers)
        except Exception as error:
            blockers.append('MOUNT_CONFIGURATION_ERROR:' + str(error))
        if self.passive_session_error:
            blockers.append('SESSION_INCOMPATIBLE:' + self.passive_session_error)
        manifest = self.passive_session.manifest
        if manifest is None:
            blockers.append('PASSIVE_SESSION_MISSING')
        stable, stability = self._table_touchoff_stability()
        if not stable:
            blockers.append('ROBOT_NOT_STABLE:' + stability['reason'])
        return {'hardware_ready': not bool(hardware.blockers) and bundle is not None,
                'passive_capture_ready': not bool(blockers),
                'real_motion_ready': self.is_ready(),
                'geometry_verified': bool(self.mount is not None and self.mount.rotation_seed_verified),
                'point_cloud_source_usable': bundle is not None and not any(
                    item.startswith('ORBBEC_POINT_CLOUD_') for item in blockers),
                'native_cloud_state': (None if bundle is None else native_state),
                'robot_stability': stability, 'blockers': blockers}

    def supervise(self):
        if self.auto_pending:
            self.auto_pending = False
            self.start_operation(False)
        if self.state == 'READY' and not self.is_ready():
            acceptance = live_acceptance_error(self.workflow.report) if self.workflow else ''
            self.status('FAIL', self.health_error() or acceptance or 'Verification expired or was cancelled')
        if self.state in ('CAPTURING', 'LOADING', 'CALIBRATING', 'SOLVING', 'VERIFYING'):
            reason = self.health_error()
            if reason:
                self.stop.set()
                self.status('FAIL', reason)
        active_goal = self.active_goal
        if active_goal is not None and (self.health_error() or self.stop.is_set()):
            active_goal.cancel_goal_async()
            self.stop.set()
        workflow = self.workflow
        ready = self.is_ready()
        passive_readiness = self.passive_capture_readiness()
        message = String()
        message.data = json.dumps(self.status_payload(), allow_nan=False)
        self.publisher.publish(message)
        if ready and workflow is not None and workflow is self.workflow:
            value = workflow.solution.tool_T_camera
            msg = TransformStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.settings['carrier_frame'] or self.settings['tool_frame']
            msg.child_frame_id = self.settings['calibrated_frame']
            msg.transform.translation.x, msg.transform.translation.y, msg.transform.translation.z = value[:3, 3]
            q = Rotation.from_matrix(value[:3, :3]).as_quat()
            (msg.transform.rotation.x, msg.transform.rotation.y,
             msg.transform.rotation.z, msg.transform.rotation.w) = q
            self.broadcaster.sendTransform(msg)

    def status_payload(self):
        workflow = self.workflow
        report = workflow.report if workflow else {}
        ready = self.is_ready()
        passive_readiness = self.passive_capture_readiness()
        available = bool(
            workflow is not None
            and getattr(workflow, 'solution', None) is not None
            and getattr(workflow, 'anchor', None) is not None
        )
        hardware = self.hardware_readiness()
        thai = {
            'READY': ('ฮาร์ดแวร์พร้อมสำหรับการคาลิเบรต',
                      'ฮาร์ดแวร์ผ่านทุกเงื่อนไขความพร้อม', ''),
            'DEPTH_ERROR': ('กำลังตรวจสอบกล้อง', 'Depth ไม่พร้อม',
                            'ตรวจการเชื่อมต่อกล้องและค่า LDP แล้วลองใหม่'),
            'ROBOT_TELEMETRY_ERROR': ('กำลังตรวจสอบหุ่นยนต์',
                                      'ไม่พบข้อมูลตำแหน่งหุ่นยนต์',
                                      'ตรวจไฟเลี้ยง สาย USB และ state publisher'),
            'ROBOT_ALARM': ('กำลังตรวจสอบหุ่นยนต์',
                            'ระบบยังไม่พร้อมให้หุ่นยนต์เคลื่อนที่',
                            'แก้ alarm ของ Dobot ก่อนเริ่มคาลิเบรต'),
            'SAFETY_UNVERIFIED': ('กำลังตรวจสอบระบบความปลอดภัย',
                                  'ระบบยังไม่พร้อมให้หุ่นยนต์เคลื่อนที่',
                                  'เชื่อมต่อสัญญาณความปลอดภัยจากฮาร์ดแวร์ที่ตรวจสอบได้'),
            'SENSOR_ERROR': ('กำลังตรวจสอบกล้อง', 'Depth ไม่พร้อม',
                             'ตรวจกล้องและ encoding ของ Depth'),
            'NOT_READY': ('กำลังตรวจสอบระบบความปลอดภัย',
                          'ระบบยังไม่พร้อมให้หุ่นยนต์เคลื่อนที่',
                          'ตรวจ workspace และระยะปลอดภัยเหนือโต๊ะ'),
        }[hardware.state]
        metrics = report.get('metrics', {})
        workflow_metrics = getattr(getattr(workflow, 'solution', None), 'metrics', {}) or {}
        translation_m = metrics.get('translation_residual_m',
                                    workflow_metrics.get('translation_residual_m'))
        rotation_deg = metrics.get('rotation_residual_deg',
                                   workflow_metrics.get('rotation_residual_deg'))
        verification = report.get('result', 'FAIL')
        blockers = [] if ready else [self.reason or self.health_error()
                                     or 'markerless calibration verification missing']
        guidance = self.passive_guidance()
        return {'state': self.state, 'ready': ready, 'available': available,
                'reason': self.reason,
                'stamp': self.now_s(), 'result': 'PASS' if ready else 'FAIL',
                'architecture': 'markerless_hand_eye',
                'command_frame': self.settings['tool_frame'],
                'calibration_parent_frame': self.settings['carrier_frame'] or self.settings['tool_frame'],
                'tcp_only_consumer_supported': not bool(self.settings['carrier_frame']),
                'bundle_path': str(Path(self.settings['calibration_file']).expanduser()),
                'bundle_loaded': bool(workflow and workflow.bundle_loaded),
                'context_digest': fingerprint(workflow.context) if workflow else '',
                'geometry_verified': bool(self.mount is not None
                                          and self.mount.rotation_seed_verified),
                'readiness': {
                    'HARDWARE_READY': passive_readiness['hardware_ready'],
                    'PASSIVE_CAPTURE_READY': passive_readiness['passive_capture_ready'],
                    'REAL_MOTION_READY': passive_readiness['real_motion_ready'],
                    'GEOMETRY_VERIFIED': passive_readiness['geometry_verified'],
                    'point_cloud_source_usable': passive_readiness['point_cloud_source_usable'],
                    'native_cloud_state': passive_readiness['native_cloud_state'],
                    'blockers': passive_readiness['blockers'],
                },
                'passive_mode': True,
                'passive_pose_count': len(self.passive_captures),
                'passive_pose_metadata': list(self.passive_capture_metadata),
                'passive_guidance': guidance,
                'supervised_auto': self.supervised_auto.snapshot(),
                'samples_collected': (int(workflow.samples_collected) if workflow
                                      else len(self.passive_captures)),
                'samples_accepted': (int(workflow.samples_accepted) if workflow
                                     else len(self.passive_captures)),
                'samples_rejected': int(workflow.samples_rejected) if workflow else 0,
                'translation_residual_mm': (None if translation_m is None
                                            else float(translation_m) * 1000.0),
                'rotation_residual_deg': (None if rotation_deg is None else float(rotation_deg)),
                'verification_status': verification,
                'verification_samples': int(metrics.get('pose_count', 0)),
                'reload_verification_status': ('PASS' if workflow and workflow.reload_verified
                                               else 'MISSING'),
                'mount_translation_error_bound_mm': (None if self.mount is None
                                                     else self.mount.translation_error_bound_m
                                                     * 1000.0),
                'mount_envelope_mm': (None if self.mount is None
                                      else self.mount.envelope_radius_m * 1000.0),
                'blockers': blockers,
                'metrics': metrics,
                'depth_quality': self.live_depth_quality,
                'rgb_health': (self.camera_health or {}).get('streams', {}).get('rgb', {}),
                'depth_health': (self.camera_health or {}).get('streams', {}).get('depth', {}),
                'tcp_fresh': hardware.tcp_fresh,
                'joint_fresh': hardware.joints_fresh,
                'alarm_state': {'fresh': hardware.alarms_fresh, 'codes': list(self.alarms)},
                'physical_estop': ('PRESENT' if hardware.physical_estop_present else 'NOT PRESENT'),
                'hardware_safety': ('OPERATOR VERIFIED' if hardware.operator_safety_verified
                                    else 'NOT VERIFIED'),
                'software_estop_monitoring': hardware.software_estop_monitoring,
                'safety_input_state': {
                    'supported': hardware.safety_supported,
                    'verified': hardware.safety_verified,
                },
                'hardware_readiness': hardware.to_dict(),
                'ui': {'language': 'th', 'step': thai[0], 'status': thai[1],
                       'recommended_action': thai[2],
                       'motion_allowed': hardware.ready}}

    def auto_preflight(self):
        blockers = []
        hardware = self.hardware_readiness()
        if not hardware.ready:
            blockers.extend(hardware.blockers)
        try:
            mount_blockers = Mount.translation_constraint_blockers(
                self.settings['mount_model'], self.limits,
                carrier_frame=self.settings['carrier_frame'])
            blockers.extend(mount_blockers)
        except Exception as error:
            blockers.append('MOUNT_SAFETY_GATE_ERROR: ' + str(error))
        manifest = self.passive_session.manifest or {}
        if self.passive_session_error:
            blockers.append('SESSION_INCOMPATIBLE: ' + self.passive_session_error)
        if manifest.get('calibration_mode') != 'markerless_passive':
            blockers.append('SESSION_MODE_INVALID')
        if len(manifest.get('target_poses') or []) != 10:
            blockers.append('CALIBRATION_PLAN_MISSING_OR_INCOMPLETE')
        reference = self.table_reference()
        if reference['status'] == 'INVALID':
            blockers.append('TABLE_REFERENCE_STATUS_INVALID')
        return blockers, hardware.state

    def auto_validate_target(self, target):
        blockers = []
        xyz = np.asarray(target.get('xyz_mm', []), dtype=float)
        j4 = float(target.get('j4_deg', float('nan')))
        if xyz.shape != (3,) or not np.isfinite(xyz).all() or not np.isfinite(j4):
            return ['TARGET_NONFINITE_OR_MALFORMED']
        point = xyz * 0.001
        radius = float(np.linalg.norm(point[:2]))
        if not (0.14 <= radius <= 0.30 and point[0] >= 0.08 and 0.07 <= point[2] <= 0.23):
            blockers.append('TARGET_OUTSIDE_CALIBRATION_WORKSPACE')
        envelope = float(self.mount.envelope_radius_m if self.mount is not None else
                         yaml.safe_load(Path(self.settings['mount_model']).read_text()).get(
                             'envelope_radius_m', float('nan')))
        reference = self.table_reference()
        table_height = reference['z_m']
        if reference['status'] == 'INVALID':
            blockers.append('TABLE_REFERENCE_STATUS_INVALID')
        elif table_height is None:
            # Planning and dry-run may proceed under an explicit operator
            # acknowledgement. Coordinate clearance remains unverified and is
            # exposed in status; it is never reported as a clearance pass.
            pass
        elif not np.isfinite(envelope) or abs(envelope - 0.1526) > 1e-6:
            blockers.append('MOUNT_ENVELOPE_NOT_COMMISSIONED_152_6_MM')
        else:
            required_z = (table_height + envelope
                          + float(self.settings['calibration_minimum_clearance_m']))
            if point[2] < required_z:
                blockers.append(
                    f'CONSERVATIVE_TABLE_CLEARANCE_FAILED: target_z={point[2]:.4f}m '
                    f'< required={required_z:.4f}m')
            if np.linalg.norm(point) < envelope + float(self.settings['calibration_minimum_clearance_m']):
                blockers.append('CONSERVATIVE_BASE_CLEARANCE_FAILED')
        if not blockers:
            if not self.validator.wait_for_service(timeout_sec=2.0):
                blockers.append('TRAJECTORY_VALIDATOR_UNAVAILABLE')
            else:
                request = EvaluatePTPTrajectory.Request()
                # Calibration poses do not require a Cartesian straight-line
                # transfer.  Validate as MOVJ so the controller plans in joint
                # space; MOVL remains an audit alternative, never the sole
                # feasibility criterion.
                request.motion_type = 1
                request.target = [float(value) for value in xyz] + [j4]
                future = self.validator.call_async(request)
                deadline = time.monotonic() + 8.0
                while not future.done() and time.monotonic() < deadline:
                    if not self.hardware_readiness().ready:
                        blockers.append('READINESS_LOST_DURING_PATH_VALIDATION')
                        break
                    time.sleep(0.02)
                if not blockers:
                    if not future.done() or future.result() is None:
                        blockers.append('TRAJECTORY_VALIDATION_TIMEOUT')
                    elif not future.result().is_valid:
                        blockers.append('JOINT_OR_PATH_VALIDATION_FAILED: '
                                        + future.result().message)
        return blockers

    def table_height_m(self):
        """Prefer a qualified passive touch-off over an unset launch parameter."""
        touch_off = self.table_touchoff.summary()
        measured = touch_off['table_surface_z_in_magician_base_link_mm']
        if measured is not None:
            return float(measured) / 1000.0
        return float(self.settings['calibration_table_height_m'])

    def table_reference(self):
        """State of the table datum, distinct from all remaining safety gates."""
        measured = self.table_height_m()
        if np.isfinite(measured):
            return {'status': 'MEASURED', 'source': 'manual_touch_off', 'z_m': measured,
                    'blocker': False, 'coordinate_clearance_verified': True,
                    'warning': None}
        acknowledged = (self.settings['table_reference_status'] == 'operator_confirmed'
                        and self.settings['table_reference_source']
                        == 'physical_operator_confirmation')
        if acknowledged:
            return {'status': 'OPERATOR_CONFIRMED_UNVERIFIED',
                    'source': 'physical_operator_confirmation', 'z_m': None,
                    'blocker': False, 'coordinate_clearance_verified': False,
                    'warning': 'TABLE_REFERENCE_UNVERIFIED: coordinate table clearance not verified'}
        return {'status': 'INVALID', 'source': self.settings['table_reference_source'],
                'z_m': None, 'blocker': True,
                'coordinate_clearance_verified': False,
                'warning': 'TABLE_REFERENCE_STATUS_INVALID'}

    def _table_touchoff_stability(self):
        now = self.now_s()
        with self.lock:
            recent = [item for item in self.history if 0 <= now - item[0] <= 0.7]
        if len(recent) < 3:
            return False, {'tcp_span_mm': None, 'joint_span_deg': None,
                           'reason': 'insufficient_fresh_robot_samples'}
        latest = recent[-1]
        tcp_span = max(np.linalg.norm(item[1][:3, 3] - latest[1][:3, 3])
                       for item in recent) * 1000.0
        joint_span = max(np.linalg.norm(item[2] - latest[2]) for item in recent) * 180.0 / np.pi
        stable = tcp_span <= 1.0 and joint_span <= 0.5
        return stable, {'tcp_span_mm': float(tcp_span), 'joint_span_deg': float(joint_span),
                        'reason': '' if stable else 'robot_not_settled'}

    def table_touchoff_capture_service(self, request, response):
        """Snapshot manual contact only; no action/service can move the robot here."""
        stable, stability = self._table_touchoff_stability()
        if not stable:
            response.success = False
            response.message = json.dumps({'accepted': False, **self.table_touchoff.summary(),
                                           'pose_stability': stability,
                                           'rejection_reasons': [stability['reason']]},
                                          allow_nan=False, separators=(',', ':'))
            return response
        with self.lock:
            tool_z_mm = float(self.history[-1][1][2, 3] * 1000.0)
        table_z_mm = self.table_touchoff.add(tool_z_mm)
        result = self.table_touchoff.summary()
        response.success = True
        response.message = json.dumps({'accepted': True, 'measured_tool_z_mm': tool_z_mm,
                                       'derived_table_z_mm': table_z_mm,
                                       'pose_stability': stability, **result,
                                       'geometry_verified': False,
                                       'motion_command_sent': False},
                                      allow_nan=False, separators=(',', ':'))
        return response

    def table_touchoff_status_service(self, request, response):
        response.success = True
        response.message = json.dumps({**self.table_touchoff.summary(),
                                       'geometry_verified': False,
                                       'motion_command_sent': False},
                                      allow_nan=False, separators=(',', ':'))
        return response

    def table_touchoff_clear_service(self, request, response):
        self.table_touchoff.clear()
        response.success = True
        response.message = json.dumps({**self.table_touchoff.summary(),
                                       'motion_command_sent': False},
                                      allow_nan=False, separators=(',', ':'))
        return response

    def passive_guidance(self):
        count = len(self.passive_captures)
        targets = ((self.passive_session.manifest or {}).get('target_poses') or [])
        progress = [
            {'pose_index': index,
             'state': ('ACCEPTED' if index <= count else
                       'GUIDE_TO_TARGET' if index == count + 1 else 'PENDING')}
            for index in range(1, 11)
        ]
        if count >= 10:
            return {'state': 'COLLECTION_COMPLETE', 'capture_enabled': False,
                    'automatic_capture': False, 'progress': progress}
        if not targets or len(targets) < count + 1:
            return {'state': 'PLAN_UNAVAILABLE', 'capture_enabled': False,
                    'automatic_capture': False, 'progress': progress}
        with self.lock:
            history = list(self.history)
        if not history:
            return {'state': 'TCP_UNAVAILABLE', 'capture_enabled': False,
                    'automatic_capture': False, 'progress': progress}
        now = self.now_s()
        recent = [item for item in history if 0 <= now - item[0] <= 0.7]
        latest = history[-1]
        stable = False
        stability = {'tcp_span_mm': None, 'joint_span_deg': None}
        if len(recent) >= 3:
            tcp_span = max(np.linalg.norm(item[1][:3, 3] - latest[1][:3, 3])
                           for item in recent) * 1000.0
            joint_span = max(np.linalg.norm(item[2] - latest[2])
                             for item in recent) * 180.0 / np.pi
            stability = {'tcp_span_mm': float(tcp_span),
                         'joint_span_deg': float(joint_span)}
            stable = tcp_span <= 1.0 and joint_span <= 0.5
        result = compute_guidance(
            latest[1][:3, 3] * 1000.0, np.rad2deg(latest[2][3]),
            targets[count], stable, self.hardware_readiness().ready)
        result['progress'] = progress
        result['pose_stability'] = stability
        return result

    def checkpoint(self):
        if self.stop.is_set():
            raise CalibrationError('Calibration cancelled')
        reason = self.health_error()
        if reason:
            raise CalibrationError(reason)

    def start_service(self, request, response):
        response.success, response.message = self.start_operation(False)
        return response

    def recalibrate_service(self, request, response):
        response.success, response.message = self.start_operation(True)
        return response

    def verify_service(self, request, response):
        from pathlib import Path
        if self.operation_lock.locked():
            response.success, response.message = False, 'Calibration is already running'
            return response
        if not Path(self.settings['calibration_file']).expanduser().is_file():
            self.status('FAIL', 'No saved calibration to verify')
            response.success, response.message = False, self.reason
            return response
        response.success, response.message = self.start_operation(False, verify_only=True)
        return response

    def ready_service(self, request, response):
        # This endpoint is intentionally passive-data readiness. Geometry is an
        # output of the collection/solve workflow, never an input to it.
        self.ensure_camera_sync()
        readiness = self.passive_capture_readiness()
        response.success = readiness['passive_capture_ready']
        response.message = json.dumps(readiness, allow_nan=False, separators=(',', ':'))
        return response

    def _passive_reply(self, response, accepted, **fields):
        payload = {'accepted': bool(accepted), **fields}
        response.success = bool(accepted)
        response.message = json.dumps(payload, allow_nan=False, separators=(',', ':'))
        return response

    def _prepare_passive_capture(self):
        """Enable capture inputs and measured mount constraint without motion."""
        if self.operation_lock.locked():
            raise CalibrationError('An automatic calibration operation is active')
        if self.mount is None:
            internal = self.camera_reference_to_optical()
            self.mount = Mount.load_translation_constraint(
                self.settings['mount_model'], internal, self.limits,
                carrier_frame=self.settings['carrier_frame'])
        self.ensure_camera_sync()
        deadline = time.monotonic() + self.settings['capture_timeout_s']
        while time.monotonic() < deadline:
            with self.lock:
                bundle = self.bundle
            if bundle is not None:
                if self.calibration_context is None:
                    self.calibration_context = self.camera_context(bundle[2])
                return
            time.sleep(0.03)
        raise CalibrationError('Waiting for synchronized RGB, depth, CameraInfo and PointCloud2')

    def capture_pose_service(self, request, response):
        """Capture one operator-positioned pose; this method has no motion path."""
        reasons = []
        try:
            guidance = self.passive_guidance()
            if self.passive_captures and not guidance.get('capture_enabled', False):
                return self._passive_reply(
                    response, False, pose_index=len(self.passive_captures) + 1,
                    guidance=guidance,
                    rejection_reasons=['Passive guidance target has not been reached'],
                    geometry_verified=False)
            self.passive_capture_active = True
            self._prepare_passive_capture()
            capture = self.capture()
            blur_score = float(cv2.Laplacian(
                cv2.cvtColor(capture.rgb, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
            if blur_score < 40.0:
                reasons.append(f'image_blur_score_too_low:{blur_score:.3f}<40')

            distances = [pose_distance(capture.calibration_pose, item.calibration_pose)
                         for item in self.passive_captures]
            if any(distance < 0.004 and angle < 2.0 for distance, angle in distances):
                reasons.append('pose_baseline_too_small_or_duplicate')

            registration_quality = {'status': 'ANCHOR'}
            overlap = None
            if self.passive_captures and not reasons:
                registration = register(self.passive_captures[-1], capture, self.limits,
                                        seed=len(self.passive_captures))
                registration_quality = {'status': 'PASS', **registration.quality}
                overlap = float(registration.quality['registration_fitness'])

            with self.lock:
                nearest = min(self.history, key=lambda item: abs(item[0] - capture.stamp))
                history = [item for item in self.history
                           if capture.stamp - 0.68 <= item[0] <= capture.stamp + 0.08]
                bundle = self.bundle
            if not history:
                reasons.append('robot_pose_history_missing_at_exposure')
            tcp_span_mm = (max(np.linalg.norm(item[1][:3, 3] - nearest[1][:3, 3])
                               for item in history) * 1000.0 if history else None)
            joint_span_deg = (max(np.linalg.norm(item[2] - nearest[2])
                                  for item in history) * 180.0 / np.pi if history else None)
            stamps = [stamp_seconds(message) for message in bundle]
            sync_skew_ms = float((max(stamps) - min(stamps)) * 1000.0)
            rgb_health = (self.camera_health or {}).get('streams', {}).get('rgb', {})
            depth_health = (self.camera_health or {}).get('streams', {}).get('depth', {})
            xyz_mm = [float(value * 1000.0) for value in capture.base_T_tool[:3, 3]]
            j4_yaw_deg = float(np.rad2deg(nearest[2][3]))
            fields = {
                'pose_index': len(self.passive_captures) + 1,
                'XYZ_mm': xyz_mm,
                'J4_yaw_deg': j4_yaw_deg,
                'rgb_fps': rgb_health.get('timestamp_fps', rgb_health.get('fps')),
                'health_node_rgb_fps': rgb_health.get('fps'),
                'depth_fps': depth_health.get('timestamp_fps', depth_health.get('fps')),
                'sync_skew_ms': sync_skew_ms,
                'depth_valid_ratio': float(capture.quality['depth_valid_ratio']),
                'point_cloud_source': capture.quality['point_cloud_source'],
                'cloud_point_count': int(capture.quality['filtered_cloud_points']),
                'cloud_frame_id': capture.quality['cloud_frame_id'],
                'cloud_timestamp': capture.quality['cloud_timestamp'],
                'native_cross_validation': capture.quality['native_cross_validation'],
                'blur_score': blur_score,
                'pose_stability': {'tcp_span_mm': tcp_span_mm,
                                   'joint_span_deg': joint_span_deg},
                'scene_overlap': overlap,
                'registration_quality': registration_quality,
                'plane_diagnostics': {key: value for key, value in capture.quality.items()
                                     if key.startswith('plane_') or key.endswith('cloud_points')
                                     or key == 'debug_artifact'},
                'rejection_reasons': reasons,
                'geometry_verified': False,
            }
            if reasons:
                return self._passive_reply(response, False, **fields)
            self.passive_session.save_pose(
                capture, nearest[2], fields, stamps[0], stamps[1],
                self.intrinsics_fingerprint(bundle[2]),
                camera_info={
                    'width': int(bundle[2].width), 'height': int(bundle[2].height),
                    'k': list(bundle[2].k), 'p': list(bundle[2].p),
                    'd': list(bundle[2].d),
                    'distortion_model': bundle[2].distortion_model,
                    'frame_id': bundle[2].header.frame_id,
                },
                joint_names=[f'magician_joint_{i}' for i in range(1, 5)])
            self.passive_captures.append(capture)
            self.passive_capture_metadata.append(fields)
            if len(self.passive_captures) == 1:
                self.passive_session.ensure_plan(
                    calibration_plan(xyz_mm, j4_yaw_deg))
            fields['pose_index'] = len(self.passive_captures)
            fields['next_guidance'] = self.passive_guidance()
            return self._passive_reply(response, True, **fields)
        except Exception as error:
            return self._passive_reply(
                response, False, pose_index=len(self.passive_captures) + 1,
                rejection_reasons=[str(error)], geometry_verified=False)
        finally:
            self.passive_capture_active = False

    def passive_capture_test_service(self, request, response):
        """Three non-persistent passive captures. This service never commands motion."""
        reports = []
        try:
            self.passive_capture_active = True
            self._prepare_passive_capture()
            for _ in range(3):
                capture = self.capture()
                quality = capture.quality
                native_metrics = quality['native_cross_validation']
                cloud_stamp = float(quality['cloud_timestamp'])
                extent_mm = ((np.max(capture.cloud, axis=0) - np.min(capture.cloud, axis=0))
                             * 1000.0).tolist()
                reports.append({
                    'point_cloud_source': quality['point_cloud_source'],
                    'native_cloud_fresh': quality['native_cloud_state'] == 'fresh',
                    'generated_cloud_used': quality['point_cloud_source'] == 'DEPTH_DEPROJECTION',
                    'cloud_frame': quality['cloud_frame_id'],
                    'cloud_points': int(quality['filtered_cloud_points']),
                    'finite_points': int(quality['filtered_cloud_points']),
                    'nan_inf_ratio': quality['nan_inf_ratio'],
                    'timestamp': float(capture.stamp),
                    'rgb_depth_skew_ms': quality['rgb_depth_skew_ms'],
                    'depth_cloud_skew_ms': quality['depth_cloud_skew_ms'],
                    'depth_valid_ratio': float(quality['depth_valid_ratio']),
                    'plane_inliers': int(quality['plane_inlier_count']),
                    'plane_inlier_ratio': float(quality['plane_inlier_ratio']),
                    'plane_RMS_mm': float(quality['plane_rms_m']) * 1000.0,
                    'cloud_extent_mm': extent_mm,
                    'native_cloud_metrics': native_metrics,
                    'capture': 'ACCEPTED', 'rejection_reason': '',
                })
                time.sleep(0.15)
            response.success = True
            response.message = json.dumps({'markerless_capture_data_path': 'READY',
                                           'captures': reports,
                                           'auto_real_motion_enabled': False,
                                           'geometry_verified': False}, allow_nan=False)
        except Exception as error:
            reports.append({'capture': 'REJECTED', 'rejection_reason': str(error),
                            'scene_geometry_diagnostic': self._scene_geometry_diagnostic()})
            response.success = False
            response.message = json.dumps({'markerless_capture_data_path': 'NOT_READY',
                                           'captures': reports,
                                           'auto_real_motion_enabled': False,
                                           'geometry_verified': False}, allow_nan=False)
        finally:
            self.passive_capture_active = False
        return response

    def _scene_signature(self, capture):
        cloud = capture.cloud
        low, high = np.quantile(cloud, [0.02, 0.98], axis=0)
        voxel_m = 0.02
        occupied = np.unique(np.floor((cloud - low) / voxel_m).astype(np.int16), axis=0)
        histogram, _ = np.histogram(capture.depth[np.isfinite(capture.depth)], bins=32,
                                   range=(self.limits.min_depth_m, self.limits.max_depth_m), density=True)
        features = cv2.ORB_create(nfeatures=800).detect(
            cv2.cvtColor(capture.rgb, cv2.COLOR_BGR2GRAY), None)
        return {'plane': capture.plane.tolist(), 'extent_m': (high - low).tolist(),
                'depth_histogram': histogram.tolist(), 'depth_mean_m': float(np.mean(capture.depth)),
                'depth_std_m': float(np.std(capture.depth)),
                'voxel_size_m': voxel_m, 'voxel_occupancy': int(len(occupied)),
                'feature_count': int(len(features)), 'timestamp': float(capture.stamp),
                'camera_intrinsics_fingerprint': fingerprint(capture.intrinsics.tolist())}

    def validate_plan_service(self, request, response):
        """Read-only continuous MOVJ audit: current -> P1 -> ... -> P10."""
        try:
            with self.lock:
                if not self.history:
                    raise CalibrationError('Current robot joints are unavailable')
                current_pose = self.history[-1][1]
                start_xyz = (current_pose[:3, 3] * 1000.0).tolist()
                start_joints = (self.history[-1][2] * 180.0 / np.pi).tolist()
            plan = (self.passive_session.manifest or {}).get('target_poses') or []
            if len(plan) != 10:
                raise CalibrationError('Calibration plan must contain exactly 10 poses')
            limits = np.array([[-120., 120.], [-5., 90.], [-15., 90.], [-140., 140.]])
            soft = float(self.settings['planning_soft_margin_deg'])
            segments, failures = [], []
            previous_xyz, previous_joints, previous_j4 = start_xyz, start_joints, 0.0
            collision = PyBulletCollisionServer()
            for index, pose in enumerate(plan, 1):
                target_xyz, j4 = [float(x) for x in pose['xyz_mm']], float(pose['j4_deg'])
                target = target_xyz + [j4]
                target_joints = calc_inv_kin(*target)
                if target_joints is False:
                    failures.append(f'segment_{index}: IK_FAILED')
                    continue
                target_joints = np.asarray(target_joints, dtype=float)
                start_vector = np.asarray(previous_joints, dtype=float)
                count = max(2, int(np.ceil(np.max(np.abs(target_joints - start_vector)) / 2.0)) + 1)
                samples = np.linspace(start_vector, target_joints, count)
                low_margin = samples - limits[:, 0]
                high_margin = limits[:, 1] - samples
                hard = np.minimum(low_margin, high_margin)
                min_hard = hard.min(axis=0)
                min_soft = float(min_hard.min() - soft)
                collision_pass = bool(collision.validate_trajectory(1, previous_xyz + [previous_j4], target,
                                                                    True, joint_step_deg=2.0))
                passed = bool(np.all(min_hard > 0) and min_soft >= 0 and collision_pass)
                item = {'segment_index': index, 'start_XYZ_J4': previous_xyz + [previous_j4],
                        'target_XYZ_J4': target, 'start_joint_vector_deg': start_vector.tolist(),
                        'target_joint_vector_deg': target_joints.tolist(), 'selected_ik_branch': 'analytic_single_branch',
                        'trajectory_sample_count': int(count), 'joint_min_deg': samples.min(axis=0).tolist(),
                        'joint_max_deg': samples.max(axis=0).tolist(), 'minimum_hard_limit_margin_deg': min_hard.tolist(),
                        'minimum_soft_margin_deg': min_soft, 'collision_envelope': 'PASS' if collision_pass else 'FAIL',
                        'workspace': 'PASS', 'overall': 'PASS' if passed else 'FAIL',
                        'failure_sample_reason': '' if passed else 'hard_or_soft_margin_or_collision'}
                segments.append(item)
                if not passed:
                    failures.append(f'segment_{index}: ' + item['failure_sample_reason'])
                previous_xyz, previous_joints, previous_j4 = target_xyz, target_joints.tolist(), j4
            passed = len(segments) == 10 and not failures
            response.success = passed
            response.message = json.dumps({'plan_sequence_validation': 'PASS' if passed else 'FAIL',
                                           'motion_type': 'MOVJ/PTP', 'planning_soft_margin_deg': soft,
                                           'hard_joint_limits_deg': limits.tolist(), 'segments': segments,
                                           'failures': failures, 'motion_command_sent': False}, allow_nan=False)
        except Exception as error:
            response.success = False
            response.message = json.dumps({'plan_sequence_validation': 'FAIL', 'reason': str(error),
                                           'motion_command_sent': False})
        return response

    def scene_baseline_service(self, request, response):
        """Create a robust, non-persistent scene baseline; this has no motion path."""
        try:
            self.passive_capture_active = True
            self._prepare_passive_capture()
            capture = self.capture()
            self.scene_baseline = self._scene_signature(capture)
            response.success = True
            response.message = json.dumps({'scene_baseline': 'VALID', **self.scene_baseline,
                                           'persisted_pose': False, 'motion_command_sent': False},
                                          allow_nan=False)
        except Exception as error:
            response.success = False
            response.message = json.dumps({'scene_baseline': 'INVALID', 'reason': str(error),
                                           'persisted_pose': False, 'motion_command_sent': False})
        finally:
            self.passive_capture_active = False
        return response

    def scene_verify_service(self, request, response):
        try:
            if self.scene_baseline is None:
                raise CalibrationError('Scene baseline is missing')
            self.passive_capture_active = True
            self._prepare_passive_capture()
            current = self._scene_signature(self.capture())
            base = self.scene_baseline
            plane_angle = float(np.rad2deg(np.arccos(np.clip(
                abs(np.dot(base['plane'][:3], current['plane'][:3])), -1., 1.))))
            extent_change = float(np.max(np.abs(np.asarray(base['extent_m']) - current['extent_m'])))
            histogram_l1 = float(np.mean(np.abs(np.asarray(base['depth_histogram']) - current['depth_histogram'])))
            voxel_change = abs(base['voxel_occupancy'] - current['voxel_occupancy']) / max(base['voxel_occupancy'], 1)
            feature_change = abs(base['feature_count'] - current['feature_count']) / max(base['feature_count'], 1)
            passed = plane_angle <= 2.0 and extent_change <= .020 and histogram_l1 <= .15 and voxel_change <= .25 and feature_change <= .40
            if not passed:
                self.status('PAUSED', 'Scene changed beyond baseline thresholds')
            response.success = passed
            response.message = json.dumps({'scene_unchanged': 'PASS' if passed else 'FAIL',
                                           'plane_angle_deg': plane_angle, 'extent_change_m': extent_change,
                                           'depth_histogram_l1': histogram_l1, 'voxel_change_ratio': voxel_change,
                                           'feature_change_ratio': feature_change, 'current': current,
                                           'geometry_verified': False, 'motion_command_sent': False}, allow_nan=False)
        except Exception as error:
            response.success = False
            response.message = json.dumps({'scene_unchanged': 'FAIL', 'reason': str(error),
                                           'geometry_verified': False, 'motion_command_sent': False})
        finally:
            self.passive_capture_active = False
        return response

    def _scene_geometry_diagnostic(self):
        """Report the unchanged scene gate inputs even when it rejects a capture."""
        try:
            with self.lock:
                bundle = self.bundle
            if bundle is None:
                return {'available': False, 'reason': 'RGB_DEPTH_CAMERAINFO_NOT_SYNCHRONIZED'}
            _, depth, info = bundle
            depth_m = np.asarray(self.bridge.imgmsg_to_cv2(depth, 'passthrough'), dtype=float)
            if depth.encoding == '16UC1':
                depth_m *= 0.001
            intrinsics = np.array(info.p).reshape(3, 4)[:, :3]
            if intrinsics[0, 0] <= 0:
                intrinsics = np.array(info.k).reshape(3, 3)
            native, native_state = self._native_cloud_for(stamp_seconds(depth))
            source = ('ORBBEC_TOPIC' if native is not None else 'DEPTH_DEPROJECTION')
            if native is not None:
                raw = point_cloud2.read_points(native, field_names=('x', 'y', 'z'), skip_nans=False)
                points = np.column_stack([raw[name].reshape(-1) for name in ('x', 'y', 'z')])
            else:
                points = self._deproject_depth(depth_m, intrinsics)
            finite = points[np.isfinite(points).all(axis=1)]
            ranged = finite[(finite[:, 2] >= self.limits.min_depth_m)
                            & (finite[:, 2] <= self.limits.max_depth_m)]
            result = {'available': True, 'point_cloud_source': source,
                      'native_cloud_state': native_state, 'cloud_frame': self.settings['camera_frame'],
                      'finite_cloud_points': int(len(ranged)),
                      'nan_inf_ratio': float(1.0 - len(finite) / max(len(points), 1)),
                      'thresholds': {'min_points': self.limits.min_points,
                                     'min_scene_width_m': self.limits.min_scene_width_m,
                                     'min_scene_thickness_m': self.limits.min_scene_thickness_m,
                                     'depth_range_m': [self.limits.min_depth_m, self.limits.max_depth_m]}}
            if len(ranged) < self.limits.min_points:
                result['failed_thresholds'] = ['finite_cloud_points < min_points']
                return result
            low, high = np.quantile(ranged, [0.02, 0.98], axis=0)
            trimmed = ranged[((ranged >= low) & (ranged <= high)).all(axis=1)]
            centered = trimmed - np.median(trimmed, axis=0)
            covariance = np.cov(centered, rowvar=False)
            eigenvalues = np.linalg.eigvalsh(covariance)[::-1]
            spread = np.sqrt(np.maximum(eigenvalues, 0.0))
            voxel_m = 0.02
            voxels = np.unique(np.floor((trimmed - low) / voxel_m).astype(np.int64), axis=0)
            grid = np.maximum(np.ceil((high - low) / voxel_m).astype(int), 1)
            failures = []
            if len(trimmed) < self.limits.min_points:
                failures.append('trimmed_points < min_points')
            if spread[1] < self.limits.min_scene_width_m:
                failures.append('scene_spread_second < min_scene_width_m')
            if spread[2] < self.limits.min_scene_thickness_m:
                failures.append('scene_spread_third < min_scene_thickness_m')
            result.update({
                'xyz_bounding_box_extent_m': (high - low).tolist(),
                'depth_range_m': [float(ranged[:, 2].min()), float(ranged[:, 2].max())],
                'depth_standard_deviation_m': float(np.std(ranged[:, 2])),
                'covariance_eigenvalues_m2': eigenvalues.tolist(),
                'eigenvalue_ratios_to_largest': (eigenvalues / max(eigenvalues[0], 1e-15)).tolist(),
                'scene_spread_m': spread.tolist(),
                'planar_score': float(1.0 - eigenvalues[2] / max(eigenvalues[0], 1e-15)),
                'nonplanar_score': float(eigenvalues[2] / max(eigenvalues[0], 1e-15)),
                'voxel_size_m': voxel_m, 'occupied_voxels': int(len(voxels)),
                'possible_voxels': int(np.prod(grid)),
                'voxel_coverage_ratio': float(len(voxels) / np.prod(grid)),
                'failed_thresholds': failures,
            })
            return result
        except Exception as error:
            return {'available': False, 'reason': 'diagnostic_failed:' + str(error)}

    def delete_last_pose_service(self, request, response):
        if self.operation_lock.locked():
            return self._passive_reply(response, False,
                                       rejection_reasons=['Calibration operation is active'])
        if not self.passive_captures:
            return self._passive_reply(response, False,
                                       rejection_reasons=['No passive poses to delete'])
        self.passive_captures.pop()
        self.passive_capture_metadata.pop()
        self.passive_session.delete_last()
        return self._passive_reply(response, True,
                                   pose_count=len(self.passive_captures),
                                   geometry_verified=False)

    def clear_poses_service(self, request, response):
        if self.operation_lock.locked():
            return self._passive_reply(response, False,
                                       rejection_reasons=['Calibration operation is active'])
        if self.passive_session.manifest is not None:
            self.passive_session.discard()
        self.passive_session.new()
        self.passive_captures.clear()
        self.passive_capture_metadata.clear()
        self.last_capture_stamp = 0.0
        self.last_capture = None
        return self._passive_reply(response, True, pose_count=0,
                                   geometry_verified=False)

    def session_status_service(self, request, response):
        manifest = self.passive_session.manifest
        return self._passive_reply(
            response, True,
            session=(dict(manifest) if manifest else None),
            persistence_path=(str(self.passive_session.session_dir)
                              if self.passive_session.session_dir else None),
            restored_pose_count=len(self.passive_captures),
            compatibility_error=self.passive_session_error,
            geometry_verified=False)

    def session_new_service(self, request, response):
        if self.operation_lock.locked():
            return self._passive_reply(response, False,
                                       rejection_reasons=['Calibration operation is active'])
        if self.passive_captures:
            return self._passive_reply(
                response, False,
                rejection_reasons=['Discard the current non-empty session before creating a new one'])
        manifest = self.passive_session.new()
        self.passive_session_error = ''
        return self._passive_reply(response, True, session=manifest,
                                   persistence_path=str(self.passive_session.session_dir),
                                   geometry_verified=False)

    def session_resume_service(self, request, response):
        if self.operation_lock.locked():
            return self._passive_reply(response, False,
                                       rejection_reasons=['Calibration operation is active'])
        try:
            intrinsics_digest = ''
            with self.lock:
                if self.bundle is not None:
                    intrinsics_digest = self.intrinsics_fingerprint(self.bundle[2])
            captures, metadata = self.passive_session.restore(intrinsics_digest)
            self.passive_captures, self.passive_capture_metadata = captures, metadata
            self.passive_session_error = ''
            return self._passive_reply(
                response, True, restored_pose_count=len(captures),
                persistence_path=str(self.passive_session.session_dir),
                geometry_verified=False)
        except CalibrationError as error:
            self.passive_session_error = str(error)
            return self._passive_reply(response, False,
                                       rejection_reasons=[str(error)],
                                       geometry_verified=False)

    def session_discard_service(self, request, response):
        if self.operation_lock.locked():
            return self._passive_reply(response, False,
                                       rejection_reasons=['Calibration operation is active'])
        try:
            discarded = self.passive_session.discard()
            self.passive_captures.clear()
            self.passive_capture_metadata.clear()
            self.passive_session_error = ''
            return self._passive_reply(
                response, True,
                discarded_path=str(discarded) if discarded else None,
                restored_pose_count=0, geometry_verified=False)
        except (CalibrationError, OSError) as error:
            return self._passive_reply(response, False,
                                       rejection_reasons=[str(error)],
                                       geometry_verified=False)

    def auto_start_service(self, request, response):
        targets = list((self.passive_session.manifest or {}).get('target_poses') or [])
        response.success, response.message = self.supervised_auto.start(
            targets, accepted_count=len(self.passive_captures), dry_run=True)
        return response

    def auto_pause_service(self, request, response):
        response.success, response.message = self.supervised_auto.pause()
        return response

    def auto_resume_service(self, request, response):
        response.success, response.message = self.supervised_auto.resume()
        return response

    def auto_abort_service(self, request, response):
        response.success, response.message = self.supervised_auto.abort()
        return response

    def auto_status_service(self, request, response):
        response.success = True
        response.message = json.dumps({**self.supervised_auto.snapshot(),
                                       'table_reference': self.table_reference(),
                                       'table_reference_blocker': False,
                                       'geometry_verified': False,
                                       'auto_real_motion_enabled': False}, allow_nan=False,
                                      separators=(',', ':'))
        return response

    def cancel_service(self, request, response):
        self.stop.set()
        # Do not erase a specific terminal diagnosis (identity mismatch,
        # unsafe mount, failed verification, etc.) when the system-wide STOP
        # follows that failure. Active states still become an explicit cancel.
        if self.state != 'FAIL' or not self.reason:
            self.status('FAIL', 'Calibration cancelled')
        if self.active_goal is not None:
            self.active_goal.cancel_goal_async()
        response.success, response.message = True, 'Cancellation requested; picking blocked'
        return response

    def start_operation(self, recalibrate, verify_only=False):
        if not self.operation_lock.acquire(blocking=False):
            return False, 'Calibration is already running'
        self.stop.clear()
        self.workflow = None
        self.status('STARTING')
        self.worker = threading.Thread(target=self.run_operation, args=(recalibrate, verify_only), daemon=True)
        self.worker.start()
        return True, 'Started; observe /calibration/status for PASS/FAIL'

    def run_operation(self, recalibrate, verify_only=False):
        try:
            if not self.settings['camera_id']:
                raise CalibrationError('camera_id must identify the connected camera serial/device')
            self.calibration_context = None
            try:
                self.mount = Mount.load(self.settings['mount_model'], self.limits,
                                        carrier_frame=self.settings['carrier_frame'])
            except CalibrationError:
                internal = self.camera_reference_to_optical()
                self.mount = Mount.load_translation_constraint(
                    self.settings['mount_model'], internal, self.limits,
                    carrier_frame=self.settings['carrier_frame'])
            self.ensure_camera_sync()
            deadline = time.monotonic() + self.settings['capture_timeout_s']
            while self.health_error():
                if self.stop.wait(0.03) or time.monotonic() > deadline:
                    raise CalibrationError(self.health_error() or 'Cancelled')
            with self.lock:
                self.calibration_context = self.camera_context(self.bundle[2])
            self.after_motion_stamp = self.now_s()
            self.workflow = Workflow(self, self.mount, self.settings['calibration_file'],
                                     self.calibration_context, self.limits)
            report = self.workflow.run(recalibrate, verify_only=verify_only)
            if (report['result'] == 'FAIL' and not recalibrate and not verify_only
                    and not self.stop.is_set()
                    and self.settings['recalibrate_on_failure']):
                self.workflow.run(recalibrate=True)
        except Exception as error:
            self.status('FAIL', str(error))
            self.get_logger().error(str(error))
        finally:
            self.operation_lock.release()

    def camera_reference_to_optical(self):
        """Read the Orbbec-owned factory/static internal transform."""
        try:
            item = self.carrier_tf.lookup_transform(
                self.settings['camera_reference_frame'], self.settings['camera_frame'],
                rclpy.time.Time())
        except TransformException as error:
            raise CalibrationError('Orbbec factory camera TF unavailable: ' + str(error)) from error
        p, q = item.transform.translation, item.transform.rotation
        quaternion = np.array([q.x, q.y, q.z, q.w], dtype=float)
        translation = np.array([p.x, p.y, p.z], dtype=float)
        if (not np.isfinite(np.r_[translation, quaternion]).all()
                or not np.isclose(np.linalg.norm(quaternion), 1.0, atol=1e-3)):
            raise CalibrationError('Orbbec factory camera TF is invalid')
        return transform(Rotation.from_quat(quaternion).as_matrix(), translation)

    def carrier_pose_at(self, stamp):
        """Lookup measured/validated kinematics at exposure time; never use latest TF."""
        try:
            item = self.carrier_tf.lookup_transform(
                self.settings['base_frame'], self.settings['carrier_frame'],
                rclpy.time.Time(nanoseconds=int(round(stamp * 1e9))))
        except TransformException as error:
            raise CalibrationError('Camera-carrier TF unavailable at exposure: ' + str(error)) from error
        p, q = item.transform.translation, item.transform.rotation
        quat = np.array([q.x, q.y, q.z, q.w])
        if not np.isfinite(quat).all() or not np.isclose(np.linalg.norm(quat), 1., atol=1e-3):
            raise CalibrationError('Invalid camera-carrier quaternion')
        value = transform(Rotation.from_quat(quat).as_matrix(), [p.x, p.y, p.z])
        if not np.isfinite(value).all():
            raise CalibrationError('Invalid camera-carrier translation')
        return value

    def _deproject_depth(self, depth_m, intrinsics):
        """Factory optical convention: +X right, +Y down, +Z forward, metres."""
        height, width = depth_m.shape
        v, u = np.mgrid[:height, :width]
        z = depth_m.reshape(-1)
        valid = np.isfinite(z) & (z >= self.limits.min_depth_m) & (z <= self.limits.max_depth_m)
        x = (u.reshape(-1)[valid] - intrinsics[0, 2]) * z[valid] / intrinsics[0, 0]
        y = (v.reshape(-1)[valid] - intrinsics[1, 2]) * z[valid] / intrinsics[1, 1]
        return np.column_stack((x, y, z[valid]))

    def _native_cloud_for(self, depth_stamp):
        """Return native cloud only when it is fresh and same-exposure compatible."""
        with self.lock:
            cloud = self.last_native_cloud
            received = self.last_native_cloud_receive_monotonic
        if cloud is None or received is None:
            return None, 'missing'
        age = time.monotonic() - received
        skew = abs(stamp_seconds(cloud) - depth_stamp)
        if age > 1.5:
            return None, 'stale'
        if cloud.header.frame_id != self.settings['camera_frame']:
            return None, 'frame_mismatch'
        if skew > 0.100:
            return None, 'timestamp_incompatible'
        return cloud, 'fresh'

    def _cloud_cross_validation(self, native, generated):
        if native is None:
            return {'native_reference': 'unavailable'}
        raw = point_cloud2.read_points(native, field_names=('x', 'y', 'z'), skip_nans=True)
        reference = np.column_stack([raw[name].reshape(-1) for name in ('x', 'y', 'z')])
        reference = reference[np.isfinite(reference).all(axis=1)]
        if not len(reference) or not len(generated):
            return {'native_reference': 'empty', 'native_point_count': int(len(reference))}
        # Nearest-neighbour comparison is robust to the driver's compacted cloud.
        sample = generated[::max(1, len(generated) // 20000)]
        distances, _ = cKDTree(reference).query(sample)
        return {'native_reference': 'fresh', 'native_point_count': int(len(reference)),
                'generated_point_count': int(len(generated)),
                'median_xyz_difference_m': float(np.median(distances)),
                'rms_xyz_difference_m': float(np.sqrt(np.mean(distances ** 2))),
                'frame_consistent': native.header.frame_id == self.settings['camera_frame']}

    def capture(self):
        deadline = time.monotonic() + self.settings['capture_timeout_s']
        reason = 'Waiting for settled synchronized capture'
        while time.monotonic() < deadline:
            if self.stop.wait(0.03):
                raise CalibrationError('Calibration cancelled')
            reason = self.health_error()
            if reason:
                continue
            with self.lock:
                rgb, depth, info = self.bundle
                history = list(self.history)
            stamps = [stamp_seconds(message) for message in [rgb, depth, info]]
            # For passive capture the exposure timestamp is RGB/depth/info;
            # the low-rate static cloud must not make it appear stale.
            stamp = min(stamps)
            if stamp <= self.last_capture_stamp:
                continue
            try:
                pose = settled_pose(history, stamp, self.after_motion_stamp)
                # Also check the end of the synchronized exposure window.
                settled_pose(history, max(stamps[:3]) if self.passive_capture_active
                             else max(stamps), self.after_motion_stamp)
                carrier = None
                if self.settings['carrier_frame']:
                    # Check the complete settling interval, not just one TF sample.
                    relevant = [h for h in history if stamp - 0.68 <= h[0] <= max(stamps) + 0.08]
                    carrier_history = [(h[0], self.carrier_pose_at(h[0]), h[2]) for h in relevant]
                    carrier = settled_pose(carrier_history, stamp, self.after_motion_stamp)
                    settled_pose(carrier_history, max(stamps), self.after_motion_stamp)
            except CalibrationError as error:
                reason = str(error)
                continue
            rgb_array = self.bridge.imgmsg_to_cv2(rgb, 'bgr8')
            if depth.encoding not in ('16UC1', '32FC1'):
                raise CalibrationError('Depth must be 16UC1 millimetres or 32FC1 metres')
            depth_array = np.asarray(self.bridge.imgmsg_to_cv2(depth, 'passthrough'), dtype=float)
            if depth.encoding == '16UC1':
                depth_array *= 0.001
            if depth_array.shape != (info.height, info.width):
                raise CalibrationError('CameraInfo dimensions do not match aligned depth')
            intrinsics = np.array(info.p).reshape(3, 4)[:, :3]
            if intrinsics[0, 0] <= 0:
                if np.any(np.abs(info.d) > 1e-8):
                    raise CalibrationError('Rectified RGB/depth and projection intrinsics required')
                intrinsics = np.array(info.k).reshape(3, 3)
            native, native_state = self._native_cloud_for(stamp_seconds(depth))
            requested = self.settings['point_cloud_source']
            if requested not in ('AUTO', 'ORBBEC_TOPIC', 'DEPTH_DEPROJECTION'):
                raise CalibrationError('point_cloud_source must be AUTO, ORBBEC_TOPIC, or DEPTH_DEPROJECTION')
            source = ('ORBBEC_TOPIC' if requested == 'ORBBEC_TOPIC' else
                      'DEPTH_DEPROJECTION' if requested == 'DEPTH_DEPROJECTION' else
                      ('ORBBEC_TOPIC' if native is not None else 'DEPTH_DEPROJECTION'))
            if source == 'ORBBEC_TOPIC' and native is None:
                raise CalibrationError('Requested ORBBEC_TOPIC is ' + native_state)
            if source == 'ORBBEC_TOPIC':
                raw = point_cloud2.read_points(native, field_names=('x', 'y', 'z'), skip_nans=True)
                points = np.column_stack([raw[name].reshape(-1) for name in ('x', 'y', 'z')])
            else:
                points = self._deproject_depth(depth_array, intrinsics)
            raw_point_count = int(len(points))
            result = make_capture(stamp, pose, rgb_array, depth_array, intrinsics, points,
                                  self.mount.tool_T_camera, self.limits,
                                  base_T_carrier=carrier,
                                  arbitrary_plane=self.passive_capture_active)
            result.quality['total_valid_cloud_points'] = raw_point_count
            result.quality['filtered_cloud_points'] = int(len(result.cloud))
            result.quality['point_cloud_source'] = source
            result.quality['cloud_frame_id'] = self.settings['camera_frame']
            result.quality['cloud_timestamp'] = stamp_seconds(depth) if source == 'DEPTH_DEPROJECTION' else stamp_seconds(native)
            result.quality['rgb_depth_skew_ms'] = abs(stamp_seconds(rgb) - stamp_seconds(depth)) * 1000.0
            result.quality['depth_cloud_skew_ms'] = abs(
                stamp_seconds(depth) - result.quality['cloud_timestamp']) * 1000.0
            result.quality['nan_inf_ratio'] = float(1.0 - raw_point_count / depth_array.size) if source == 'DEPTH_DEPROJECTION' else None
            result.quality['native_cloud_state'] = native_state
            result.quality['native_cross_validation'] = self._cloud_cross_validation(native, result.cloud)
            if self.passive_capture_active:
                debug_path = Path('~/.ros/dobot/passive_pose_1_debug.npz').expanduser()
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                distances = np.abs(result.cloud @ result.plane[:3] + result.plane[3])
                np.savez_compressed(debug_path, point_cloud_before_filter=points,
                                    point_cloud_after_filter=result.cloud,
                                    plane_inliers=result.cloud[distances <= self.limits.plane_inlier_m],
                                    plane_coefficients=result.plane)
                result.quality['debug_artifact'] = str(debug_path)
            # Conversion/registration must not race a camera configuration change.
            if self.camera_context(info) != self.calibration_context:
                raise CalibrationError('Camera changed during capture')
            # Registration-independent capture is already guarded at the
            # exposure timestamp. In passive mode, expensive point-cloud
            # decoding must not turn a valid exposure into a post-hoc stale
            # failure; the next requested pose rechecks freshness.
            if not self.passive_capture_active:
                self.checkpoint()
            self.last_capture_stamp, self.last_capture = max(stamps), result
            return result
        raise CalibrationError('Capture timeout: ' + reason)

    def wait_future(self, future, timeout):
        deadline = time.monotonic() + timeout
        while not future.done():
            if self.stop.wait(0.02):
                raise CalibrationError('Calibration cancelled')
            if time.monotonic() > deadline:
                raise CalibrationError('Motion/validation service timed out')
            if self.health_error():
                raise CalibrationError(self.health_error())
        result = future.result()
        if result is None:
            raise CalibrationError('Motion/validation service returned no result')
        return result

    def move(self, target):
        if self.stop.is_set() or self.health_error():
            raise CalibrationError(self.health_error() or 'Cancelled')
        with self.lock:
            current = self.history[-1][1].copy()
        check_path(current, target, self.last_capture, self.mount, self.limits)
        if not self.validator.wait_for_service(timeout_sec=2) or not self.motion.wait_for_server(timeout_sec=2):
            raise CalibrationError('Collision validator or PTP motion server is unavailable')
        yaw = float(np.rad2deg(np.arctan2(target[1, 0], target[0, 0])))
        target_raw = [*map(float, target[:3, 3] * 1000), yaw]
        request = EvaluatePTPTrajectory.Request()
        request.motion_type, request.target = 2, target_raw
        validation = self.wait_future(self.validator.call_async(request), 8)
        if not validation.is_valid:
            raise CalibrationError('Trajectory rejected: ' + validation.message)
        with self.lock:
            distance, angle = pose_distance(current, self.history[-1][1])
        if distance > 0.001 or angle > 0.3:
            raise CalibrationError('Robot moved while validating the calibration trajectory')
        goal = PointToPoint.Goal()
        goal.motion_type, goal.target_pose = 2, target_raw
        # Commissioning moves use the operator-authorized low-speed limit.
        goal.velocity_ratio, goal.acceleration_ratio = 0.05, 0.05
        self.checkpoint()
        future = self.motion.send_goal_async(goal)
        try:
            self.active_goal = self.wait_future(future, 5)
            if not self.active_goal.accepted:
                raise CalibrationError('Calibration motion was rejected')
            result = self.wait_future(self.active_goal.get_result_async(), self.settings['motion_timeout_s'])
            if result.status != GoalStatus.STATUS_SUCCEEDED:
                raise CalibrationError('Calibration motion did not succeed')
            with self.lock:
                distance, angle = pose_distance(target, self.history[-1][1])
            if distance > 0.002 or angle > 0.5:
                raise CalibrationError('Motion result disagrees with measured TCP')
            self.after_motion_stamp = self.now_s()
        except Exception:
            # A delayed goal acceptance must not leave the robot moving after
            # a timeout or cancellation has already failed calibration.
            def cancel_late(completed):
                try:
                    handle = completed.result()
                    if handle and handle.accepted:
                        handle.cancel_goal_async()
                except Exception:
                    pass
            future.add_done_callback(cancel_late)
            if self.active_goal is not None and self.active_goal.accepted:
                self.active_goal.cancel_goal_async()
            self.stop.set()
            raise
        finally:
            self.active_goal = None


def main(args=None):
    rclpy.init(args=args)
    node = CalibrationNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.stop.set()
        if node.active_goal is not None:
            node.active_goal.cancel_goal_async()
        if node.worker is not None:
            node.worker.join(timeout=2)
        executor.shutdown(timeout_sec=2)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
