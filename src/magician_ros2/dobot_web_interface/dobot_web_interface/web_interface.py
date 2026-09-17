import base64
import hmac
import math
import os
import threading
import time
import json
from html import escape
import subprocess
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from dobot_msgs.action import PointToPoint
from dobot_msgs.msg import DobotAlarmCodes
from dobot_msgs.srv import ExecuteHomingProcedure, GripperControl, SuctionCupControl
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dobot_web_interface.system_integration import StartupState
from dobot_web_interface.system_integration import StartupStateMachine
from dobot_web_interface.system_integration import aggregate_system_readiness
from dobot_web_interface.system_integration import is_pose
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
import uvicorn
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from std_msgs.msg import String
from std_srvs.srv import Trigger


TOOL_MAPPINGS = ('canonical',)


# The operator application deliberately has a very small vocabulary.  Keep
# the identifiers at this boundary rather than exposing detector class names
# or pose data to the browser.
OPERATOR_JOB_SPECS = {
    'black': {'class_name': 'black_cap', 'label': 'สีดำ'},
    'white': {'class_name': 'white_cap', 'label': 'สีขาว'},
    'yellow': {'class_name': 'yellow_cap', 'label': 'สีเหลือง'},
    'pick_all': {'class_name': 'all', 'label': 'หยิบทั้งหมด'},
}
OPERATOR_PLACE_LABELS = {
    'Zone A': 'โซน A',
    'Zone B': 'โซน B',
    'Zone C': 'โซน C',
    'Reject': 'คัดทิ้ง',
}


def operator_detection_counts(detections):
    """Return only the three operator-facing object counts.

    Detector payloads contain pixel positions, depth and confidence values;
    none of those belongs in the operator status response.
    """
    counts = {'black': 0, 'white': 0, 'yellow': 0}
    class_to_job = {
        spec['class_name']: job for job, spec in OPERATOR_JOB_SPECS.items()
        if job != 'pick_all'
    }
    for detection in detections if isinstance(detections, list) else []:
        if not isinstance(detection, dict):
            continue
        job = class_to_job.get(str(detection.get('class_name', '')))
        if job is not None:
            counts[job] += 1
    return counts


def normalize_tool_mapping(value):
    mapping = str(value or 'canonical').strip().lower()
    if mapping not in TOOL_MAPPINGS:
        raise ValueError(f'tool_mapping must be one of {", ".join(TOOL_MAPPINGS)}')
    return mapping


def map_web_gripper_payload(payload, mapping='canonical'):
    mapping = normalize_tool_mapping(mapping)
    return dict(payload), 'gripper'


def map_web_suction_payload(payload, mapping='canonical'):
    mapping = normalize_tool_mapping(mapping)
    return dict(payload), 'suction'

try:
    from dobot_calibration.bundle import VerifiedBundle
    from dobot_calibration.geometry import CalibrationError
except ImportError:
    VerifiedBundle = None
    CalibrationError = ValueError

try:
    from dobot_vision_yolo.target_selector_node import PlaceStore
    from dobot_vision_yolo.target_selector_node import TargetSelectionError
    from dobot_vision_yolo.target_selector_node import classes_from_detections
    from dobot_vision_yolo.target_selector_node import load_configured_classes
    from dobot_vision_yolo.target_selector_node import select_target_from_detections
except ImportError:
    PlaceStore = None
    TargetSelectionError = ValueError
    classes_from_detections = None
    load_configured_classes = None
    select_target_from_detections = None

try:
    from dobot_vision_yolo.safety_guard import SafetyGuard
    from dobot_vision_yolo.safety_guard import load_safety_config
except ImportError:
    SafetyGuard = None
    load_safety_config = None

try:
    from dobot_vision_yolo.automatic_placement import AutomaticPlacementConfig
    from dobot_vision_yolo.automatic_placement import AutomaticSuctionPlacementController
    from dobot_vision_yolo.automatic_pick import AutomaticPickConfig
    from dobot_vision_yolo.automatic_pick import AutomaticSuctionPickController
    from dobot_vision_yolo.vision_pick_place_node import HTTPMotionExecutor
    from dobot_vision_yolo.vision_pick_place_node import build_motion_sequence
except ImportError:
    AutomaticPlacementConfig = None
    AutomaticSuctionPlacementController = None
    AutomaticPickConfig = None
    AutomaticSuctionPickController = None
    HTTPMotionExecutor = None
    build_motion_sequence = None

def normalize_tcp_pose(value, xyz_unit='m'):
    values = [float(item) for item in value]
    if len(values) != 4 or not np.isfinite(values).all():
        raise ValueError('TCP pose must be finite [x, y, z, yaw]')
    if xyz_unit == 'm':
        return [values[0] * 1000.0, values[1] * 1000.0, values[2] * 1000.0, values[3]]
    if xyz_unit == 'mm':
        return values
    raise ValueError('TCP xyz_unit must be m or mm')


def _intrinsics_from_camera_info(message):
    matrix = list(message.k)
    if len(matrix) != 9:
        raise ValueError('CameraInfo.k must contain 9 values')
    width = int(message.width)
    height = int(message.height)
    fx = float(matrix[0])
    fy = float(matrix[4])
    if width <= 0 or height <= 0 or fx <= 0.0 or fy <= 0.0:
        raise ValueError('CameraInfo has invalid image size or focal length')
    return {
        'image_width': width,
        'image_height': height,
        'fx': fx,
        'fy': fy,
        'cx': float(matrix[2]),
        'cy': float(matrix[5]),
        'distortion_coefficients': [float(value) for value in message.d],
    }


class DobotWebNode(Node):
    def __init__(self):
        super().__init__('dobot_web_interface')

        self.declare_parameter('host', '127.0.0.1')
        self.declare_parameter('port', 8080)
        self.declare_parameter(
            'api_token',
            os.environ.get('DOBOT_WEB_API_TOKEN', ''),
        )
        self.declare_parameter('camera_raw_topic', '/camera/color/image_raw')
        self.declare_parameter('camera_compressed_topic', '/camera/color/image_raw/compressed')
        self.declare_parameter('camera_info_topic', '/camera/color/camera_info')
        self.declare_parameter('camera_device', '')
        self.declare_parameter('camera_width', 1280)
        self.declare_parameter('camera_height', 720)
        self.declare_parameter('camera_fps', 15.0)
        self.declare_parameter('stream_fps', 12.0)
        self.declare_parameter('jpeg_quality', 80)
        self.declare_parameter('vision_status_topic', '/dobot_vision/status')
        self.declare_parameter('vision_detections_topic', '/dobot_vision/detections')
        self.declare_parameter('vision_detect_once_topic', '/dobot_vision/detect_once')
        self.declare_parameter('vision_annotated_path', '/tmp/dobot_vision_annotated.jpg')
        self.declare_parameter('vision_place_positions_path', '')
        self.declare_parameter('vision_workspace_path', '')
        self.declare_parameter('vision_yolo_config_path', '')
        self.declare_parameter('vision_mode', 'fixed_camera')
        self.declare_parameter('vision_engine', 'rgbd_shape')
        self.declare_parameter(
            'tool_mapping', os.environ.get('DOBOT_TOOL_MAPPING', 'canonical')
        )
        self.declare_parameter('tcp_pose_topic', 'dobot_pose_raw')
        self.declare_parameter('fallback_tcp_pose_topic', '')
        self.declare_parameter(
            'vision_selected_target_topic',
            '/dobot_vision_yolo/selected_target',
        )
        # Full-cell integration is opt-in for the standalone web node, but is
        # enabled by dobot_auto.launch.py.  A production launch therefore
        # cannot admit a pick based on a stale saved calibration or a UI-only
        # notion of readiness.
        self.declare_parameter('require_integrated_startup', False)
        self.declare_parameter('startup_auto', False)
        self.declare_parameter('startup_auto_motion', False)
        self.declare_parameter('calibration_status_topic', '/calibration/status')
        self.declare_parameter('camera_health_topic', '/camera/health')
        self.declare_parameter('calibration_verify_service', '/calibration/verify')
        self.declare_parameter('calibration_start_service', '/calibration/start')
        self.declare_parameter('calibration_cancel_service', '/calibration/cancel')
        self.declare_parameter('calibration_recalibrate_service', '/calibration/recalibrate')
        self.declare_parameter('calibration_bundle_path', '~/.ros/dobot/markerless_calibration.npz')
        self.declare_parameter('observation_pose_mm', [220.0, 0.0, 80.0, 0.0])
        self.declare_parameter('pick_all_max_items', 100)

        self.host = str(self.get_parameter('host').value)
        self.port = int(self.get_parameter('port').value)
        self.api_token = str(self.get_parameter('api_token').value)
        self.camera_raw_topic = str(self.get_parameter('camera_raw_topic').value)
        self.camera_compressed_topic = str(
            self.get_parameter('camera_compressed_topic').value
        )
        self.camera_info_topic = str(self.get_parameter('camera_info_topic').value)
        self.camera_device = str(self.get_parameter('camera_device').value)
        self.camera_width = int(self.get_parameter('camera_width').value)
        self.camera_height = int(self.get_parameter('camera_height').value)
        self.camera_fps = float(self.get_parameter('camera_fps').value)
        self.stream_fps = float(self.get_parameter('stream_fps').value)
        self.jpeg_quality = int(self.get_parameter('jpeg_quality').value)
        self.vision_status_topic = str(self.get_parameter('vision_status_topic').value)
        self.vision_detections_topic = str(
            self.get_parameter('vision_detections_topic').value
        )
        self.vision_detect_once_topic = str(
            self.get_parameter('vision_detect_once_topic').value
        )
        self.vision_annotated_path = Path(
            str(self.get_parameter('vision_annotated_path').value)
        )
        self.vision_place_positions_path = str(
            self.get_parameter('vision_place_positions_path').value
        )
        self.vision_workspace_path = str(
            self.get_parameter('vision_workspace_path').value
        )
        self.vision_yolo_config_path = str(
            self.get_parameter('vision_yolo_config_path').value
        )
        self.vision_mode = str(self.get_parameter('vision_mode').value)
        self.vision_engine = str(self.get_parameter('vision_engine').value)
        self.tool_mapping = normalize_tool_mapping(
            self.get_parameter('tool_mapping').value
        )
        self.tcp_pose_topic = str(self.get_parameter('tcp_pose_topic').value)
        self.fallback_tcp_pose_topic = str(
            self.get_parameter('fallback_tcp_pose_topic').value
        )
        self.vision_selected_target_topic = str(
            self.get_parameter('vision_selected_target_topic').value
        )
        self.require_integrated_startup = bool(
            self.get_parameter('require_integrated_startup').value
        )
        self.startup_auto = bool(self.get_parameter('startup_auto').value)
        self.startup_auto_motion = bool(
            self.get_parameter('startup_auto_motion').value
        )
        self.calibration_status_topic = str(
            self.get_parameter('calibration_status_topic').value
        )
        self.camera_health_topic = str(
            self.get_parameter('camera_health_topic').value
        )
        self.calibration_verify_service = str(
            self.get_parameter('calibration_verify_service').value
        )
        self.calibration_start_service = str(
            self.get_parameter('calibration_start_service').value
        )
        self.calibration_cancel_service = str(
            self.get_parameter('calibration_cancel_service').value
        )
        self.calibration_recalibrate_service = str(
            self.get_parameter('calibration_recalibrate_service').value
        )
        self.calibration_bundle_path = str(
            self.get_parameter('calibration_bundle_path').value
        )
        observation_pose = list(self.get_parameter('observation_pose_mm').value)
        if not is_pose(observation_pose):
            raise ValueError('observation_pose_mm must be four finite numbers')
        self.observation_pose_mm = [float(value) for value in observation_pose]
        self.pick_all_max_items = int(self.get_parameter('pick_all_max_items').value)
        if not 1 <= self.pick_all_max_items <= 1000:
            raise ValueError('pick_all_max_items must be within [1, 1000]')

        self.bridge = CvBridge()
        self._frame_condition = threading.Condition()
        self._latest_jpeg = None
        self._latest_frame_time = None
        self._latest_frame_source = None
        self._latest_frame_stamp_sec = None
        self._latest_frame_id = ''
        self._frame_sequence = 0
        self._last_frame_encode_time = 0.0
        self._last_calibration_frame_source = None
        self._last_calibration_capture_metadata = {}
        self._latest_camera_intrinsics = None
        self._latest_camera_intrinsics_time = None
        self._placeholder_jpeg = self._make_placeholder()
        self._capture_stop = threading.Event()
        self._capture_thread = None
        self._direct_camera_connected = False

        self._goal_lock = threading.Lock()
        self._active_goal_handle = None
        self._last_feedback = None
        self._last_result = None
        self._last_goal_time = None
        self._latest_joints_deg = None
        self._latest_joints_time = None
        self._latest_tcp_pose = None
        self._latest_tcp_pose_time = None
        self._latest_tcp_pose_source = ''
        self._homing_confirmed = False
        self._vision_lock = threading.Lock()
        self._vision_status = None
        self._vision_status_time = None
        self._vision_detections = None
        self._vision_detections_time = None
        self._vision_last_command = None
        self._vision_selected_target = None
        self._vision_operation_lock = threading.Lock()
        self._vision_operation_state_lock = threading.Lock()
        self._vision_cancel_event = threading.Event()
        self._vision_operation_active = False
        self._vision_operation_started_at = None
        self._integration_lock = threading.RLock()
        self._calibration_status = None
        self._calibration_status_time = None
        self._camera_health = None
        self._camera_health_time = None
        self._alarm_codes = None
        self._alarm_time = None
        self._system_fault = ''
        self._observation_confirmed = False
        self._observation_time = None
        self._startup_action_active = False
        self._startup_machine = StartupStateMachine(
            auto_home=self.startup_auto and self.startup_auto_motion,
            auto_observation=self.startup_auto and self.startup_auto_motion,
        )
        self._operator_job_lock = threading.RLock()
        self._operator_cancel_event = threading.Event()
        self._control_lock = threading.RLock()
        self._control_state = 'IDLE'
        self._control_owner = ''
        self._control_ticket = 0
        self._control_stop_acknowledged = False
        self._operator_job = {
            'active': False,
            'state': 'IDLE',
            'message': 'รอคำสั่ง',
            'job': '',
            'place_id': '',
            'completed': 0,
            'total': 0,
            'failed': 0,
        }
        self._calibration_operation_lock = threading.Lock()
        self._markerless_bundle = (
            VerifiedBundle(self.calibration_bundle_path)
            if VerifiedBundle is not None else None
        )
        self._place_store = (
            PlaceStore(self.vision_place_positions_path)
            if PlaceStore is not None
            else None
        )
        self._safety_guard = self._make_safety_guard()

        self.ptp_action = ActionClient(self, PointToPoint, 'PTP_action')
        self.homing_client = self.create_client(
            ExecuteHomingProcedure, 'dobot_homing_service'
        )
        self.gripper_client = self.create_client(GripperControl, 'dobot_gripper_service')
        self.suction_client = self.create_client(
            SuctionCupControl, 'dobot_suction_cup_service'
        )
        self.calibration_verify_client = self.create_client(
            Trigger, self.calibration_verify_service
        )
        self.calibration_start_client = self.create_client(
            Trigger, self.calibration_start_service
        )
        self.calibration_cancel_client = self.create_client(
            Trigger, self.calibration_cancel_service
        )
        self.calibration_recalibrate_client = self.create_client(
            Trigger, self.calibration_recalibrate_service
        )
        self.calibration_auto_clients = {
            action: self.create_client(Trigger, f'/calibration/auto/{action}')
            for action in ('start', 'pause', 'resume', 'abort')
        }

        if not self.camera_compressed_topic:
            self.create_subscription(
                Image,
                self.camera_raw_topic,
                self._raw_image_callback,
                qos_profile_sensor_data,
            )
        if self.camera_compressed_topic:
            self.create_subscription(
                CompressedImage,
                self.camera_compressed_topic,
                self._compressed_image_callback,
                qos_profile_sensor_data,
            )
        if self.camera_info_topic:
            self.create_subscription(
                CameraInfo,
                self.camera_info_topic,
                self._camera_info_callback,
                qos_profile_sensor_data,
            )
        self.create_subscription(
            JointState,
            'dobot_joint_states',
            self._joint_state_callback,
            10,
        )
        self.create_subscription(
            Float64MultiArray,
            self.tcp_pose_topic,
            lambda msg: self._tcp_pose_callback(msg, self.tcp_pose_topic),
            10,
        )
        if self.fallback_tcp_pose_topic and self.fallback_tcp_pose_topic != self.tcp_pose_topic:
            self.create_subscription(
                Float64MultiArray,
                self.fallback_tcp_pose_topic,
                lambda msg: self._tcp_pose_callback(msg, self.fallback_tcp_pose_topic),
                10,
            )
        self.create_subscription(
            String,
            self.vision_status_topic,
            self._vision_status_callback,
            10,
        )
        self.create_subscription(
            String,
            self.vision_detections_topic,
            self._vision_detections_callback,
            10,
        )
        self.create_subscription(
            String,
            self.calibration_status_topic,
            self._calibration_status_callback,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.create_subscription(
            String,
            self.camera_health_topic,
            self._camera_health_callback,
            10,
        )
        self.create_subscription(
            DobotAlarmCodes,
            '/dobot_alarms',
            self._alarm_callback,
            10,
        )
        self.vision_detect_once_publisher = self.create_publisher(
            String,
            self.vision_detect_once_topic,
            10,
        )
        self.vision_selected_target_publisher = self.create_publisher(
            String,
            self.vision_selected_target_topic,
            10,
        )
        # The supervisor only observes and cancels.  All physical startup
        # actions are dispatched by a short-lived worker, never from a ROS
        # subscription callback.
        self.create_timer(0.25, self._integration_supervisor)
        self.create_timer(0.50, self._advance_startup)

        self.get_logger().info(
            f'Web interface will listen on http://{self.host}:{self.port}'
        )
        self.get_logger().info(
            f'Camera topics: {self.camera_raw_topic}, {self.camera_compressed_topic}'
        )
        self.get_logger().info(
            'Vision topics: '
            f'{self.vision_status_topic}, {self.vision_detections_topic}, '
            f'{self.vision_detect_once_topic}'
        )
        if self._markerless_bundle is not None:
            self.get_logger().info(f'Markerless calibration bundle: {self._markerless_bundle.path}')
        if self._place_store is not None:
            self.get_logger().info(f'Vision place config: {self._place_store.path}')
        if self._safety_guard is not None:
            self.get_logger().info(
                f'Vision safety config: {self._safety_guard.config.as_dict()}'
            )
        if self.camera_device:
            self._capture_thread = threading.Thread(
                target=self._capture_device_loop,
                name='dobot_web_camera_capture',
                daemon=True,
            )
            self._capture_thread.start()
            self.get_logger().info(f'Direct camera device: {self.camera_device}')

    def _make_safety_guard(self):
        if SafetyGuard is None or load_safety_config is None:
            return None
        try:
            config = load_safety_config(self.vision_workspace_path)
        except Exception as exc:
            self.get_logger().warn(f'Failed to load vision safety config: {exc}')
            config = load_safety_config('')
        return SafetyGuard(
            workspace=config.workspace,
            dry_run=config.dry_run_default,
            config=config,
        )

    def _make_placeholder(self):
        image = np.full((540, 960, 3), (28, 31, 36), dtype=np.uint8)
        cv2.putText(
            image,
            'Waiting for camera frame',
            (250, 270),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            (222, 226, 230),
            2,
            cv2.LINE_AA,
        )
        ok, data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return b''
        return data.tobytes()

    def _raw_image_callback(self, msg):
        now = time.monotonic()
        minimum_period = 1.0 / max(0.1, self.stream_fps)
        if now - self._last_frame_encode_time < minimum_period:
            return
        self._last_frame_encode_time = now
        try:
            if msg.encoding == 'mono8':
                cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
            else:
                cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self._store_cv_image(cv_image, self.camera_raw_topic, msg)
        except Exception as exc:
            self.get_logger().warn(f'Failed to convert raw camera frame: {exc}')

    def _compressed_image_callback(self, msg):
        try:
            if 'jpeg' in msg.format.lower() or 'jpg' in msg.format.lower():
                self._store_jpeg(bytes(msg.data), self.camera_compressed_topic, msg)
                return

            buffer = np.frombuffer(msg.data, dtype=np.uint8)
            cv_image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            if cv_image is None:
                raise ValueError('cv2.imdecode returned no image')
            self._store_cv_image(cv_image, self.camera_compressed_topic, msg)
        except Exception as exc:
            self.get_logger().warn(f'Failed to convert compressed camera frame: {exc}')

    def _camera_info_callback(self, msg):
        try:
            intrinsics = _intrinsics_from_camera_info(msg)
        except ValueError as exc:
            self.get_logger().warn(f'Ignored invalid CameraInfo: {exc}')
            return
        intrinsics['frame_id'] = str(msg.header.frame_id)
        with self._frame_condition:
            self._latest_camera_intrinsics = intrinsics
            self._latest_camera_intrinsics_time = time.monotonic()

    def _store_cv_image(self, cv_image, source, message=None):
        ok, data = cv2.imencode(
            '.jpg',
            cv_image,
            [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
        )
        if ok:
            self._store_jpeg(data.tobytes(), source, message)

    @staticmethod
    def _header_metadata(message):
        header = getattr(message, 'header', None)
        stamp = getattr(header, 'stamp', None)
        stamp_sec = None
        if stamp is not None:
            stamp_sec = float(stamp.sec) + float(stamp.nanosec) / 1_000_000_000.0
        return stamp_sec, str(getattr(header, 'frame_id', '') or '')

    def _store_jpeg(self, jpeg_bytes, source, message=None):
        stamp_sec, frame_id = self._header_metadata(message)
        with self._frame_condition:
            self._latest_jpeg = jpeg_bytes
            self._latest_frame_time = time.monotonic()
            self._latest_frame_source = source
            self._latest_frame_stamp_sec = stamp_sec
            self._latest_frame_id = frame_id
            self._frame_sequence += 1
            self._frame_condition.notify_all()

    def _joint_state_callback(self, msg):
        if len(msg.position) < 4:
            return

        with self._goal_lock:
            self._latest_joints_deg = [
                round(float(np.degrees(value)), 2)
                for value in msg.position[:4]
            ]
            self._latest_joints_time = time.monotonic()

    def _tcp_pose_callback(self, msg, source):
        if normalize_tcp_pose is None:
            return
        try:
            pose = normalize_tcp_pose(list(msg.data[:4]), xyz_unit='m')
        except Exception as exc:
            self.get_logger().warn(f'Invalid TCP pose from {source}: {exc}')
            return
        with self._goal_lock:
            self._latest_tcp_pose = pose
            self._latest_tcp_pose_time = time.monotonic()
            self._latest_tcp_pose_source = source

    def _vision_status_callback(self, msg):
        payload = self._parse_json_message(msg.data, 'vision status')
        with self._vision_lock:
            self._vision_status = payload
            self._vision_status_time = time.monotonic()

    def _vision_detections_callback(self, msg):
        payload = self._parse_json_message(msg.data, 'vision detections')
        with self._vision_lock:
            self._vision_detections = payload
            self._vision_detections_time = time.monotonic()

    def _calibration_status_callback(self, msg):
        payload = self._parse_json_message(msg.data, 'calibration status')
        with self._integration_lock:
            self._calibration_status = payload
            self._calibration_status_time = time.monotonic()
            startup_verification_failed = bool(
                self.startup_auto
                and payload.get('state') == 'FAIL'
                and self._startup_machine.state is StartupState.VERIFYING_CALIBRATION
            )

        # Calibration must remain valid throughout a real operation.  The
        # supervisor will cancel a sequence which loses the topic as well;
        # handling an explicit FAIL here makes that transition immediate.
        if payload.get('state') == 'FAIL' and (
            self._operation_is_active() or startup_verification_failed
        ):
            self._latch_system_fault(
                'CALIBRATION_FAILED: ' + str(payload.get('reason') or 'verification failed'),
                stop_motion=True,
            )

    def _camera_health_callback(self, msg):
        payload = self._parse_json_message(msg.data, 'camera health')
        with self._integration_lock:
            self._camera_health = payload
            self._camera_health_time = time.monotonic()

    def _alarm_callback(self, msg):
        with self._integration_lock:
            self._alarm_codes = [int(value) for value in msg.alarms_list]
            self._alarm_time = time.monotonic()

    def _operation_is_active(self):
        with self._vision_operation_state_lock:
            vision_active = self._vision_operation_active
        with self._operator_job_lock:
            operator_active = bool(self._operator_job.get('active'))
        with self._control_lock:
            control_active = bool(self._control_owner)
        return bool(vision_active or operator_active or control_active)

    def _control_snapshot(self):
        with self._control_lock:
            return {
                'state': self._control_state,
                'owner': self._control_owner,
                'stop_acknowledged': self._control_stop_acknowledged,
            }

    def _begin_control_operation(self, owner):
        """Atomically reserve START so a concurrent STOP cannot be cleared."""
        with self._control_lock:
            if self._control_state in ('STARTING', 'RUNNING', 'STOPPING', 'FAULT'):
                raise RuntimeError('ระบบกำลังทำงานหรือกำลังหยุด กรุณารอ')
            if self._control_owner:
                raise RuntimeError('มีงานกำลังทำอยู่')
            self._control_ticket += 1
            ticket = self._control_ticket
            self._control_owner = str(owner)
            self._control_state = 'STARTING'
            self._control_stop_acknowledged = False
            self._vision_cancel_event.clear()
            self._operator_cancel_event.clear()
            return ticket

    def _mark_control_running(self, ticket):
        with self._control_lock:
            if ticket != self._control_ticket or not self._control_owner:
                return False
            if (
                self._control_state == 'STOPPING'
                or self._vision_cancel_event.is_set()
                or self._operator_cancel_event.is_set()
            ):
                self._control_state = 'STOPPING'
                return False
            if self._control_state != 'STARTING':
                return False
            self._control_state = 'RUNNING'
            return True

    def _request_control_stop(self):
        with self._control_lock:
            self._vision_cancel_event.set()
            self._operator_cancel_event.set()
            self._control_stop_acknowledged = False
            if self._control_state != 'FAULT':
                self._control_state = 'STOPPING'
            return bool(self._control_owner)

    def _acknowledge_control_stop(self):
        with self._control_lock:
            self._control_stop_acknowledged = True
            if not self._control_owner and self._control_state == 'STOPPING':
                self._control_state = 'IDLE'

    def _finish_control_operation(self, ticket):
        with self._control_lock:
            if ticket != self._control_ticket:
                return
            self._control_owner = ''
            if self._control_state == 'FAULT':
                return
            if self._control_state == 'STOPPING' and not self._control_stop_acknowledged:
                return
            self._control_state = 'IDLE'

    def _fault_control_operation(self):
        with self._control_lock:
            self._control_state = 'FAULT'
            self._vision_cancel_event.set()
            self._operator_cancel_event.set()

    def _reset_control_fault(self):
        with self._control_lock:
            if self._control_owner or self._control_state == 'STOPPING':
                raise RuntimeError('Cannot reset while an operation is stopping')
            self._control_state = 'IDLE'
            self._control_stop_acknowledged = False
            self._vision_cancel_event.clear()
            self._operator_cancel_event.clear()

    def calibration_runtime_status(self):
        """Return only a fresh live calibration result for system admission."""
        with self._integration_lock:
            payload = dict(self._calibration_status or {})
            received_at = self._calibration_status_time
        if received_at is None:
            return {
                'ready': False,
                'state': 'UNKNOWN',
                'result': 'FAIL',
                'age_sec': None,
                'reason': 'calibration status has not been received',
            }
        payload['age_sec'] = round(time.monotonic() - received_at, 2)
        if payload['age_sec'] > 2.0:
            payload['ready'] = False
            payload['result'] = 'FAIL'
            payload['reason'] = 'calibration status is stale'
        return payload

    def camera_health_runtime_status(self):
        with self._integration_lock:
            payload = dict(self._camera_health or {})
            received_at = self._camera_health_time
        if received_at is None:
            return {
                'ready': False,
                'age_sec': None,
                'blockers': ['camera_health_missing'],
                'usb': {'identity_valid': False, 'camera_identity': ''},
            }
        payload['age_sec'] = round(time.monotonic() - received_at, 2)
        if payload['age_sec'] > 2.0:
            payload['ready'] = False
            blockers = list(payload.get('blockers', []))
            if 'camera_health_stale' not in blockers:
                blockers.append('camera_health_stale')
            payload['blockers'] = blockers
        return payload

    def _readiness_snapshot(self, *, ignore_motion_activity=False):
        status = self.status()
        real_motion_enabled = bool(self._safety().config.allow_real_motion)
        result = aggregate_system_readiness(
            status=status,
            vision=self.vision_status(),
            calibration=self.calibration_runtime_status(),
            homed=status.get('motion', {}).get('homing_confirmed', False),
            at_observation=self._observation_confirmed,
            require_calibration=self.require_integrated_startup,
            fault=self._system_fault,
            camera_health=self.camera_health_runtime_status(),
            real_motion_enabled=real_motion_enabled,
        )
        if ignore_motion_activity:
            result['components']['motion_idle'] = True
            result['blockers'] = [
                blocker for blocker in result['blockers']
                if blocker != 'MOTION_IDLE_NOT_READY'
            ]
            result['ready'] = not result['blockers']
        return result

    def system_readiness(self):
        """The single readiness view used by the web API and motion gates."""
        result = self._readiness_snapshot()
        with self._integration_lock:
            startup = self._startup_machine.advance(result)
            startup_fault = self._startup_machine.fault
        if self.require_integrated_startup and startup.state is not StartupState.READY:
            result['ready'] = False
            if startup_fault:
                result['blockers'] = [
                    'FAULT: ' + startup_fault,
                    *[item for item in result['blockers'] if not item.startswith('FAULT: ')],
                ]
            elif startup.state.value not in ('WAITING_FOR_HOME', 'MOVING_TO_OBSERVATION'):
                # Component-specific blockers already explain the earlier
                # startup stages.  Keep this state only for the operator log.
                pass
        result['startup'] = startup.as_dict()
        result['observation_pose_configured'] = list(self.observation_pose_mm)
        result['motion_mode'] = (
            'REAL' if result['runtime']['real_motion_enabled'] else 'DRY_RUN'
        )
        return result

    def system_startup(self):
        """Explicitly begin/retry the non-motion portion of startup ordering."""
        if self._operation_is_active():
            raise RuntimeError('Cannot restart system startup while a job is active')
        self._reset_control_fault()
        with self._integration_lock:
            self._system_fault = ''
            self._startup_machine.reset()
            readiness = self._readiness_snapshot()
            decision = self._startup_machine.advance(readiness)
            if (
                decision.action != 'verify_calibration'
                or self.calibration_start_client.service_is_ready()
            ) and decision.action:
                self._startup_machine.mark_dispatched(decision.action)
        if decision.action == 'verify_calibration':
            self._dispatch_calibration_verification()
        elif decision.action == 'home' and self.startup_auto_motion:
            self._dispatch_startup_worker(self._run_startup_home, 'home')
        elif decision.action == 'move_observation' and self.startup_auto_motion:
            self._dispatch_startup_worker(self._move_to_observation_pose, 'observation')
        return {
            'accepted': True,
            'startup': decision.as_dict(),
            'system': self.system_readiness(),
        }

    def _motion_is_authorized(self):
        """Check live dependencies while allowing the current sequence to run."""
        result = self._readiness_snapshot(ignore_motion_activity=True)
        components = result['components']
        # Observation is an admission invariant for a *new* sequence.  It is
        # necessarily false between approach and return, so it must not cancel
        # the sequence that is actively restoring that pose.
        required = ('robot', 'camera', 'vision', 'calibration', 'home')
        if not self.require_integrated_startup:
            required = ('robot', 'camera', 'vision', 'home')
        return bool(all(components.get(name) for name in required) and not self._system_fault)

    def _latch_system_fault(self, reason, *, stop_motion=False):
        reason = str(reason or 'system fault')
        newly_latched = False
        with self._integration_lock:
            if not self._system_fault:
                self._system_fault = reason
                self._startup_machine.fail(reason)
                newly_latched = True
                self.get_logger().error(f'[SYSTEM] FAULT {reason}')
        if newly_latched:
            self._fault_control_operation()
        if stop_motion and newly_latched:
            self._request_safe_stop(reason)

    def _request_safe_stop(self, reason='stop requested'):
        """Signal every active controller before cancelling the current goal."""
        self._request_control_stop()
        motion_result = self.cancel_move()
        self._request_calibration_cancel()
        self._acknowledge_control_stop()
        with self._operator_job_lock:
            if self._operator_job.get('active'):
                self._operator_job.update(
                    state='STOPPING',
                    message='กำลังหยุดงานอย่างปลอดภัย',
                )
        self.get_logger().warn(f'[SYSTEM] STOP {reason}')
        return motion_result

    def _request_calibration_cancel(self):
        """Cancel live calibration as part of the same STOP domain as motion."""
        if not self.calibration_cancel_client.service_is_ready():
            return False
        try:
            self.calibration_cancel_client.call_async(Trigger.Request())
            return True
        except Exception as exc:
            self.get_logger().warn(f'[SYSTEM] calibration cancel unavailable: {exc}')
            return False

    def _integration_supervisor(self):
        """Abort active work as soon as a required live source disappears."""
        if not self._operation_is_active():
            return
        if self._motion_is_authorized():
            return
        readiness = self._readiness_snapshot(ignore_motion_activity=True)
        blocker = next(iter(readiness.get('blockers', [])), 'live readiness lost')
        self._latch_system_fault(str(blocker), stop_motion=True)

    def _advance_startup(self):
        if not (self.require_integrated_startup and self.startup_auto):
            return
        with self._integration_lock:
            decision = self._startup_machine.advance(self._readiness_snapshot())
            if (
                decision.action == 'verify_calibration'
                and not self.calibration_start_client.service_is_ready()
            ):
                # Process startup is asynchronous; service absence here is a
                # wait condition, not a calibration failure.
                return
            if decision.action:
                self._startup_machine.mark_dispatched(decision.action)
        if decision.action == 'verify_calibration':
            self._dispatch_calibration_verification()
        elif decision.action == 'home':
            self._dispatch_startup_worker(self._run_startup_home, 'home')
        elif decision.action == 'move_observation':
            self._dispatch_startup_worker(
                self._move_to_observation_pose, 'observation',
            )

    def _dispatch_calibration_verification(self):
        """Load and verify a saved bundle, or calibrate once when safely permitted."""
        if not self.calibration_start_client.service_is_ready():
            return
        future = self.calibration_start_client.call_async(Trigger.Request())

        def finished(request_future):
            try:
                response = request_future.result()
                if not response.success:
                    self._latch_system_fault(
                        'CALIBRATION_VERIFICATION_FAILED: ' + str(response.message),
                    )
                else:
                    self.get_logger().info('[SYSTEM] guarded calibration workflow requested')
            except Exception as exc:
                self._latch_system_fault(f'CALIBRATION_VERIFICATION_FAILED: {exc}')

        future.add_done_callback(finished)

    def _dispatch_startup_worker(self, callback, label):
        with self._integration_lock:
            if self._startup_action_active:
                return
            self._startup_action_active = True

        def run():
            try:
                callback()
            except Exception as exc:
                self._latch_system_fault(f'{label.upper()}_FAILED: {exc}', stop_motion=True)
            finally:
                with self._integration_lock:
                    self._startup_action_active = False

        threading.Thread(
            target=run,
            name=f'dobot_startup_{label}',
            daemon=True,
        ).start()

    def _run_startup_home(self):
        result = self.call_homing(move_to_observation=False)
        if not result.get('success'):
            raise RuntimeError(result.get('message', 'HOME command failed'))
        self._move_to_observation_pose()

    def _move_to_observation_pose(self):
        """Return to the configured safe observation pose and mark it live."""
        if self._vision_cancel_event.is_set() or self._operator_cancel_event.is_set():
            raise RuntimeError('observation move canceled')
        guard = self._safety()
        if not guard.config.allow_real_motion:
            raise RuntimeError('real motion is disabled by safety configuration')
        decision = guard.validate_target_pose(self.observation_pose_mm)
        if not decision.allowed:
            raise RuntimeError(decision.reason)
        response = self._automatic_pick_move(
            self.observation_pose_mm,
            0.20,
            0.15,
            'return_to_observation_pose',
        )
        if response.get('accepted') is False or response.get('success') is False:
            raise RuntimeError(response.get('message', 'observation move was rejected'))
        with self._integration_lock:
            self._observation_confirmed = True
            self._observation_time = time.monotonic()
        self.get_logger().info('[SYSTEM] observation pose reached')
        return {'reached': True, 'pose': list(self.observation_pose_mm)}

    def _parse_json_message(self, data, label):
        try:
            payload = json.loads(data)
            if isinstance(payload, dict):
                return payload
            raise ValueError('JSON payload must be an object')
        except Exception as exc:
            self.get_logger().warn(f'Invalid {label} JSON: {exc}')
            return {
                'error': f'Invalid {label} JSON: {exc}',
                'raw': data,
            }

    def _capture_device_loop(self):
        warn_after = 0.0
        frame_delay = 1.0 / max(self.camera_fps, 1.0)

        while not self._capture_stop.is_set():
            capture = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
            if not capture.isOpened():
                self._direct_camera_connected = False
                now = time.monotonic()
                if now >= warn_after:
                    self.get_logger().warn(
                        f'Unable to open camera device {self.camera_device}'
                    )
                    warn_after = now + 5.0
                self._capture_stop.wait(2.0)
                continue

            self._direct_camera_connected = True
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)
            capture.set(cv2.CAP_PROP_FPS, self.camera_fps)
            self.get_logger().info(
                f'Camera device opened: {self.camera_device} '
                f'{self.camera_width}x{self.camera_height}@{self.camera_fps:g}'
            )

            try:
                while not self._capture_stop.is_set():
                    started = time.monotonic()
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        self._direct_camera_connected = False
                        self.get_logger().warn('Camera frame capture failed')
                        break

                    self._store_cv_image(frame, self.camera_device)
                    elapsed = time.monotonic() - started
                    self._capture_stop.wait(max(frame_delay - elapsed, 0.0))
            finally:
                capture.release()

            self._capture_stop.wait(1.0)

    def get_frame(self, wait_timeout=1.0):
        with self._frame_condition:
            if self._latest_jpeg is None:
                self._frame_condition.wait(timeout=wait_timeout)
            return self._latest_jpeg or self._placeholder_jpeg

    def status(self):
        with self._frame_condition:
            frame_age = None
            if self._latest_frame_time is not None:
                frame_age = round(time.monotonic() - self._latest_frame_time, 2)
            frame_source = self._latest_frame_source
            intrinsics_source = 'yaml_fallback'
            intrinsics_age = None
            if self._latest_camera_intrinsics_time is not None:
                intrinsics_age = round(
                    time.monotonic() - self._latest_camera_intrinsics_time,
                    2,
                )
                if intrinsics_age <= 5.0:
                    intrinsics_source = 'camera_info'

        with self._goal_lock:
            active_goal = self._active_goal_handle is not None
            last_feedback = self._last_feedback
            last_result = self._last_result
            joints_deg = self._latest_joints_deg
            joints_age = None
            if self._latest_joints_time is not None:
                joints_age = round(time.monotonic() - self._latest_joints_time, 2)
            tcp_pose = self._latest_tcp_pose
            tcp_pose_source = self._latest_tcp_pose_source
            tcp_pose_age = None
            if self._latest_tcp_pose_time is not None:
                tcp_pose_age = round(time.monotonic() - self._latest_tcp_pose_time, 2)
            homing_confirmed = self._homing_confirmed
            last_goal_age = None
            if self._last_goal_time is not None:
                last_goal_age = round(time.monotonic() - self._last_goal_time, 2)

        with self._vision_operation_state_lock:
            vision_operation_active = self._vision_operation_active
            vision_operation_age = None
            if self._vision_operation_started_at is not None:
                vision_operation_age = round(
                    time.monotonic() - self._vision_operation_started_at,
                    2,
                )

        with self._integration_lock:
            alarm_codes = list(self._alarm_codes or [])
            alarm_age = None
            if self._alarm_time is not None:
                alarm_age = round(time.monotonic() - self._alarm_time, 2)
            alarm_state_fresh = alarm_age is not None and alarm_age <= 1.0
        camera_health = self.camera_health_runtime_status()

        return {
            'camera': {
                'raw_topic': self.camera_raw_topic,
                'compressed_topic': self.camera_compressed_topic,
                'device': self.camera_device,
                'direct_camera_connected': self._direct_camera_connected,
                'frame_age_sec': frame_age,
                'frame_source': frame_source,
                'has_frame': frame_source is not None,
                'camera_info_topic': self.camera_info_topic,
                'intrinsics_source': intrinsics_source,
                'intrinsics_age_sec': intrinsics_age,
            },
            'ros': {
                'ptp_action_ready': self.ptp_action.server_is_ready(),
                'homing_ready': self.homing_client.service_is_ready(),
                'gripper_ready': self._web_tool_ready('gripper'),
                'suction_ready': self._web_tool_ready('suction'),
                'tool_mapping': self.tool_mapping,
                'alarm_state_fresh': alarm_state_fresh,
                'no_critical_alarm': bool(alarm_state_fresh and not alarm_codes),
                'alarm_codes': alarm_codes,
            },
            'motion': {
                'active_goal': active_goal,
                'last_goal_age_sec': last_goal_age,
                'last_feedback': last_feedback,
                'last_result': last_result,
                'joints_deg': joints_deg,
                'joints_age_sec': joints_age,
                'current_tcp_pose': tcp_pose,
                'current_tcp_pose_source': tcp_pose_source,
                'current_tcp_pose_age_sec': tcp_pose_age,
                'homing_confirmed': homing_confirmed,
                'vision_sequence_active': vision_operation_active,
                'vision_sequence_age_sec': vision_operation_age,
            },
            'camera_health': camera_health,
        }

    def vision_status(self):
        now = time.monotonic()
        with self._vision_lock:
            payload = dict(self._vision_status or {})
            received_at = self._vision_status_time
            last_command = self._vision_last_command

        if received_at is None:
            return {
                'ok': False,
                'detector_running': False,
                'vision_engine': self.vision_engine,
                'error': 'Vision detector status has not been received.',
                'age_sec': None,
                'fps': 0.0,
                'loop_fps': 0.0,
                'inference_fps': None,
                'inference_time_ms': None,
                'model_path': '',
                'confidence_threshold': None,
                'dry_run': True,
                'detect_only': True,
                'source_type': '',
                'source_ok': False,
                'model_loaded': False,
                'last_command': last_command,
                'raw': {},
            }

        age_sec = round(now - received_at, 2)
        stale = age_sec > 5.0
        model_error = payload.get('model_error') or ''
        last_error = payload.get('last_error') or payload.get('error') or ''
        error = ''
        if stale:
            error = f'Vision detector status is stale ({age_sec}s old).'
        elif model_error:
            error = model_error
        elif last_error:
            error = last_error

        return {
            'ok': not stale and not error,
            'vision_engine': payload.get('vision_engine', self.vision_engine),
            'detector_running': not stale,
            'error': error,
            'age_sec': age_sec,
            'fps': (
                float(payload['fps'])
                if payload.get('fps') is not None
                else None
            ),
            'loop_fps': float(payload.get('loop_fps') or 0.0),
            'inference_fps': (
                float(payload['inference_fps'])
                if payload.get('inference_fps') is not None
                else None
            ),
            'inference_time_ms': payload.get('inference_time_ms'),
            'inference_count': int(payload.get('inference_count') or 0),
            'detection_count': int(payload.get('detection_count') or 0),
            'configured_classes': payload.get('configured_classes', []),
            'model_classes': payload.get('model_classes', {}),
            'class_warnings': payload.get('class_warnings', []),
            'cuda_available': bool(payload.get('cuda_available', False)),
            'model_path': payload.get('model_path')
            or payload.get('configured_model_path')
            or '',
            'configured_model_path': payload.get('configured_model_path', ''),
            'fallback_model_path': payload.get('fallback_model_path', ''),
            'confidence_threshold': payload.get('confidence_threshold'),
            'dry_run': bool(payload.get('dry_run', True)),
            'detect_only': bool(payload.get('detect_only', True)),
            'source_type': payload.get('source_type', ''),
            'source_ok': bool(payload.get('source_ok', False)),
            'rgb_ok': bool(payload.get('rgb_ok', payload.get('source_ok', False))),
            'depth_ok': bool(payload.get('depth_ok', False)),
            'depth_stream_ok': bool(payload.get(
                'depth_stream_ok', payload.get('depth_ok', False))),
            'depth_data_valid': bool(payload.get(
                'depth_data_valid', payload.get('depth_ok', False))),
            'depth_valid_ratio': payload.get('depth_valid_ratio'),
            'sync_ok': bool(payload.get('sync_ok', False)),
            'camera_info_ok': bool(payload.get('camera_info_ok', False)),
            'sync_delta_ms': payload.get('sync_delta_ms'),
            'table_depth_mm': payload.get('table_depth_mm'),
            'real_motion': bool(payload.get('real_motion', False)),
            'model_loaded': bool(payload.get('model_loaded', False)),
            'annotated_image_path': payload.get(
                'annotated_image_path',
                str(self.vision_annotated_path),
            ),
            'last_command': last_command,
            'raw': payload,
        }

    def vision_detections(self):
        now = time.monotonic()
        with self._vision_lock:
            payload = dict(self._vision_detections or {})
            received_at = self._vision_detections_time

        if received_at is None:
            return {
                'ok': False,
                'error': 'Vision detections have not been received.',
                'age_sec': None,
                'stamp': None,
                'detections': [],
            }

        age_sec = round(now - received_at, 2)
        stale = age_sec > 5.0
        detections = payload.get('detections', [])
        if not isinstance(detections, list):
            detections = []
        return {
            'ok': not stale and not payload.get('error'),
            'error': (
                f'Vision detections are stale ({age_sec}s old).'
                if stale
                else payload.get('error', '')
            ),
            'age_sec': age_sec,
            'stamp': payload.get('stamp'),
            'detections': detections,
            'raw': payload,
        }

    def vision_detect_once(self, payload):
        dry_run = bool(payload.get('dry_run', True))
        if not dry_run:
            raise ValueError('Vision detect_once is dry_run only in this phase')

        command = {
            'stamp': time.time(),
            'dry_run': True,
            'object_class': str(payload.get('object_class', 'all')),
            'place_id': str(payload.get('place_id', payload.get('place_position', ''))),
            'place_position': str(payload.get('place_position', 'staging')),
        }
        msg = String()
        msg.data = json.dumps(command, separators=(',', ':'))
        self.vision_detect_once_publisher.publish(msg)
        with self._vision_lock:
            self._vision_last_command = command

        return {
            'accepted': True,
            'dry_run': True,
            'message': 'Dry-run detect_once command published. No robot motion was sent.',
            'command': command,
            'status': self.vision_status(),
            'detections': self.vision_detections(),
        }

    def vision_classes(self):
        if classes_from_detections is None or load_configured_classes is None:
            raise ConnectionError('dobot_vision_yolo target selector tools are not available')

        detected = classes_from_detections(self.vision_detections().get('detections', []))
        configured = load_configured_classes(self.vision_yolo_config_path)
        return {
            'classes': sorted(set(configured + detected)),
            'configured_classes': configured,
            'detected_classes': detected,
        }

    def vision_places(self):
        return self._places().status()

    @staticmethod
    def _operator_job_spec(value):
        job = str(value or '').strip().lower()
        if job not in OPERATOR_JOB_SPECS:
            raise ValueError('เลือกชิ้นงานไม่ถูกต้อง')
        return job, dict(OPERATOR_JOB_SPECS[job])

    def _operator_places(self):
        """List configured canonical zones without leaking their poses."""
        configured = self._places().status().get('places', {})
        return [
            {'id': place_id, 'label': label}
            for place_id, label in OPERATOR_PLACE_LABELS.items()
            if place_id in configured
        ]

    def _operator_place(self, value):
        place_id = str(value or '').strip()
        if place_id not in {item['id'] for item in self._operator_places()}:
            raise ValueError('ตำแหน่งวางไม่ถูกต้องหรือยังไม่พร้อม')
        return place_id

    @staticmethod
    def _operator_check(key, ok, reason=''):
        labels = {
            'robot': 'หุ่นยนต์',
            'camera': 'กล้อง',
            'depth': 'ความลึก',
            'calibration': 'การคาลิเบรต',
            'suction': 'หัวดูด',
            'objects': 'ชิ้นงานที่ตรวจพบ',
            'place': 'ตำแหน่งวาง',
            'safety': 'การตรวจสอบความปลอดภัย',
            'system': 'ระบบรวม',
        }
        return {
            'key': key,
            'label': labels[key],
            'ok': bool(ok),
            'status': 'พร้อมใช้งาน' if ok else 'ไม่พร้อมใช้งาน',
            'reason': str(reason or ('ผ่านการตรวจสอบจากข้อมูลสด' if ok else 'ยังไม่มีหลักฐานพร้อมใช้งาน')),
        }

    @staticmethod
    def _operator_fault_message(system):
        """Translate stable backend blocker codes into actionable Thai text."""
        blockers = system.get('blockers', []) if isinstance(system, dict) else []
        code = str(blockers[0]) if blockers else ''
        messages = {
            'ROBOT_NOT_READY': 'ตรวจไฟเลี้ยง สาย USB และการเชื่อมต่อหุ่นยนต์',
            'CAMERA_NOT_READY': 'ตรวจสายกล้อง พอร์ต USB 3 และภาพ RGB-D',
            'VISION_NOT_READY': 'รอระบบตรวจจับและข้อมูล RGB-D ที่ตรงเวลา',
            'CALIBRATION_NOT_READY': 'การคาลิเบรตยังไม่ผ่านการตรวจสอบกับกล้องตัวนี้',
            'HOME_NOT_READY': 'หุ่นยนต์ยังไม่ผ่าน HOME กรุณาตรวจพื้นที่ก่อนสั่ง HOME',
            'OBSERVATION_NOT_READY': 'หุ่นยนต์ยังไม่อยู่ที่จุดสังเกตที่กำหนด',
            'MOTION_IDLE_NOT_READY': 'รอให้คำสั่งเคลื่อนที่ปัจจุบันหยุดก่อน',
            'REAL_MOTION_NOT_READY': 'ระบบยังอยู่ในโหมดทดสอบและไม่อนุญาตการเคลื่อนไหวจริง',
        }
        if code.startswith('FAULT:'):
            return 'ระบบหยุดเพื่อความปลอดภัย กรุณาตรวจสอบฮาร์ดแวร์และเริ่มตรวจระบบใหม่'
        return messages.get(code, 'ระบบยังไม่พร้อม กรุณาตรวจสอบสถานะอุปกรณ์')

    def _operator_job_snapshot(self):
        """Copy the user-safe progress record while holding its lock."""
        with self._operator_job_lock:
            record = dict(self._operator_job)
        job_label = OPERATOR_JOB_SPECS.get(record['job'], {}).get('label', '')
        place_label = OPERATOR_PLACE_LABELS.get(record['place_id'], '')
        return {
            'active': bool(record['active']),
            'state': str(record['state']),
            'message': str(record['message']),
            'job': job_label,
            'place': place_label,
            'completed': int(record['completed']),
            'total': int(record['total']),
            'failed': int(record['failed']),
        }

    def _operator_set_job(self, **values):
        with self._operator_job_lock:
            self._operator_job.update(values)

    def _operator_preflight(self, job, place_id):
        """Run the real pick guards and reduce them to operator-safe status.

        This deliberately uses the same target selection and safety report as
        execution.  A green operator screen is therefore not a client-side
        approximation of the robot safety decision.
        """
        _, spec = self._operator_job_spec(job)
        place_id = self._operator_place(place_id)
        system = self.status()
        vision = self.vision_status()
        detections = self.vision_detections()
        counts = operator_detection_counts(detections.get('detections', []))
        request = {
            'dry_run': True,
            'object_class': spec['class_name'],
            'place_id': place_id,
            'vision_mode': self.vision_mode,
            'selection_mode': 'highest_confidence',
        }
        selected = self._select_target_preview_source(request)
        safety = self._safety_report({
            'selected_target': selected,
            'dry_run': False,
            'vision_mode': self.vision_mode,
            'place_id': place_id,
        })
        safety_checks = {
            item.get('name'): bool(item.get('ok'))
            for item in safety.get('checks', [])
            if isinstance(item, dict)
        }
        safety_reasons = {
            item.get('name'): str(item.get('reason') or '')
            for item in safety.get('checks', [])
            if isinstance(item, dict)
        }
        motion = system.get('motion', {})
        ros = system.get('ros', {})
        robot_ok = bool(
            ros.get('ptp_action_ready')
            and not motion.get('active_goal')
            and not motion.get('vision_sequence_active')
        )
        integrated_system = {'ready': True, 'blockers': []}
        system_ok = True
        if getattr(self, 'require_integrated_startup', False):
            integrated_system = self.system_readiness()
            system_ok = bool(integrated_system.get('ready'))
        camera_ok = bool(
            safety_checks.get('camera') and safety_checks.get('yolo')
        )
        depth_ok = bool(
            vision.get('depth_stream_ok') and vision.get('depth_data_valid')
        )
        calibration_ok = bool(safety_checks.get('calibration'))
        suction_ok = bool(ros.get('suction_ready'))
        objects_ok = bool(selected.get('selected'))
        # Destination configuration is an independent readiness component.
        # Target workspace validity belongs to Object/Safety and must not make
        # an otherwise valid taught place appear missing.
        place_ok = bool(safety_checks.get('place'))
        system_reason = '; '.join(map(str, integrated_system.get('blockers', [])))
        selected_reason = str(
            selected.get('reason') or selected.get('rejection_reason')
            or ('พบเป้าหมายที่เลือกได้' if objects_ok else 'ไม่มีเป้าหมายที่ผ่านเกณฑ์')
        )
        place_reason = (
            safety_reasons.get('place') if objects_ok else
            f'{place_id}: รอ calibration/target ที่ valid เพื่อยืนยัน trajectory แบบ live'
        )
        checks = [
            self._operator_check('robot', robot_ok,
                                 'action server พร้อมและไม่มี motion ค้าง' if robot_ok else 'action server ไม่พร้อมหรือมี motion ค้าง'),
            self._operator_check('camera', camera_ok,
                                 '; '.join(filter(None, (safety_reasons.get('camera'), safety_reasons.get('yolo'))))),
            self._operator_check('depth', depth_ok,
                                 f"depth_stream_ok={bool(vision.get('depth_stream_ok'))}, depth_data_valid={bool(vision.get('depth_data_valid'))}, valid_ratio={vision.get('depth_valid_ratio', 'unknown')}"),
            self._operator_check('calibration', calibration_ok,
                                 safety_reasons.get('calibration') or system_reason or 'ยังไม่มี live verification PASS'),
            self._operator_check('suction', suction_ok,
                                 'service พร้อม' if suction_ok else 'dobot_suction_cup_service ไม่พร้อม'),
            self._operator_check('objects', objects_ok, selected_reason),
            self._operator_check('place', place_ok, place_reason),
            self._operator_check('safety', bool(safety.get('allowed')),
                                 str(safety.get('reason') or 'ทุก safety gate ผ่าน')),
            self._operator_check('system', system_ok,
                                 system_reason or 'ทุก integrated startup gate ผ่าน'),
        ]
        return {
            'ready': all(item['ok'] for item in checks),
            'checks': checks,
            'counts': counts,
            'selected': selected,
            'system': integrated_system,
        }

    def operator_status(self, payload=None):
        """Return a compact, Thai-ready status for the operator screen only."""
        payload = payload if isinstance(payload, dict) else {}
        job = str(payload.get('job', 'black') or 'black').strip().lower()
        place_id = str(payload.get('place_id', 'Zone A') or 'Zone A').strip()
        try:
            job, spec = self._operator_job_spec(job)
            place_id = self._operator_place(place_id)
            preflight = self._operator_preflight(job, place_id)
        except Exception:
            # A status poll must fail closed, but a malformed browser value
            # should never surface internal exception text to an operator.
            spec = OPERATOR_JOB_SPECS['black']
            preflight = {
                'ready': False,
                'counts': {'black': 0, 'white': 0, 'yellow': 0},
                'checks': [
                    self._operator_check(key, False)
                    for key in (
                        'robot', 'camera', 'depth', 'calibration',
                        'suction', 'objects', 'place', 'safety', 'system',
                    )
                ],
                'system': {'ready': False, 'blockers': []},
            }
        try:
            places = self._operator_places()
        except Exception:
            places = []
        operation = self._operator_job_snapshot()
        active = operation['active']
        control = self._control_snapshot()
        command_idle = control['state'] == 'IDLE'
        motion_mode = 'REAL' if self._safety().config.allow_real_motion else 'DRY_RUN'
        try:
            calibration_runtime = self.calibration_runtime_status()
            calibration_guidance = calibration_runtime.get('passive_guidance', {})
            supervised_auto = calibration_runtime.get('supervised_auto', {})
        except AttributeError:
            calibration_guidance = {}
            supervised_auto = {}
        return {
            'ready': bool(preflight['ready'] and not active and command_idle),
            'overall_status': (
                'พร้อมใช้งาน' if preflight['ready'] and not active and command_idle
                else 'ไม่พร้อมใช้งาน'
            ),
            'checks': preflight['checks'],
            'counts': preflight['counts'],
            'jobs': [
                {'id': name, 'label': item['label']}
                for name, item in OPERATOR_JOB_SPECS.items()
            ],
            'places': places,
            'selected_job': spec['label'],
            'selected_place': OPERATOR_PLACE_LABELS.get(place_id, ''),
            'operation': operation,
            'control': control,
            'motion_mode': motion_mode,
            'calibration_guidance': calibration_guidance,
            'supervised_auto': supervised_auto,
            'fault_message': (
                '' if preflight['ready'] else
                self._operator_fault_message(preflight.get('system'))
            ),
            'pick_all': {
                'completed': operation['completed'] if operation['job'] == 'หยิบทั้งหมด' else 0,
                'total': operation['total'] if operation['job'] == 'หยิบทั้งหมด' else 0,
                'failed': operation['failed'] if operation['job'] == 'หยิบทั้งหมด' else 0,
            },
        }

    def operator_start(self, payload):
        """Start one safe operator job after repeating the server preflight."""
        if not isinstance(payload, dict):
            raise ValueError('ข้อมูลเริ่มงานไม่ถูกต้อง')
        job, _ = self._operator_job_spec(payload.get('job'))
        place_id = self._operator_place(payload.get('place_id'))
        control_ticket = self._begin_control_operation('operator')
        try:
            with self._operator_job_lock:
                if self._operator_job['active']:
                    raise RuntimeError('มีงานกำลังทำอยู่')
                preflight = self._operator_preflight(job, place_id)
                if not preflight['ready']:
                    raise ValueError('ระบบไม่พร้อมใช้งาน กรุณาตรวจสอบสถานะก่อนเริ่มงาน')
                counts = dict(preflight['counts'])
                total = sum(counts.values()) if job == 'pick_all' else 1
                if total <= 0:
                    raise ValueError('ไม่พบชิ้นงานที่เลือก')
                self._operator_job = {
                    'active': True,
                    'state': 'STARTING',
                    'message': 'กำลังเริ่มงาน',
                    'job': job,
                    'place_id': place_id,
                    'completed': 0,
                    'total': total,
                    'failed': 0,
                }
        except Exception as exc:
            self._finish_control_operation(control_ticket)
            if isinstance(exc, RuntimeError):
                raise
            raise ValueError(
                'ระบบไม่พร้อมใช้งาน กรุณาตรวจสอบสถานะก่อนเริ่มงาน'
            ) from exc
        threading.Thread(
            target=self._run_operator_job,
            args=(job, place_id, counts, control_ticket),
            name='dobot_operator_job',
            daemon=True,
        ).start()
        return {'accepted': True, 'message': 'เริ่มทำงานแล้ว'}

    def _request_fresh_detection(self, object_class='all', place_id=''):
        """Publish detect-once and require a newer healthy detector snapshot."""
        with self._vision_lock:
            before = self._vision_detections_time
        self.vision_detect_once({
            'dry_run': True,
            'object_class': str(object_class or 'all'),
            'place_id': str(place_id or ''),
        })
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if self._vision_cancel_event.is_set() or self._operator_cancel_event.is_set():
                raise RuntimeError('detection canceled')
            with self._vision_lock:
                received_at = self._vision_detections_time
            if received_at is not None and (before is None or received_at > before):
                detections = self.vision_detections()
                if not detections.get('ok'):
                    raise ValueError(detections.get('error') or 'fresh detections unavailable')
                return detections
            self._vision_cancel_event.wait(0.05)
        raise TimeoutError('timed out waiting for fresh detections')

    @staticmethod
    def _operator_next_job(counts):
        for job in ('black', 'white', 'yellow'):
            if int(counts.get(job, 0)) > 0:
                return job
        return None

    def _operator_fail(self, state, message):
        with self._operator_job_lock:
            self._operator_job['active'] = False
            self._operator_job['state'] = state
            self._operator_job['failed'] = int(self._operator_job['failed']) + 1
            self._operator_job['message'] = message

    def _run_operator_job(self, job, place_id, initial_counts, control_ticket=None):
        """Run a serial, re-detected pick loop with no cached target schedule.

        Pick-all deliberately does *not* use the initial object count as a
        motion schedule.  Each iteration starts from a new detector frame at
        observation, and the frame following every completed placement starts
        the next iteration.  This avoids acting on a part that has moved,
        disappeared, or was introduced after the job began.
        """
        completed = 0
        disappeared = 0
        try:
            if control_ticket is not None and not self._mark_control_running(control_ticket):
                self._operator_set_job(
                    active=False,
                    state='STOPPED',
                    message='หยุดงานอย่างปลอดภัย',
                )
                return
            while True:
                if self._operator_cancel_event.is_set():
                    self._operator_set_job(
                        active=False,
                        state='STOPPED',
                        message='หยุดงานอย่างปลอดภัย',
                    )
                    return

                if job == 'pick_all':
                    self._operator_set_job(
                        state='DETECTING',
                        message='กำลังตรวจหาชิ้นงานรอบใหม่',
                    )
                    scene = self._request_fresh_detection('all', place_id)
                    counts = operator_detection_counts(scene.get('detections', []))
                    one_job = self._operator_next_job(counts)
                    self._operator_set_job(total=completed + sum(counts.values()))
                    if one_job is None:
                        self._operator_set_job(
                            active=False,
                            state='DONE',
                            message='เสร็จสิ้น',
                        )
                        return
                    if completed >= self.pick_all_max_items:
                        self._operator_fail(
                            'FAILED',
                            'หยุดงานอย่างปลอดภัย: ถึงขีดจำกัดจำนวนชิ้นงาน',
                        )
                        return
                else:
                    one_job = job
                    if completed:
                        self._operator_set_job(
                            active=False,
                            state='DONE',
                            message='เสร็จสิ้น',
                        )
                        return

                self._operator_set_job(
                    state='PICKING',
                    message=f'กำลังหยิบชิ้นที่ {completed + 1}',
                )
                preflight = self._operator_preflight(one_job, place_id)
                if not preflight['ready']:
                    # A target can disappear after the fresh pick-all frame
                    # but before selection.  Re-detect and continue rather
                    # than moving toward an old coordinate.  Other preflight
                    # failures (depth, calibration, reachability, camera) are
                    # terminal and leave the controllers in their safe state.
                    if (
                        job == 'pick_all'
                        and not preflight.get('selected', {}).get('selected')
                        and disappeared < 3
                    ):
                        disappeared += 1
                        self.get_logger().info('[PICK_ALL] target disappeared; re-detecting')
                        continue
                    state = (
                        'TARGET_DISAPPEARED'
                        if not preflight.get('selected', {}).get('selected')
                        else 'FAILED'
                    )
                    self._operator_fail(
                        state,
                        'หยุดงานอย่างปลอดภัย: ไม่พบชิ้นงานหรือระบบไม่พร้อมใช้งาน',
                    )
                    return
                disappeared = 0
                _, spec = self._operator_job_spec(one_job)
                result = self.vision_pick_selected(
                    {
                        'dry_run': False,
                        'confirm_real_motion': True,
                        'object_class': spec['class_name'],
                        'place_id': place_id,
                        'vision_mode': self.vision_mode,
                        'selection_mode': 'highest_confidence',
                        'max_attempts': 2,
                    },
                    clear_cancel_event=False,
                )
                if not result.get('executed') or not result.get('placed'):
                    self._operator_fail(
                        'STOPPED' if self._operator_cancel_event.is_set() else 'FAILED',
                        (
                            'หยุดงานอย่างปลอดภัย'
                            if self._operator_cancel_event.is_set()
                            else 'หยุดงานอย่างปลอดภัย: หยิบหรือวางไม่สำเร็จ'
                        ),
                    )
                    return
                completed += 1
                with self._operator_job_lock:
                    self._operator_job['completed'] = completed

                if job != 'pick_all':
                    self._operator_set_job(
                        active=False,
                        state='DONE',
                        message='เสร็จสิ้น',
                    )
                    return
                # The next loop is deliberately entered only after the
                # placement controller has verified release, returned to the
                # observation pose, and this method has asked for a new frame.
        except Exception as exc:
            if self._operator_cancel_event.is_set() or self._vision_cancel_event.is_set():
                self._operator_set_job(
                    active=False,
                    state='STOPPED',
                    message='หยุดงานอย่างปลอดภัย',
                )
            else:
                self.get_logger().warn(f'[OPERATOR] job failed safely: {exc}')
                self._operator_fail(
                    'FAILED',
                    'หยุดงานอย่างปลอดภัย: การทำงานไม่สำเร็จ',
                )
        finally:
            if control_ticket is not None:
                self._finish_control_operation(control_ticket)

    def operator_stop(self):
        """Stop the UI job and propagate cancellation to the robot backend."""
        self._operator_cancel_event.set()
        result = self.vision_cancel()
        with self._operator_job_lock:
            if self._operator_job['active']:
                self._operator_job.update(
                    state='STOPPING',
                    message='กำลังหยุดงานอย่างปลอดภัย',
                )
        return {
            'requested': bool(result.get('requested')),
            'message': 'ส่งคำสั่งหยุดแล้ว',
        }

    def vision_select_target(self, payload):
        result = self._select_target_preview_source(payload)
        with self._vision_lock:
            self._vision_selected_target = result

        if result.get('selected'):
            msg = String()
            msg.data = json.dumps(result, separators=(',', ':'))
            self.vision_selected_target_publisher.publish(msg)

        return result

    def _select_target_preview_source(self, payload):
        if select_target_from_detections is None:
            raise ConnectionError('dobot_vision_yolo target selector tools are not available')

        dry_run = bool(payload.get('dry_run', True))
        if not dry_run:
            raise ValueError('Vision target selection is dry_run only in this phase')

        detections = self.vision_detections()
        if not detections.get('ok'):
            raise ValueError(
                detections.get('error') or 'Vision detections are not available.'
            )

        vision_mode = self._vision_mode_from_payload(payload)
        payload = dict(payload)
        payload['vision_mode'] = vision_mode
        if vision_mode != 'eye_in_hand':
            raise ValueError('Production markerless calibration requires eye_in_hand topology')
        pixel_transformer = self._eye_in_hand_pixel_transformer()
        calibration_label = 'Markerless hand-eye calibration'
        source = 'dobot_web_interface:markerless_hand_eye'

        image_size = (
            int(payload.get('image_width', 640)),
            int(payload.get('image_height', 480)),
        )
        result = select_target_from_detections(
            detections,
            payload,
            self._places(),
            None,
            dry_run=True,
            image_size=image_size,
            min_confidence=float(payload.get('min_confidence', 0.0)),
            source=source,
            pixel_transformer=pixel_transformer,
            calibration_label=calibration_label,
        )
        result['vision_mode'] = vision_mode
        return result

    def _vision_mode_from_payload(self, payload):
        mode = str(payload.get('vision_mode', self.vision_mode) or 'fixed_camera')
        if mode not in ('fixed_camera', 'eye_in_hand'):
            raise ValueError('vision_mode must be fixed_camera or eye_in_hand')
        return mode

    def _eye_in_hand_pixel_transformer(self):
        tcp_pose_mm = self._current_tcp_pose()
        if tcp_pose_mm is None:
            raise ValueError('TCP pose is unavailable for eye-in-hand vision')
        if self._markerless_bundle is None:
            raise ConnectionError('dobot_calibration bundle consumer is unavailable')
        tcp_pose_m = [value / 1000.0 for value in tcp_pose_mm[:3]] + [tcp_pose_mm[3]]

        def transform(_center_pixel, detection):
            xyz = self._markerless_bundle.camera_point_to_base(
                detection.get('camera_xyz_mm'), tcp_pose_m,
                self.calibration_runtime_status())
            return {
                'robot_xyz': xyz, 'robot_xy': xyz[:2], 'pick_z': xyz[2],
                'safe_z': max(60.0, xyz[2] + 30.0),
                'calibration_valid': True, 'position_available': True,
                'position_estimate': False,
                'position_source': 'markerless_verified_bundle',
                'validation': {'result': 'PASS', 'source': '/calibration/status'},
                'tcp_pose': tcp_pose_mm,
            }

        return transform

    def vision_safety(self):
        return self._safety_report({})

    def vision_validate_pick(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('validate_pick payload must be an object')
        return self._safety_report(payload)

    def vision_preview_pick(self, payload):
        if build_motion_sequence is None:
            raise ConnectionError('dobot_vision_yolo motion preview tools are not available')
        if not isinstance(payload, dict):
            raise ValueError('preview_pick payload must be an object')
        if not bool(payload.get('dry_run', True)):
            raise ValueError('Vision motion preview is dry_run only in this phase')

        selected_target = self._select_target_preview_source(payload)
        with self._vision_lock:
            self._vision_selected_target = selected_target

        if not selected_target.get('selected'):
            return {
                'accepted': False,
                'dry_run': True,
                'preview_only': True,
                'reason': selected_target.get('reason', 'No target selected'),
                'selected_target': selected_target,
                'motion_sequence': [],
            }

        safety = self._safety_report({
            'selected_target': selected_target,
            'dry_run': True,
        })
        if not safety.get('allowed'):
            return {
                'accepted': False,
                'dry_run': True,
                'preview_only': True,
                'reason': safety.get('reason', 'Safety validation failed'),
                'selected_target': selected_target,
                'safety': safety,
                'motion_sequence': [],
            }

        sequence = build_motion_sequence(selected_target, self._safety())
        return {
            'accepted': True,
            'dry_run': True,
            'preview_only': True,
            'message': 'Dry-run motion preview generated. No robot command was sent.',
            'selected_target': selected_target,
            'safety': safety,
            'motion_sequence': sequence,
        }

    def vision_pick_selected(self, payload, *, clear_cancel_event=True):
        if HTTPMotionExecutor is None:
            raise ConnectionError('dobot_vision_yolo real motion tools are not available')
        if not isinstance(payload, dict):
            raise ValueError('pick_selected payload must be an object')

        if not self._vision_operation_lock.acquire(blocking=False):
            raise RuntimeError('A vision pick-and-place sequence is already active')

        control_ticket = None
        try:
            if clear_cancel_event:
                control_ticket = self._begin_control_operation('vision')
        except Exception:
            self._vision_operation_lock.release()
            raise
        with self._vision_operation_state_lock:
            self._vision_operation_active = True
            self._vision_operation_started_at = time.monotonic()

        try:
            if control_ticket is not None and not self._mark_control_running(control_ticket):
                return {
                    'accepted': False,
                    'executed': False,
                    'aborted_safely': True,
                    'reason': 'STOP acknowledged before motion started',
                }
            return self._vision_pick_selected_locked(payload)
        finally:
            with self._vision_operation_state_lock:
                self._vision_operation_active = False
                self._vision_operation_started_at = None
            self._vision_operation_lock.release()
            if control_ticket is not None:
                self._finish_control_operation(control_ticket)

    def _vision_pick_selected_locked(self, payload):

        guard = self._safety()
        dry_run = self._payload_bool(payload.get('dry_run', True))
        confirm_real_motion = self._payload_bool(
            payload.get('confirm_real_motion', False)
        )

        if not guard.config.allow_real_motion:
            return {
                'accepted': False,
                'executed': False,
                'dry_run': dry_run,
                'reason': 'allow_real_motion=false; real robot motion is disabled',
            }
        if dry_run:
            return {
                'accepted': False,
                'executed': False,
                'dry_run': True,
                'reason': 'dry_run=true; real robot motion is disabled',
            }
        if not confirm_real_motion:
            return {
                'accepted': False,
                'executed': False,
                'dry_run': False,
                'reason': 'confirm_real_motion=true is required',
            }
        if self.require_integrated_startup:
            readiness = self._readiness_snapshot(ignore_motion_activity=True)
            with self._integration_lock:
                startup = self._startup_machine.advance(readiness)
            readiness['startup'] = startup.as_dict()
            if not readiness.get('ready') or startup.state is not StartupState.READY:
                return {
                    'accepted': False,
                    'executed': False,
                    'dry_run': False,
                    'reason': 'system startup/readiness is not complete',
                    'system': readiness,
                }

        selection_payload = dict(payload)
        selection_payload['dry_run'] = True
        selected_target = self._select_target_preview_source(selection_payload)
        if not selected_target.get('selected'):
            return {
                'accepted': False,
                'executed': False,
                'dry_run': False,
                'reason': selected_target.get('reason', 'No target selected'),
                'selected_target': selected_target,
            }

        selected_target = dict(selected_target)
        selected_target['dry_run'] = False
        with self._vision_lock:
            self._vision_selected_target = selected_target

        safety = self._safety_report({
            'selected_target': selected_target,
            'dry_run': False,
        })
        if not safety.get('allowed'):
            return {
                'accepted': False,
                'executed': False,
                'dry_run': False,
                'reason': safety.get('reason', 'Safety validation failed'),
                'selected_target': selected_target,
                'safety': safety,
            }

        if (
            AutomaticSuctionPickController is None
            or AutomaticPickConfig is None
            or AutomaticSuctionPlacementController is None
            or AutomaticPlacementConfig is None
        ):
            raise ConnectionError('automatic suction-pick controller is not available')

        tool_type = str(payload.get('tool_type', 'suction')).lower()
        if tool_type != 'suction':
            raise ValueError('automatic visual-servo picking requires tool_type=suction')

        # A caller may lower the coarse rates, but cannot raise them above the
        # automatic-pick limits.  Descent/fine rates are intentionally fixed
        # in the controller rather than being exposed as an API speed knob.
        requested_velocity = float(payload.get('velocity_ratio', 0.25))
        requested_acceleration = float(payload.get('acceleration_ratio', 0.20))
        automatic_config = AutomaticPickConfig(
            # Preserve the original API value so the controller can reject a
            # fractional or otherwise malformed retry budget rather than
            # silently truncating it.
            max_attempts=payload.get('max_attempts', 2),
            coarse_velocity_ratio=min(requested_velocity, 0.25),
            coarse_acceleration_ratio=min(requested_acceleration, 0.20),
        )
        selection_request = dict(payload)
        selection_request['dry_run'] = True

        controller = AutomaticSuctionPickController(
            config=automatic_config,
            redetect_target=self._automatic_pick_redetect_target,
            move=self._automatic_pick_move,
            set_suction=self._automatic_pick_set_suction,
            verify_pick=lambda target: self._automatic_pick_verify(
                target,
                selection_request,
            ),
            current_pose=self._current_tcp_pose,
            validate_pose=guard.validate_target_pose,
            cancel_requested=self._vision_cancel_event.is_set,
        )
        with self._integration_lock:
            # Once a sequence departs from observation, no following motion
            # may be admitted from a stale "at observation" flag.
            self._observation_confirmed = False
        result = controller.execute(selection_request, initial_target=selected_target)
        if result.get('executed'):
            placement = AutomaticSuctionPlacementController(
                config=AutomaticPlacementConfig(),
                resolve_zone=self._automatic_placement_zone,
                inspect_zone=self._automatic_placement_inspect_zone,
                move=self._automatic_pick_move,
                set_suction=self._automatic_pick_set_suction,
                verify_release=self._automatic_placement_verify_release,
                current_pose=self._current_tcp_pose,
                validate_pose=guard.validate_target_pose,
                cancel_requested=self._vision_cancel_event.is_set,
            ).execute({
                'place_id': selected_target['place_id'],
                'object_class': selected_target['class_name'],
                'selection_request': selection_request,
            })
            result['pick_executed'] = True
            result['placement'] = placement
            result['placed'] = bool(placement.get('placed'))
            result['executed'] = bool(placement.get('executed'))
            result['aborted_safely'] = bool(placement.get('aborted_safely', False))
            if result['placed']:
                try:
                    result['observation'] = self._move_to_observation_pose()
                    result['observation_returned'] = True
                except Exception as exc:
                    # The part may already be released, so never attempt to
                    # pick it again.  Latch a fault and require an operator
                    # recovery rather than claiming the cell is ready.
                    result['observation_returned'] = False
                    result['executed'] = False
                    result['aborted_safely'] = False
                    result['reason'] = f'placement completed but observation return failed: {exc}'
                    self._latch_system_fault(
                        'OBSERVATION_RETURN_FAILED: ' + str(exc),
                        stop_motion=True,
                    )
        else:
            result['placed'] = False
        result.update(
            dry_run=False,
            transport='http_api',
            message=(
                'Automatic RGB-D assisted pick and placement completed.'
                if result.get('executed') else
                (
                    'Automatic pick-and-place aborted safely.'
                    if result.get('aborted_safely', True) else
                    'Automatic pick-and-place recovery failed; operator intervention required.'
                )
            ),
            selected_target=selected_target,
            safety=safety,
            tool_type='suction',
        )
        return result

    def _automatic_placement_zone(self, place_id):
        """Resolve a configured nominal zone without accepting arbitrary poses."""
        return self._places().get_placement_zone(str(place_id))

    def _automatic_placement_inspect_zone(self, zone, request):
        """Return one new RGB-D zone observation or an explicit fail-closed result."""
        before = None
        with self._vision_lock:
            before = self._vision_detections_time
        self.vision_detect_once({
            'dry_run': True,
            'object_class': str(request.get('object_class', 'all')),
            'place_id': str(zone.get('place_id', zone.get('zone_id', ''))),
        })
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if self._vision_cancel_event.is_set():
                raise RuntimeError('automatic placement canceled while waiting for inspection')
            with self._vision_lock:
                received_at = self._vision_detections_time
            if received_at is not None and (before is None or received_at > before):
                detections = self.vision_detections()
                if not detections.get('ok'):
                    raise ValueError(
                        detections.get('error') or 'fresh placement inspection unavailable'
                    )
                return self._automatic_placement_observation(
                    detections.get('raw', {}), zone,
                )
            self._vision_cancel_event.wait(0.05)
        raise TimeoutError('timed out waiting for a fresh RGB-D placement inspection')

    @staticmethod
    def _automatic_placement_observation(payload, zone):
        """Extract the zone-specific RGB-D contract from a detector payload.

        The RGB-D producer publishes ``placement_inspections`` (or the legacy
        ``zone_inspections``) keyed by canonical zone id.  A missing record is
        deliberately an invalid occupancy result, never an empty zone.
        """
        if not isinstance(payload, dict):
            payload = {}
        zone_id = str(zone.get('zone_id', '') or '')
        place_id = str(zone.get('place_id', '') or '')
        records = payload.get('placement_inspections', payload.get('zone_inspections'))
        observation = None
        if isinstance(records, dict):
            observation = records.get(zone_id, records.get(place_id))
        elif isinstance(records, list):
            for candidate in records:
                if not isinstance(candidate, dict):
                    continue
                candidate_zone = str(
                    candidate.get('zone_id', candidate.get('place_id', '')) or ''
                )
                if candidate_zone in (zone_id, place_id):
                    observation = candidate
                    break
        if observation is None:
            direct = payload.get('placement_inspection')
            if isinstance(direct, dict):
                direct_zone = str(
                    direct.get('zone_id', direct.get('place_id', zone_id)) or ''
                )
                if direct_zone in (zone_id, place_id):
                    observation = direct
        if not isinstance(observation, dict):
            return {
                'fresh': True,
                'occupancy_valid': False,
                'reason': f'fresh RGB-D inspection missing for zone {zone_id or place_id}',
            }
        result = dict(observation)
        result['fresh'] = True
        result.setdefault('zone_id', zone_id)
        return result

    def _automatic_placement_verify_release(self, zone):
        """Require a new RGB-D observation that explicitly identifies the part."""
        observation = self._automatic_placement_inspect_zone(
            zone,
            {
                'place_id': zone.get('place_id', zone.get('zone_id', '')),
                'object_class': 'all',
                'verify_release': True,
            },
        )
        if observation.get('occupancy_valid') is not True:
            return {
                'released': False,
                'reason': observation.get('reason', 'post-release occupancy is unavailable'),
            }
        if observation.get('release_verified') is True:
            return {
                'released': True,
                'method': 'rgbd_release_verified',
                'observation': observation,
            }
        if observation.get('occupied') is True and observation.get('placed_object_detected') is True:
            return {
                'released': True,
                'method': 'rgbd_placed_object_detected',
                'observation': observation,
            }
        return {
            'released': False,
            'reason': observation.get('reason', 'RGB-D did not verify object release'),
            'observation': observation,
        }

    def _automatic_pick_redetect_target(self, request):
        """Request and wait for one new detector result before re-selection."""
        request = dict(request)
        reference = request.pop('_automatic_reference_target', None)
        self._request_fresh_detection(
            request.get('object_class', 'all'), request.get('place_id', ''),
        )
        selected = (
            self._automatic_pick_select_reacquired_target(request, reference)
            if isinstance(reference, dict)
            else self._select_target_preview_source(request)
        )
        if selected.get('selected'):
            with self._vision_lock:
                self._vision_selected_target = selected
        return selected

    def _automatic_pick_select_reacquired_target(self, request, reference):
        """Bind a fresh observation to the coarse target, not a transient ID.

        YOLO and the RGB-D detector both assign frame-local IDs.  Reusing a
        ``manual_id`` at this point could report a target as absent simply
        because its index changed, which would be an unsafe false pick
        verification.  Transform each current same-class candidate to base
        coordinates and choose only the closest one to the coarse target.
        """
        class_name = str(reference.get('class_name', '') or '')
        reference_pose = reference.get('pick_pose', [])
        if not class_name or not isinstance(reference_pose, (list, tuple)):
            return {
                'selected': False,
                'reason': 'coarse target has no class/base pose for re-detection',
            }

        detections = self.vision_detections()
        if not detections.get('ok'):
            raise ValueError(detections.get('error') or 'fresh detections unavailable')
        candidates = []
        min_confidence = self._safety().config.min_confidence
        for detection in detections.get('detections', []):
            if str(detection.get('class_name', '') or '') != class_name:
                continue
            detection_id = detection.get('id', detection.get('detection_id'))
            if detection_id is None:
                continue
            candidate_request = dict(request)
            candidate_request.update(
                object_class=class_name,
                selection_mode='manual_id',
                manual_id=detection_id,
                dry_run=True,
            )
            candidate = self._select_target_preview_source(candidate_request)
            if (
                candidate.get('selected')
                and float(candidate.get('confidence', 0.0)) >= min_confidence
            ):
                candidates.append(candidate)

        if not candidates:
            return {
                'selected': False,
                'reason': f"no fresh '{class_name}' target was found",
            }

        def distance(candidate):
            pose = candidate.get('pick_pose', [])
            try:
                return math.hypot(
                    float(pose[0]) - float(reference_pose[0]),
                    float(pose[1]) - float(reference_pose[1]),
                )
            except (IndexError, TypeError, ValueError):
                return float('inf')

        selected = min(candidates, key=distance)
        if not math.isfinite(distance(selected)):
            return {
                'selected': False,
                'reason': 'fresh target has no valid base-frame pose',
            }
        return selected

    def _automatic_pick_move(self, pose, velocity_ratio, acceleration_ratio, label):
        """Run one guarded Cartesian move through the existing local API."""
        executor = HTTPMotionExecutor(
            self._local_api_base_url(),
            velocity_ratio=float(velocity_ratio),
            acceleration_ratio=float(acceleration_ratio),
            tool_type='suction',
            cancel_event=self._vision_cancel_event,
            api_token=self.api_token,
        )
        result = executor.execute([
            {
                'step': label,
                # HTTPMotionExecutor reserves move_* commands for a blocking
                # Cartesian move; the audit label is retained separately.
                'command': 'move_automatic_pick',
                'pose': [float(value) for value in pose],
            }
        ])
        return dict(result[-1].get('response') or {})

    def _automatic_pick_set_suction(self, enable):
        # A cancellation must stop new robot motion, but it must never prevent
        # the safety cleanup that turns suction off.  Use an uncancelled local
        # event only for the off command; the caller already requested action
        # cancellation through ``vision_cancel``.
        cancel_event = self._vision_cancel_event if enable else threading.Event()
        executor = HTTPMotionExecutor(
            self._local_api_base_url(),
            velocity_ratio=0.10,
            acceleration_ratio=0.10,
            tool_type='suction',
            cancel_event=cancel_event,
            api_token=self.api_token,
        )
        command = 'suction_on' if enable else 'suction_off'
        result = executor.execute([
            {
                'step': command,
                'command': command,
                'pose': None,
            }
        ])
        return dict(result[-1].get('response') or {})

    def _automatic_pick_verify(self, target, selection_request):
        """Verify with a new observation; no missing/failed frame is a pick."""
        request = dict(selection_request)
        request['_automatic_reference_target'] = dict(target)
        observed = self._automatic_pick_redetect_target(request)
        if not observed.get('selected'):
            # The detector was fresh and healthy but the requested target is
            # absent at the pick location after lift.
            return {
                'picked': True,
                'method': 'fresh_post_lift_detection',
                'reason': 'requested target is absent after lift',
            }
        if observed.get('class_name') != target.get('class_name'):
            return {
                'picked': False,
                'method': 'fresh_post_lift_detection',
                'reason': 'different class was selected after lift',
            }
        try:
            initial_depth = float(target.get('depth_mm'))
            observed_depth = float(observed.get('depth_mm'))
            depth_delta = abs(observed_depth - initial_depth)
        except (TypeError, ValueError):
            depth_delta = None
        if (
            depth_delta is not None
            and target.get('depth_valid') is True
            and observed.get('depth_valid') is True
            and depth_delta >= 15.0
        ):
            return {
                'picked': True,
                'method': 'fresh_post_lift_depth',
                'reason': f'target depth changed after lift ({depth_delta:.3f} mm)',
            }
        try:
            previous = target.get('pick_pose', [])
            current = observed.get('pick_pose', [])
            distance = math.hypot(
                float(previous[0]) - float(current[0]),
                float(previous[1]) - float(current[1]),
            )
        except (IndexError, TypeError, ValueError):
            return {
                'picked': False,
                'method': 'fresh_post_lift_detection',
                'reason': 'post-lift target pose is invalid',
            }
        if distance <= 12.0:
            return {
                'picked': False,
                'method': 'fresh_post_lift_detection',
                'reason': f'target remains at pick location ({distance:.3f} mm)',
                'remaining_target': observed,
            }
        return {
            'picked': True,
            'method': 'fresh_post_lift_detection',
            'reason': f'target moved from pick location ({distance:.3f} mm)',
        }

    def vision_cancel(self):
        control_active = self._request_control_stop()
        motion_result = self.cancel_move()
        if hasattr(self, 'calibration_cancel_client'):
            self._request_calibration_cancel()
        self._acknowledge_control_stop()
        with self._vision_operation_state_lock:
            sequence_active = self._vision_operation_active
        return {
            'requested': bool(control_active or sequence_active or motion_result.get('requested')),
            'vision_sequence_cancel_requested': bool(sequence_active),
            'motion_cancel': motion_result,
            'message': (
                'Vision sequence cancellation requested.'
                if sequence_active
                else motion_result.get('message', 'No active vision sequence')
            ),
        }

    def stop_all(self):
        """Shared STOP endpoint: cancel jobs, current PTP motion, and startup."""
        with self._integration_lock:
            self._startup_machine.stop('stop requested')
        motion_result = self._request_safe_stop('operator STOP')
        return {
            'requested': bool(motion_result.get('requested') or self._operation_is_active()),
            'message': 'Stop requested for every active state.',
            'motion_cancel': motion_result,
        }

    def _local_api_base_url(self):
        host = self.host
        if host in ('0.0.0.0', '::', ''):
            host = '127.0.0.1'
        return f'http://{host}:{self.port}'

    @staticmethod
    def _payload_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(value)

    def _safety_report(self, payload):
        guard = self._safety()
        selected_target = payload.get('selected_target')
        if selected_target is None:
            with self._vision_lock:
                selected_target = self._vision_selected_target

        status = self.status()
        dry_run = payload.get('dry_run')
        if dry_run is None:
            if isinstance(selected_target, dict) and 'dry_run' in selected_target:
                dry_run = bool(selected_target.get('dry_run', True))
            else:
                dry_run = guard.config.dry_run_default

        place_status = self._places().status()
        vision_mode = str(payload.get('vision_mode', self.vision_mode) or 'fixed_camera')
        if isinstance(selected_target, dict):
            vision_mode = str(selected_target.get('vision_mode', vision_mode))
        tcp_pose = self._current_tcp_pose() if vision_mode == 'eye_in_hand' else None
        calibration_status = self.calibration_runtime_status()
        return guard.validate_pick(
            selected_target=selected_target,
            camera_status=status.get('camera', {}),
            yolo_status=self.vision_status(),
            calibration_status=calibration_status,
            places=place_status.get('places', {}),
            dry_run=dry_run,
            robot_homed=status.get('motion', {}).get('homing_confirmed', False),
            vision_mode=vision_mode,
            tcp_pose=tcp_pose,
        )

    def get_vision_annotated(self):
        if self.vision_annotated_path.exists():
            return self.vision_annotated_path.read_bytes()
        return self._make_vision_placeholder()

    def vision_calibration(self):
        """Compatibility view backed exclusively by /calibration/status."""
        return self.calibration_runtime_status()

    def supervised_calibration_control(self, action):
        if action not in self.calibration_auto_clients:
            raise ValueError('Unknown supervised calibration action')
        client = self.calibration_auto_clients[action]
        if not client.service_is_ready():
            raise ConnectionError(f'/calibration/auto/{action} is unavailable')
        future = client.call_async(Trigger.Request())
        return {'accepted': True, 'action': action,
                'request_pending': not future.done(), 'dry_run': True,
                'motion_command_sent': False}

    def vision_auto_calibrate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('auto calibration payload must be an object')
        if self._operation_is_active():
            raise RuntimeError('Stop active robot/vision operations before calibration')
        if not self.calibration_recalibrate_client.service_is_ready():
            raise ConnectionError('/calibration/recalibrate markerless service is unavailable')
        future = self.calibration_recalibrate_client.call_async(Trigger.Request())
        return {
            'accepted': True,
            'architecture': 'markerless_hand_eye',
            'service': self.calibration_recalibrate_service,
            'status_topic': self.calibration_status_topic,
            'message': 'Markerless calibration requested; observe /calibration/status',
            'request_pending': not future.done(),
        }
    def vision_calibration_test_point(self, payload):
        return self.vision_eye_in_hand_test_pixel(payload)

    def vision_eye_in_hand_status(self):
        status = self.calibration_runtime_status()
        status['vision_mode'] = 'eye_in_hand'
        status['architecture'] = 'markerless_hand_eye'
        status['tcp_pose_available'] = self._current_tcp_pose() is not None
        return status

    def vision_eye_in_hand_calibrate(self, payload):
        return self.vision_auto_calibrate(dict(payload or {}, vision_mode='eye_in_hand'))

    def get_eye_in_hand_annotated(self):
        # The normal detector view is useful during markerless calibration;
        # there is intentionally no fiducial overlay.
        return self.get_vision_annotated()

    def vision_eye_in_hand_test_pixel(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('markerless test payload must be an object')
        if self._markerless_bundle is None:
            raise ConnectionError('dobot_calibration bundle consumer is unavailable')
        camera_xyz = payload.get('camera_xyz_mm')
        if camera_xyz is None:
            raise ValueError('camera_xyz_mm from registered depth is required')
        tcp_pose_mm = self._current_tcp_pose()
        if tcp_pose_mm is None:
            raise ValueError('TCP pose is unavailable; transform rejected')
        tcp_pose_m = [value / 1000.0 for value in tcp_pose_mm[:3]] + [tcp_pose_mm[3]]
        xyz = self._markerless_bundle.camera_point_to_base(
            camera_xyz, tcp_pose_m, self.calibration_runtime_status())
        return {
            'robot_xyz': xyz,
            'robot_xy': xyz[:2],
            'pick_z': xyz[2],
            'safe_z': max(60.0, xyz[2] + 30.0),
            'calibration_valid': True,
            'position_available': True,
            'position_estimate': False,
            'position_source': 'markerless_verified_bundle',
            'validation': {'result': 'PASS', 'source': '/calibration/status'},
            'dry_run': True,
        }

    def _places(self):
        if self._place_store is None:
            raise ConnectionError(
                'dobot_vision_yolo target selector tools are not available'
            )
        return self._place_store

    def _safety(self):
        if self._safety_guard is None:
            raise ConnectionError(
                'dobot_vision_yolo safety guard tools are not available'
            )
        return self._safety_guard

    def _current_tcp_pose(self):
        with self._goal_lock:
            if self._latest_tcp_pose is not None:
                return list(self._latest_tcp_pose)

        status = self.status()
        if extract_tcp_pose_from_status is None:
            return None
        tcp_pose = extract_tcp_pose_from_status(status)
        if tcp_pose is not None:
            with self._goal_lock:
                self._latest_tcp_pose = tcp_pose
                self._latest_tcp_pose_time = time.monotonic()
                self._latest_tcp_pose_source = 'api_status'
        return tcp_pose

    def _latest_cv_frame(self):
        with self._frame_condition:
            jpeg_bytes = self._latest_jpeg
        if not jpeg_bytes:
            return None
        buffer = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        return cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    def _capture_fresh_frames(self, sample_count, timeout_sec):
        requested = max(8, min(int(sample_count), 30))
        timeout = max(1.0, min(float(timeout_sec), 15.0))
        deadline = time.monotonic() + timeout
        frames = []
        capture_records = []
        with self._frame_condition:
            last_sequence = self._frame_sequence
        selected_source = None
        while len(frames) < requested and time.monotonic() < deadline:
            with self._frame_condition:
                while (
                    (self._latest_jpeg is None or self._frame_sequence == last_sequence)
                    and time.monotonic() < deadline
                ):
                    self._frame_condition.wait(
                        timeout=min(0.25, max(0.0, deadline - time.monotonic()))
                    )
                if self._latest_jpeg is None or self._frame_sequence == last_sequence:
                    break
                jpeg_bytes = bytes(self._latest_jpeg)
                frame_source = self._latest_frame_source
                frame_received_at = self._latest_frame_time
                frame_stamp_sec = self._latest_frame_stamp_sec
                frame_id = self._latest_frame_id
                last_sequence = self._frame_sequence
            if frame_received_at is None or not 0 <= time.monotonic() - frame_received_at <= 1.0:
                continue
            if selected_source is None:
                selected_source = frame_source
            if frame_source != selected_source:
                continue
            frame = cv2.imdecode(
                np.frombuffer(jpeg_bytes, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if frame is not None:
                frames.append(frame)
                with self._goal_lock:
                    tcp_pose = (
                        list(self._latest_tcp_pose)
                        if self._latest_tcp_pose is not None
                        else None
                    )
                    tcp_received_at = self._latest_tcp_pose_time
                    tcp_source = self._latest_tcp_pose_source
                    motion_active = self._active_goal_handle is not None
                receive_delta_ms = None
                tcp_age_ms = None
                if frame_received_at is not None and tcp_received_at is not None:
                    receive_delta_ms = abs(frame_received_at - tcp_received_at) * 1000.0
                    tcp_age_ms = max(0.0, frame_received_at - tcp_received_at) * 1000.0
                capture_records.append(
                    {
                        'frame_index': len(frames) - 1,
                        'sequence': int(last_sequence),
                        'source': frame_source,
                        'frame_id': frame_id,
                        'ros_stamp_sec': (
                            round(frame_stamp_sec, 9)
                            if frame_stamp_sec is not None
                            else None
                        ),
                        'tcp_pose_mm_deg': tcp_pose,
                        'tcp_pose_source': tcp_source,
                        'motion_active': motion_active,
                        'frame_to_tcp_receive_delta_ms': (
                            round(receive_delta_ms, 3)
                            if receive_delta_ms is not None
                            else None
                        ),
                        'tcp_pose_age_at_frame_ms': (
                            round(tcp_age_ms, 3) if tcp_age_ms is not None else None
                        ),
                    }
                )
            if time.monotonic() >= deadline:
                break
        if len(frames) < 8:
            raise TimeoutError(
                f'Only {len(frames)} fresh camera frames arrived; need at least 8'
            )
        self._last_calibration_frame_source = selected_source
        deltas = [
            record['frame_to_tcp_receive_delta_ms']
            for record in capture_records
            if record['frame_to_tcp_receive_delta_ms'] is not None
        ]
        self._last_calibration_capture_metadata = {
            'method': (
                'ROS image header stamp; TCP receive time only '
                '(dobot_pose_raw has no Header)'
            ),
            'exact_rgb_tcp_sync_available': False,
            'frame_source': selected_source,
            'frame_count': len(frames),
            'max_frame_to_tcp_receive_delta_ms': max(deltas) if deltas else None,
            'frames': capture_records,
        }
        return frames

    @staticmethod
    def _extract_image_point(payload):
        if 'pixel' in payload:
            return payload['pixel']
        if 'image_point' in payload:
            return payload['image_point']
        if 'u' in payload and 'v' in payload:
            return [payload['u'], payload['v']]
        raise ValueError('pixel, image_point, or u/v is required')

    @staticmethod
    def _extract_robot_point(payload):
        if 'robot_point' in payload:
            return payload['robot_point']
        if 'x' in payload and 'y' in payload:
            return [payload['x'], payload['y']]
        if 'robot_x' in payload and 'robot_y' in payload:
            return [payload['robot_x'], payload['robot_y']]
        raise ValueError('robot_point or robot_x/robot_y is required')

    def _make_vision_placeholder(self):
        image = np.full((480, 640, 3), (28, 31, 36), dtype=np.uint8)
        cv2.putText(
            image,
            'Vision detector offline',
            (130, 220),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 214, 120),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            'Start yolo_detector_node in dry-run mode',
            (80, 265),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (222, 226, 230),
            1,
            cv2.LINE_AA,
        )
        ok, data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return b''
        return data.tobytes()

    def send_move(self, payload):
        target_pose = payload.get('target_pose')
        if not isinstance(target_pose, list) or len(target_pose) != 4:
            raise ValueError('target_pose must contain four numbers')

        goal = PointToPoint.Goal()
        goal.motion_type = int(payload.get('motion_type', 1))
        goal.target_pose = [float(value) for value in target_pose]
        goal.velocity_ratio = float(payload.get('velocity_ratio', 0.5))
        goal.acceleration_ratio = float(payload.get('acceleration_ratio', 0.3))

        if goal.motion_type not in [1, 2, 4, 5]:
            raise ValueError('motion_type must be one of 1, 2, 4, 5')
        if not 0.0 < goal.velocity_ratio <= 1.0:
            raise ValueError('velocity_ratio must be within (0.0, 1.0]')
        if not 0.0 < goal.acceleration_ratio <= 1.0:
            raise ValueError('acceleration_ratio must be within (0.0, 1.0]')

        # Manual and automatic moves share this endpoint.  The observation
        # invariant is restored only by _move_to_observation_pose after the
        # blocking action completes; any other target immediately revokes it.
        if any(
            abs(float(value) - expected) > 1e-3
            for value, expected in zip(goal.target_pose, self.observation_pose_mm)
        ):
            with self._integration_lock:
                self._observation_confirmed = False

        with self._goal_lock:
            if self._active_goal_handle is not None:
                raise RuntimeError('A motion goal is already active')

        if not self.ptp_action.wait_for_server(timeout_sec=0.25):
            raise ConnectionError('PTP_action server is not available')

        future = self.ptp_action.send_goal_async(
            goal,
            feedback_callback=self._feedback_callback,
        )
        goal_handle = self._wait_for_future(future, 5.0)
        if not goal_handle.accepted:
            return {'accepted': False, 'message': 'Goal rejected'}

        with self._goal_lock:
            self._active_goal_handle = goal_handle
            self._last_goal_time = time.monotonic()
            self._last_result = None

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_callback)

        return {
            'accepted': True,
            'message': 'Goal accepted',
            'target_pose': list(goal.target_pose),
            'motion_type': goal.motion_type,
        }

    def cancel_move(self):
        with self._goal_lock:
            goal_handle = self._active_goal_handle

        if goal_handle is None:
            return {'requested': False, 'message': 'No active goal'}

        future = goal_handle.cancel_goal_async()
        response = self._wait_for_future(future, 5.0)
        return {
            'requested': True,
            'goals_canceling': len(response.goals_canceling),
        }

    def call_homing(self, *, move_to_observation=True):
        if self._operation_is_active():
            raise RuntimeError('Cannot HOME while an automatic operation is active; press STOP first')
        if not self.homing_client.wait_for_service(timeout_sec=0.25):
            raise ConnectionError('dobot_homing_service is not available')
        response = self._wait_for_future(
            self.homing_client.call_async(ExecuteHomingProcedure.Request()),
            20.0,
        )
        with self._goal_lock:
            self._homing_confirmed = bool(response.success)
        result = {
            'success': bool(response.success),
            'message': response.instruction,
        }
        if not response.success:
            return result

        with self._integration_lock:
            self._observation_confirmed = False
            self._observation_time = None
            # A deliberate HOME after resolving a fault starts a new safe
            # startup pass.  It cannot make a failed calibration look valid;
            # the calibration component still has to publish fresh PASS.
            self._startup_machine.reset()
            self._system_fault = ''
        self._vision_cancel_event.clear()
        self._operator_cancel_event.clear()
        if move_to_observation:
            self._dispatch_startup_worker(
                self._move_to_observation_pose,
                'observation',
            )
            result['observation_pending'] = True
        return result

    def _web_tool_ready(self, web_tool):
        if web_tool not in ('gripper', 'suction'):
            return False
        client = self.gripper_client if web_tool == 'gripper' else self.suction_client
        return client.service_is_ready()

    def call_gripper(self, payload):
        if not self.gripper_client.wait_for_service(timeout_sec=0.25):
            raise ConnectionError('dobot_gripper_service is not available')
        state = str(payload.get('state', '')).lower()
        if state not in ['open', 'close']:
            raise ValueError('state must be open or close')

        request = GripperControl.Request()
        request.gripper_state = state
        request.keep_compressor_running = bool(
            payload.get('keep_compressor_running', False)
        )
        response = self._wait_for_future(self.gripper_client.call_async(request), 8.0)
        return {
            'success': bool(response.success),
            'message': response.message,
        }

    def call_web_gripper(self, payload):
        self.get_logger().info("[END_EFFECTOR] command=GRIPPER service=dobot_gripper_service")
        mapped_payload, backend = map_web_gripper_payload(payload, self.tool_mapping)
        result = self.call_gripper(mapped_payload)
        result.update(command="gripper_" + str(mapped_payload.get("state")), service="dobot_gripper_service")
        return result

    def call_suction(self, payload):
        if not self.suction_client.wait_for_service(timeout_sec=0.25):
            raise ConnectionError('dobot_suction_cup_service is not available')
        request = SuctionCupControl.Request()
        request.enable_suction = bool(payload.get('enable_suction', False))
        response = self._wait_for_future(self.suction_client.call_async(request), 8.0)
        return {
            "service": "dobot_suction_cup_service",
            'success': bool(response.success),
            'message': response.message,
        }

    def call_web_suction(self, payload):
        self.get_logger().info("[END_EFFECTOR] command=SUCTION service=dobot_suction_cup_service")
        mapped_payload, backend = map_web_suction_payload(payload, self.tool_mapping)
        result = self.call_suction(mapped_payload)
        result.update(command="suction_on" if mapped_payload.get("enable_suction") else "suction_off", service="dobot_suction_cup_service")
        return result

    def _feedback_callback(self, feedback_msg):
        feedback = [round(value, 3) for value in feedback_msg.feedback.current_pose]
        with self._goal_lock:
            self._last_feedback = feedback

    def _result_callback(self, future):
        try:
            result_msg = future.result()
            achieved_pose = [
                round(value, 3) for value in result_msg.result.achieved_pose
            ]
            result = {
                'status': int(result_msg.status),
                'achieved_pose': achieved_pose,
            }
        except Exception as exc:
            result = {
                'status': -1,
                'error': str(exc),
            }

        with self._goal_lock:
            self._last_result = result
            self._active_goal_handle = None

    def _wait_for_future(self, future, timeout_sec):
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        if not done.wait(timeout=timeout_sec):
            raise TimeoutError('ROS call timed out')
        return future.result()

    def restart_connection(self):
        command = ['systemctl', '--user', 'restart', 'dobot-magician.service']

        def restart_later():
            time.sleep(0.4)
            try:
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
            except Exception as exc:
                self.get_logger().error(f'Failed to restart Dobot service: {exc}')

        threading.Thread(
            target=restart_later,
            name='dobot_service_restart',
            daemon=True,
        ).start()
        return {
            'accepted': True,
            'message': 'Dobot connection restart requested. Reconnect in a few seconds.',
            'command': ' '.join(command),
        }

    def shutdown(self):
        self._capture_stop.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)


def create_app(node):
    app = FastAPI(title='Dobot Web Interface')
    static_dir = Path(__file__).with_name('static')

    if node.api_token:
        @app.middleware('http')
        async def require_authentication(request, call_next):
            if not _basic_auth_valid(request, node.api_token):
                return Response(
                    content='Authentication required',
                    status_code=401,
                    headers={'WWW-Authenticate': 'Basic realm="Dobot Magician"'},
                )
            return await call_next(request)

    app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')

    @app.get('/', response_class=HTMLResponse)
    def index():
        return (static_dir / 'operator.html').read_text(encoding='utf-8')

    @app.get('/api/operator/status')
    def api_operator_status(job: str = 'black', place_id: str = 'Zone A'):
        return _call_api(node.operator_status, {'job': job, 'place_id': place_id})

    @app.post('/api/operator/start')
    async def api_operator_start(request: Request):
        payload = await request.json()
        return await run_in_threadpool(
            lambda: _call_api(node.operator_start, payload, busy_status=409)
        )

    @app.post('/api/operator/stop')
    def api_operator_stop():
        return _call_api(node.operator_stop)

    @app.post('/api/calibration/auto/{action}')
    def api_calibration_auto(action: str):
        return _call_api(node.supervised_calibration_control, action, busy_status=409)

    @app.get('/api/system/status')
    def api_system_status():
        return _call_api(node.system_readiness)

    @app.post('/api/system/startup')
    def api_system_startup():
        return _call_api(node.system_startup, busy_status=409)

    @app.get('/api/status')
    def api_status():
        return node.status()

    @app.get('/api/snapshot')
    def snapshot():
        return Response(content=node.get_frame(), media_type='image/jpeg')

    @app.get('/api/vision/status')
    def api_vision_status():
        return node.vision_status()

    @app.get('/api/vision/detections')
    def api_vision_detections():
        return node.vision_detections()

    @app.get('/api/vision/classes')
    def api_vision_classes():
        return _call_api(node.vision_classes)

    @app.get('/api/vision/places')
    def api_vision_places():
        return _call_api(node.vision_places)

    @app.get('/api/vision/safety')
    def api_vision_safety():
        return _call_api(node.vision_safety)

    @app.get('/api/vision/annotated')
    def api_vision_annotated():
        return Response(
            content=node.get_vision_annotated(),
            media_type='image/jpeg',
            headers={'Cache-Control': 'no-store'},
        )

    @app.get('/api/vision/calibration')
    def api_vision_calibration():
        return _call_api(node.vision_calibration)

    @app.get('/api/vision/eye_in_hand/status')
    def api_vision_eye_in_hand_status():
        return _call_api(node.vision_eye_in_hand_status)

    @app.get('/api/vision/eye_in_hand/annotated')
    def api_vision_eye_in_hand_annotated():
        return Response(
            content=node.get_eye_in_hand_annotated(),
            media_type='image/jpeg',
            headers={'Cache-Control': 'no-store'},
        )

    @app.get('/stream')
    def stream():
        def frames():
            delay = 1.0 / max(node.stream_fps, 1.0)
            while True:
                frame = node.get_frame()
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    + f'Content-Length: {len(frame)}\r\n\r\n'.encode('ascii')
                    + frame
                    + b'\r\n'
                )
                time.sleep(delay)

        return StreamingResponse(
            frames(),
            media_type='multipart/x-mixed-replace; boundary=frame',
        )

    @app.post('/api/move')
    async def api_move(request: Request):
        payload = await request.json()
        return await run_in_threadpool(
            lambda: _call_api(node.send_move, payload, busy_status=409)
        )

    @app.post('/api/cancel')
    def api_cancel():
        return _call_api(node.stop_all)

    @app.post('/api/homing')
    def api_homing():
        return _call_api(node.call_homing)

    @app.post('/api/restart_connection')
    def api_restart_connection():
        return _call_api(node.restart_connection)

    @app.post('/api/gripper')
    async def api_gripper(request: Request):
        payload = await request.json()
        return await run_in_threadpool(
            lambda: _call_api(node.call_web_gripper, payload)
        )

    @app.post('/api/suction')
    async def api_suction(request: Request):
        payload = await request.json()
        return await run_in_threadpool(
            lambda: _call_api(node.call_web_suction, payload)
        )

    @app.post('/api/vision/detect_once')
    async def api_vision_detect_once(request: Request):
        return _call_api(node.vision_detect_once, await request.json())

    @app.post('/api/vision/select_target')
    async def api_vision_select_target(request: Request):
        return _call_api(node.vision_select_target, await request.json())

    @app.post('/api/vision/validate_pick')
    async def api_vision_validate_pick(request: Request):
        return _call_api(node.vision_validate_pick, await request.json())

    @app.post('/api/vision/preview_pick')
    async def api_vision_preview_pick(request: Request):
        return _call_api(node.vision_preview_pick, await request.json())

    @app.post('/api/vision/pick_selected')
    async def api_vision_pick_selected(request: Request):
        payload = await request.json()
        return await run_in_threadpool(
            lambda: _call_api(node.vision_pick_selected, payload, busy_status=409)
        )

    @app.post('/api/vision/cancel')
    def api_vision_cancel():
        return _call_api(node.vision_cancel)

    @app.post('/api/vision/calibration/auto')
    async def api_vision_auto_calibrate(request: Request):
        payload = await request.json()
        return await run_in_threadpool(
            lambda: _call_api(
                node.vision_auto_calibrate,
                payload,
                busy_status=409,
            )
        )

    @app.post('/api/vision/calibration/test_point')
    async def api_vision_calibration_test_point(request: Request):
        return _call_api(node.vision_calibration_test_point, await request.json())

    @app.post('/api/vision/eye_in_hand/calibrate')
    async def api_vision_eye_in_hand_calibrate(request: Request):
        return _call_api(node.vision_eye_in_hand_calibrate, await request.json())

    @app.post('/api/vision/eye_in_hand/test_pixel')
    async def api_vision_eye_in_hand_test_pixel(request: Request):
        return _call_api(node.vision_eye_in_hand_test_pixel, await request.json())

    return app


def _basic_auth_valid(request, expected_token):
    authorization = request.headers.get('authorization', '')
    if not authorization.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(
            authorization[6:],
            validate=True,
        ).decode('utf-8')
        username, token = decoded.split(':', 1)
    except (ValueError, UnicodeDecodeError):
        return False
    return hmac.compare_digest(username, 'dobot') and hmac.compare_digest(
        token,
        expected_token,
    )


def _call_api(func, *args, busy_status=400):
    try:
        return func(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=busy_status, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc


def main(args=None):
    rclpy.init(args=args)
    node = DobotWebNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    ros_thread = threading.Thread(target=executor.spin, daemon=True)
    ros_thread.start()

    app = create_app(node)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=node.host,
            port=node.port,
            log_level='info',
            access_log=False,
        )
    )

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        ros_thread.join(timeout=2.0)
        node.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
