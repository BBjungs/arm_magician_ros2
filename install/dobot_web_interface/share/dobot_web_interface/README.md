# Dobot Web Interface

Browser control panel for Dobot Magician with a live MJPEG camera view.

## Run

```bash
cd /home/bbcontact/magician_ros2
source /opt/ros/jazzy/setup.bash
source install/setup.bash

ros2 launch dobot_web_interface dobot_auto.launch.py \
  start_bringup:=false start_camera:=true start_vision:=false \
  host:=127.0.0.1 port:=8080
```

Open:

```text
http://<robot-ip>:8080/
```

## Dobot Control Stack

Run the Dobot control stack in another terminal before using motion or tool buttons:

```bash
cd /home/bbcontact/magician_ros2
source /opt/ros/jazzy/setup.bash
source install/setup.bash

export MAGICIAN_TOOL=extended_gripper
ros2 launch dobot_bringup dobot_magician_control_system.launch.py
```

## Camera Topics

The default camera is the Orbbec Gemini from
`https://github.com/BBjungs/orbbec_camera.git`. `dobot_auto.launch.py` starts
`orbbec_camera/ob_camera.launch.py` with registered color and depth streams.
The web interface listens to the color topics and factory CameraInfo below:

```text
/camera/color/image_raw
/camera/color/image_raw/compressed
/camera/color/camera_info
/camera/depth/image_raw
```

Direct V4L2 capture is disabled by default to avoid opening the same Orbbec
device twice. A non-Orbbec USB camera remains available as an explicit fallback:

```bash
ros2 launch dobot_web_interface dobot_web_interface.launch.py \
  camera_device:=/dev/video0
```

## Autostart

Autostart settings live in:

```text
/home/bbcontact/magician_ros2/config/dobot-autostart.env
```

The user service file is:

```text
/home/bbcontact/magician_ros2/systemd/dobot-magician.service
```

After installing the user service:

```bash
systemctl --user status dobot-magician.service
systemctl --user restart dobot-magician.service
journalctl --user -u dobot-magician.service -f
```

## HTTP API

```text
GET  /api/status
GET  /stream
GET  /api/snapshot
POST /api/homing
POST /api/move
POST /api/cancel
POST /api/gripper
POST /api/suction
GET  /api/vision/calibration/board.svg?mode=fixed_camera
POST /api/vision/calibration/auto
```

The Calibration page uses a one-click multi-frame process. Manual U/V/X/Y entry
is retained under the advanced section for commissioning and recovery only.
Factory lens calibration is read automatically from
`/camera/color/camera_info` when that topic is available; direct USB cameras
fall back to the configured intrinsics YAML.

The default bind address is `127.0.0.1`. To expose the control API on the LAN,
set `DOBOT_WEB_API_TOKEN` to a long random value and launch with `host:=0.0.0.0`.
The browser uses HTTP Basic Authentication with username `dobot` and the token
as its password. Startup fails closed when a non-loopback host has no token.
