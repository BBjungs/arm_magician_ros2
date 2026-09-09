import json

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from std_msgs.msg import String

from dobot_vision_yolo.camera_calibration_tool import CalibrationError
from dobot_vision_yolo.camera_calibration_tool import CalibrationStore
from dobot_vision_yolo.eye_in_hand_transform import CameraIntrinsicsStore
from dobot_vision_yolo.eye_in_hand_transform import EyeInHandConfigStore
from dobot_vision_yolo.eye_in_hand_transform import EyeInHandError
from dobot_vision_yolo.eye_in_hand_transform import normalize_tcp_pose


class PixelToRobotNode(Node):
    def __init__(self):
        super().__init__("pixel_to_robot_node")
        self.declare_parameter("dry_run", True)
        self.declare_parameter("detections_topic", "/dobot_vision/detections")
        self.declare_parameter("robot_detections_topic", "/dobot_vision/detections_robot")
        self.declare_parameter("selected_target_topic", "/dobot_vision_yolo/selected_target")
        self.declare_parameter("robot_target_topic", "/dobot_vision_yolo/robot_target")
        self.declare_parameter("status_topic", "/dobot_vision/pixel_to_robot/status")
        self.declare_parameter("calibration_config_path", "")
        self.declare_parameter("vision_mode", "fixed_camera")
        self.declare_parameter("eye_in_hand_config_path", "")
        self.declare_parameter("camera_intrinsics_path", "")
        self.declare_parameter("tcp_pose_topic", "dobot_pose_raw")
        self.declare_parameter("fallback_tcp_pose_topic", "")
        self.declare_parameter("status_period_sec", 5.0)

        self.dry_run = bool(self.get_parameter("dry_run").value)
        self.detections_topic = str(self.get_parameter("detections_topic").value)
        self.robot_detections_topic = str(
            self.get_parameter("robot_detections_topic").value
        )
        self.selected_target_topic = str(
            self.get_parameter("selected_target_topic").value
        )
        self.robot_target_topic = str(self.get_parameter("robot_target_topic").value)
        self.status_topic = str(self.get_parameter("status_topic").value)
        self.store = CalibrationStore(
            str(self.get_parameter("calibration_config_path").value)
        )
        self.vision_mode = str(self.get_parameter("vision_mode").value)
        self.eye_store = EyeInHandConfigStore(
            str(self.get_parameter("eye_in_hand_config_path").value)
        )
        self.intrinsics_store = CameraIntrinsicsStore(
            str(self.get_parameter("camera_intrinsics_path").value)
        )
        self.tcp_pose_topic = str(self.get_parameter("tcp_pose_topic").value)
        self.fallback_tcp_pose_topic = str(
            self.get_parameter("fallback_tcp_pose_topic").value
        )
        self.latest_tcp_pose = None

        self.robot_detections_publisher = self.create_publisher(
            String,
            self.robot_detections_topic,
            10,
        )
        self.robot_target_publisher = self.create_publisher(
            String,
            self.robot_target_topic,
            10,
        )
        self.status_publisher = self.create_publisher(String, self.status_topic, 10)
        self.detections_subscription = self.create_subscription(
            String,
            self.detections_topic,
            self._detections_callback,
            10,
        )
        self.selected_target_subscription = self.create_subscription(
            String,
            self.selected_target_topic,
            self._selected_target_callback,
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
            "Pixel-to-robot node ready. dry_run=%s, detections_topic=%s, config=%s"
            % (self.dry_run, self.detections_topic, self.store.path)
        )

    def _tcp_pose_callback(self, msg, _source):
        try:
            self.latest_tcp_pose = normalize_tcp_pose(
                list(msg.data[:4]),
                xyz_unit="m",
            )
        except EyeInHandError as exc:
            self._publish_error(str(exc))

    def _detections_callback(self, msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self._publish_error(f"Invalid detections JSON: {exc}")
            return

        status = self._calibration_status()
        detections = payload.get("detections", [])
        if not isinstance(detections, list):
            self._publish_error("detections must be a list")
            return

        position_available = self._position_available(status)
        enriched = []
        for detection in detections:
            item = dict(detection)
            center_pixel = item.get("center_pixel")
            if not position_available:
                item["robot_xy_error"] = (
                    "Calibration is incomplete; robot_xy not computed"
                )
            elif center_pixel is None:
                item["robot_xy_error"] = "center_pixel is missing"
            else:
                try:
                    result = self._test_point(center_pixel)
                    item["robot_xy"] = result["robot_xy"]
                    item["pick_pose_mm"] = [
                        result["robot_xy"][0],
                        result["robot_xy"][1],
                        result["pick_z"],
                        0.0,
                    ]
                    item["position_source"] = result.get("position_source")
                    item["position_estimate"] = bool(
                        result.get("position_estimate", False)
                    )
                except (CalibrationError, EyeInHandError) as exc:
                    item["robot_xy_error"] = str(exc)
            enriched.append(item)

        output = {
            "stamp": payload.get("stamp"),
            "dry_run": self.dry_run,
            "vision_mode": self.vision_mode,
            "calibration_complete": status["is_complete"],
            "position_available": position_available,
            "position_source": status.get("position_source"),
            "validation": status.get("validation", {}),
            "detections": enriched,
        }
        self._publish_json(self.robot_detections_publisher, output)

    def _selected_target_callback(self, msg):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self._publish_error(f"Invalid selected target JSON: {exc}")
            return

        if not payload.get("selected", False):
            self.get_logger().info("No selected target to transform.")
            return

        status = self._calibration_status()
        if not self._position_available(status):
            self._publish_error(
                "Calibration is incomplete; pick pose will not be published"
            )
            return

        center_pixel = payload.get("center_pixel")
        if center_pixel is None:
            self._publish_error("Selected target has no center_pixel")
            return

        try:
            result = self._test_point(center_pixel)
        except (CalibrationError, EyeInHandError) as exc:
            self._publish_error(str(exc))
            return

        pick_pose = [
            result["robot_xy"][0],
            result["robot_xy"][1],
            result["pick_z"],
            0.0,
        ]
        target = {
            "source": "pixel_to_robot_node",
            "dry_run": self.dry_run,
            "vision_mode": self.vision_mode,
            "selected": True,
            "id": payload.get("id"),
            "class_name": payload.get("class_name"),
            "confidence": payload.get("confidence"),
            "center_pixel": center_pixel,
            "robot_xy": result["robot_xy"],
            "safe_z": result["safe_z"],
            "pick_z": result["pick_z"],
            "pick_pose": pick_pose,
            "pose_mm": pick_pose,
            "calibration_valid": bool(result.get("calibration_valid", False)),
            "position_available": bool(result.get("position_available", True)),
            "position_estimate": bool(result.get("position_estimate", False)),
            "position_source": result.get("position_source"),
            "place_id": payload.get("place_id"),
            "place_pose": payload.get("place_pose"),
            "selection_mode": payload.get("selection_mode"),
            "detection": payload.get("detection"),
            "request": payload.get("request"),
            "validation": result["validation"],
        }
        self._publish_json(self.robot_target_publisher, target)
        self.get_logger().info("Published dry-run robot target pose from calibration.")

    def _publish_status(self):
        status = self._calibration_status()
        self._publish_json(
            self.status_publisher,
            {
                "dry_run": self.dry_run,
                "vision_mode": self.vision_mode,
                "calibration_complete": status["is_complete"],
                "position_available": self._position_available(status),
                "position_source": status.get("position_source"),
                "point_count": status["point_count"],
                "validation": status.get("validation", {}),
                "validation_errors": status.get("validation_errors", []),
                "config_path": status["config_path"],
                "tcp_pose": self.latest_tcp_pose,
            },
        )

    def _calibration_status(self):
        if self.vision_mode == "eye_in_hand":
            status = self.eye_store.status(tcp_pose=self.latest_tcp_pose)
            status.setdefault("point_count", 0)
            status.setdefault("validation_errors", [])
            return status
        return self.store.status()

    def _position_available(self, status):
        if self.vision_mode == "eye_in_hand":
            return bool(
                status.get("position_available", False)
                or status.get("can_estimate_position", False)
                or status.get("is_complete", False)
            )
        return bool(status.get("is_complete", False))

    def _test_point(self, center_pixel):
        if self.vision_mode != "eye_in_hand":
            return self.store.test_point(center_pixel)
        if self.latest_tcp_pose is None:
            raise EyeInHandError("TCP pose is unavailable")
        return self.eye_store.test_pixel(
            center_pixel,
            self.latest_tcp_pose,
            self.intrinsics_store.load(),
        )

    def _publish_error(self, message):
        self.get_logger().warn(message)
        self._publish_json(
            self.status_publisher,
            {
                "dry_run": self.dry_run,
                "calibration_complete": False,
                "error": message,
            },
        )

    @staticmethod
    def _publish_json(publisher, payload):
        msg = String()
        msg.data = json.dumps(payload, separators=(",", ":"))
        publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PixelToRobotNode()
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
