# One-Click Vision Calibration

The normal calibration flow is designed to require one user action after the
calibration board is positioned and measured: select the camera mode, confirm
printed scale and measured fixture pose, and press **Auto Calibrate**. Calibration never moves the robot and always runs in dry-run mode.

## What the user must do

1. Open **Settings and Calibration** in the Web UI.
2. Open the printable ArUco board for the selected camera mode. Print at 100%
   scale (A4 portrait, Actual size, no Fit-to-page or browser headers/footers).
   The Web link opens `/api/vision/calibration/print?mode=eye_in_hand`, with
   a Print / Save PDF button. Each marker is 30 × 30 mm; center spacing is
   80 × 160 mm, while the artwork is 130 × 210 mm. Measure both axes after
   printing. The original SVG endpoint remains available.
3. Mount the print on a rigid, flat sheet. Place it against the known table
   reference or fixture. Marker labels use **board-local** coordinates, not robot
   base coordinates. Measure the center crosshair's XYZ and board orientation
   relative to the robot base and confirm they match the printed `pose_base`.
   Include sheet/fixture thickness; configured values are not measured truth.
4. For the wrist-mounted camera select **Eye-in-hand** (the Web default).
   Confirm that the mount follows the TCP rotation assumed by the model.
   Keep the board, camera, and robot still, check the measured-fixture box,
   then press **Auto Calibrate** once. Confirmation resets after each attempt.
5. Validate independent, physically measured points before dry-run pick preview.
   A good reprojection error alone does not prove the fixture pose is correct.

The fixed-camera and eye-in-hand paths share
`dobot_vision_yolo/config/aruco_board.yaml`. The current dictionary is
`DICT_4X4_50`, the required IDs are `[0, 1, 2, 3]`, and all four markers
must be fully visible in every frame used by a solve. A missing marker may be
projected as a red visualization aid, but it is never a calibration
observation.

The OpenCV corner order is explicitly top-left, top-right, bottom-right,
bottom-left in a right-handed board frame. SVG/image pixel Y points down, but
board +Y points up on the printable sheet. The printable ID layout is:

```text
3 ---- 2     +X: 0 -> 1
|      |
0 ---- 1     +Y: 0 -> 3 (up on the print)
```

Marker centers are board-local coordinates:

```text
ID 3 [-40,  80, 0] mm    ID 2 [ 40,  80, 0] mm
ID 0 [-40, -80, 0] mm    ID 1 [ 40, -80, 0] mm
```

The 80 x 160 mm values are center-to-center spans. The separate configured
`pose_base` maps this local board frame to the Dobot base frame. With the
current fixture pose `[220, 0, -35]` mm and zero rotation this produces the
absolute marker centers `[180,-80,-35]`, `[260,-80,-35]`,
`[260,80,-35]`, and `[180,80,-35]`.

Boards generated before this handedness fix placed IDs 0/1 on the top row.
Those sheets reflected board Y and must not be used for eye-in-hand PnP even if
a 2-D fixed-camera homography appears to pass. Reprint the board: the corrected
sheet has IDs 3/2 on the top row and IDs 0/1 on the bottom row.

> A fixed physical reference is unavoidable. Vision can detect a bad image or
> inconsistent geometry, but it cannot detect a board that is consistently
> placed at the wrong robot X/Y coordinates. A locating fixture is strongly
> recommended so the operator only has to place the board against a stop.

## What the system checks automatically

### Fixed camera

The system captures 12 fresh frames and divides them into separate fitting and
verification sets. It then checks:

- every required marker is repeatedly detected in both sets;
- corner jitter is low enough that the camera and board were stationary;
- markers cover enough of the camera image;
- the RANSAC homography has enough inliers;
- error on the untouched verification frames is within limits;
- leave-one-marker-out cross-validation is within limits.

Default limits are in
`src/magician_ros2/dobot_vision_yolo/config/camera_to_robot.yaml` under
`auto_calibration`.

### Eye-in-hand camera

When the camera publishes ROS `CameraInfo`, the system automatically uses its
factory lens calibration (`fx`, `fy`, principal point, and distortion). The
YAML intrinsics file remains a display/conversion fallback, but new automatic
Eye-in-hand calibration requires fresh ROS CameraInfo (within 5 seconds), with
matching image resolution and optical frame. It rejects a fallback-only run.

The system discards the pre-request cached image and captures multiple fresh
frames. TCP state must be received within 500 ms at the start/end. Every captured
frame must have TCP timing evidence within 500 ms and remain within 0.5 mm / 0.2°
of the starting pose; sampled active goals are rejected. CameraInfo must not
change during the capture. These receipt-time checks are not exact synchronization
and do not prevent commands from other ROS clients: do not command motion during
calibration. It estimates the camera mount from every valid frame, then checks:

- enough frames contain all required markers;
- solvePnP reprojection error is within limits;
- camera translation and rotation estimates agree between frames;
- the resulting camera mount distance is physically plausible;
- the camera optical axis is looking down within the configured limit.

This is an **anchored-board extrinsic solve**, not general hand-eye
`AX=XB`. Its equations use column vectors:

```text
T_base_camera = T_base_tcp * T_tcp_camera
P_base        = T_base_camera * P_camera

T_base_camera = T_base_board * inverse(T_camera_board)
T_tcp_camera  = inverse(T_base_tcp) * T_base_camera
```

`T_camera_board` comes from solvePnP using board-local points.
`T_base_board` must come from a physically measured locating fixture. A
single TCP pose cannot simultaneously determine an unknown board pose and an
unknown camera mount. If the board is free to move, use a separate multi-pose
hand-eye workflow with sufficiently different robot translations and
rotations; do not treat this anchored solve as `calibrateHandEye()`.

The configured camera mount is always `T_tcp_camera` (parent `tcp`, child
`camera_optical`). RPY uses column vectors with
`R = Rz(yaw) @ Ry(pitch) @ Rx(roll)`: intrinsic XYZ, equivalently extrinsic
ZYX. The optical frame follows the camera convention (+X right, +Y down, +Z
forward). The default 180-degree roll makes optical +Z point toward base -Z
when the TCP rotation is zero.

The `dobot_pose_raw` topic publishes XYZ in metres and R in degrees. ROS
subscribers convert XYZ explicitly to millimetres; all calibration geometry and
translations after that boundary are millimetres.

RGB frames have a ROS header timestamp. `dobot_pose_raw` is a headerless
`Float64MultiArray`, so exact RGB/TCP synchronization is not available; the
diagnostics report receive-time delta and reject a run if the TCP changes while
frames are captured. Registered depth and RGB/depth synchronization are
reported for diagnosis, but ArUco homography/PnP uses RGB corners and does not
consume depth.

Default limits are in
`src/magician_ros2/dobot_vision_yolo/config/eye_in_hand.yaml` under `aruco`.

## Fail-safe save behavior

A new result is saved only when every required check passes. If recalibration
fails, the last valid calibration remains active and the response reports
`previous_calibration_preserved=true`. An unsuccessful attempt cannot replace a
known-good calibration.

Default pass gates are not relaxed by the UI:

- valid frames at least 80% (10 of the normal 12 captures);
- homography RANSAC inliers at least 80%;
- held-out mean error at most 5 mm and maximum at most 10 mm;
- marker leave-one-out mean error at most 5 mm and maximum at most 10 mm.

The UI reports:

- fresh frame count;
- detected or missing marker IDs;
- image/mount stability;
- independent verification error;
- whether a new result was saved or the previous result was preserved.

## HTTP API

Generate the board for the selected mode:

```text
GET /api/vision/calibration/board.svg?mode=fixed_camera
GET /api/vision/calibration/board.svg?mode=eye_in_hand
```

Run the same one-click process used by the UI:

```bash
curl -X POST http://localhost:8080/api/vision/calibration/auto \
  -H 'Content-Type: application/json' \
  -d '{"dry_run":true,"vision_mode":"fixed_camera"}'
```

For a wrist-mounted camera, use `"vision_mode":"eye_in_hand"`.

Read the most recent status:

```text
GET /api/vision/calibration
GET /api/vision/eye_in_hand/status
```

The fixed-camera result uses `source=aruco_auto_holdout`; the eye-in-hand result
uses `source=aruco_auto_multiframe`.

## Manual fallback

Manual U/V and robot X/Y entry remains available under **Advanced: Manual
fixed-camera calibration**. It is intended for commissioning or recovery when
an ArUco board cannot be used. Use at least four widely separated points, keep
them on the same table plane, and test independent points before use.

Do not enable real pick motion merely because calibration passed. Verify a few
known positions in dry-run, then perform the first hardware test at low speed
with an operator ready to stop the robot.

## Deployment and ready-to-print fallback

The current-backend print page is generated from the selected mode's board config.
Its print ID is a checksum of the SVG, not certification of physical measurement.
A frozen standard-board fallback is served at `/static/calibration_board_a4.html`;
regenerate it if board geometry or fixture config changes. A ready-to-print PDF is
also served at `/static/calibration_eye_in_hand_a4.pdf`.

After building, the existing Python Web process must be reloaded to activate the
new API and capture guards. The updated UI checks the new print endpoint and
blocks calibration if the backend is still old; printing remains available through
the fallback. Do not restart the complete hardware stack merely to reload the Web.
The new eye-in-hand API requires JSON `fixture_measured: true` and boolean
`dry_run: true`; this is an operator declaration, not an automatic measurement.
The legacy eye-in-hand calibrate endpoint now uses the same multi-frame guards
and rejects manual mount/marker overrides.

Keep Vision `dry_run_default: true` and `allow_real_motion: false`. No homing,
actuation, tool test, or robot motion is part of printing/calibration commissioning.
