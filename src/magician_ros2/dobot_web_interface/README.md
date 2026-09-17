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

The root page is the Thai operator screen.  Its normal flow is
**เลือกชิ้นงาน → ตำแหน่งวาง → เริ่มทำงาน** and it shows only the camera,
safe readiness, object counts, and job progress.

The operator Stop command calls the vision cancellation path, which also
requests cancellation of the active robot motion.

## Integrated startup and readiness

`dobot_auto.launch.py` enables the full-cell gate by default.  It admits a
real pick only in this deterministic order:

```text
robot services + fresh joints → live camera → synchronized valid RGB-D
→ fresh calibration PASS → HOME → observation pose → ready
```

The launch starts the calibration verifier idle; it does not move the robot on
its own. On the operator page, press **ตรวจระบบ** to request startup
verification, then **HOME และจุดสังเกต** after the work area is clear.  The
HOME request returns the robot to the configured observation pose before
pick-all can begin.  `startup_auto:=true startup_auto_motion:=true` is an
explicit opt-in for a supervised installation that authorizes automatic HOME
and observation motion.

The backend publishes the same decision at `GET /api/system/status`. A stale
camera/depth frame, Dobot service or joint-telemetry loss, calibration failure,
or failed observation return latches a fault, cancels active motion, and blocks
new jobs until startup is repeated. `/api/cancel`, the operator Stop button,
and `/api/vision/cancel` all reach the active sequence.

`pick_all` has no cached initial schedule: it returns to observation and
requests a fresh frame after every verified placement. A part that disappears
before selection is re-detected without motion; invalid depth, unreachable
poses, a lost camera, a lost robot, or an occupied placement zone stop the job
in a safe state.

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

The service is the only production owner of the Dobot, Orbbec and port 8080.
It sources ROS 2 Jazzy and this workspace explicitly, resolves the connected
Orbbec identity, requires the Depth USB function to remain on SuperSpeed, and
monitors the stable Dobot serial target plus the readiness API schema. A USB
disconnect or re-enumeration stops the complete launch before systemd performs
a bounded restart. User lingering must remain enabled so the service starts at
boot without an interactive login.

Production startup automatically asks the guarded calibration subsystem to
load and verify the bundle bound to the detected camera. A missing or rejected
bundle can start one recalibration attempt only when the calibration node's
independent depth, robot telemetry, alarm, hardware-safety, mount and trajectory
checks pass. `STARTUP_AUTO_MOTION=false` keeps HOME and observation motion
disabled during boot until the workcell is commissioned.

## HTTP API

```text
GET  /api/status
GET  /api/system/status
GET  /api/operator/status
GET  /stream
GET  /api/snapshot
POST /api/operator/start
POST /api/operator/stop
POST /api/system/startup
POST /api/homing
POST /api/move
POST /api/cancel
POST /api/gripper
POST /api/suction
GET  /api/vision/calibration/board.svg?mode=fixed_camera
POST /api/vision/calibration/auto
```

The calibration API supports a one-click multi-frame process for commissioning
and recovery.
Factory lens calibration is read automatically from
`/camera/color/camera_info` when that topic is available; direct USB cameras
fall back to the configured intrinsics YAML.

The default bind address is `127.0.0.1`. To expose the control API on the LAN,
set `DOBOT_WEB_API_TOKEN` to a long random value and launch with `host:=0.0.0.0`.
The browser uses HTTP Basic Authentication with username `dobot` and the token
as its password. Startup fails closed when a non-loopback host has no token.
