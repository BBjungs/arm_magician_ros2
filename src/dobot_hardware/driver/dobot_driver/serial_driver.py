"""USB selection and serialized access to a Magician controller."""

from contextlib import nullcontext
from math import isfinite
import re
from threading import Lock
from time import monotonic

import serial
from serial.tools import list_ports

from .protocol.packet import FrameDecoder, HEADER, READ, checksum, encode_query
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
    def __init__(self, port: str, timeout: float, *, hardware_home=False):
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError("Serial timeout must be finite and positive")
        self.port = port
        self._timeout = timeout
        self._controller_timeout = max(timeout, 1.0) if hardware_home else timeout
        self.last_reply_issue = ''
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
        # Match the production Magician interface's asserted modem lines in live HOME mode.
        self._serial.dtr = hardware_home
        self._serial.rts = hardware_home
        self._serial.port = port
        self._serial.open()

    def close(self):
        with self._lock:
            self._serial.close()

    def read_pose(self):
        return self._query(Command.POSE)

    def read_alarms(self):
        return self._query(Command.ALARMS)

    def read_suction(self, *, deadline=None):
        return self._query(Command.SUCTION_CUP, deadline=deadline)

    def read_gripper(self, *, deadline=None):
        return self._query(Command.GRIPPER, deadline=deadline)

    def read_identity_part(self, index, *, deadline=None):
        commands = (Command.DEVICE_NAME, Command.DEVICE_SERIAL, Command.FIRMWARE_VERSION)
        return self._query(commands[index], deadline=deadline)

    def read_identity(self):
        return tuple(self.read_identity_part(index) for index in range(3))

    def _query(self, command: Command, *, deadline=None):
        if not isinstance(command, Command):
            raise ValueError("Command is outside the Dobot readback set")
        timeout = self._controller_timeout if command in (Command.POSE, Command.ALARMS) else self._timeout
        if deadline is not None:
            timeout = min(timeout, deadline - monotonic())
            if timeout <= 0:
                return None
        return self._exchange(encode_query(command), command, READ,
                              lambda data: decode_response(command, data), timeout)

    def start_homing(self, *, write_guard=nullcontext):
        """Magician SetHOMECmd(0), immediate write with a float32 zero parameter."""
        payload = bytes((31, 1, 0, 0, 0, 0))
        frame = HEADER + bytes((len(payload),)) + payload + bytes((checksum(payload),))
        def decode_ack(data):
            # Accept the empty acknowledgement or the 64-bit command index
            # used by Magician firmware. A local echo has four parameter bytes.
            if len(data) not in (0, 8):
                raise ValueError(f"Unexpected HOME acknowledgement size {len(data)}")
            return True

        if self._exchange(frame, 31, 1, decode_ack, self._controller_timeout, write_guard) is None:
            raise TimeoutError(f"HOME acknowledgement missing ({self.last_reply_issue}). "
                               "Check the arm before sending HOME again.")

    def _exchange(self, frame, command, expected_control, decode, timeout, write_guard=nullcontext):
        with self._lock:
            with write_guard():
                self._serial.reset_input_buffer()
                if self._serial.write(frame) != len(frame):
                    raise OSError("Incomplete Dobot serial write")
            deadline = monotonic() + timeout
            received = 0
            detail = ''
            decoder = FrameDecoder()
            while (remaining := deadline - monotonic()) > 0:
                self._serial.timeout = remaining
                data = self._serial.read(min(256, max(1, self._serial.in_waiting)))
                if not data:
                    break
                received += len(data)
                for response_id, control, payload in decoder.feed(data):
                    if response_id == command and control == expected_control:
                        try:
                            result = decode(payload)
                            self.last_reply_issue = ''
                            return result
                        except ValueError as error:
                            detail = str(error)
            reason = detail or ('no matching valid frame' if received else f'no bytes received in {timeout:g} s')
            self.last_reply_issue = (f'{self.port}, TX {frame.hex(" ")} ({len(frame)} bytes written), '
                                     f'RX {received} bytes: {reason}')
        return None
