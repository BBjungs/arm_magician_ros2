# Calibration-free eye-in-hand approach

Implemented in the local workspace on 2026-11-07. This mode approaches a single
black cap and stops before contact. It does not pick, turn on suction, infer TCP
alignment from image centering, load a hand-eye bundle, or certify calibration.
The existing calibrated Auto Pick workflow retains its calibration checks.

## Implementation

- `dobot_vision_yolo/visual_servo_controller.py`: ROS-independent adaptive IBVS,
  target association, config validation and conservative camera/tool envelope.
- `dobot_web_interface/visual_servo_runtime.py`: stationary RGB-D sampling,
  fresh telemetry, explicit enable lease, exclusive control ownership, guarded
  MOVL, cancellation, delayed action response handling and shutdown cancellation.
- `dobot_vision_yolo/config/visual_servo.yaml`: requested initial limits and
  additional stability/timeout limits. Geometry remains unconfirmed by default.
- `dobot_kinematics/trajectory_validator_server.py`: dedicated strict MOVL
  service requires collision and ground checking, fresh finite telemetry,
  translations no greater than 3 mm, and existing IK/joint/path/collision checks.
- `dobot_web_interface/web_interface.py` and `static/visual_servo.*`: separate
  `/visual-servo` page, telemetry and ENABLE / START APPROACH / PAUSE / STOP APIs.
  Package data installs all page assets. The operator page links to the mode.

The controller consumes the existing RGB-D shape detector's `black_cap` packets:
`center_pixel`, `bbox`, `confidence`, `depth_mm`, `depth_valid`, RGB/depth exposure
timestamps, registered-depth flag, image dimensions and optical frame IDs.
It associates the same object by position, box size and depth; ambiguous matches
stop the session. A detector's per-frame numeric ID is not treated as identity.
Image size and frame identity must remain constant during a session.

Each observation is a median of at least three fresh, post-motion RGB-D frames
with fresh, stationary TCP feedback. Pre-motion depths are never mixed into the
filter. RGB/depth age and skew, target confidence, stationarity and feature
spread are checked independently.

The state sequence is DETECT → DEPTH → CHECK → LEARN → ALIGN → VERIFY → APPROACH
→ STOP. CHECK and VERIFY occur around every movement. Three independent, small
base translations learn a local 3×3 Jacobian of `(u, v, optical depth)` against
**measured TCP displacement**, not requested displacement. Z is probed as a third
independent direction to make depth observable; it is never assumed to be the
camera optical axis. Rejected probes are not sent or blindly reversed.

Commands use damped least squares:

```text
delta_tcp = gain * J.T * inverse(J * J.T + damping² * I) * desired_feature_change
J_next = J + (measured_feature_change - J * measured_tcp_change)
             * measured_tcp_change.T / ||measured_tcp_change||²
```

While aligning, desired depth change is zero. Approach is admitted only after
pixel alignment and a learned direction predicts decreasing depth. Singular or
ill-conditioned models, insufficient response, physically inconsistent depth
gradients, increased pixel error, lack of depth progress and model residuals
cause SAFE_STOP. The measured update is retained for diagnostics; there is no
automatic guessed reverse movement. PAUSE/STOP require fresh ENABLE and learning.

## Safety and limits

Before every dispatch, the mode requires fresh alarm-free robot feedback,
confirmed HOME, no existing motion/control fault, no competing startup or
calibration operation, fresh unambiguous RGB-D, existing workspace permission
for real motion, confirmed assembly geometry, and strict trajectory validation.
Validation is tied to start pose, target pose and time and is single-use.
During motion, live health and cancel/enable-expiry checks continue. Late accepted
goals are cancelled; an uncertain motion result latches a control fault and
cannot be retried as an ordinary stopped operation.

A missing calibration bundle is a calibrated-startup failure, not a fabricated
robot hardware fault. It still blocks Auto Pick. Calibration failure during
Auto Pick still cancels that operation. Existing robot/control faults are never
cleared by selecting or enabling IBVS. No `calibration_valid=True` is synthesized.

`free_volume_min_mm` / `free_volume_max_mm` describe a **measured obstacle-free
box in robot base coordinates**. `assembly_radius_mm` must enclose the whole
camera, carrier, tool and relevant protrusions around TCP. The box is eroded by
this radius plus clearance before checking each straight segment. Stop depth
must exceed `2 * assembly_radius_mm + clearance_mm + max_step_mm`, accounting
conservatively for optical-center/TCP offset. These measurements describe a
collision envelope, not an extrinsic calibration matrix.

The existing PyBullet robot/ground model and surveyed box do not reconstruct
arbitrary obstacles or prove the entire physical workcell safe. The operator
must survey the table, full arm sweep, cables and obstacles. The workpiece must
remain stationary. The 1 mm probe, 3 mm step and 10% speed defaults are not
physical safety certifications. Default `geometry_confirmed: false`, empty
bounds and zero radius block real movement; a checkbox cannot override them.

## Web operation

Open `/visual-servo`. It shows live camera preview, target bounding box and
reference, pixel error, optical depth, TCP, learned direction, model condition,
robot/servo state, confidence and exposure timestamps. Preview and telemetry may
have different display timestamps; the controller uses source-stamped RGB-D,
not the browser image. Missing telemetry disables ENABLE/START and hides stale
target overlays. STOP/PAUSE stay accessible during pending requests.

ENABLE/START use existing Maintenance authentication (`DOBOT_MAINTENANCE_TOKEN`
or the existing configured API token). The page keeps the entered token only in
memory; it does not save it in browser storage. Cross-origin commands are rejected.
ENABLE requires explicit confirmations of clear workspace, tested E-STOP and
measured assembly envelope, then expires after 60 seconds. ENABLE itself sends
no motion. STOP/PAUSE need no authentication, consistent with accessible stopping.

HOME remains a prerequisite, not a calibration procedure. An explicitly requested
`POST /api/homing?move_to_observation=false` uses the existing guarded HOME without
dispatching the calibrated observation-pose workflow. The existing HOME endpoint
default remains unchanged. HOME itself moves hardware and needs operator clearance.

## Validation and reproduction

No physical motion experiments were performed for this implementation. Tests use
pure Python simulation, mocked ROS transports/API objects, PyBullet DIRECT and a
Chromium browser whose requests are intercepted with simulated responses.

Final results: **223 passed, 2 skipped, 0 failures/errors** (225 collected).
The two existing browser-script contract tests require Node.js, which is absent
on this host. The new page was independently tested in Chromium: all nine browser
checks passed. All three affected ROS packages built successfully. Installed
package metadata includes the three new UI assets and the YAML config is installed.
The live hardware service was not restarted for this implementation; load the new
runtime only during the approved idle-cell commissioning step below.

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
.venv/bin/python -m pytest -q \
  src/magician_ros2/dobot_web_interface/test \
  src/magician_ros2/dobot_vision_yolo/test \
  src/magician_ros2/dobot_kinematics/test/test_visual_servo_validation.py \
  src/magician_ros2/dobot_kinematics/test/test_collision_safety.py \
  src/magician_ros2/dobot_kinematics/test/test_trajectory_validator_diagnostics.py \
  --junitxml=docs/evidence/visual-servo/unit-simulation-results.xml

.venv/bin/python /usr/bin/colcon build --symlink-install \
  --packages-select dobot_vision_yolo dobot_web_interface dobot_kinematics

# Optional UI environment: Python Playwright plus its Chromium installation.
PLAYWRIGHT_BROWSERS_PATH=/tmp/ibvs-ui-browsers \
  /tmp/ibvs-ui-env/bin/python \
  src/magician_ros2/dobot_web_interface/test/visual_servo_browser_check.py
```

Evidence is in `docs/evidence/visual-servo/`: JUnit results, browser check results,
and desktop/mobile screenshots labelled SIMULATION. Simulation covers 12 unknown
camera orientations, partial achieved moves, depth increasing during approach,
target loss, stale exposure, failed collision validation, insufficient/singular
response, inconsistent image motion and budget exhaustion. Runtime tests cover
operator gates, stale robot feedback, pending START/STOP races, late action
acceptance, uncertain result cancellation, median sampling and shutdown.

Two old regression tests were repaired to assert the actual SafetyGuard
`allowed` / list-of-checks schema and correct package source paths. The production
SafetyGuard was not weakened to satisfy those tests.

## Operator-authorized short trial — pending

1. Resolve robot alarms and verify HOME through the existing guarded workflow.
   Confirm the full workspace is clear and test the physical E-STOP. Supply the
   measured free-volume bounds, assembly radius and clearance; choose a stop
   depth consistent with the physical assembly and sensor's valid depth range.
2. Copy `config/visual-servo-short-trial.example.yaml` to a commissioned config,
   populate measured values and confirm geometry only after inspection. That
   template allows at most one validated +X probe of 1 mm, then SAFE_STOP at its
   budget. It does not attempt a full approach or automatically return.
3. Set `DOBOT_VISUAL_SERVO_CONFIG` to that file and configure operator credentials
   for the service. Real-motion permission remains governed by the existing
   workspace config. No such permissions were enabled by this change.
4. After explicit operator approval, load/restart the service while the cell is
   idle, open the separate page, confirm the checks, ENABLE and START APPROACH.
   Record before/after TCP, RGB-D timestamps, `(u,v,D)`, alarms and cancellation.
   Use E-STOP if stopping cannot be confirmed. Inspect results before authorizing
   independent Y/Z probes or increasing the budget for a complete approach.
5. Actual grasping is outside this mode. It requires independently verified
   camera-to-TCP observations or confirmed mounting geometry and a separate
   validated grasp trajectory.

The implementation/build is ready for review. Hardware trials, commissioning
measurements and E-STOP verification remain pending operator authorization.
