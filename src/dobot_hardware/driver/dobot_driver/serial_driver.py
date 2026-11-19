"""USB selection and serialized read-only access to a Magician controller."""

from math import isfinite
import re
from threading import Lock
from time import monotonic

import serial
from serial.tools import list_ports

from .protocol.packet import FrameDecoder, READ, encode_query
from .protocol.readback import Command, decode_response


def resolve_port(path: str, usb_id: str, usb_serial_number: str) -> str:
    if path:
        return path
    if not usb_id:
        raise OSError("Configure serial_port or a USB VID:PID to select the Dobot")
    if not re.fullmatch(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{4}", usb_id):
        raise ValueError("usb_id must have the form VID:PID in hexadecimal")

    vendor, product = (int(part, 16) for part in usb_id.split(":"))
    matches = [port.device for port in list_ports.comports()
               if (port.vid, port.pid) == (vendor, product)
               and (not usb_serial_number or port.serial_number == usb_serial_number)]
    if len(matches) != 1:
        raise OSError(f"Expected one USB serial match for {usb_id}, found {len(matches)}")
    return matches[0]


class DobotSerial:
    def __init__(self, port: str, timeout: float):
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError("Serial timeout must be finite and positive")
        self.port = port
        self._timeout = timeout
        self._lock = Lock()
        self._serial = serial.Serial(
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
            exclusive=True,
        )
        self._serial.dtr = False
        self._serial.rts = False
        self._serial.port = port
        self._serial.open()

    def close(self):
        with self._lock:
            self._serial.close()

    def read_pose(self):
        return self._query(Command.POSE)

    def read_alarms(self):
        return self._query(Command.ALARMS)

    def read_suction(self):
        return self._query(Command.SUCTION_CUP)

    def read_gripper(self):
        return self._query(Command.GRIPPER)

    def read_identity(self):
        return (
            self._query(Command.DEVICE_NAME),
            self._query(Command.DEVICE_SERIAL),
            self._query(Command.FIRMWARE_VERSION),
        )

    def _query(self, command: Command):
        if not isinstance(command, Command):
            raise ValueError("Command is outside the Dobot readback set")
        frame = encode_query(command)
        with self._lock:
            self._serial.reset_input_buffer()
            if self._serial.write(frame) != len(frame):
                raise OSError("Incomplete Dobot serial write")
            deadline = monotonic() + self._timeout
            decoder = FrameDecoder()
            while (remaining := deadline - monotonic()) > 0:
                self._serial.timeout = remaining
                data = self._serial.read(min(256, max(1, self._serial.in_waiting)))
                if not data:
                    break
                for response_id, control, payload in decoder.feed(data):
                    if response_id == command and control == READ:
                        try:
                            return decode_response(command, payload)
                        except ValueError:
                            continue
        return None
