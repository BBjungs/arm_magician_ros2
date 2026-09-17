# Markerless automatic eye-in-hand calibration

This package calibrates a camera rigidly attached to the Dobot Magician's
**rotating TCP**, using synchronized natural RGB features, aligned depth,
PointCloud2, TCP/joints and a static tabletop scene. It uses no fiducials,
calibration boards, image clicks or user XYZ points.

## Full live acceptance status

The stricter live Phase 5 acceptance is **not complete**. A mathematical
solver/verification PASS alone no longer grants ROS picking readiness.
`LIVE_VALIDATION_NOT_COMPLETED` blocks readiness until live hardware,
table stability, observability, independent verification, repeatability,
reload verification, a READY geometry health check and real-object validation
have all been completed. The current mathematical workflow does not yet
produce that complete live acceptance record. Synthetic workflow tests can
still reach their internal READY state; that state does not authorize picking.

Live readiness recovery identified the installed Orbbec Gemini/Astra profile
as 640x400 Y11 at 30 Hz. With depth registration enabled, the driver publishes
the registered 640x480 `16UC1` image on `/camera/depth/image_raw` in
`camera_color_optical_frame`; the registered cloud is
`/camera/depth/points`. LDP must be disabled for this workcell:
with LDP enabled every depth pixel was zero, while disabling it restored
plausible metric depth. The supplied Phase 5 configuration uses the discovered
interfaces. Topic names remain configurable for another driver or camera.

Depth validity is checked directly on every depth stream callback, as well as
synchronized captures. Invalid or stale depth latches failure even if the
point-cloud publisher stops. `/calibration/status` includes `depth_quality`
and the separate `hardware_readiness` record with exact blockers.

The current Magician driver exposes live TCP, joints and alarm responses but no
hardware E-stop or safety-state interface. An empty `safety_state_topic`
therefore returns `SAFETY_UNVERIFIED` and blocks every calibration movement.
A deployment may configure this parameter only to a fresh `std_msgs/Bool`
topic backed by a real workcell safety device, where true means motion is
permitted. It must never be filled by a constant or synthetic publisher.
The unverified mount model and unobservable tool-Z remain separate later Phase
5 blockers. No tool-Z value is invented.

## The Magician's observability limit

For measured TCP poses `G_i = base_T_tool_i`, registration estimates
`B_ij = camera_i_T_camera_j`. The solver uses
`A_ij X = X B_ij`, where `A_ij = inverse(G_i) G_j` and
`X = tool_T_camera_optical`. All internal translations are metres.

XYZ/yaw motion cannot determine the translation of the camera along tool Z.
Adding any tool-Z offset to X produces the same relative camera motions.
An unknown table plane and static scene cannot resolve this gauge: their
unknown base heights shift by the same amount. Small residuals therefore do
not establish a fully observed six-parameter transform.

The implementation estimates the other five parameters and fixes tool Z to
a **verified CAD/mount model**, records its uncertainty and provenance, and
checks numerical observability of the remaining parameters. A model must
also provide an enclosing radius for attached hardware. No numeric mount
defaults are invented. The supplied `config/mount_model.yaml` is deliberately
unverified and blocks automatic movement and picking until real machine
geometry is available. This is a machine configuration dependency, not a
manual scene calibration step.

The repository's optional historical Realsense mount is on `magician_link_4`,
upstream of wrist yaw. It must not be treated as rigid to the rotating TCP.
Use a camera rigid to the reported TCP, or implement and validate a separate
kinematic frame model before using that mount.

## Measured translation and markerless rotation workflow

Production calibration is exclusively markerless. ArUco, AprilTag, ChArUco,
checkerboards and other calibration targets are prohibited. The workflow
estimates camera motion from natural RGB-D scene structure and holds the
as-built translation constraint fixed while solving mount rotation. The live
Orbbec factory TF remains authoritative for internal camera frames.

First fill `config/eye-in-hand-mount-measurement-form.yaml` with unsigned
millimetre magnitudes and the physical direction words in that file. Do not
enter signed XYZ or any guessed rotation. Check the derived translation before
launching:

```bash
scripts/convert_eye_in_hand_mount_measurements.py \
  config/eye-in-hand-mount-measurement-form.yaml
```

Collect 8–12 settled poses total, using 2–3 poses only for held-out validation.
Every accepted pose contains synchronized TCP/joints, RGB, registered depth,
CameraInfo and point cloud after the robot has stopped. Natural RGB-D feature
registration estimates relative camera motion; 3D RANSAC and dense trimmed ICP
refine it. Table-plane RANSAC and common-scene consistency constrain the
nonlinear hand-eye solve. Held-out poses are never used to refit the result.

The current generated workflow uses six training poses and three held-out
poses (nine total), which is within this production requirement. Any weak scene,
registration failure, degeneracy or held-out residual failure keeps
`geometry_verified: false`.

## Build and launch

Install ROS dependencies through rosdep for this package. The implementation
uses NumPy, SciPy and OpenCV; Open3D is not required. Build in a ROS 2 workspace:

```bash
colcon build --packages-up-to dobot_calibration dobot_kinematics dobot_state_updater dobot_demos
source install/setup.bash
ros2 launch dobot_calibration markerless_calibration.launch.py \
  mount_model:=/path/to/verified_mount.yaml camera_id:=CAMERA_SERIAL
```

Run the updated Dobot state publisher, PTP server and trajectory validator,
plus the camera's registered RGB-D pipeline. Set topic names in a copy of
`config/calibration.yaml` and pass `config:=/path/to/calibration.yaml`.
RGB must be rectified; depth and cloud must be registered into that same
optical frame. All four streams, including CameraInfo, need fresh stamped
messages. Set the stable physical camera serial/device identifier as
`camera_id`. TCP must use `magician_base_link`, in metres; joints are radians.
The adapter converts MOVL targets to millimetres/degrees for `PTP_action`.

The robot starts from its measured TCP, with no user position input. The
current pose must already be inside the conservative front workspace
(radius 140–300 mm, X >= 80 mm, Z 70–230 mm) with enough table clearance
for the entire CAD enclosure plus 25 mm, three axial standard deviations,
and the configured bounds on mount translation/rotation error. The full local
pose set must also remain reachable under the arm and joint-limit model.
The scene must contain a broad table and textured, nonplanar static objects.
An empty/textureless table is intentionally rejected. Keep the scene static
through calibration, saving and reload verification.

Launch is passive by default. Starting calibration commands physical motion:

```bash
# Load a matching saved calibration and verify; calibrate if no file exists.
ros2 service call /calibration/start std_srvs/srv/Trigger '{}'
# Discard the old solution for this run and collect a new calibration.
ros2 service call /calibration/recalibrate std_srvs/srv/Trigger '{}'
# Verify an existing file using new independent poses.
ros2 service call /calibration/verify std_srvs/srv/Trigger '{}'
# Query the current verification result / readiness.
ros2 service call /calibration/ready std_srvs/srv/Trigger '{}'
ros2 topic echo /calibration/status
ros2 service call /calibration/cancel std_srvs/srv/Trigger '{}'
```

`auto_start:=true` starts the same load/calibrate/verify workflow on launch.
`recalibrate_on_failure` permits one new calibration attempt after a failed
load or verification during `/calibration/start`. The explicit
`/calibration/verify` operation never refits or falls back to calibration. With its default `false`, failure blocks picking and
requires a new start/recalibrate request. A cancelled or timed-out motion
never triggers an automatic retry. Start responses acknowledge the operation;
the status topic reports its eventual `PASS`/`FAIL` and metrics.

## Safety and evidence

- Six small XYZ/yaw offsets are generated from the initial measured TCP.
  Each uses MOVL at 10% velocity and acceleration and must pass the new
  `/dobot_calibration_validation_service`, which enables the existing arm
  collision model and joint-limit checks. The generic validator alone is
  insufficient because its historical collision checks are commented out.
- All local training and verification paths are preflighted against the initial
  observed scene before training motion. Each executed step checks fresh geometry.
- Table clearance and the observed scene are checked along the full swept
  tool/camera enclosure, inflated for the allowed mount error and path sampling.
  This checks observed obstacles; the legacy arm model
  does not model arbitrary unseen obstacles or people. The workcell must
  provide clear arm travel and exclusive use of robot motion during calibration.
- Capture requires fresh synchronized RGB/depth/CameraInfo/cloud and robot
  samples bracketing the exposure, at least 0.6 s after action completion,
  with submillimetre TCP and small joint variation. Alarms, telemetry loss,
  changed intrinsics, rejected motion, timeout or cancellation fail closed.
  Cancellation and health are rechecked after solving, verification and saving;
  settled captures must match their commanded target.
- Mutual natural-feature matches, depth discontinuity filtering and 3D
  RANSAC initialize registration. Dense trimmed ICP, bidirectional overlap,
  feature consistency and nonplanarity checks reject weak geometry.
- An orientation-constrained RANSAC estimates the table. Robust nonlinear
  refinement combines hand-eye motion, fixed 3D feature correspondences and
  common-base plane consistency. Registration does not start from the
  solution being evaluated.
- Three held-out poses must differ from every training pose. Verification
  estimates fresh camera motions against the stored scene and other held-out
  captures, without fitting X again. It checks translation/rotation residuals,
  plane angle/offset, cloud error, registration fitness and depth-valid ratio.

The worst pair residual, lowest overlap and lowest depth ratio control PASS.
Failed verification retains its computed metrics; loss of readiness always
reports FAIL, even if an earlier verification passed.
Default limits: translation 4 mm, rotation 1.5 degrees, plane offset 4 mm,
plane angle 1.5 degrees, dense consistency 5 mm, registration RMSE 4 mm,
bidirectional registration fitness 0.60, depth-valid ratio 0.35. Limits are
immutable startup ROS parameters under `quality.*`; adjust only with measured sensor
performance and application tolerance.

Verified calibration is saved atomically to
`~/.ros/dobot/markerless_calibration.npz`. This non-pickle bundle includes X,
training poses, the anchor RGB/depth/cloud/plane, camera/mount identity,
intrinsics, thresholds, observability, mount uncertainty and quality reports.
An incompatible/corrupt file fails closed. A stored PASS does not confer
readiness: loading always collects new held-out observations. Replacing the
scene, remounting the camera or changing intrinsics requires recalibration.

Only READY publishes `TCP -> calibrated_camera_optical_frame`. This is a
calibrated alias of the registered optical frame, not a camera-body frame.
Consumers must transform optical points using that alias and enforce the
readiness gate; TF buffers can retain old transforms after failure.

Readiness expires after 600 s and is revoked on sensor/robot telemetry loss
or alarms. `/calibration/status` publishes a fresh heartbeat every 0.2 s.
The repository's `pick_and_place` demo requires this lease before every
movement and gripper command; it cancels an active movement if readiness is
lost and does not resume automatically. The gripper remains in its current
state on failure. Other picking applications must use `PickingGuard` or the
same fail-closed readiness contract. Generic PTP/homing/manual interfaces
remain robot control interfaces, not picking clients.

## Validation

```bash
source /opt/ros/jazzy/setup.bash  # Or the ROS distribution used for the build.
source install/setup.bash
OPENBLAS_NUM_THREADS=1 ROS_DOMAIN_ID=187 python3 -m pytest dobot_calibration/test -q
```

The deterministic test renderer produces a textured static tabletop with
objects at several heights and known camera/robot motion. Tests cover actual
RGB-D registration and constrained transform recovery, independent PASS/FAIL,
the unobservable tool-Z gauge, scene rejection, persistence, pose settling,
path checks, readiness expiry and real offline collision/trajectory checks.
ROS smoke tests use an isolated domain and never import the robot driver. Synthetic tests do not certify the physical
mount, camera driver timing, collision model or real robot accuracy. Perform
the first hardware run in a clear workcell and inspect the reported metrics.
