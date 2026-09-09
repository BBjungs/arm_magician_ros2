"""ROS adapter for guarded markerless calibration; no hardware access on import."""

from collections import deque
from dataclasses import asdict
import json
import threading
import time

import message_filters
import numpy as np
from scipy.spatial.transform import Rotation
import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from action_msgs.msg import GoalStatus
from rcl_interfaces.msg import ParameterDescriptor
from cv_bridge import CvBridge
from dobot_msgs.action import PointToPoint
from dobot_msgs.msg import DobotAlarmCodes
from dobot_msgs.srv import EvaluatePTPTrajectory
from geometry_msgs.msg import PoseStamped, TransformStamped
from sensor_msgs.msg import CameraInfo, Image, JointState, PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger
from tf2_ros import TransformBroadcaster

from .depth_health import depth_quality
from .geometry import CalibrationError, Limits, Mount, pose_distance, transform
from .hardware_readiness import DepthStabilityWindow, evaluate_hardware_readiness
from .registration import make_capture
from .workflow import Workflow, check_path, settled_pose
from .validation_status import live_acceptance_error


def stamp_seconds(message):
    return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9


class CalibrationNode(Node):
    def __init__(self):
        super().__init__('markerless_calibration')
        defaults = {
            'rgb_topic': '/camera/color/image_raw',
            'depth_topic': '/camera/depth/image_raw',
            'camera_info_topic': '/camera/color/camera_info',
            'cloud_topic': '/camera/depth_registered/points',
            'tcp_topic': '/dobot_TCP', 'joints_topic': '/dobot_joint_states',
            'alarms_topic': '/dobot_alarms', 'safety_state_topic': '',
            'base_frame': 'magician_base_link', 'tool_frame': 'TCP',
            'camera_frame': 'camera_color_optical_frame',
            'calibrated_frame': 'calibrated_camera_optical_frame',
            'camera_id': '', 'mount_model': '',
            'calibration_file': '~/.ros/dobot/markerless_calibration.npz',
            'auto_start': False, 'recalibrate_on_failure': False,
            'ready_ttl_s': 600.0, 'capture_timeout_s': 15.0,
            'motion_timeout_s': 25.0,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value, ParameterDescriptor(read_only=True))
        self.settings = {name: self.get_parameter(name).value for name in defaults}
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
        self.bundle = None
        self.live_depth_quality = None
        self.live_depth_stamp = None
        self.depth_window = DepthStabilityWindow()
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
        self.mount = None
        self.calibration_context = None
        self.state, self.reason = 'UNCALIBRATED', 'Calibration has not been verified'
        self.bridge = CvBridge()
        self.broadcaster = TransformBroadcaster(self)
        self.publisher = self.create_publisher(
            String, '/calibration/status',
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
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
        self.camera_subscribers = [message_filters.Subscriber(
            self, kind, self.settings[name], qos_profile=qos_profile_sensor_data)
            for kind, name in [(Image, 'rgb_topic'), (Image, 'depth_topic'),
                               (CameraInfo, 'camera_info_topic'), (PointCloud2, 'cloud_topic')]]
        self.camera_sync = message_filters.ApproximateTimeSynchronizer(
            self.camera_subscribers, queue_size=12, slop=0.08)
        self.camera_sync.registerCallback(self.on_camera)
        # The point cloud may stop when depth becomes invalid. Observe depth
        # directly as well, so loss of synchronization cannot hide bad depth.
        self.create_subscription(Image, self.settings['depth_topic'], self.on_depth,
                                 qos_profile_sensor_data)
        self.validator = self.create_client(EvaluatePTPTrajectory,
                                             '/dobot_calibration_validation_service',
                                             callback_group=self.group)
        self.motion = ActionClient(self, PointToPoint, '/PTP_action', callback_group=self.group)
        self.create_service(Trigger, '/calibration/start', self.start_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/recalibrate', self.recalibrate_service,
                            callback_group=self.group)
        self.create_service(Trigger, '/calibration/verify', self.verify_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/ready', self.ready_service, callback_group=self.group)
        self.create_service(Trigger, '/calibration/cancel', self.cancel_service, callback_group=self.group)
        self.create_timer(0.2, self.supervise, callback_group=self.group)
        self.auto_pending = self.settings['auto_start']

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

    def on_camera(self, rgb, depth, info, cloud):
        self.on_depth(depth)
        with self.lock:
            self.bundle = (rgb, depth, info, cloud)

    def on_depth(self, depth):
        try:
            quality = depth_quality(self.bridge.imgmsg_to_cv2(depth, 'passthrough'),
                                    depth.encoding, self.limits)
        except Exception as error:
            quality = {'status': 'SENSOR_ERROR', 'code': 'DEPTH_DECODE_FAILED',
                       'reason': str(error), 'depth_valid_ratio': 0.}
        stamp = stamp_seconds(depth)
        with self.lock:
            self.live_depth_quality = quality
            self.live_depth_stamp = stamp
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
                depth_stamp=self.live_depth_stamp,
                depth_stable=self.depth_window.stable(now),
                tcp_stamp=self.tcp_stamp, joints_stamp=self.joints_stamp,
                alarm_stamp=self.alarm_stamp if self.alarm_stamp else None,
                alarms=list(self.alarms),
                robot_connected=self.robot_response_seen and recent_response,
                safety_supported=safety_supported,
                safety_verified=safety_verified)

    def health_error(self):
        now = self.now_s()
        readiness = self.hardware_readiness()
        if not readiness.ready:
            return readiness.reason
        with self.lock:
            if self.bundle is None:
                return 'Waiting for synchronized RGB, depth, CameraInfo and PointCloud2'
            if self.live_depth_quality is None:
                return 'Depth quality has not been established'
            if self.live_depth_quality['status'] != 'VALID_DEPTH':
                return self.live_depth_quality['code'] + ': ' + self.live_depth_quality['reason']
            stamps = [stamp_seconds(message) for message in self.bundle]
            if any(not 0 <= now - stamp < 0.5 for stamp in stamps):
                return 'RGB-D/point-cloud telemetry is stale'
            if any(message.header.frame_id != self.settings['camera_frame'] for message in self.bundle):
                return 'RGB-D/point-cloud frames must all be the registered optical frame'
            if self.calibration_context is not None and self.camera_context(self.bundle[2]) != self.calibration_context:
                return 'Camera identity or intrinsics changed'
        return ''

    def camera_context(self, info):
        return {
            'camera_id': self.settings['camera_id'], 'camera_frame': info.header.frame_id,
            'base_frame': self.settings['base_frame'], 'tool_frame': self.settings['tool_frame'],
            'width': int(info.width), 'height': int(info.height),
            'k': list(info.k), 'p': list(info.p), 'd': list(info.d),
            'distortion_model': info.distortion_model,
            'binning': [info.binning_x, info.binning_y],
            'roi': [info.roi.x_offset, info.roi.y_offset, info.roi.width, info.roi.height],
            'mount_digest': self.mount.digest if self.mount else '',
        }

    def status(self, state, reason=''):
        self.state, self.reason = state, reason

    def is_ready(self):
        workflow = self.workflow
        return (self.state == 'READY' and workflow is not None
                and workflow.state == 'READY'
                and workflow.verified_monotonic is not None
                and time.monotonic() - workflow.verified_monotonic < self.settings['ready_ttl_s']
                and not live_acceptance_error(workflow.report)
                and not self.health_error() and not self.stop.is_set())

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
        message = String()
        message.data = json.dumps(self.status_payload(), allow_nan=False)
        self.publisher.publish(message)
        if ready and workflow is not None and workflow is self.workflow:
            value = workflow.solution.tool_T_camera
            msg = TransformStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.settings['tool_frame']
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
        return {'state': self.state, 'ready': ready, 'reason': self.reason,
                'stamp': self.now_s(), 'result': 'PASS' if ready else 'FAIL',
                'metrics': report.get('metrics', {}),
                'depth_quality': self.live_depth_quality,
                'hardware_readiness': hardware.to_dict(),
                'ui': {'language': 'th', 'step': thai[0], 'status': thai[1],
                       'recommended_action': thai[2],
                       'motion_allowed': hardware.ready}}

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
        response.success = self.is_ready()
        response.message = 'PASS' if response.success else 'FAIL: ' + (self.reason or self.health_error())
        return response

    def cancel_service(self, request, response):
        self.stop.set()
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
            self.mount = Mount.load(self.settings['mount_model'], self.limits)
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
                rgb, depth, info, cloud = self.bundle
                history = list(self.history)
            stamps = [stamp_seconds(message) for message in [rgb, depth, info, cloud]]
            stamp = min(stamps)
            if stamp <= self.last_capture_stamp:
                continue
            try:
                pose = settled_pose(history, stamp, self.after_motion_stamp)
                # Also check the end of the synchronized exposure window.
                settled_pose(history, max(stamps), self.after_motion_stamp)
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
            raw = point_cloud2.read_points(cloud, field_names=('x', 'y', 'z'), skip_nans=True)
            points = np.column_stack([raw[name].reshape(-1) for name in ('x', 'y', 'z')])
            result = make_capture(stamp, pose, rgb_array, depth_array, intrinsics, points,
                                  self.mount.tool_T_camera, self.limits)
            # Conversion/registration must not race a camera configuration change.
            if self.camera_context(info) != self.calibration_context:
                raise CalibrationError('Camera changed during capture')
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
        goal.velocity_ratio, goal.acceleration_ratio = 0.10, 0.10
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
