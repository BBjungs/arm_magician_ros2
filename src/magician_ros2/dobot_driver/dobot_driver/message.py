import struct
import time

from dobot_driver.parsers import parsers

class Message:
    def __init__(self, header, length, id, rw, is_queued, params, direction='in'):
        self.header = header
        self.length = length
        self.id = id
        self.rw = rw
        self.is_queued = is_queued
        self.raw_params = []
        self.params = []

        if direction == 'in':
            self.raw_params = params
            self.params = self.parse_params('in')
        elif direction == 'out':
            self.params = params
            self.raw_params = self.parse_params('out')

    @staticmethod
    def calculate_checksum(payload):
        r = sum(payload) % 256
        # Calculate the two's complement
        check_byte = (256 - r) % 256
        return check_byte

    @staticmethod
    def verify_checksum(payload, checksum):
        a = sum(payload) % 256
        is_correct = True if (a + checksum) % 256 == 0 else False
        return is_correct

    @staticmethod
    def parse(message):
        message_bytes = list(message)

        if len(message_bytes) < 6:
            return None

        header = message_bytes[0:2]
        if header != [0xAA, 0xAA]:
            return None
        length = message_bytes[2]
        if len(message_bytes) != length + 4:
            return None
        id = message_bytes[3]
        control = message_bytes[4]
        rw = (control & 1) == 1
        is_queued = ((control & 2) >> 1) == 1
        params = message_bytes[5:-1]
        checksum = message_bytes[-1]

        if control & ~0x03 or id not in parsers:
            return None
        if not Message.verify_checksum([id] + [control] + params, checksum):
            return None

        try:
            return Message(header, length, id, rw, is_queued, params)
        except (IndexError, struct.error, TypeError, ValueError):
            return None

    @staticmethod
    def _read_exact(serial, size, deadline):
        data = bytearray()
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            original_timeout = getattr(serial, "timeout", None)
            if hasattr(serial, "timeout"):
                serial.timeout = remaining if original_timeout is None else min(original_timeout, remaining)
            try:
                chunk = serial.read(size - len(data))
            finally:
                if hasattr(serial, "timeout"):
                    serial.timeout = original_timeout
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    @staticmethod
    def read(serial, expected_id=None, expected_rw=None, expected_is_queued=None, timeout=None):
        """Read one matching, checksum-valid packet within a bounded timeout."""
        if timeout is None:
            timeout = getattr(serial, "timeout", None)
        timeout = 1.0 if timeout is None else float(timeout)
        deadline = time.monotonic() + max(0.0, timeout)
        saw_aa = False
        while time.monotonic() < deadline:
            byte = Message._read_exact(serial, 1, deadline)
            if byte is None:
                return None
            if byte == b"\xaa":
                if not saw_aa:
                    saw_aa = True
                    continue
            else:
                saw_aa = False
                continue
            length_data = Message._read_exact(serial, 1, deadline)
            if length_data is None:
                return None
            length = length_data[0]
            if length < 2:
                saw_aa = False
                continue
            payload_and_checksum = Message._read_exact(serial, length + 1, deadline)
            if payload_and_checksum is None:
                return None
            response = Message.parse(b"\xaa\xaa" + length_data + payload_and_checksum)
            saw_aa = False
            if response is None:
                continue
            if expected_id is not None and response.id != expected_id:
                continue
            if expected_rw is not None and response.rw != expected_rw:
                continue
            if expected_is_queued is not None and response.is_queued != expected_is_queued:
                continue
            return response
        return None

    def parse_params(self, direction):
        message_parsers = parsers[self.id]

        if direction == 'in':
            if message_parsers is None:
                return None

            parser = None
            if self.rw == 0 and self.is_queued == 0:
                parser = message_parsers[0]
            elif self.rw == 1 and self.is_queued == 0:
                parser = message_parsers[1]
            elif self.rw == 1 and self.is_queued == 1:
                parser = message_parsers[2]

            if parser is None:
                return []

            return parser(self.raw_params)
        elif direction == 'out':
            if message_parsers is None:
                return []

            parser = None
            if direction == 'out' and self.rw == 1:
                parser = message_parsers[3]

            if parser is None:
                return []

            return parser(self.params)

    def package(self):
        self.length = 2 + len(self.raw_params)
        control = int('000000' + str(int(self.is_queued)) + str(int(self.rw)), 2)
        self.checksum = Message.calculate_checksum([self.id] + [control] + self.raw_params)

        result = bytes(self.header + [self.length] + [self.id] + [control] + self.raw_params + [self.checksum])

        return result
