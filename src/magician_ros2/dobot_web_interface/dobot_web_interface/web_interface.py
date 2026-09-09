import base64
import hmac
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
from dobot_msgs.srv import ExecuteHomingProcedure, GripperControl, SuctionCupControl
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dobot_web_interface.calibration_print import calibration_print_page
from dobot_web_interface.calibration_capture import validate_stationary_capture
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
import uvicorn
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from std_msgs.msg import String


_ARUCO_OPERATION_LOCK = threading.RLock()


TOOL_MAPPINGS = ('canonical',)


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
    from dobot_vision_yolo.aruco_board import aruco_dictionary
    from dobot_vision_yolo.camera_calibration_tool import CalibrationError
    from dobot_vision_yolo.camera_calibration_tool import CalibrationStore
except ImportError:
    aruco_dictionary = None
    CalibrationError = ValueError
    CalibrationStore = None

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
    from dobot_vision_yolo.vision_pick_place_node import HTTPMotionExecutor
    from dobot_vision_yolo.vision_pick_place_node import build_motion_sequence
    from dobot_vision_yolo.vision_pick_place_node import build_real_motion_sequence
except ImportError:
    HTTPMotionExecutor = None
    build_motion_sequence = None
    build_real_motion_sequence = None

try:
    from dobot_vision_yolo.eye_in_hand_transform import CameraIntrinsicsStore
    from dobot_vision_yolo.eye_in_hand_transform import EyeInHandConfigStore
    from dobot_vision_yolo.eye_in_hand_transform import EyeInHandError
    from dobot_vision_yolo.eye_in_hand_transform import extract_tcp_pose_from_status
    from dobot_vision_yolo.eye_in_hand_transform import normalize_tcp_pose
    from dobot_vision_yolo.eye_in_hand_transform import render_aruco_overlay
except ImportError:
    CameraIntrinsicsStore = None
    EyeInHandConfigStore = None
    EyeInHandError = ValueError
    extract_tcp_pose_from_status = None
    normalize_tcp_pose = None
    render_aruco_overlay = None


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
        self.declare_parameter('vision_calibration_path', '')
        self.declare_parameter('vision_place_positions_path', '')
        self.declare_parameter('vision_workspace_path', '')
        self.declare_parameter('vision_yolo_config_path', '')
        self.declare_parameter('vision_mode', 'fixed_camera')
        self.declare_parameter('vision_engine', 'rgbd_shape')
        self.declare_parameter(
            'tool_mapping', os.environ.get('DOBOT_TOOL_MAPPING', 'canonical')
        )
        self.declare_parameter('vision_eye_in_hand_path', '')
        self.declare_parameter('vision_camera_intrinsics_path', '')
        self.declare_parameter('tcp_pose_topic', 'dobot_pose_raw')
        self.declare_parameter('fallback_tcp_pose_topic', '')
        self.declare_parameter(
            'vision_selected_target_topic',
            '/dobot_vision_yolo/selected_target',
        )

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
        self.vision_calibration_path = str(
            self.get_parameter('vision_calibration_path').value
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
        self.vision_eye_in_hand_path = str(
            self.get_parameter('vision_eye_in_hand_path').value
        )
        self.vision_camera_intrinsics_path = str(
            self.get_parameter('vision_camera_intrinsics_path').value
        )
        self.tcp_pose_topic = str(self.get_parameter('tcp_pose_topic').value)
        self.fallback_tcp_pose_topic = str(
            self.get_parameter('fallback_tcp_pose_topic').value
        )
        self.vision_selected_target_topic = str(
            self.get_parameter('vision_selected_target_topic').value
        )

        self.bridge = CvBridge()
        self._frame_condition = threading.Condition()
        self._latest_jpeg = None
        self._latest_frame_time = None
        self._latest_frame_source = None
        self._latest_frame_stamp_sec = None
        self._latest_frame_id = ''
        self._frame_sequence = 0
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
        self._calibration_operation_lock = threading.Lock()
        self._calibration_store = (
            CalibrationStore(self.vision_calibration_path)
            if CalibrationStore is not None
            else None
        )
        self._place_store = (
            PlaceStore(self.vision_place_positions_path)
            if PlaceStore is not None
            else None
        )
        self._eye_in_hand_store = (
            EyeInHandConfigStore(self.vision_eye_in_hand_path)
            if EyeInHandConfigStore is not None
            else None
        )
        self._intrinsics_store = (
            CameraIntrinsicsStore(self.vision_camera_intrinsics_path)
            if CameraIntrinsicsStore is not None
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

        self.create_subscription(
            Image,
            self.camera_raw_topic,
            self._raw_image_callback,
            qos_profile_sensor_data,
        )
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
        if self._calibration_store is not None:
            self.get_logger().info(
                f'Vision calibration config: {self._calibration_store.path}'
            )
        if self._place_store is not None:
            self.get_logger().info(f'Vision place config: {self._place_store.path}')
        if self._eye_in_hand_store is not None:
            self.get_logger().info(
                f'Eye-in-hand config: {self._eye_in_hand_store.path}'
            )
        if self._intrinsics_store is not None:
            self.get_logger().info(
                f'Camera intrinsics config: {self._intrinsics_store.path}'
            )
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
            },
            'motion': {
                'active_goal': active_goal,
                'last_goal_age_sec': last_goal_age,
                'last_feedback': last_feedback,
                'last_result': last_result,
                'joints_deg': joints_deg,
                'current_tcp_pose': tcp_pose,
                'current_tcp_pose_source': tcp_pose_source,
                'current_tcp_pose_age_sec': tcp_pose_age,
                'homing_confirmed': homing_confirmed,
                'vision_sequence_active': vision_operation_active,
                'vision_sequence_age_sec': vision_operation_age,
            },
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
        pixel_transformer = None
        calibration_label = 'Calibration'
        source = 'dobot_web_interface'
        if vision_mode == 'eye_in_hand':
            pixel_transformer = self._eye_in_hand_pixel_transformer()
            calibration_label = 'Eye-in-hand calibration'
            source = 'dobot_web_interface:eye_in_hand'

        image_size = (
            int(payload.get('image_width', 640)),
            int(payload.get('image_height', 480)),
        )
        result = select_target_from_detections(
            detections,
            payload,
            self._places(),
            self._calibration(),
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
        tcp_pose = self._current_tcp_pose()
        if tcp_pose is None:
            raise ValueError('TCP pose is unavailable for eye-in-hand vision')
        eye_store = self._eye_in_hand()
        intrinsics = self._current_intrinsics()
        workspace = self._safety().workspace

        def transform(center_pixel):
            result = eye_store.test_pixel(
                center_pixel,
                tcp_pose,
                intrinsics,
                workspace=workspace,
            )
            result['tcp_pose'] = tcp_pose
            return result

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

    def vision_pick_selected(self, payload):
        if HTTPMotionExecutor is None or build_real_motion_sequence is None:
            raise ConnectionError('dobot_vision_yolo real motion tools are not available')
        if not isinstance(payload, dict):
            raise ValueError('pick_selected payload must be an object')

        if not self._vision_operation_lock.acquire(blocking=False):
            raise RuntimeError('A vision pick-and-place sequence is already active')

        self._vision_cancel_event.clear()
        with self._vision_operation_state_lock:
            self._vision_operation_active = True
            self._vision_operation_started_at = time.monotonic()

        try:
            return self._vision_pick_selected_locked(payload)
        finally:
            with self._vision_operation_state_lock:
                self._vision_operation_active = False
                self._vision_operation_started_at = None
            self._vision_operation_lock.release()

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

        tool_type = str(payload.get('tool_type', 'suction')).lower()
        velocity_ratio = float(payload.get('velocity_ratio', 0.3))
        acceleration_ratio = float(payload.get('acceleration_ratio', 0.2))
        wait_after_tool_sec = float(payload.get('wait_after_tool_sec', 0.5))
        sequence = build_real_motion_sequence(
            selected_target,
            guard,
            tool_type=tool_type,
            wait_after_tool_sec=wait_after_tool_sec,
        )
        executor = HTTPMotionExecutor(
            self._local_api_base_url(),
            velocity_ratio=velocity_ratio,
            acceleration_ratio=acceleration_ratio,
            tool_type=tool_type,
            cancel_event=self._vision_cancel_event,
            api_token=self.api_token,
        )
        execution_log = executor.execute(sequence)
        return {
            'accepted': True,
            'executed': True,
            'dry_run': False,
            'transport': 'http_api',
            'message': 'Real vision pick-and-place sequence executed via HTTP API.',
            'selected_target': selected_target,
            'safety': safety,
            'motion_sequence': sequence,
            'execution_log': execution_log,
            'velocity_ratio': velocity_ratio,
            'acceleration_ratio': acceleration_ratio,
            'tool_type': tool_type,
        }

    def vision_cancel(self):
        self._vision_cancel_event.set()
        motion_result = self.cancel_move()
        with self._vision_operation_state_lock:
            sequence_active = self._vision_operation_active
        return {
            'requested': bool(sequence_active or motion_result.get('requested')),
            'vision_sequence_cancel_requested': bool(sequence_active),
            'motion_cancel': motion_result,
            'message': (
                'Vision sequence cancellation requested.'
                if sequence_active
                else motion_result.get('message', 'No active vision sequence')
            ),
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
        calibration_status = (
            self._eye_in_hand().status(
                tcp_pose=tcp_pose,
                intrinsics=self._current_intrinsics(),
            )
            if vision_mode == 'eye_in_hand'
            else self.vision_calibration()
        )
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
        return self._calibration().status()

    def vision_calibration_add_point(self, payload):
        image_point = self._extract_image_point(payload)
        robot_point = self._extract_robot_point(payload)
        return self._run_calibration_change(
            self._calibration().add_point,
            image_point,
            robot_point,
        )

    def vision_calibration_remove_point(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('calibration remove payload must be an object')
        if 'index' in payload:
            index = int(payload['index'])
        elif 'point_id' in payload:
            index = int(payload['point_id']) - 1
        elif 'id' in payload:
            index = int(payload['id']) - 1
        else:
            raise ValueError('index or point_id is required')
        return self._run_calibration_change(
            self._calibration().remove_point,
            index,
        )

    def vision_calibration_compute(self):
        return self._run_calibration_change(self._calibration().compute)

    def _run_calibration_change(self, callback, *args):
        if not self._calibration_operation_lock.acquire(blocking=False):
            raise RuntimeError('Another calibration check is already running')
        try:
            with _ARUCO_OPERATION_LOCK:
                return callback(*args)
        finally:
            self._calibration_operation_lock.release()

    def vision_auto_calibrate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('auto calibration payload must be an object')
        if payload.get('dry_run', True) is not True:
            raise ValueError('Automatic calibration is dry_run only')
        mode = self._vision_mode_from_payload(payload)
        if mode == 'eye_in_hand' and payload.get('fixture_measured') is not True:
            raise ValueError(
                'Confirm printed scale and measured board pose_base before calibration'
            )
        return self._run_calibration_change(
            self._perform_auto_calibration,
            mode,
        )

    def _stationary_calibration_preflight(self):
        motion = self.status()['motion']
        if motion.get('active_goal') or motion.get('vision_sequence_active'):
            raise ValueError('Stop robot commands and Vision sequences before calibration')
        age = motion.get('current_tcp_pose_age_sec')
        if age is None or not np.isfinite(age) or not 0 <= age <= 0.5:
            raise ValueError('Fresh TCP state within 500 ms is required')
        with self._frame_condition:
            stamp = self._latest_camera_intrinsics_time
            if stamp is None or not 0 <= time.monotonic() - stamp <= 5.0:
                raise ValueError('Fresh CameraInfo is required; YAML fallback is not accepted')
            intrinsics = dict(self._latest_camera_intrinsics or {})
        return motion['current_tcp_pose'], intrinsics

    def _perform_auto_calibration(self, mode):
        tcp_pose = None
        if mode == 'eye_in_hand':
            tcp_pose, intrinsics = self._stationary_calibration_preflight()
            if tcp_pose is None:
                raise ValueError('TCP pose is unavailable; calibration rejected')
            aruco = self._eye_in_hand().load()['aruco']
            sample_count = int(aruco.get('auto_sample_count', 12))
            timeout_sec = float(aruco.get('auto_capture_timeout_sec', 5.0))
        else:
            auto_config = self._calibration().load()['auto_calibration']
            sample_count = int(auto_config.get('sample_count', 12))
            timeout_sec = float(auto_config.get('capture_timeout_sec', 5.0))

        frames = self._capture_fresh_frames(sample_count, timeout_sec)
        if mode == 'eye_in_hand':
            ending_tcp_pose, ending_intrinsics = self._stationary_calibration_preflight()
            records = self._last_calibration_capture_metadata.get('frames', [])
            validate_stationary_capture(tcp_pose, records)
            if intrinsics != ending_intrinsics:
                raise ValueError('CameraInfo changed during capture; retry')
            if any(
                frame.shape[1] != intrinsics.get('image_width')
                or frame.shape[0] != intrinsics.get('image_height')
                for frame in frames
            ):
                raise ValueError('CameraInfo resolution does not match calibration images')
            if any(
                not record.get('frame_id')
                or record['frame_id'] != intrinsics.get('frame_id')
                for record in records
            ):
                raise ValueError('CameraInfo optical frame does not match calibration images')
            if ending_tcp_pose is None:
                raise ValueError('TCP pose was lost during calibration')
            translation_change = float(
                np.linalg.norm(
                    np.asarray(ending_tcp_pose[:3], dtype=np.float64)
                    - np.asarray(tcp_pose[:3], dtype=np.float64)
                )
            )
            rotation_delta = float(ending_tcp_pose[3]) - float(tcp_pose[3])
            rotation_change = abs((rotation_delta + 180.0) % 360.0 - 180.0)
            if translation_change > 0.5 or rotation_change > 0.2:
                raise ValueError(
                    'Robot moved during calibration; keep the arm still and retry'
                )
            self._intrinsics().save(intrinsics)
            result = self._eye_in_hand().auto_calibrate_from_frames(
                frames,
                tcp_pose,
                intrinsics,
            )
            result['tcp_pose_available'] = True
            result['current_tcp_pose'] = tcp_pose
            result['marker_status'] = result.get('validation', {})
        else:
            result = self._calibration().auto_compute(frames)
        result['dry_run'] = True
        result['vision_mode'] = mode
        result['captured_frame_count'] = len(frames)
        result['calibration_frame_source'] = self._last_calibration_frame_source
        capture_sync = dict(
            getattr(self, '_last_calibration_capture_metadata', {}) or {}
        )
        intrinsics = (
            self._current_intrinsics()
            if hasattr(self, '_current_intrinsics')
            else None
        )
        vision_status = (
            self.vision_status() if hasattr(self, 'vision_status') else {}
        )
        raw_vision = vision_status.get('raw', {}) if isinstance(vision_status, dict) else {}
        intrinsics_complete = (
            isinstance(intrinsics, dict)
            and all(key in intrinsics for key in ('fx', 'fy', 'cx', 'cy'))
        )
        camera_diagnostics = {
            'calibration_input': 'RGB only',
            'calibration_model': (
                'anchored_board_solvePnP'
                if mode == 'eye_in_hand'
                else 'planar_homography'
            ),
            'image_resolution': {
                'width': int(frames[0].shape[1]),
                'height': int(frames[0].shape[0]),
            },
            'image_frame_id': (
                capture_sync.get('frames', [{}])[0].get('frame_id', '')
                if capture_sync.get('frames')
                else ''
            ),
            'camera_intrinsics': intrinsics,
            'camera_matrix': (
                [
                    [intrinsics['fx'], 0.0, intrinsics['cx']],
                    [0.0, intrinsics['fy'], intrinsics['cy']],
                    [0.0, 0.0, 1.0],
                ]
                if intrinsics_complete
                else None
            ),
            'distortion_coefficients': (
                intrinsics.get('distortion_coefficients')
                if isinstance(intrinsics, dict)
                else None
            ),
            'depth_alignment': {
                'used_for_calibration': False,
                'required_for_calibration': False,
                'registered_depth': raw_vision.get('registered_depth'),
                'sync_ok': raw_vision.get('sync_ok'),
                'sync_delta_ms': raw_vision.get('sync_delta_ms'),
                'depth_stream_ok': raw_vision.get('depth_stream_ok'),
                'depth_data_valid': raw_vision.get('depth_data_valid'),
                'depth_valid_ratio': raw_vision.get('depth_valid_ratio'),
                'note': (
                    'ArUco calibration uses RGB corners with homography/PnP; '
                    'aligned depth is reported but not used in the solve.'
                ),
            },
        }
        result['camera_diagnostics'] = camera_diagnostics
        result['synchronization'] = capture_sync
        attempt = result.get('calibration_attempt') or result.get('last_auto_attempt')
        if isinstance(attempt, dict):
            attempt['camera_diagnostics'] = camera_diagnostics
            attempt['synchronization'] = capture_sync
        if hasattr(self, 'get_logger') and isinstance(attempt, dict):
            logger = self.get_logger()
            quality = attempt.get('quality', {})
            logger.info(
                '[CALIBRATION] mode=%s dictionary=%s required=%s detected=%s '
                'valid_frames=%s/%s inlier_ratio=%s warning=%s'
                % (
                    mode,
                    attempt.get('dictionary'),
                    attempt.get('required_ids'),
                    attempt.get('detected_ids'),
                    quality.get('valid_frame_count', quality.get('valid_sample_count')),
                    quality.get('frame_count'),
                    quality.get('inlier_ratio'),
                    attempt.get('warning', ''),
                )
            )
            logger.info(
                '[CALIBRATION][camera] resolution=%s frame_id=%s K=%s '
                'distortion=%s depth_alignment=%s synchronization=%s'
                % (
                    camera_diagnostics.get('image_resolution'),
                    camera_diagnostics.get('image_frame_id'),
                    camera_diagnostics.get('camera_matrix'),
                    camera_diagnostics.get('distortion_coefficients'),
                    camera_diagnostics.get('depth_alignment'),
                    capture_sync,
                )
            )
            for frame_debug in attempt.get('frame_diagnostics', []):
                logger.info(
                    '[CALIBRATION][frame %s] detected=%s missing=%s rejected=%s '
                    'blur=%s valid=%s reasons=%s'
                    % (
                        frame_debug.get('frame_index'),
                        frame_debug.get('detected_ids'),
                        frame_debug.get('missing_ids'),
                        frame_debug.get('rejected_marker_count'),
                        frame_debug.get('blur_laplacian_variance'),
                        frame_debug.get('valid_for_solve', True),
                        frame_debug.get('rejection_reasons', []),
                    )
                )
                for detected_marker in frame_debug.get('markers', []):
                    logger.info(
                        '[CALIBRATION][frame %s][marker %s] corners_px=%s '
                        'center_px=%s sides_px=%s area_px2=%s quality=%s'
                        % (
                            frame_debug.get('frame_index'),
                            detected_marker.get('id'),
                            detected_marker.get('corners_pixel'),
                            detected_marker.get('center_pixel'),
                            detected_marker.get('side_lengths_px'),
                            detected_marker.get('area_px2'),
                            detected_marker.get('quality_type'),
                        )
                    )
                if frame_debug.get('detected_board_geometry'):
                    logger.info(
                        '[CALIBRATION][frame %s][board] expected=%s detected=%s'
                        % (
                            frame_debug.get('frame_index'),
                            quality.get('expected_board_geometry'),
                            frame_debug.get('detected_board_geometry'),
                        )
                    )
            for marker_debug in attempt.get('marker_validation', []):
                logger.info(
                    '[CALIBRATION][marker %s] expected=%s predicted=%s delta=%s '
                    'error_mm=%s'
                    % (
                        marker_debug.get('id'),
                        marker_debug.get('expected_xyz_mm'),
                        marker_debug.get('predicted_xyz_mm'),
                        marker_debug.get('delta_xyz_mm'),
                        marker_debug.get('error_norm_mm'),
                    )
                )
            transforms = attempt.get('transforms', {})
            for transform_name, transform_debug in transforms.items():
                if transform_name == 'markers' or not isinstance(transform_debug, dict):
                    continue
                logger.info(
                    '[CALIBRATION][transform] %s XYZ_mm=%s RPY_deg=%s matrix_row_major=%s'
                    % (
                        transform_debug.get('name', transform_name),
                        transform_debug.get('translation_mm'),
                        transform_debug.get('rotation_rpy_deg'),
                        transform_debug.get('matrix_row_major'),
                    )
                )
            for marker_transforms in transforms.get('markers', []):
                for transform_name in ('T_camera_marker', 'T_base_marker'):
                    transform_debug = marker_transforms.get(transform_name, {})
                    logger.info(
                        '[CALIBRATION][transform][marker %s] %s XYZ_mm=%s RPY_deg=%s'
                        % (
                            marker_transforms.get('id'),
                            transform_debug.get('name', transform_name),
                            transform_debug.get('translation_mm'),
                            transform_debug.get('rotation_rpy_deg'),
                        )
                    )
        return result

    def vision_calibration_test_point(self, payload):
        image_point = self._extract_image_point(payload)
        return self._calibration().test_point(image_point)

    def vision_eye_in_hand_status(self):
        tcp_pose = self._current_tcp_pose()
        status = self._eye_in_hand().status(
            tcp_pose=tcp_pose,
            intrinsics=self._current_intrinsics(),
        )
        status['dry_run'] = True
        status['vision_mode'] = 'eye_in_hand'
        status['tcp_pose_available'] = tcp_pose is not None
        status['current_tcp_pose'] = tcp_pose
        status['marker_status'] = status.get('validation', {})
        return status

    def vision_eye_in_hand_calibrate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('eye-in-hand calibrate payload must be an object')
        if payload.get('update_mount') is not None or payload.get('save_detected_markers'):
            raise ValueError('Use measured anchored-board multi-frame calibration without overrides')
        return self.vision_auto_calibrate(dict(payload, vision_mode='eye_in_hand'))

    def get_eye_in_hand_annotated(self):
        if render_aruco_overlay is None:
            return self._make_vision_placeholder()
        if not _ARUCO_OPERATION_LOCK.acquire(blocking=False):
            return self._make_vision_placeholder()
        try:
            frame = self._latest_cv_frame()
            if frame is None:
                return self._make_vision_placeholder()
            overlay = render_aruco_overlay(
                frame,
                self._eye_in_hand().load(),
                self._current_intrinsics(),
                tcp_pose=self._current_tcp_pose(),
            )
            ok, data = cv2.imencode(
                '.jpg',
                overlay['image'],
                [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
            )
            if ok:
                return data.tobytes()
        except Exception as exc:
            self.get_logger().warn(f'Failed render ArUco overlay: {exc}')
        finally:
            _ARUCO_OPERATION_LOCK.release()
        return self._make_vision_placeholder()

    def get_calibration_board_svg(self, mode='fixed_camera'):
        if mode == 'eye_in_hand':
            config = self._eye_in_hand().load()['aruco']
        elif mode == 'fixed_camera':
            config = self._calibration().load()['auto_calibration']
        else:
            raise ValueError('mode must be fixed_camera or eye_in_hand')
        board = config['board']
        if not hasattr(cv2, 'aruco') or aruco_dictionary is None:
            raise ConnectionError('OpenCV ArUco support is unavailable')
        with _ARUCO_OPERATION_LOCK:
            dictionary = aruco_dictionary(cv2, board['dictionary'])
        marker_length = float(board['marker_length_mm'])
        marker_ids = [int(marker_id) for marker_id in board['required_ids']]
        missing_layout = [
            marker_id
            for marker_id in marker_ids
            if str(marker_id) not in board.get('markers', {})
        ]
        if missing_layout:
            raise ValueError(
                'Marker positions are missing for ids: '
                + ', '.join(str(marker_id) for marker_id in missing_layout)
            )
        centers = {
            marker_id: board['markers'][str(marker_id)]['center_mm']
            for marker_id in marker_ids
        }
        min_x = min(float(center[0]) for center in centers.values())
        max_x = max(float(center[0]) for center in centers.values())
        min_y = min(float(center[1]) for center in centers.values())
        max_y = max(float(center[1]) for center in centers.values())
        margin = 10.0
        origin_x = min_x - marker_length / 2.0 - margin
        # Board coordinates are Cartesian/right-handed (+Y up), while SVG Y
        # grows down.  Inverting Y here is essential: drawing both axes in the
        # same direction creates a reflection that a 2-D homography can hide,
        # but a rigid solvePnP transform cannot represent.
        origin_y = max_y + marker_length / 2.0 + margin
        width = max_x - min_x + marker_length + 2.0 * margin
        height = max_y - min_y + marker_length + 2.0 * margin
        elements = [
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{width:.3f}mm" height="{height:.3f}mm" '
                f'viewBox="0 0 {width:.3f} {height:.3f}">'
            ),
            f'<rect width="{width:.3f}" height="{height:.3f}" fill="white"/>',
            f'<metadata>{escape(json.dumps(board, ensure_ascii=False))}</metadata>',
            (
                f'<text x="3" y="3" font-family="sans-serif" font-size="2" '
                f'fill="#333">DOBOT ARUCO {board["dictionary"]} — PRINT AT 100%</text>'
            ),
            (
                f'<rect x="{margin:.3f}" y="{margin:.3f}" '
                f'width="{width - 2.0 * margin:.3f}" '
                f'height="{height - 2.0 * margin:.3f}" '
                'fill="none" stroke="#888" stroke-width="0.3"/>'
            ),
        ]
        for marker_id in marker_ids:
            marker_image = np.zeros((240, 240), dtype=np.uint8)
            with _ARUCO_OPERATION_LOCK:
                if hasattr(cv2.aruco, 'generateImageMarker'):
                    cv2.aruco.generateImageMarker(
                        dictionary,
                        marker_id,
                        240,
                        marker_image,
                        1,
                    )
                else:  # pragma: no cover - older OpenCV
                    marker_image = cv2.aruco.drawMarker(dictionary, marker_id, 240)
            ok, encoded = cv2.imencode('.png', marker_image)
            if not ok:
                raise RuntimeError(f'Unable to render ArUco marker {marker_id}')
            image_data = base64.b64encode(encoded.tobytes()).decode('ascii')
            center_x = float(centers[marker_id][0])
            center_y = float(centers[marker_id][1])
            x = float(center_x) - origin_x - marker_length / 2.0
            y = origin_y - float(center_y) - marker_length / 2.0
            yaw_deg = float(
                board['markers'][str(marker_id)].get('yaw_deg', 0.0)
            )
            svg_yaw_deg = -yaw_deg
            rotation = (
                f' transform="rotate({svg_yaw_deg:g} '
                f'{x + marker_length / 2.0:.3f} '
                f'{y + marker_length / 2.0:.3f})"'
                if abs(yaw_deg) > 1e-9
                else ''
            )
            elements.append(
                f'<rect x="{x - 2.0:.3f}" y="{y - 2.0:.3f}" '
                f'width="{marker_length + 4.0:.3f}" '
                f'height="{marker_length + 4.0:.3f}" fill="white"/>'
            )
            elements.append(
                f'<image x="{x:.3f}" y="{y:.3f}" '
                f'width="{marker_length:.3f}" height="{marker_length:.3f}" '
                f'xlink:href="data:image/png;base64,{image_data}"{rotation}/>'
            )
            label_y = y - 3.5 if y >= 4.0 else y + marker_length + 5.0
            elements.append(
                f'<text x="{x + marker_length / 2.0:.3f}" y="{label_y:.3f}" '
                'font-family="sans-serif" font-size="3" text-anchor="middle" '
                f'fill="#333">ID {marker_id}  board X={center_x:g} '
                f'Y={center_y:g}</text>'
            )
        elements.extend(
            [
                (
                    f'<path d="M {-origin_x - 4:.3f} {origin_y:.3f} h 8 '
                    f'M {-origin_x:.3f} {origin_y - 4:.3f} v 8" '
                    'fill="none" stroke="#111" stroke-width="0.25"/>'
                    f'<text x="{-origin_x:.3f}" y="{origin_y + 9:.3f}" '
                    'font-family="sans-serif" font-size="3" text-anchor="middle">'
                    'BOARD ORIGIN (0,0,0)</text>'
                ),
                (
                    f'<text x="36" y="{height - 1.5:.3f}" '
                    'font-family="sans-serif" font-size="3" fill="#333">'
                    '+X: ID0→ID1   +Y: ID0→ID3 (ขึ้นบนแผ่น)</text>'
                ),
                (
                    f'<line x1="3" y1="{height - 5:.3f}" x2="33" '
                    f'y2="{height - 5:.3f}" stroke="#111" stroke-width="0.5"/>'
                ),
                (
                    f'<text x="18" y="{height - 1.5:.3f}" '
                    'font-family="sans-serif" font-size="3" text-anchor="middle" '
                    'fill="#333">30 mm check ruler</text>'
                ),
                '</svg>',
            ]
        )
        return ''.join(elements).encode('utf-8')

    def vision_eye_in_hand_test_pixel(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('eye-in-hand test_pixel payload must be an object')
        image_point = self._extract_image_point(payload)
        tcp_pose = self._current_tcp_pose()
        if tcp_pose is None:
            raise ValueError('TCP pose is unavailable; test_pixel rejected')
        result = self._eye_in_hand().test_pixel(
            image_point,
            tcp_pose,
            self._current_intrinsics(),
            workspace=self._safety().workspace,
        )
        result['dry_run'] = True
        return result

    def _calibration(self):
        if self._calibration_store is None:
            raise ConnectionError(
                'dobot_vision_yolo calibration tools are not available'
            )
        return self._calibration_store

    def _eye_in_hand(self):
        if self._eye_in_hand_store is None:
            raise ConnectionError(
                'dobot_vision_yolo eye-in-hand tools are not available'
            )
        return self._eye_in_hand_store

    def _intrinsics(self):
        if self._intrinsics_store is None:
            raise ConnectionError(
                'dobot_vision_yolo camera intrinsics tools are not available'
            )
        return self._intrinsics_store

    def _current_intrinsics(self):
        with self._frame_condition:
            intrinsics = self._latest_camera_intrinsics
            received_at = self._latest_camera_intrinsics_time
        if (
            intrinsics is not None
            and received_at is not None
            and time.monotonic() - received_at <= 5.0
        ):
            return dict(intrinsics)
        return self._intrinsics().load()

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

    def call_homing(self):
        if not self.homing_client.wait_for_service(timeout_sec=0.25):
            raise ConnectionError('dobot_homing_service is not available')
        response = self._wait_for_future(
            self.homing_client.call_async(ExecuteHomingProcedure.Request()),
            20.0,
        )
        with self._goal_lock:
            self._homing_confirmed = bool(response.success)
        return {
            'success': bool(response.success),
            'message': response.instruction,
        }

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
        return (static_dir / 'index.html').read_text(encoding='utf-8')

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

    @app.get('/api/vision/calibration/print', response_class=HTMLResponse)
    def api_vision_calibration_print(mode: str = 'eye_in_hand'):
        svg = _call_api(node.get_calibration_board_svg, mode)
        return HTMLResponse(
            content=_call_api(calibration_print_page, svg, mode),
            headers={'Cache-Control': 'no-store'},
        )

    @app.get('/api/vision/calibration/board.svg')
    def api_vision_calibration_board(mode: str = 'fixed_camera'):
        return Response(
            content=_call_api(node.get_calibration_board_svg, mode),
            media_type='image/svg+xml',
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
        return _call_api(node.cancel_move)

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

    @app.post('/api/vision/calibration/add_point')
    async def api_vision_calibration_add_point(request: Request):
        return _call_api(node.vision_calibration_add_point, await request.json())

    @app.post('/api/vision/calibration/remove_point')
    async def api_vision_calibration_remove_point(request: Request):
        return _call_api(node.vision_calibration_remove_point, await request.json())

    @app.post('/api/vision/calibration/compute')
    def api_vision_calibration_compute():
        return _call_api(node.vision_calibration_compute)

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
