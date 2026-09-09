import pytest
import serial

from dobot_driver.interface import Interface
from dobot_driver.message import Message


class FakeSerial:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read(self, _size):
        return next(self.chunks, b"")


def test_checksum_round_trip():
    payload = [10, 0, 1, 2, 3]
    checksum = Message.calculate_checksum(payload)
    assert Message.verify_checksum(payload, checksum)


def test_parse_rejects_truncated_message():
    assert Message.parse(b"\xaa\xaa\x02") is None


def test_read_rejects_truncated_payload_after_valid_header():
    serial = FakeSerial([b"\xaa\xaa", b"\x05", b"\x0a\x00"])
    assert Message.read(serial) is None


def test_serial_transaction_releases_lock_after_write_error(
    monkeypatch,
    tmp_path,
):
    class WritableSerial:
        out_waiting = 0

        def __init__(self, **_kwargs):
            self.fail = True
            self.is_open = True
            self.timeout = 0.01
            self.rx = bytearray()

        def write(self, payload):
            if self.fail:
                self.fail = False
                raise serial.SerialException("write failed")
            command_id = payload[3]
            control = payload[4]
            checksum = Message.calculate_checksum([command_id, control])
            self.rx.extend(bytes([0xAA, 0xAA, 2, command_id, control, checksum]))

        def read(self, size):
            data = bytes(self.rx[:size])
            del self.rx[:size]
            return data

        def flush(self):
            pass

    fake_serial = WritableSerial()
    monkeypatch.setattr(serial, "Serial", lambda **_kwargs: fake_serial)
    monkeypatch.setenv(
        "DOBOT_SERIAL_LOCK_PATH",
        str(tmp_path / "serial.lock"),
    )
    interface = Interface("/dev/fake-dobot")
    message = Message([0xAA, 0xAA], 2, 31, True, False, [0], direction="out")

    with pytest.raises(serial.SerialException, match="write failed"):
        interface.send_only(message)

    interface.send_only(message)
