# Jetson LAN deployment

The live dashboard runs at `http://172.30.10.101:8080/` after the legacy Production service is disabled. The existing Python HTTP backend serves the dashboard at `/`, health at `/health`, and same-origin status, control and an MJPEG stream at `/api/stream.mjpg`. The browser needs no ROS installation.

## Host checks

Run these on the Jetson host in the development checkout, using a terminal with access to the host network and systemd.

```bash
cd /home/jetson/arm_magician_ws/.hardware-only-reset
git status --short --branch
ip -brief -4 address
ss -ltnp '( sport = :8080 or sport = :18080 )'
systemctl --user status dobot-magician.service dobot-eye-center-live.service --no-pager
```

Confirm that `172.30.10.101` is assigned to the Jetson and that the intended clients are on the configured private network. The deployment defaults to `172.30.10.0/24`. Set `DOBOT_WEB_ALLOWED_CLIENTS` to the approved comma-separated IPv4 CIDRs if the workcell uses a different range. The backend binds the specific IP and checks the actual peer address and exact Host on all requests. A browser Origin, when present, must match the HTTP origin. Wildcard and public binds are rejected. Keep this HTTP service on an isolated, trusted LAN. Any client on the allowed network can view the live feed and select a target.

## Build and verify on the alternate port

```bash
source /opt/ros/jazzy/setup.bash
rosdep check --from-paths src --ignore-src --rosdistro jazzy
colcon build --base-paths src --cmake-args -DBUILD_TESTING=OFF
source install/setup.bash
DOBOT_WEB_PORT=18080 scripts/start-eye-center-dashboard
```

From another terminal on the Jetson, verify the listener and the HTTP response. Then repeat the curl commands from an allowed LAN client and open the first URL in its browser.

```bash
curl -v http://172.30.10.101:18080/
curl -v http://172.30.10.101:18080/health
curl -fsS http://172.30.10.101:18080/api/status
curl -fsS -o /dev/null http://172.30.10.101:18080/app.css
curl -fsS -o /dev/null http://172.30.10.101:18080/app.js
```

Open the dashboard and check the camera status, RGB frame rate and frame age. When registered depth is valid, the dashboard also shows depth skew and allows target selection. If depth drops out, live RGB video continues and target selection resumes once registered depth recovers. For `Camera Offline`, the diagnostic field in `/api/status` reports what the receiver is waiting for. `Dashboard unavailable` means the browser could not update its status.

## Restart and enable the live dashboard at boot

On the Jetson, run the following from the development checkout as `jetson`.

```bash
scripts/open-eye-center --restart
```

This restarts the managed Orbbec driver and dashboard. The check waits for two increasing frame IDs with fresh registered RGB-D data. Running the same command without `--restart` starts the units if necessary. During acquisition, a host clock step larger than one second triggers a camera service restart so frame timestamps can synchronize again. The command disables and stops the legacy user service `dobot-magician.service`, including its robot, vision and web processes. It leaves the old unit and sources on disk. The live dashboard supersedes the two transient Eye-in-Hand previews and binds port 8080. The camera unit uses the same hardware lock as the legacy launcher, checks for existing camera processes, ROS publishers and busy Orbbec USB devices, and starts only the Orbbec driver when needed. A separate camera publisher can continue serving the dashboard. The live unit uses hardware-home mode and opens the dedicated Dobot USB serial port for telemetry and operator-confirmed HOME.

The Jetson account has systemd linger enabled. Its enabled user services start at boot before login. The dashboard retries startup if the LAN address is still being configured. Check the service and camera independently:

```bash
systemctl --user is-enabled dobot-eye-center-live.service
systemctl --user status dobot-eye-center-live.service --no-pager
curl --noproxy '*' -fsS http://172.30.10.101:8080/health
```

## Read-only hardware view

Use the default `DOBOT_WEB_MODE=read-only` and the same `ROS_DOMAIN_ID` and discovery settings as the existing drivers. The launcher defaults to domain 0 with Cyclone DDS and subnet discovery. It subscribes to the official Orbbec RGB, depth and CameraInfo topics and to the Dobot GET driver's device, TCP, joint, alarm, suction and gripper topics. Verify the topic publishers on the Jetson. The HTTP process only subscribes to ROS topics. The separate camera unit owns the Orbbec driver when required. A missing driver shows a disconnected status while the web endpoint stays healthy. In simulation, RGB and motion are identified as mock, and the simulator publishes on a separate topic namespace.

The dashboard's startup script sources only the Jazzy underlay and the development overlay, checks the installed imports, and replaces itself with the ROS application process. The unit sends SIGINT on shutdown and limits repeated restarts. The installed live unit sets `DOBOT_WEB_MODE=hardware-home` and selects the controller with `DOBOT_HOME_PORT`. HOME reads the current pose and alarms, then sends the firmware homing command after operator confirmation. Camera availability is independent of HOME. On acknowledgement, wait for the arm to stop and the LED to turn green. The physical emergency stop interrupts firmware motion. Observation Pose and Auto Center are simulation controls.

For the isolated test camera, run `DOBOT_WEB_MODE=simulation ROS_DOMAIN_ID=42 DOBOT_WEB_PORT=18080 scripts/start-eye-center-dashboard` on an available port.
