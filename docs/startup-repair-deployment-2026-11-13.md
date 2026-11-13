# Startup repair and controlled deployment

Production has NOT been deployed or restarted during this investigation. No
physical motion, HOME, camera open or serial open was used in the software tests.
This runbook requires explicit operator authorization before the deployment block.

## Root cause and evidence

The original journal contains the complete failures at 2026-11-13 15:39 Bangkok:

```
markerless_calibration: node.py:374 in __init__
web_interface: web_interface.py:433 in __init__
from dobot_msgs.srv import SelectCalibrationObject
ImportError: cannot import name 'SelectCalibrationObject' from 'dobot_msgs.srv'
```

Both resolve interfaces from
`install/dobot_msgs/lib/python3.12/site-packages/dobot_msgs/srv/__init__.py`.
Production Python modules resolve through `build/` symlinks into the edited
source tree. The generated production messages have not been rebuilt together
with that source. The service was added to source CMakeLists.txt, and exists in
the isolated overlay; it is absent from the production generated Python module.
Both module imports succeed because the failing import is inside the constructor.
This is a partial-release mismatch, not missing camera data or a plane threshold.

Exact original commands (parameter files have been retained in evidence):

```
/home/jetson/arm_magician_ws/install/dobot_calibration/lib/dobot_calibration/markerless_calibration --ros-args --params-file /home/jetson/arm_magician_ws/install/dobot_calibration/share/dobot_calibration/config/calibration.yaml --params-file /tmp/launch_params_p5yr8u56
/home/jetson/arm_magician_ws/install/dobot_web_interface/lib/dobot_web_interface/web_interface --ros-args --params-file /tmp/launch_params_bo09vctb
```

Do not execute those production commands as a diagnostic. The non-spinning
constructor probe reproduced both failures with the production overlay and both
successes with the matching isolated overlay. It used DDS domain 191, localhost
discovery, no executor and no camera device. The historical journal independently
confirms the same function, line and exception under the actual launch parameters.

Read the original journal with:

```bash
journalctl --no-pager _SYSTEMD_USER_UNIT=dobot-magician.service \
  --since '2026-11-13 15:39:00' --until '2026-11-13 15:41:00' -o cat
```

`journalctl --user -u ...` did not return the corresponding records here; querying
the system journal's `_SYSTEMD_USER_UNIT` field did. Both launch nodes used
`output='screen'`: child tracebacks went to stdout/stderr captured by systemd,
while launch.log primarily retained launch events. They now use `output='both'`.
The lifecycle wrapper additionally appends full exception tracebacks to
`$ROS_LOG_DIR/startup-failures.log` and stderr, retaining nonzero failure status.

The old unit permits three starts in 120 seconds. A startup attempt can consume
the 90-second web deadline, failure grace, stack shutdown and 10-second restart
delay. Such attempts age out of that window, allowing an unbounded sequence of
slow failures (800 restarts observed). The source unit now permits three starts
per hour; configuration exit 78 is non-restarting. The startup script runs a
native generated-interface/import preflight before any hardware wait/launch.

Observed environment: Python 3.12.3, NumPy 1.26.4, SciPy 1.11.4,
FastAPI 0.101.0, Uvicorn 0.27.1; production selects Cyclone DDS. Import evidence
includes resolved paths and complete AMENT_PREFIX_PATH/PYTHONPATH. The installed
entry points use the workspace virtual environment. Rebuild via that interpreter:
plain system `colcon` produces `/usr/bin/python3` shebangs and is not equivalent.

## Changes in this repair

| File relative to workspace | Purpose |
|---|---|
| `scripts/start_dobot_autostart.sh` | Fail before hardware launch on incoherent interfaces/dependencies; exit 78 |
| `systemd/dobot-magician.service` | Longer restart accounting window; do not retry configuration exit 78 |
| `config/dobot-commissioning.env` | Uninstalled initial commissioning overrides |
| `src/magician_ros2/dobot_calibration/dobot_calibration/startup_preflight.py` | Resolve required interfaces, load native type support and import dependent modules without initializing ROS |
| `src/magician_ros2/dobot_calibration/dobot_calibration/node_lifecycle.py` | Retain original traceback; destroy partially constructed nodes; keep context alive through worker/executor cleanup |
| `src/magician_ros2/dobot_calibration/dobot_calibration/node.py` | Use lifecycle cleanup; expose object startup restore switch |
| `src/magician_ros2/dobot_calibration/launch/markerless_calibration.launch.py` | Expose restore switch and retain child output |
| `src/magician_ros2/dobot_calibration/package.xml` | Declare existing runtime dependency on dobot_kinematics |
| `src/magician_ros2/dobot_calibration/test/test_startup_lifecycle.py` | Initialization failure, native interfaces, cleanup, commissioning and restart-policy regression |
| `src/magician_ros2/dobot_web_interface/dobot_web_interface/web_interface.py` | Cover constructor/app/bind failures, partial cleanup and executor-thread failure propagation |
| `src/magician_ros2/dobot_web_interface/launch/dobot_auto.launch.py` | Bind saved-object restore to startup_auto; retain child output |
| `src/magician_ros2/dobot_web_interface/test/test_startup_runtime.py` | Actual installed launch, HTTP, ROS object service, restart, invalid parameters and occupied-port tests |

Previous object calibration/Visual Servo changes and unrelated dirty/untracked
files remain in place. The repair does not alter geometry thresholds, E-stop,
collision/workspace rules, calibration admission, motion authorization or picking
permissions. The earlier 0.25 plane threshold remains confined to the legacy path.

## Startup safety audit

`STARTUP_AUTO=false` now also disables the independent saved-object restoration
timer. `auto_start=false` and `recalibrate_on_failure=false` are passed to the
calibration node. Web startup HOME/observation actions require both startup_auto
and startup_auto_motion. Visual Servo creates no worker or enable permit at boot.
The RGB-D launch sets dry_run=true and allow_real_motion=false. Suction and HOME
commands occur in explicit service callbacks, not their constructors.

Hardware bringup still opens serial for telemetry, loads HOME position parameters
and writes initial joint/cartesian PTP speed/acceleration parameters. These are
hardware writes, although they do not issue HOME/PTP targets. Therefore software
flags are not treated as authorization to start physical bringup. Operator must
check stationary state, no controller motion/queued job, stopped external clients,
and workcell safety before the authorized start. Keep original E-stop/interlocks
engaged according to the cell procedure; do not release them to make tests pass.

The supplemental environment limits HTTP and DDS to localhost and a separate
domain during commissioning. Confirm all local ROS clients in that domain are
part of this stack. Web/Visual Servo real-motion permissions remain false and
hardware acceptance is still required. Do not call HOME, calibration start,
commission, authorize, picking or servo enable endpoints during initial validation.

## Software tests

Executed regression: **427 calibration tests**, **219 web/RGB-D/Visual Servo
tests**, zero failures/skips. The 8 focused startup tests also passed (these are
included in the preceding regression totals). Real Chromium passed object
calibration and Visual Servo workflows with mocked HTTP and no page errors.
The calibration suite includes the full ten-pose injected-transport integration,
independent verification, object-only plane-gate regression and Dry Run. Real
camera frames, physical mounting correctness and hardware acceptance require the
authorized deployment and are not inferred from synthetic data.

Evidence: `docs/evidence/startup-repair/` contains the actual production
tracebacks/parameters, matched constructor probes, JUnit XML, browser results
and build output. `test-summary.json` records exact counts and durations.
Python syntax checks passed for 154 files. Shell syntax, scoped git whitespace
checks and `systemd-analyze --user verify` passed. Systemd restart policy was checked statically; the live unit was not
installed, fault-injected or restarted. Process startup/HTTP/ROS integration and
failure recovery were exercised using real installed executables in isolation.

The final isolated dependency-closure build finished **all 16 packages in
6 min 5 s**. Native interface preflight passed against that overlay. A further
**66 tests passed** against the complete overlay: the same 8 startup tests plus
58 Visual Servo simulation, collision/workspace, trajectory diagnostics and PTP
safety tests. Do not add the repeated startup tests twice when counting coverage.

| Requested category | Executed result |
|---|---|
| Build | PASS, all 16 dependency packages; Python entry points use .venv |
| Unit Tests | PASS, included in 427 calibration / 219 web-RGB-D-servo results |
| Integration Tests | PASS, simulated ten-pose acquisition and actual installed ROS/HTTP startup |
| Object-Based Calibration | PASS in software, including no plane-function calls and independent verification |
| Web API | PASS; real ROS service rejection for absent data and mocked API regressions |
| Chromium | PASS for object calibration and Visual Servo, mocked transport |
| Dry Run | PASS, real RGB-D math with injected motion transport; no hardware motion |
| Startup Validation | PASS in isolated launch at localhost:8080, two clean start/stop cycles, parameter/bind failures |
| Production camera/robot validation | NOT RUN; explicit operator deployment authorization required |

Final stages:

```
SOFTWARE_BUILD=PASS
SOFTWARE_TESTS=PASS
STARTUP_FAILURE_RESOLVED=PASS_ISOLATED
PRODUCTION_DEPLOYED=NO_AWAITING_OPERATOR_AUTHORIZATION
OBJECT_CALIBRATION_READY=SOFTWARE_ONLY_HARDWARE_PENDING
HARDWARE_ACCEPTANCE=NOT_RUN
REAL_PICKING_AUTHORIZED=NO
```

At handoff the production service is still inactive, NRestarts=800. No live
camera-health or physical calibration claim is made. Missing/changed reference
objects, stale depth, symmetric/poor geometry, unverified mounting, inadequate
observability, residual/held-out accuracy failures and unmet live acceptance
continue to block calibration/picking as designed.

After sourcing the intended overlay, reproduce tests with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ROS_DOMAIN_ID=187 \
ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_LOG_DIR=/tmp/startup-cal-regression-logs \
.venv/bin/python -m pytest src/magician_ros2/dobot_calibration/test \
  -q --tb=short --junitxml=/tmp/startup-calibration-tests.xml

PATH=/tmp/object-ui-env/lib/python3.12/site-packages/playwright/driver:$PATH \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ROS_DOMAIN_ID=190 \
ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_LOG_DIR=/tmp/startup-web-regression-logs \
.venv/bin/python -m pytest src/magician_ros2/dobot_web_interface/test \
  src/magician_ros2/dobot_vision_rgbd/test \
  src/magician_ros2/dobot_vision_yolo/test/test_visual_servo_controller.py \
  src/magician_ros2/dobot_vision_yolo/test/test_markerless_readiness.py \
  -q --tb=short --junitxml=/tmp/startup-web-rgbd-tests.xml

PLAYWRIGHT_BROWSERS_PATH=/tmp/object-ui-browsers /tmp/object-ui-env/bin/python \
  src/magician_ros2/dobot_web_interface/test/object_calibration_browser_check.py
PLAYWRIGHT_BROWSERS_PATH=/tmp/object-ui-browsers /tmp/object-ui-env/bin/python \
  src/magician_ros2/dobot_web_interface/test/visual_servo_browser_check.py
```

The installed launch fixture requires port 8080 to be free and runs only
calibration/web nodes in domain 193; never run it concurrently with production.
It deliberately rejects stale/missing object observations instead of fabricating
calibration readiness. Browser fixtures intercept all requests; hardware is absent.

Rebuild the six changed/dependent packages in isolation (unchanged dependencies
come from the recorded production underlay):

```bash
cd /home/jetson/arm_magician_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
source /tmp/object-calibration-install/setup.bash
.venv/bin/python -m colcon --log-base /tmp/startup-repair-build-logs build \
  --packages-select dobot_msgs dobot_kinematics dobot_calibration \
    dobot_vision_yolo dobot_vision_rgbd dobot_web_interface \
  --build-base /tmp/object-calibration-build \
  --install-base /tmp/object-calibration-install
source /tmp/object-calibration-install/setup.bash
.venv/bin/python -m dobot_calibration.startup_preflight
```

The full repository dependency closure contains 16 packages: dobot_msgs,
dobot_description, dobot_driver, orbbec_camera_msgs, dobot_kinematics,
dobot_diagnostics, dobot_end_effector, dobot_homing, dobot_motion,
dobot_state_updater, orbbec_camera, dobot_bringup, dobot_calibration,
dobot_vision_yolo, dobot_vision_rgbd and dobot_web_interface. Deployment builds
that closure in dependency order, not only the two failed Python packages.

## Authorized deployment only

Do not execute this section until an operator authorizes deployment and confirms
the physical stationary/no-job checks. These commands have NOT been executed.
Use one terminal so variables persist. Ensure sufficient disk space for a complete
workspace backup and a separate release; do not delete calibration data for space.

1. Record and back up the current state, including untracked files and symlink targets:

```bash
cd /home/jetson/arm_magician_ws
stamp=$(date +%Y%m%d-%H%M%S)
backup="/home/jetson/dobot-backups/$stamp"
mkdir -p "$backup"
git status --short > "$backup/git-status.txt"
git diff --binary > "$backup/worktree.patch"
git ls-files --others --exclude-standard > "$backup/untracked.txt"
git rev-parse HEAD > "$backup/git-head.txt"
systemctl --user cat dobot-magician.service > "$backup/effective-unit.txt"
systemctl --user show dobot-magician.service > "$backup/service-state.txt"
ps -eo pid,args > "$backup/processes.txt"
.venv/bin/python -m pip freeze > "$backup/python-packages.txt"
cp -a /home/jetson/.config/systemd/user/dobot-magician.service "$backup/installed-unit"
if test -d /home/jetson/.config/systemd/user/dobot-magician.service.d; then
  cp -a /home/jetson/.config/systemd/user/dobot-magician.service.d "$backup/installed-dropins"
fi
# Operator confirms stationary/no motion job BEFORE this stop.
systemctl --user stop dobot-magician.service
test "$(systemctl --user show -p ActiveState --value dobot-magician.service)" = inactive
tar --exclude='./.git' -cpf "$backup/workspace.tar" .
if test -d /home/jetson/.ros/dobot; then
  tar -C /home/jetson/.ros -cpf "$backup/calibration.tar" dobot
fi
sha256sum "$backup"/*.tar > "$backup/archives.sha256"
```

Review `git-status.txt`/`untracked.txt` and archives before proceeding. The existing
production install is a known broken partial release; this backup preserves data
and enables rollback, but is not itself a known-good runnable release.

2. Build a separate non-symlink release from the reviewed source (no production launch):

```bash
release="/home/jetson/arm_magician_ws/releases/$stamp"
mkdir -p "$release"
source /opt/ros/jazzy/setup.bash
source /home/jetson/arm_magician_ws/install/setup.bash
CMAKE_BUILD_PARALLEL_LEVEL=2 .venv/bin/python -m colcon \
  --log-base "$release/log" build --executor sequential \
  --packages-up-to dobot_web_interface \
  --build-base "$release/build" --install-base "$release/install" \
  --cmake-args -DBUILD_TESTING=OFF
source "$release/install/setup.bash"
.venv/bin/python -m dobot_calibration.startup_preflight
head -1 "$release/install/dobot_calibration/lib/dobot_calibration/markerless_calibration"
head -1 "$release/install/dobot_web_interface/lib/dobot_web_interface/web_interface"
colcon list --names-only --packages-up-to dobot_web_interface > "$release/packages.txt"
.venv/bin/python -m pip freeze > "$release/python-packages.txt"
```

Both shebangs must identify `/home/jetson/arm_magician_ws/.venv/bin/python`.
Re-run the tests below against this release before enabling it. No stale build
artifacts should be copied into the release and no `--symlink-install` is used.

3. Stage the service and release selection. Keep the original install in place;
the launcher sources an optional release local_setup after the canonical underlay.
Do not replace the canonical install with a symlink to a release built on top of
it: that can make colcon's recorded prefix chain recursive.

```bash
install -m 644 systemd/dobot-magician.service \
  /home/jetson/.config/systemd/user/dobot-magician.service
mkdir -p /home/jetson/.config/systemd/user/dobot-magician.service.d
cat > /home/jetson/.config/systemd/user/dobot-magician.service.d/commissioning.conf <<'EOF'
[Service]
EnvironmentFile=/home/jetson/arm_magician_ws/config/dobot-commissioning.env
# Operator manually investigates every commissioning failure.
Restart=no
EOF
printf '[Service]\nEnvironment=DOBOT_RELEASE_SETUP=%s/install/local_setup.bash\n' "$release" \
  > /home/jetson/.config/systemd/user/dobot-magician.service.d/release.conf
systemctl --user daemon-reload
systemctl --user cat dobot-magician.service
systemctl --user show dobot-magician.service -p Restart -p RestartPreventExitStatus \
  -p StartLimitIntervalUSec -p StartLimitBurst
```

**Final operator authorization boundary:** confirm no active motion/queue, physical
stationary state, retained interlocks, no duplicate serial/camera owners, and no
real-motion permission. Only then execute ONE start:

```bash
systemctl --user reset-failed dobot-magician.service
systemctl --user start dobot-magician.service
journalctl --no-pager _SYSTEMD_USER_UNIT=dobot-magician.service -n 120 -o cat
systemctl --user show dobot-magician.service -p ActiveState -p SubState \
  -p NRestarts -p ExecMainStatus
curl --fail http://127.0.0.1:8080/api/system/status
curl --fail http://127.0.0.1:8080/api/operator/status
curl --fail http://127.0.0.1:8080/api/vision/calibration
export ROS_DOMAIN_ID=194 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 node list --no-daemon
ros2 service list | rg '/calibration/object/'
ros2 param get /markerless_calibration object_startup_restore
ros2 param get /dobot_web_interface startup_auto
ros2 param get /dobot_web_interface startup_auto_motion
timeout 10 ros2 topic echo /camera/health --once
timeout 10 ros2 topic hz /camera/color/image_raw
timeout 10 ros2 topic hz /camera/depth/image_raw
```

Expected: both nodes remain alive, no new restarts during at least five minutes of
observation, HTTP 200, live camera identity/RGB/depth health, object endpoints
present, startup flags false, DRY_RUN and real picking disabled. Calibration may
correctly remain NOT_READY pending object data, physical mount evidence and live
acceptance. Do not change quality thresholds or assert readiness to finish this
check. A failure means stop once and inspect the retained traceback; do not cycle
the service repeatedly. Keep commissioning overrides until hardware acceptance.

## Rollback

Stop the new release. Restore a previously accepted compatible release if one
exists; the pre-repair install captured here remains known-broken, so default to
leaving it stopped. Do not restart it merely to see whether it works.

```bash
cd /home/jetson/arm_magician_ws
systemctl --user stop dobot-magician.service
# The original install was never replaced; restore unit/drop-ins to deselect release.
cp -a "$backup/installed-unit" /home/jetson/.config/systemd/user/dobot-magician.service
mv /home/jetson/.config/systemd/user/dobot-magician.service.d \
  "/home/jetson/.config/systemd/user/dobot-magician.service.d.failed-$stamp"
if test -d "$backup/installed-dropins"; then
  cp -a "$backup/installed-dropins" /home/jetson/.config/systemd/user/dobot-magician.service.d
fi
systemctl --user daemon-reload
sha256sum -c "$backup/archives.sha256"
```

The full workspace archive includes scripts, sources and generated files because
old symlink installs depend on source/build targets. Extract it into a separate
recovery directory first, compare, and restore the complete compatible set only
after review; do not overlay half of it on the running workspace. Calibration
was not changed by startup validation. If later hardware work changed it, archive
that newer directory before restoring the saved `calibration.tar`. Restarting any
restored release requires fresh operator authorization. Never git-clean or reset
the preserved worktree to perform rollback.

## Subsequent UI-only preview

After the operator reported connection refused, a transient user service
`dobot-web-preview.service` was started to expose the tested web UI at
`http://172.30.10.101:8080`. HTTP and system-status requests returned 200.
It uses the isolated overlay, DDS domain 195 with localhost discovery, disabled
startup/automatic motion/camera preview and no maintenance credentials. It starts
no robot, camera, detector or calibration nodes. Status confirms DRY_RUN,
real_motion_enabled=false and disconnected hardware. Production remains inactive
with NRestarts=800; this is not hardware deployment or acceptance.

The transient unit conflicts with and is ordered before the production unit,
so it cannot share the web port with production. Before rerunning port-8080
fixtures or executing the authorized deployment, stop only the preview:

```bash
systemctl --user stop dobot-web-preview.service
```

The preview is temporary and is not enabled at reboot.
