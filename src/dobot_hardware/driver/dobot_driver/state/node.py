"""Publish controller readbacks without accepting device commands."""

import math

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
    def __init__(self):
        super().__init__("dobot_readback", start_parameter_services=False)
        self._port = self.declare_parameter(
            "serial_port", "", ParameterDescriptor(read_only=True)
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
            "poll_period", 0.5, ParameterDescriptor(read_only=True)
        ).value
        for name, value in (("serial_timeout", self._serial_timeout), ("poll_period", poll_period)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

        self._device = None
        self._identity = None
        self._status = self.create_publisher(DeviceStatus, "dobot/device_status", 10)
        self._joints = self.create_publisher(JointState, "joint_states", 10)
        self._tcp = self.create_publisher(PoseStamped, "dobot/tcp_pose", 10)
        self._alarms = self.create_publisher(AlarmState, "dobot/alarms", 10)
        self._suction = self.create_publisher(ToolState, "dobot/suction", 10)
        self._gripper = self.create_publisher(ToolState, "dobot/gripper", 10)
        self._timer = self.create_timer(poll_period, self._poll)

    def close_device(self):
        device, self._device = self._device, None
        self._identity = None
        if device is not None:
            try:
                device.close()
            except OSError as error:
                self.get_logger().warning(f"Error closing Dobot serial port: {error}")

    def _poll(self):
        port = self._port
        try:
            if self._device is None:
                port = resolve_port(port, self._usb_id, self._usb_serial)
                self._device = DobotSerial(port, self._serial_timeout)
            port = self._device.port
            pose = self._device.read_pose()
            if pose is None:
                raise TimeoutError("No valid Dobot pose response")
            pose_stamp = self.get_clock().now().to_msg()
            if self._identity is None:
                self._identity = self._device.read_identity()
            alarms = self._device.read_alarms()
            suction = self._device.read_suction()
            gripper = self._device.read_gripper()
        except (OSError, ValueError) as error:
            self.close_device()
            self.get_logger().warning(f"Dobot unavailable: {error}", throttle_duration_sec=5.0)
            self._status.publish(DeviceStatus(
                header=Header(stamp=self.get_clock().now().to_msg()), port=port,
            ))
            return

        name, serial_number, version = self._identity
        header = Header(stamp=pose_stamp)
        self._status.publish(DeviceStatus(
            header=header, connected=True, port=port, device_name=name or "",
            serial_number=serial_number or "", firmware_version=list(version or ()),
        ))
        joints, tcp = pose_messages(pose, pose_stamp)
        self._joints.publish(joints)
        self._tcp.publish(tcp)
        self._alarms.publish(AlarmState(header=header, valid=alarms is not None, codes=alarms or []))
        for publisher, readback in ((self._suction, suction), (self._gripper, gripper)):
            enabled, active = readback if readback is not None else (False, False)
            publisher.publish(ToolState(
                header=header, valid=readback is not None, control_enabled=enabled, active=active,
            ))


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
