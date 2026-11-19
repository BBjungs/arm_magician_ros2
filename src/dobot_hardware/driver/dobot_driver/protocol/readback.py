"""Command IDs and GET response payloads from the Magician wire protocol."""

from enum import IntEnum
from math import isfinite
import struct


class Command(IntEnum):
    DEVICE_SERIAL = 0
    DEVICE_NAME = 1
    FIRMWARE_VERSION = 2
    POSE = 10
    ALARMS = 20
    SUCTION_CUP = 62
    GRIPPER = 63


def decode_response(command: Command, payload: bytes):
    """Raise ValueError for malformed or non-finite readbacks."""
    if command in (Command.DEVICE_SERIAL, Command.DEVICE_NAME):
        if not payload:
            raise ValueError("Device identity response is empty")
        return payload.split(b"\0", 1)[0].decode("ascii")

    if command == Command.FIRMWARE_VERSION:
        # Firmware replies may include a suffix after the first three bytes.
        if len(payload) < 3:
            raise ValueError("Firmware version needs three components")
        return tuple(payload[:3])

    if command == Command.POSE:
        if len(payload) != 32:
            raise ValueError("Pose response must be eight float32 values")
        pose = struct.unpack("<8f", payload)
        if not all(map(isfinite, pose)):
            raise ValueError("Pose contains a non-finite value")
        return pose

    if command == Command.ALARMS:
        if len(payload) != 16:
            raise ValueError("Alarm response must be a 128-bit bitmap")
        return [byte_index * 8 + bit
                for byte_index, value in enumerate(payload)
                for bit in range(8) if value & (1 << bit)]

    if command in (Command.SUCTION_CUP, Command.GRIPPER):
        if len(payload) != 2 or any(value not in (0, 1) for value in payload):
            raise ValueError("Tool response must contain two boolean bytes")
        return bool(payload[0]), bool(payload[1])

    raise ValueError(f"Unsupported readback ID {command}")
