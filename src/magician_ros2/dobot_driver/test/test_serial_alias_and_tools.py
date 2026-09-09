import os
from unittest.mock import Mock

from dobot_driver.interface import Interface
import dobot_driver.interface as driver


def test_serial_aliases_use_one_process_lock(tmp_path, monkeypatch):
    device = tmp_path / 'device'
    device.touch()
    alias = tmp_path / 'stable-device-id'
    alias.symlink_to(device)
    monkeypatch.delenv('DOBOT_SERIAL_LOCK_PATH', raising=False)
    monkeypatch.setattr(driver.serial, 'Serial', Mock())
    real_open = os.open
    def open_in_tmp(path, flags, mode):
        return real_open(tmp_path / os.path.basename(path), flags, mode)
    monkeypatch.setattr(driver.os, 'open', open_in_tmp)
    instances = []
    try:
        instances.extend([Interface(str(device)), Interface(str(alias))])
        assert os.fstat(instances[0]._process_lock_fd).st_ino == os.fstat(instances[1]._process_lock_fd).st_ino
    finally:
        for instance in instances:
            os.close(instance._process_lock_fd)


def test_suction_and_gripper_use_distinct_protocol_commands():
    interface = object.__new__(Interface)
    interface.send_only = Mock()
    packets = []
    for method in [interface.set_end_effector_suction_cup, interface.set_end_effector_gripper]:
        for enabled in [True, False]:
            method(enabled, enabled)
            packet = list(interface.send_only.call_args.args[0].package())
            packets.append(packet[3])
            assert packet[5:7] == [int(enabled), int(enabled)]
    assert packets == [62, 62, 63, 63]
