# Software verification

Checks ran on Jetson ARM64 with ROS 2 Jazzy and Python 3.12. All robot motion and image production in automated tests used mock devices.

| Check | Result |
| --- | --- |
| Fresh Colcon build of hardware-only baseline `1095058` | 6 packages passed |
| Development Colcon build | 7 packages passed |
| `rosdep check --from-paths src --ignore-src --rosdistro jazzy` | Declared dependencies satisfied |
| Installed Python imports, ROS launch arguments, generated action and native type support | Passed |
| Existing hardware protocol and offline ROS readback tests | 8 passed |
| Auto Center unit, simulation and integration tests | 24 passed |
| In-process ROS graph and HTTP workflow | Passed with real ROS publishers, subscriptions and action transport, and an in-memory HTTP connection |
| Desktop 1280 px and mobile 360 px viewport checks | Passed panel placement and horizontal overflow checks in offscreen Qt WebKit |
| Dashboard JavaScript syntax | Parsed with GJS |
| Passive readiness without devices | Returned unavailable telemetry and exit code 1 as expected |
| Interactive browser over an actual HTTP socket | Pending. This sandbox denied socket binding. |
| Hardware acceptance | Pending separate operator authorization |

The simulation regression matrix includes left, right, up, down and corner targets under normal, reversed and coupled Jacobians. It also verifies a singular Jacobian, an already-centered target with no servo moves, stable-frame confirmation, bounded fixed-Z/R corrections, and the absence of additional motion after CENTERED. Other cases cover HSV detection and depth sampling, ROI ambiguity, target identity, frame freshness, revoked leases, forged action permits, exact command replay, swept collision, workspace and joint limits, STOP during a live native action, late action results, alarms, controller disconnect, uncertain stop, readback mismatch, and clean restart.

Re-run the full offline suite after building and sourcing the development overlay. The test harness drives the same HTTP handlers and native ROS graph used by the mock application.

```bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=OFF
export ROS_LOG_DIR="$(mktemp -d)"
python3 -m pytest -q tests
ros2 launch dobot_auto_center auto_center.launch.py --show-args
ros2 interface show dobot_auto_center/action/GuardedMove
```

Physical mounting, actual registered depth, firmware compatibility, installed pose and joint conventions, HOME, full physical workspace and collision clearance, E-stop and real stop/cancel remain commissioning checks. The installed application rejects attempts to enable real motion.

## Jetson LAN deployment verification

The dedicated unit and launcher target `172.30.10.101:8080`. Simulation defaults to a separate DDS domain and publishes camera data in its own topic namespace. The configured client range is `172.30.10.0/24`.

| Check | Result |
| --- | --- |
| Colcon cached build and development overlay | All seven packages built. The development overlay included the rebuilt application and the unchanged baseline camera and GET driver artifacts. Installed executable linkage and ROS imports passed. |
| Offline regression suite | 34 tests passed |
| LAN request handling | Passed for root HTML, health, static assets, JSON API and a fresh mock JPEG using the target Host header and an allowed client address |
| Network and motion authorization | Passed for out-of-range client rejection, cross-origin rejection, command deduplication, confirmed mock HOME and Auto Center, STOP and read-only motion rejection |
| Camera and robot telemetry | Mock RGB and robot states verified. Camera timeout retired old JPEGs without taking down health. Passive firmware, TCP, alarms and tool outputs verified using ROS message fixtures. |
| Dashboard JS and layout | Executed JavaScript against a LAN API/DOM fixture. Checked side-by-side desktop and stacked mobile layout at 1280 and 360 px in offscreen Qt WebKit. |
| Startup and systemd configuration | Bash syntax and systemd unit verification passed. The launcher reached the HTTP socket setup on port 18080. |
| Host TCP, alternate port and LAN client verification | Socket creation returned `Operation not permitted`. Curl did not receive HTTP responses at 18080 or 8080. |
| Host service and Production port ownership | Netlink and the systemd bus were unavailable in the sandbox. Unit installation, service enablement and LAN client verification remain pending. |

The live IP assignment and physical sensor states require host verification. The [LAN deployment procedure](LAN_DEPLOYMENT.md) includes an alternate-port test, a port-ownership check, the unit installation, and a separate LAN-client test.

## Direct simulation controls

The development dashboard package rebuilt successfully on ROS 2 Jazzy. All 34 offline tests passed using HTTP requests without login credentials, including confirmed HOME, observation pose, target selection, Auto Center to CENTERED, STOP from another client without a lease, fault handling and read-only motion rejection. The LAN allowlist and browser-origin checks also apply to STOP.

The JavaScript fixture verified that opening the page sends only reads, STOP works before a session exists, the first workflow action acquires a single browser lease, and read-only mode disables motion controls. Offscreen layouts passed at 1280 and 360 px. The installed dashboard assets matched the source. The development service restart was blocked by the sandbox systemd bus permissions. Curl to the LAN root and health endpoint received no HTTP response from this environment.
