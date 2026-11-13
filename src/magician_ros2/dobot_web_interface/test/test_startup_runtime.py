"""Real installed entry points; private DDS domain, no camera/robot processes."""
import base64
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.request import Request, urlopen

import pytest
from ament_index_python.packages import get_package_prefix


def executable(package, name):
    return str(Path(get_package_prefix(package)) / 'lib' / package / name)


def environment(tmp_path):
    env = os.environ.copy()
    env.update(ROS_DOMAIN_ID='193', ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST',
               RMW_IMPLEMENTATION='rmw_cyclonedds_cpp', ROS_LOG_DIR=str(tmp_path),
               DOBOT_MAINTENANCE_TOKEN='startup-test', OPENBLAS_NUM_THREADS='1')
    return env


def stop(process):
    if process.poll() is None:
        # Launch forwards SIGINT to children; do not send each child two signals.
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            pytest.fail('Startup fixture failed graceful shutdown')


def test_installed_launch_http_object_services_and_clean_restart(tmp_path):
    # Production service stays stopped; the launch contains ONLY these two nodes.
    with socket.socket() as port_check:
        port_check.bind(('127.0.0.1', 8080))
    command = ['ros2', 'launch', 'dobot_web_interface', 'dobot_auto.launch.py',
               'start_bringup:=false', 'start_camera:=false', 'start_vision:=false',
               'start_calibration:=true', 'startup_auto:=false',
               'startup_auto_recalibrate:=false', 'startup_auto_motion:=false',
               'enable_camera_preview:=false', 'host:=127.0.0.1', 'port:=8080',
               'calibration_file:=' + str(tmp_path / 'missing.npz')]
    for cycle in range(2):
        log = tmp_path / f'launch-{cycle}.log'
        with log.open('w') as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                       env=environment(tmp_path), start_new_session=True)
            try:
                deadline = time.monotonic() + 30
                while True:
                    assert process.poll() is None, log.read_text()
                    try:
                        with urlopen('http://127.0.0.1:8080/api/system/status', timeout=1) as reply:
                            status = json.load(reply)
                        break
                    except OSError:
                        assert time.monotonic() < deadline, log.read_text()
                        time.sleep(.2)
                assert status['motion_mode'] == 'DRY_RUN'
                assert not status['runtime']['robot_connected']
                assert not status['runtime']['calibration_verified']
                with urlopen('http://127.0.0.1:8080/static/object_calibration.js') as reply:
                    assert reply.status == 200
                request = Request('http://127.0.0.1:8080/api/calibration/object/select',
                    data=b'{}', headers={'Content-Type': 'application/json',
                    'Authorization': 'Basic ' + base64.b64encode(b'maintenance:startup-test').decode()})
                with urlopen(request, timeout=10) as reply:
                    result = json.load(reply)
                # A live service must reject missing sensor evidence, not invent readiness.
                assert not result['accepted'] and not result['motion_command_sent'], result
                assert 'OBJECT_DETECTIONS_STALE' in json.dumps(result), result
                time.sleep(3)  # Includes the saved-object timer deadline.
                assert process.poll() is None
            finally:
                stop(process)
        assert process.returncode == 0, log.read_text()
        assert 'Traceback' not in log.read_text(), log.read_text()


def test_constructor_failure_is_logged_and_not_hidden(tmp_path):
    command = [executable('dobot_calibration', 'markerless_calibration'),
               '--ros-args', '-p', 'ready_ttl_s:=-1.0']
    result = subprocess.run(command, env=environment(tmp_path), capture_output=True,
                            text=True, timeout=15)
    assert result.returncode != 0
    log = (tmp_path / 'startup-failures.log').read_text()
    assert 'ready_ttl_s must be finite and positive' in log
    assert '__init__' in log and 'Traceback' in result.stderr


def test_http_bind_failure_exits_and_records_traceback(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        command = [executable('dobot_web_interface', 'web_interface'), '--ros-args',
                   '-p', f'port:={port}', '-p', 'host:=127.0.0.1',
                   '-p', 'startup_auto:=false', '-p', 'startup_auto_motion:=false',
                   '-p', 'enable_camera_preview:=false']
        result = subprocess.run(command, env=environment(tmp_path), capture_output=True,
                                text=True, timeout=15)
    assert result.returncode != 0
    assert 'address already in use' in result.stderr
    assert 'SystemExit' in (tmp_path / 'startup-failures.log').read_text()
