# Dobot Web Interface

Browser control panel for Dobot Magician with a live MJPEG camera view.

## Run

```bash
cd /home/jetson/arm_magician_ws
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

The **Home · กลับจุดเริ่มต้น** button beside Start calls the existing
HOME command, then returns to the observation pose. It is available without
Maintenance credentials and is disabled during a job, calibration, a pending Start/HOME
request, or loss of status. The dashboard shows the command result separately
from readiness so polling does not hide an error.

The service watchdog uses the fresh detector heartbeat (`vision_process_alive`)
for process recovery. Invalid depth still blocks production readiness through
`vision_running`, but does not restart the robot and dashboard in a loop.
Home displays its current blocking reason when work is active or status is lost.

The operator preview requests up to 10 JPEGs per second, with only one image
request in flight and no image polling while the tab is hidden. RGB-D fusion
retains the original sensor resolution, intrinsics, thresholds, and processing
rate; only its final annotated preview is reduced to 480 pixels wide at JPEG
quality 80. Atomic preview replacement prevents partial JPEG reads. These display
settings are `annotated_max_width` and `annotated_jpeg_quality` in
`dobot_vision_rgbd/config/rgbd_vision.yaml`.

Auto Calibration is read-only on the operator screen: current pose, accepted
poses, percentage, RGB-D acquisition, result, last verified save, and failure
reason are polled without issuing motion. STOP remains visible, including
while the camera is enlarged; it cancels calibration and robot/vision work and
latches startup stopped. It does not replace the physical Emergency Stop.

### Maintenance access

Commissioning, plan authorization, manual capture/solve, diagnostics and
startup recovery live at `/maintenance`. Configure `DOBOT_MAINTENANCE_TOKEN`
in the web process environment (or the existing `api_token` / `DOBOT_WEB_API_TOKEN`).
Use HTTP Basic username `maintenance` and the configured token as the password;
API clients can use `Authorization: Bearer <token>`. No token means access is
disabled, not unrestricted. Use the site's trusted HTTPS gateway for remote
credentials. The page, its static assets and maintenance command APIs enforce
access on the server. Existing API paths are retained; clients calling these
commands must now authenticate. Operator status, start and STOP remain available
without maintenance credentials. HOME and Abort also remain available without
credentials; HOME retains the server activity and browser origin checks.

Authentication grants access to Maintenance only. Each motion plan still
requires all seven on-site confirmations, the exact plan fingerprint, a fresh
run-specific authorization, commissioning and the existing live safety checks.

## Integrated startup and readiness

`dobot_auto.launch.py` enables the full-cell gate by default.  It admits a
real pick only in this deterministic order:

```text
robot services + fresh joints → live camera → synchronized valid RGB-D
→ fresh calibration PASS → HOME → observation pose → ready
```

The launch defaults to `startup_auto:=true`: the server requests the existing
AutomaticCalibration worker once after device readiness. Page navigation and
polling never start a calibration. A new calibration runs ten poses without
Capture/Next/Continue after authorization. A matching saved bundle instead
uses three independent verification poses, without refitting or collecting ten
new poses; these motions require the same explicit authorization. Completing
two-pose commissioning automatically prepares the next plan, which needs its
own authorization. `startup_auto_motion` remains false by default. HOME and
observation motion require commissioning and explicit deployment opt-in or
the authenticated Maintenance controls.

Verified geometry is saved atomically and reloaded. `AWAITING_LIVE_VALIDATION`
is not READY: the existing `live_acceptance_error` gate still requires hardware,
table stability, observability, independent verification, repeatability, reload,
real-object validation and a READY health check. The repository does not yet
produce that complete live acceptance record. Neither this UI nor automatic
collection fabricates it. Installations missing that integration remain blocked
from picking even when all ten images and the mathematical solution pass.

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
cd /home/jetson/arm_magician_ws
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
/home/jetson/arm_magician_ws/config/dobot-autostart.env
```

The user service file is:

```text
/home/jetson/arm_magician_ws/systemd/dobot-magician.service
```

On the Jetson, install Cyclone DDS, USB permissions and the user service:

```bash
cd /home/jetson/arm_magician_ws
sudo apt-get install ros-jazzy-rmw-cyclonedds-cpp
sudo install -m 0644 systemd/99-dobot-devices.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=tty --sysname-match=ttyUSB0
sudo udevadm trigger --action=change --subsystem-match=usb --attr-match=idVendor=2bc5
sudo udevadm settle
install -D -m 0644 systemd/dobot-magician.service ~/.config/systemd/user/dobot-magician.service
sudo loginctl enable-linger jetson
systemctl --user daemon-reload
systemctl --user enable --now dobot-magician.service
```

The device rules grant access through `plugdev`, which the Jetson operator
belongs to. The serial lock path is resolved from the running user's UID.
Inspect the service with:

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
launch with `host:=0.0.0.0` and open `http://<robot-ip>:8080`.
The web interface and API are available directly without a username or password,
including when a legacy `DOBOT_WEB_API_TOKEN` value is configured.
