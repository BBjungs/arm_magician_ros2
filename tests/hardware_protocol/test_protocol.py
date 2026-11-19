import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dobot_driver.protocol.packet import FrameDecoder, encode_query
from dobot_driver.protocol.readback import Command, decode_response
from dobot_driver.serial_driver import DobotSerial, resolve_port


def reply(command, payload, control=0):
    body = bytes((command, control)) + payload
    return b"\xaa\xaa" + bytes((len(body),)) + body + bytes(((-sum(body)) % 256,))


class FakeSerial:
    def __init__(self):
        self._input = b""
        self.writes = []
        self.responses = {}
        self.closed = False

    def open(self):
        self.closed = False

    def close(self):
        self.closed = True

    def reset_input_buffer(self):
        self._input = b""

    @property
    def in_waiting(self):
        return min(len(self._input), 2)

    def write(self, frame):
        self.writes.append(frame)
        self._input += self.responses.get(frame[3], b"")
        return len(frame)

    def read(self, size):
        data, self._input = self._input[:size], self._input[size:]
        return data


class ProtocolTests(unittest.TestCase):
    def test_get_frames(self):
        self.assertEqual(encode_query(Command.POSE), bytes.fromhex("aa aa 02 0a 00 f6"))
        self.assertEqual(encode_query(Command.SUCTION_CUP), bytes.fromhex("aa aa 02 3e 00 c2"))
        self.assertEqual(encode_query(Command.GRIPPER), bytes.fromhex("aa aa 02 3f 00 c1"))

    def test_decode_fragmented_and_corrupt_frames(self):
        good = reply(62, b"\x01\x00")
        bad = good[:-1] + bytes((good[-1] ^ 1,))
        decoder = FrameDecoder()
        self.assertEqual(list(decoder.feed(b"noise" + bad + good[:1])), [])
        self.assertEqual(list(decoder.feed(good[1:-1])), [])
        self.assertEqual(list(decoder.feed(good[-1:] + good)), [(62, 0, b"\x01\x00")] * 2)

    def test_fragmented_payload_can_contain_header(self):
        payload = reply(0, b"") + bytes(10)
        frame = reply(20, payload)
        decoder = FrameDecoder()
        self.assertEqual(list(decoder.feed(frame[:-1])), [])
        self.assertEqual(list(decoder.feed(frame[-1:])), [(20, 0, payload)])

    def test_decode_identity_pose_alarms_and_tools(self):
        pose = (100.0, 200.0, -30.0, 45.0, 1.0, 2.0, 3.0, -4.0)
        self.assertEqual(decode_response(Command.POSE, struct.pack("<8f", *pose)), pose)
        self.assertEqual(decode_response(Command.DEVICE_SERIAL, b"123\0"), "123")
        self.assertEqual(decode_response(Command.DEVICE_NAME, b"Magician\0"), "Magician")
        self.assertEqual(decode_response(Command.FIRMWARE_VERSION, b"\x01\x02\x03\x00"), (1, 2, 3))
        alarms = bytes((1, 128)) + bytes(13) + b"\x80"
        self.assertEqual(decode_response(Command.ALARMS, alarms), [0, 15, 127])
        self.assertEqual(decode_response(Command.SUCTION_CUP, b"\x01\x00"), (True, False))
        self.assertEqual(decode_response(Command.GRIPPER, b"\x01\x01"), (True, True))

    def test_invalid_payloads(self):
        invalid = [
            (Command.FIRMWARE_VERSION, b"\x01\x02"),
            (Command.DEVICE_NAME, b"\xff"),
            (Command.POSE, bytes(31)),
            (Command.POSE, struct.pack("<8f", float("nan"), *([0] * 7))),
            (Command.ALARMS, bytes(15)),
            (Command.GRIPPER, b"\x01\x02"),
            (Command.SUCTION_CUP, b"\x01"),
        ]
        for command, payload in invalid:
            with self.subTest(command=command, payload=payload), self.assertRaises(ValueError):
                decode_response(command, payload)


class SerialTests(unittest.TestCase):
    def test_port_selection_requires_unique_identifier(self):
        first = SimpleNamespace(device="first", vid=0x1234, pid=0x4321, serial_number="A")
        second = SimpleNamespace(device="second", vid=0x1234, pid=0x4321, serial_number="B")
        with patch("dobot_driver.serial_driver.list_ports.comports", return_value=[first, second]):
            self.assertEqual(resolve_port("/dev/example", "", ""), "/dev/example")
            self.assertEqual(resolve_port("", "1234:4321", "A"), "first")
            for usb_id, usb_serial in [("", ""), ("4321:1234", ""), ("1234:4321", "")]:
                with self.subTest(usb_id=usb_id), self.assertRaises(OSError):
                    resolve_port("", usb_id, usb_serial)
            with self.assertRaises(ValueError):
                resolve_port("", "invalid", "")

    def test_get_only_transport_filters_frames_and_times_out(self):
        wire = FakeSerial()
        wire.responses[62] = (
            reply(63, b"\x01\x01")
            + reply(62, b"\x01\x01", control=1)
            + reply(62, b"\x02\x00")
            + reply(62, b"\x01\x00")
        )
        with patch("dobot_driver.serial_driver.serial.Serial", return_value=wire) as transport:
            device = DobotSerial("fake", timeout=0.05)
            self.assertTrue(transport.call_args.kwargs["exclusive"])
            self.assertEqual(wire.writes, [])
            self.assertEqual(device.read_suction(), (True, False))
            self.assertIsNone(device.read_gripper())
            with self.assertRaises(ValueError):
                device._query(84)
            self.assertEqual(wire.writes, [encode_query(Command.SUCTION_CUP), encode_query(Command.GRIPPER)])
            device.close()
            self.assertTrue(wire.closed)
