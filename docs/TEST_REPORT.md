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
