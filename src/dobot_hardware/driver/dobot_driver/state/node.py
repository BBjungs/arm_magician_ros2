"""Publish controller readbacks without accepting device commands."""

from contextlib import nullcontext
import math
from time import monotonic
from threading import Lock

from dobot_msgs.msg import AlarmState, DeviceStatus, ToolState
from geometry_msgs.msg import PoseStamped
from rcl_interfaces.msg import ParameterDescriptor
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Header

from ..serial_driver import DobotSerial, resolve_port

BASE_FRAME = "magician_base_link"
JOINT_NAMES = [f"magician_joint_{index}" for index in range(1, 5)]


def pose_messages(pose, stamp):
    """Convert millimeters and degrees to ROS units and URDF joint coordinates."""
    x, y, z, yaw, joint1, joint2, joint3, joint4 = pose
    joints = JointState(
        header=Header(stamp=stamp),
        name=JOINT_NAMES,
        position=[math.radians(angle) for angle in (joint1, joint2, joint3 - joint2, joint4)],
    )
    tcp = PoseStamped(header=Header(stamp=stamp, frame_id=BASE_FRAME))
    tcp.pose.position.x = x / 1000.0
    tcp.pose.position.y = y / 1000.0
    tcp.pose.position.z = z / 1000.0
    half_yaw = math.radians(yaw) / 2.0
    tcp.pose.orientation.z = math.sin(half_yaw)
    tcp.pose.orientation.w = math.cos(half_yaw)
    return joints, tcp


class ReadbackNode(Node):
    def __init__(self, *, home_port=None):
        super().__init__("dobot_readback", start_parameter_services=False)
        self._home_port = home_port
        self._device_lock = Lock()
        self._port = self.declare_parameter(
            "serial_port", home_port or "", ParameterDescriptor(read_only=True)
        ).value
        self._usb_id = self.declare_parameter(
            "usb_id", "", ParameterDescriptor(read_only=True)
        ).value
        self._usb_serial = self.declare_parameter(
            "usb_serial_number", "", ParameterDescriptor(read_only=True)
        ).value
        self._serial_timeout = self.declare_parameter(
            "serial_timeout", 0.15, ParameterDescriptor(read_only=True)
        ).value
        poll_period = self.declare_parameter(
            "poll_period", 0.2 if home_port else 0.5, ParameterDescriptor(read_only=True)
        ).value
        for name, value in (("serial_timeout", self._serial_timeout), ("poll_period", poll_period)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

        self._pose_retry_limit = 5
        self._detail_budget = min(self._serial_timeout, poll_period * 0.75)
        self._missing_pose = 0
        self._device = None
        self._identity = []
        self._gripper_first = False
        self.home_issue = "Waiting for Dobot pose and alarm status"
        self._status = self.create_publisher(DeviceStatus, "dobot/device_status", 10)
        self._joints = self.create_publisher(JointState, "joint_states", 10)
        self._tcp = self.create_publisher(PoseStamped, "dobot/tcp_pose", 10)
        self._alarms = self.create_publisher(AlarmState, "dobot/alarms", 10)
        self._suction = self.create_publisher(ToolState, "dobot/suction", 10)
        self._gripper = self.create_publisher(ToolState, "dobot/gripper", 10)
        self._timer = self.create_timer(poll_period, self._poll)

    def close_device(self):
        device, self._device = self._device, None
        self._identity = []
        self._gripper_first = False
        self._missing_pose = 0
        if device is not None:
            try:
                device.close()
            except OSError as error:
                self.get_logger().warning(f"Error closing Dobot serial port: {error}")

    def _poll(self):
        with self._device_lock:
            self._poll_device()

    def start_homing(self, *, write_guard=nullcontext):
        with self._device_lock:
            if not self._home_port or self._device is None or self._device.port != self._home_port:
                raise ValueError("Dobot is disconnected")
            try:
                if self._device.read_pose() is None:
                    raise ValueError(f"Dobot pose is unavailable ({self._device.last_reply_issue})")
                alarms = self._device.read_alarms()
                if alarms is None:
                    raise ValueError(f"Dobot alarm status is unavailable ({self._device.last_reply_issue})")
                if alarms:
                    raise ValueError(f"Resolve Dobot alarms before HOME: {alarms}")
                self.get_logger().info(f"HOME pose and alarms checked, issuing firmware command on {self._device.port}")
                self._device.start_homing(write_guard=write_guard)
                self.get_logger().info("Firmware HOME acknowledgement received")
            except OSError as error:
                self.close_device()
                raise ValueError(str(error)) from error

    def _poll_device(self):
        port = self._port
        try:
            if self._device is None:
                port = resolve_port(port, self._usb_id, self._usb_serial)
                self._device = DobotSerial(port, self._serial_timeout, hardware_home=bool(self._home_port))
            port = self._device.port
            pose = self._device.read_pose()
            if pose is None:
                reason = f"No valid Dobot pose response ({self._device.last_reply_issue})"
                self._missing_pose += 1
                if self._home_port and self._missing_pose < self._pose_retry_limit:
                    # Opening and closing the CP210x toggles its modem lines. Let the
                    # controller finish starting on this session and retry only the GET.
                    self._report_unavailable(port, reason)
                    return
                if self._home_port:
                    reason += f"; reopening port after {self._missing_pose} unsuccessful pose queries"
                    self._pose_retry_limit = min(30, self._pose_retry_limit * 2)
                raise TimeoutError(reason)
            self._pose_retry_limit = 5
            self._missing_pose = 0
            pose_stamp = self.get_clock().now().to_msg()
            if not self._home_port and not self._identity:
                self._identity = list(self._device.read_identity())
            alarms = self._device.read_alarms()
        except (OSError, ValueError) as error:
            self.close_device()
            self._report_unavailable(port, str(error))
            return

        self.home_issue = (f'Dobot alarm status unavailable ({self._device.last_reply_issue})' if alarms is None else
                           f'Resolve Dobot alarms: {alarms}' if alarms else '')
        name, serial_number, version = (self._identity + [None, None, None])[:3]
        header = Header(stamp=pose_stamp)
        self._status.publish(DeviceStatus(
            header=header, connected=True, port=port, device_name=name or "",
            serial_number=serial_number or "", firmware_version=list(version or ()),
        ))
        joints, tcp = pose_messages(pose, pose_stamp)
        self._joints.publish(joints)
        self._tcp.publish(tcp)
        self._alarms.publish(AlarmState(header=header, valid=alarms is not None, codes=alarms or []))
        try:
            self._poll_details()
        except (OSError, ValueError) as error:
            self.close_device()
            self._report_unavailable(port, str(error))

    def _poll_details(self):
        # In live mode, reserve the next poll for pose and alarms even when
        # identity or a tool does not implement its optional GET.
        deadline = monotonic() + self._detail_budget if self._home_port else None
        if self._home_port and len(self._identity) < 3:
            value = self._device.read_identity_part(len(self._identity), deadline=deadline)
            self._identity.append(value)
            return
        tools = [(self._suction, self._device.read_suction), (self._gripper, self._device.read_gripper)]
        if self._gripper_first:
            tools.reverse()
        if self._home_port:
            self._gripper_first = not self._gripper_first
        for publisher, read in tools:
            if deadline is not None and monotonic() >= deadline:
                break
            readback = read(deadline=deadline)
            enabled, active = readback if readback is not None else (False, False)
            publisher.publish(ToolState(
                header=Header(stamp=self.get_clock().now().to_msg()), valid=readback is not None,
                control_enabled=enabled, active=active,
            ))

    def _report_unavailable(self, port, reason):
        self.home_issue = reason
        self.get_logger().warning(f"Dobot unavailable: {reason}", throttle_duration_sec=5.0)
        self._status.publish(DeviceStatus(header=Header(stamp=self.get_clock().now().to_msg()), port=port))


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ReadbackNode()
        try:
            rclpy.spin(node)
        finally:
            node.close_device()
            node.destroy_node()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        rclpy.try_shutdown()
