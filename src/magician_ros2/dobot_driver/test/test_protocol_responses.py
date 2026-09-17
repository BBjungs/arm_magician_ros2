import os
import struct

import pytest

import dobot_driver.interface as driver
from dobot_driver.interface import Interface
from dobot_driver.message import Message


def response_frame(command_id, control, params=b""):
    payload = bytes([command_id, control]) + bytes(params)
    checksum = Message.calculate_checksum(payload)
    return b"\xaa\xaa" + bytes([len(payload)]) + payload + bytes([checksum])


class BufferedSerial:
    out_waiting = 0
    is_open = True
    timeout = 0.01

    def __init__(self, responder=None):
        self.responder = responder
        self.rx = bytearray()
        self.writes = []

    def write(self, payload):
        self.writes.append(bytes(payload))
        if self.responder is not None:
            reply = self.responder(bytes(payload), len(self.writes))
            if reply:
                self.rx.extend(reply)

    def flush(self):
        pass

    def read(self, size):
        data = bytes(self.rx[:size])
        del self.rx[:size]
        return data

    def reset_output_buffer(self):
        pass

    def reset_input_buffer(self):
        self.rx.clear()


def make_interface(monkeypatch, tmp_path, fake_serial):
    monkeypatch.setattr(driver.serial, "Serial", lambda **_kwargs: fake_serial)
    monkeypatch.setenv("DOBOT_SERIAL_LOCK_PATH", str(tmp_path / "serial.lock"))
    return Interface("/dev/fake-dobot")


@pytest.mark.parametrize("command_id", [80, 81, 83, 84])
def test_nonqueued_ptp_ack_is_empty_and_parseable(command_id):
    parsed = Message.parse(response_frame(command_id, 1))
    assert parsed is not None
    assert parsed.id == command_id
    assert parsed.rw is True
    assert parsed.is_queued is False
    assert parsed.params == []


def test_verified_getter_payloads_and_lengths():
    assert Message.parse(
        response_frame(60, 0, struct.pack("<fff", 59.7, 0.0, -3.25))
    ).params == pytest.approx((59.7, 0.0, -3.25))
    assert Message.parse(response_frame(62, 0, b"\x01\x01")).params == (
        True,
        True,
    )
    assert Message.parse(response_frame(63, 0, b"\x01\x00")).params == (
        True,
        False,
    )
    assert Message.parse(
        response_frame(80, 0, struct.pack("<8f", *range(8)))
    ).params == pytest.approx(tuple(range(8)))
    assert Message.parse(
        response_frame(81, 0, struct.pack("<4f", *range(4)))
    ).params == pytest.approx(tuple(range(4)))
    assert Message.parse(
        response_frame(83, 0, struct.pack("<2f", 25.0, 30.0))
    ).params == pytest.approx((25.0, 30.0))
    assert Message.parse(
        response_frame(246, 0, struct.pack("<Q", 123456))
    ).params == 123456


def test_bad_payload_length_and_checksum_are_rejected():
    assert Message.parse(response_frame(62, 0, b"\x01")) is None
    damaged = bytearray(response_frame(84, 1))
    damaged[-1] ^= 0x01
    assert Message.parse(bytes(damaged)) is None


def test_reader_resynchronizes_and_returns_only_expected_id():
    bad = bytearray(response_frame(83, 1))
    bad[-1] ^= 0x01
    stream = BufferedSerial()
    stream.rx.extend(
        b"noise"
        + bytes(bad)
        + response_frame(80, 1)
        + response_frame(84, 1)
    )
    response = Message.read(
        stream,
        expected_id=84,
        expected_rw=True,
        expected_is_queued=False,
        timeout=0.1,
    )
    assert response is not None
    assert response.id == 84


def test_back_to_back_ptp_commands_leave_alarm_reply_synchronized(
    monkeypatch,
    tmp_path,
):
    def responder(request, _count):
        command_id = request[3]
        control = request[4]
        if command_id == 20:
            return response_frame(20, 0, bytes(16))
        return response_frame(command_id, control)

    fake = BufferedSerial(responder)
    interface = make_interface(monkeypatch, tmp_path, fake)

    assert interface.set_point_to_point_common_params(10, 10) == []
    assert interface.set_point_to_point_command(
        2, 54.0, 166.0, 122.0, 72.0
    ) == []
    assert interface.get_alarms_state() == tuple([0] * 16)
    assert [packet[3] for packet in fake.writes] == [83, 84, 20]
    assert fake.rx == b""


def test_suction_and_gripper_ids_and_feedback_remain_isolated(
    monkeypatch,
    tmp_path,
):
    states = {62: b"\x01\x01", 63: b"\x01\x00"}

    def responder(request, _count):
        command_id = request[3]
        control = request[4]
        params = states[command_id] if control == 0 else b""
        return response_frame(command_id, control, params)

    fake = BufferedSerial(responder)
    interface = make_interface(monkeypatch, tmp_path, fake)

    assert interface.set_end_effector_suction_cup(True, True) == []
    assert interface.get_end_effector_suction_cup() == (True, True)
    assert interface.set_end_effector_gripper(True, False) == []
    assert interface.get_end_effector_gripper() == (True, False)
    assert [packet[3] for packet in fake.writes] == [62, 62, 63, 63]


def test_queue_index_is_a_getter_and_parses_uint64(monkeypatch, tmp_path):
    def responder(request, _count):
        assert request[3] == 246
        assert request[4] == 0
        return response_frame(246, 0, struct.pack("<Q", 987654321))

    fake = BufferedSerial(responder)
    interface = make_interface(monkeypatch, tmp_path, fake)
    assert interface.get_current_queue_index() == 987654321


def test_ack_timeout_is_bounded_and_next_command_recovers(
    monkeypatch,
    tmp_path,
):
    def responder(request, count):
        if count == 1:
            return None
        return response_frame(request[3], request[4])

    fake = BufferedSerial(responder)
    interface = make_interface(monkeypatch, tmp_path, fake)

    with pytest.raises(TimeoutError, match="command ID 83"):
        interface.set_point_to_point_common_params(10, 10)
    assert interface.set_point_to_point_common_params(10, 10) == []
