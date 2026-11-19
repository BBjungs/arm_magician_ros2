"""Dobot Magician serial frame codec, independent of the transport."""

from collections.abc import Iterator

HEADER = b"\xaa\xaa"
READ = 0


def checksum(payload: bytes) -> int:
    return -sum(payload) & 0xFF


def encode_query(command: int) -> bytes:
    """Encode a non-queued GET with no parameters."""
    payload = bytes((command, READ))
    return HEADER + bytes((len(payload),)) + payload + bytes((checksum(payload),))


class FrameDecoder:
    """Extract checksum-valid frames from a stream, retaining incomplete data."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes) -> Iterator[tuple[int, int, bytes]]:
        self._buffer.extend(data)
        while True:
            start = self._buffer.find(HEADER)
            if start < 0:
                self._buffer[:] = b"\xaa" if self._buffer.endswith(b"\xaa") else b""
                return
            del self._buffer[:start]

            if len(self._buffer) < 3:
                return
            size = self._buffer[2]
            if size < 2:
                del self._buffer[0]
                continue
            end = size + 4
            if len(self._buffer) < end:
                return

            payload = self._buffer[3:end - 1]
            command, control = payload[:2]
            if control > 3 or checksum(payload) != self._buffer[end - 1]:
                del self._buffer[0]
                continue
            del self._buffer[:end]
            yield command, control, bytes(payload[2:])
