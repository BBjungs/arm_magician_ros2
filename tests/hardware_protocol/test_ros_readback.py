import math
import struct
import unittest
from unittest.mock import patch

from dobot_msgs.msg import AlarmState, DeviceStatus, ToolState
from geometry_msgs.msg import PoseStamped
from rclpy.action.graph import get_action_server_names_and_types_by_node
from rclpy.executors import SingleThreadedExecutor
import rclpy
from sensor_msgs.msg import JointState

from dobot_driver.state.node import ReadbackNode
from test_protocol import FakeSerial, reply


class ReadbackNodeTests(unittest.TestCase):
    def test_ros_graph_readback_and_reconnect(self):
        wire = FakeSerial()
        wire.responses = {
            0: reply(0, b"123\0"),
            1: reply(1, b"Magician\0"),
            2: reply(2, b"\x01\x02\x03"),
            10: reply(10, struct.pack("<8f", 100, 200, 300, 90, 10, 20, 50, 40)),
            20: reply(20, bytes((0, 2)) + bytes(14)),
            62: reply(62, b"\x01\x00"),
            # Model an unsupported gripper GET until reconnect.
        }
        expected_topics = {
            "/dobot/device_status": DeviceStatus,
            "/joint_states": JointState,
            "/dobot/tcp_pose": PoseStamped,
            "/dobot/alarms": AlarmState,
            "/dobot/suction": ToolState,
            "/dobot/gripper": ToolState,
        }
        samples = {topic: [] for topic in expected_topics}
        args = ["--ros-args", "-p", "serial_port:=/dev/fake-dobot", "-p", "poll_period:=60.0"]
        with patch("dobot_driver.serial_driver.serial.Serial", return_value=wire) as transport:
            rclpy.init(args=args)
            try:
                self._exercise_node(wire, transport, expected_topics, samples)
            finally:
                rclpy.try_shutdown()

    def _exercise_node(self, wire, transport, expected_topics, samples):
        node = ReadbackNode()
        observer = rclpy.create_node("readback_observer", use_global_arguments=False)
        executor = SingleThreadedExecutor()
        executor.add_node(observer)
        try:
            subscriptions = [
                observer.create_subscription(msg, topic, samples[topic].append, 10)
                for topic, msg in expected_topics.items()
            ]
            name, namespace = node.get_name(), node.get_namespace()
            services = node.get_service_names_and_types_by_node(name, namespace)
            self.assertLessEqual({service for service, _ in services},
                                 {"/dobot_readback/get_type_description"})
            self.assertEqual(node.get_subscriber_names_and_types_by_node(name, namespace), [])
            self.assertEqual(get_action_server_names_and_types_by_node(node, name, namespace), [])
            graph_topics = dict(node.get_publisher_names_and_types_by_node(name, namespace))
            self.assertEqual(set(graph_topics) - {"/parameter_events", "/rosout"}, set(expected_topics))
            self.assertTrue(all(sub.get_publisher_count() == 1 for sub in subscriptions))
            transport.assert_not_called()

            node._poll()
            for _ in expected_topics:
                executor.spin_once(timeout_sec=1.0)
            status = samples["/dobot/device_status"][-1]
            self.assertTrue(status.connected)
            self.assertEqual(status.serial_number, "123")
            self.assertEqual(status.device_name, "Magician")
            self.assertEqual(list(status.firmware_version), [1, 2, 3])
            joints = samples["/joint_states"][-1]
            self.assertEqual(list(joints.position), list(map(math.radians, [10, 20, 30, 40])))
            tcp = samples["/dobot/tcp_pose"][-1]
            self.assertEqual(tcp.header.frame_id, "magician_base_link")
            self.assertEqual((tcp.pose.position.x, tcp.pose.position.y, tcp.pose.position.z), (0.1, 0.2, 0.3))
            self.assertAlmostEqual(tcp.pose.orientation.z, 2 ** -0.5)
            self.assertAlmostEqual(tcp.pose.orientation.w, 2 ** -0.5)
            self.assertEqual(list(samples["/dobot/alarms"][-1].codes), [9])
            self.assertTrue(samples["/dobot/suction"][-1].valid)
            self.assertFalse(samples["/dobot/gripper"][-1].valid)

            pose_reply = wire.responses.pop(10)
            node._poll()
            executor.spin_once(timeout_sec=1.0)
            self.assertTrue(wire.closed)
            self.assertFalse(samples["/dobot/device_status"][-1].connected)
            self.assertEqual(len(samples["/joint_states"]), 1)

            wire.responses.update({10: pose_reply, 63: reply(63, b"\x01\x01")})
            node._poll()
            for _ in expected_topics:
                executor.spin_once(timeout_sec=1.0)
            self.assertEqual(transport.call_count, 2)
            self.assertTrue(samples["/dobot/device_status"][-1].connected)
            self.assertTrue(samples["/dobot/gripper"][-1].active)
            self.assertEqual([frame[3] for frame in wire.writes],
                             [10, 1, 0, 2, 20, 62, 63, 10, 10, 1, 0, 2, 20, 62, 63])
            self.assertTrue(all(len(frame) == 6 and frame[4] == 0 for frame in wire.writes))
        finally:
            executor.shutdown()
            observer.destroy_node()
            node.close_device()
            node.destroy_node()
