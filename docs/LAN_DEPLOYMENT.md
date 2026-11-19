# Jetson LAN deployment

The target is `http://172.30.10.101:8080/`. The existing Python HTTP backend serves the dashboard at `/`, health at `/health`, and same-origin status, control and JPEG frame polling under `/api`. The browser needs no ROS installation.

## Host checks

Run these on the Jetson host in the development checkout, using a terminal with access to the host network and systemd.

```bash
cd /home/jetson/arm_magician_ws/.hardware-only-reset
git status --short --branch
ip -brief -4 address
ss -ltnp '( sport = :8080 or sport = :18080 )'
systemctl status dobot-magician.service dobot-eye-center.service --no-pager
```

Confirm that `172.30.10.101` is assigned to the Jetson and that the intended clients are on the configured private network. The deployment defaults to `172.30.10.0/24`. Set `DOBOT_WEB_ALLOWED_CLIENTS` to the approved comma-separated IPv4 CIDRs if the workcell uses a different range. The backend binds the specific IP and checks the actual peer address and exact Host on all requests. A browser Origin, when present, must match the HTTP origin. Wildcard and public binds are rejected. Keep this HTTP service on an isolated, trusted LAN. HTTP leaves the operator token and camera traffic visible to observers on the network path.

## Build and verify on the alternate port

```bash
source /opt/ros/jazzy/setup.bash
rosdep check --from-paths src --ignore-src --rosdistro jazzy
colcon build --base-paths src --cmake-args -DBUILD_TESTING=OFF
source install/setup.bash
read -rsp 'Operator token (at least 24 characters): ' DOBOT_OPERATOR_TOKEN
export DOBOT_OPERATOR_TOKEN
printf '\n'
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

In the browser acquire control and run the [simulation workflow](../README.md#เริ่ม-simulation) through CENTERED. Repeat and press STOP while the mock arm is moving. Check the browser Console for exceptions and the Network panel for successful requests for fresh JPEG frames. Use Ctrl-C in the startup terminal when done.

## Move the dashboard to port 8080

If Production or another service owns 8080, keep serving the new dashboard on 18080. Record the listener owner, service and current URL. A move to 8080 then requires a separately coordinated handoff by the owner. This branch does not replace the existing service. If the host IP and ownership of 8080 can be verified and 8080 is available, install the new unit and start it.

```bash
sudo test -e /etc/dobot-eye-center.env ||
  sudo install -m 0600 /dev/null /etc/dobot-eye-center.env
sudoedit /etc/dobot-eye-center.env
```

In the root-owned environment file, set `DOBOT_OPERATOR_TOKEN` to the chosen token. The environment file supports optional network and ROS settings. The new unit defaults to simulation and uses `172.30.10.101:8080`. Without a token the dashboard is view-only.

```bash
sudo install -m 0644 systemd/dobot-eye-center.service /etc/systemd/system/dobot-eye-center.service
sudo systemctl daemon-reload
sudo systemctl enable --now dobot-eye-center.service
systemctl status dobot-eye-center.service --no-pager
journalctl -u dobot-eye-center.service -n 40 --no-pager
curl -v http://172.30.10.101:8080/
curl -v http://172.30.10.101:8080/health
```

Confirm the final URL from a second LAN device. A healthy dashboard can report a disconnected camera or robot. If the new service fails, inspect its journal for the binding or overlay error. To roll back the new listener, use `sudo systemctl disable --now dobot-eye-center.service` and re-check port ownership with `ss`.

## Read-only hardware view

Set `DOBOT_WEB_MODE=read-only` and the same `ROS_DOMAIN_ID` and discovery settings as the existing drivers in `/etc/dobot-eye-center.env`. Restart only the new dashboard unit. It subscribes to the official Orbbec RGB, depth and CameraInfo topics and to the Dobot GET driver's device, TCP, joint, alarm, suction and gripper topics. Verify the topic publishers on the Jetson. The dashboard does not launch hardware drivers or acquire their camera or serial handles. A missing driver shows a disconnected status while the web endpoint stays healthy. In simulation, RGB and motion are identified as mock, and the simulator publishes on a separate topic namespace.

The dashboard's startup script sources only the Jazzy underlay and the development overlay, checks the installed imports, and replaces itself with the ROS application process. The unit sends SIGINT on shutdown and limits repeated restarts. HOME and AUTO CENTER are available only for simulation with an authenticated operator session.
