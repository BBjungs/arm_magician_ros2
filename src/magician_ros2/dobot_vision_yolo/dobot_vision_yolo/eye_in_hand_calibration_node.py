import json
import time
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from std_msgs.msg import String

from dobot_vision_yolo.eye_in_hand_transform import CameraIntrinsicsStore
from dobot_vision_yolo.eye_in_hand_transform import EyeInHandConfigStore
from dobot_vision_yolo.eye_in_hand_transform import EyeInHandError
from dobot_vision_yolo.eye_in_hand_transform import extract_tcp_pose_from_status
from dobot_vision_yolo.eye_in_hand_transform import normalize_tcp_pose


class EyeInHandCalibrationNode(Node):
    def __init__(self):
        super().__init__("eye_in_hand_calibration_node")
        self.declare_parameter("dry_run", True)
        self.declare_parameter("eye_in_hand_config_path", "")
        self.declare_parameter("camera_intrinsics_path", "")
        self.declare_parameter("camera_device", "")
        self.declare_parameter("tcp_pose_source", "")
        self.declare_parameter("tcp_pose_topic", "")
        self.declare_parameter("fallback_tcp_pose_topic", "")
        self.declare_parameter("api_status_url", "")
        self.declare_parameter(
            "command_topic",
            "/dobot_vision/eye_in_hand/calibrate",
        )
        self.declare_parameter("status_topic", "/dobot_vision/eye_in_hand/status")
        self.declare_parameter("status_period_sec", 5.0)

        self.dry_run = bool(self.get_parameter("dry_run").value)
        self.eye_store = EyeInHandConfigStore(
            str(self.get_parameter("eye_in_hand_config_path").value)
        )
        self.intrinsics_store = CameraIntrinsicsStore(
            str(self.get_parameter("camera_intrinsics_path").value)
        )
        config = self.eye_store.load()
        self.camera_device = (
            str(self.get_parameter("camera_device").value)
            or str(config.get("camera_device", "/dev/video0"))
        )
        self.tcp_pose_source = (
            str(self.get_parameter("tcp_pose_source").value)
            or str(config.get("tcp_pose_source", "api_status"))
        )
        self.tcp_pose_topic = (
            str(self.get_parameter("tcp_pose_topic").value)
            or str(config.get("tcp_pose_topic", "dobot_pose_raw"))
        )
        self.fallback_tcp_pose_topic = (
            str(self.get_parameter("fallback_tcp_pose_topic").value)
            or str(config.get("fallback_tcp_pose_topic", ""))
        )
        self.api_status_url = (
            str(self.get_parameter("api_status_url").value)
            or str(config.get("api_status_url", "http://127.0.0.1:8080/api/status"))
        )
        self.command_topic = str(self.get_parameter("command_topic").value)
        self.status_topic = str(self.get_parameter("status_topic").value)
        self.latest_tcp_pose = None
        self.latest_tcp_pose_time = None
        self.latest_tcp_pose_source = ""
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_error = ""

        self.status_publisher = self.create_publisher(String, self.status_topic, 10)
        self.command_subscription = self.create_subscription(
            String,
            self.command_topic,
            self._command_callback,
            10,
        )
        self.tcp_subscription = self.create_subscription(
            Float64MultiArray,
            self.tcp_pose_topic,
            lambda msg: self._tcp_pose_callback(msg, self.tcp_pose_topic),
            10,
        )
        if self.fallback_tcp_pose_topic and self.fallback_tcp_pose_topic != self.tcp_pose_topic:
            self.fallback_tcp_subscription = self.create_subscription(
                Float64MultiArray,
                self.fallback_tcp_pose_topic,
                lambda msg: self._tcp_pose_callback(msg, self.fallback_tcp_pose_topic),
                10,
            )
        else:
            self.fallback_tcp_subscription = None

        period = float(self.get_parameter("status_period_sec").value)
        self.create_timer(max(period, 1.0), self._publish_status)
        self.get_logger().info(
            "Eye-in-hand calibration node ready. dry_run=%s camera=%s config=%s "
            "intrinsics=%s tcp_pose_source=%s"
            % (
                self.dry_run,
                self.camera_device,
                self.eye_store.path,
                self.intrinsics_store.path,
                self.tcp_pose_source,
            )
        )

    def _tcp_pose_callback(self, msg, source: str):
        try:
            self.latest_tcp_pose = normalize_tcp_pose(
                list(msg.data[:4]),
                xyz_unit="m",
            )
            self.latest_tcp_pose_time = time.monotonic()
            self.latest_tcp_pose_source = source
        except EyeInHandError as exc:
            self.last_error = str(exc)

    def _command_callback(self, msg):
        try:
            payload = json.loads(msg.data) if msg.data else {}
            if not isinstance(payload, dict):
                raise EyeInHandError("calibrate command payload must be an object")
            if not bool(payload.get("dry_run", True)):
                raise EyeInHandError("eye-in-hand calibration is dry_run only")
            result = self.calibrate(
                update_mount=payload.get("update_mount"),
                save_detected_markers=bool(
                    payload.get("save_detected_markers", False)
                ),
            )
            self.last_result = result
            self.last_error = ""
        except Exception as exc:
            self.last_error = str(exc)
            self.last_result = {
                "ok": False,
                "dry_run": True,
                "error": self.last_error,
            }
            self.get_logger().warn(self.last_error)
        self._publish_status()

    def calibrate(
        self,
        update_mount=None,
        save_detected_markers: bool = False,
    ) -> Dict[str, Any]:
        tcp_pose = self._current_tcp_pose()
        if tcp_pose is None:
            raise EyeInHandError("TCP pose is unavailable; calibration rejected")

        frame = self._capture_frame()
        if frame is None:
            raise EyeInHandError(f"Unable to read camera frame from {self.camera_device}")

        result = self.eye_store.calibrate_from_frame(
            frame,
            tcp_pose,
            self.intrinsics_store.load(),
            update_mount=update_mount,
            save_detected_markers=save_detected_markers,
        )
        result["dry_run"] = True
        result["camera_device"] = self.camera_device
        result["tcp_pose_source"] = self.latest_tcp_pose_source or self.tcp_pose_source
        return result

    def _capture_frame(self):
        capture = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
        if not capture.isOpened():
            capture.release()
            return None
        try:
            ok, frame = capture.read()
            if not ok or frame is None:
                return None
            return frame
        finally:
            capture.release()

    def _current_tcp_pose(self):
        if self.tcp_pose_source in ("api_status", "auto"):
            pose = self._tcp_pose_from_api()
            if pose is not None:
                self.latest_tcp_pose = pose
                self.latest_tcp_pose_time = time.monotonic()
                self.latest_tcp_pose_source = "api_status"
                return pose

        if self.latest_tcp_pose is not None:
            return list(self.latest_tcp_pose)
        return None

    def _tcp_pose_from_api(self):
        if not self.api_status_url:
            return None
        try:
            with urlopen(self.api_status_url, timeout=1.5) as response:
                status = json.loads(response.read().decode("utf-8"))
            return extract_tcp_pose_from_status(status)
        except (OSError, URLError, json.JSONDecodeError) as exc:
            self.get_logger().warn(f"Unable to read TCP pose from API status: {exc}")
            return None

    def _status_payload(self) -> Dict[str, Any]:
        tcp_pose = self.latest_tcp_pose
        tcp_age = None
        if self.latest_tcp_pose_time is not None:
            tcp_age = round(time.monotonic() - self.latest_tcp_pose_time, 2)
        status = self.eye_store.status(
            tcp_pose=tcp_pose,
            intrinsics=self.intrinsics_store.load(),
        )
        return {
            "ok": bool(status.get("is_complete", False)),
            "dry_run": True,
            "node": "eye_in_hand_calibration_node",
            "camera_device": self.camera_device,
            "tcp_pose_source": self.latest_tcp_pose_source or self.tcp_pose_source,
            "tcp_pose_age_sec": tcp_age,
            "tcp_pose": tcp_pose,
            "last_error": self.last_error,
            "last_result": self.last_result,
            "status": status,
        }

    def _publish_status(self):
        msg = String()
        msg.data = json.dumps(self._status_payload(), separators=(",", ":"))
        self.status_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = EyeInHandCalibrationNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
