"""No hardware: partial construction, failure logging, and configuration audit."""
from pathlib import Path
from unittest.mock import Mock

import pytest
import rclpy
from rclpy.node import Node

from dobot_calibration.node_lifecycle import node_lifecycle
from dobot_calibration import startup_preflight
from dobot_calibration.node import CalibrationNode, _stop_workers


def test_partial_constructor_preserves_traceback_and_releases_ros(tmp_path, monkeypatch):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    destroyed = Mock()
    class Broken(Node):
        def __init__(self):
            super().__init__('broken_fixture')
            raise ValueError('injected constructor failure')
        def destroy_node(self):
            destroyed()
            return super().destroy_node()
    with pytest.raises(ValueError, match='injected constructor'):
        with node_lifecycle(Broken):
            pytest.fail('must not yield')
    destroyed.assert_called_once()
    assert not rclpy.ok()
    log = (tmp_path / 'startup-failures.log').read_text()
    assert 'Traceback' in log and '__init__' in log and 'injected constructor failure' in log
    # The same process can initialize a new ROS context after failure.
    rclpy.init()
    rclpy.shutdown()


def test_preflight_checks_generated_native_support_without_ros_init():
    assert not rclpy.ok()
    startup_preflight.check_installation()
    assert not rclpy.ok()


def test_missing_generated_interface_is_nonretryable(tmp_path, monkeypatch):
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    import dobot_msgs.srv
    monkeypatch.delattr(dobot_msgs.srv, 'SelectCalibrationObject')
    assert startup_preflight.main() == 78
    assert 'SelectCalibrationObject' in (tmp_path / 'startup-failures.log').read_text()


def test_commissioning_disables_saved_object_timer_before_file_access(monkeypatch):
    with node_lifecycle(CalibrationNode, ['--ros-args', '-p',
                         'object_startup_restore:=false'], _stop_workers) as node:
        monkeypatch.setattr('dobot_calibration.node.np.load',
                            Mock(side_effect=AssertionError('must not load a bundle')))
        node._restore_object_on_startup()
        assert not node.object_startup_attempted
        assert not node.auto_pending
        assert node.automatic.worker is None


def test_restart_policy_covers_slow_startup_and_configuration_failure():
    root = Path(__file__).resolve().parents[4]
    unit = (root / 'systemd/dobot-magician.service').read_text()
    assert 'StartLimitIntervalSec=3600' in unit
    assert 'StartLimitBurst=3' in unit
    assert 'RestartPreventExitStatus=78' in unit
    script = (root / 'scripts/start_dobot_autostart.sh').read_text()
    assert script.index('-m dobot_calibration.startup_preflight') < script.index('wait_for_path "${DOBOT_SERIAL_PORT}"')
