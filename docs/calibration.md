# Production markerless RGB-D hand-eye calibration

Production calibration for this workcell is markerless only. Do not use
ArUco, AprilTag, ChArUco, checkerboards, printed targets, clicked image points
or photograph-derived mount angles.

## Inputs and fixed geometry

The Orbbec camera is rigidly attached to the rotating Dobot end effector. Its
factory `camera_link` to optical-frame transforms remain authoritative.
As-built measurements are stored in
`config/eye-in-hand-mount-measurement-form.yaml` and converted into the
verified tool convention:

```text
tool/J4 -> suction_tcp       = [  0, 0,  -70] mm
suction_tcp -> camera centre = [-50, 0,  -35] mm
tool/J4 -> camera centre      = [-50, 0, -105] mm
```

The measured translation is a fixed/prior constraint. Mount rotation must be
estimated from markerless scene motion; it must not be inferred from a photo.

## Capture set

Use 8–12 settled poses total. The generated workflow currently uses six
training poses and three held-out poses. Spread X, Y, Z and J4 yaw as widely as
the guarded Magician workspace permits. At every pose the robot must be fully
stopped before synchronously recording:

- TCP pose and all four joint positions;
- rectified RGB and registered depth;
- matching `CameraInfo`;
- registered `PointCloud2`.

Keep a textured, non-planar tabletop scene rigid and unchanged. People,
moving objects, poor depth, stale timestamps and insufficient pose excitation
must fail closed.

## Estimation and validation

Natural RGB-D features and 3D RANSAC estimate pairwise camera motion. Dense
trimmed ICP refines the point-cloud alignment. Table-plane RANSAC and
common-base scene/plane consistency constrain the robust nonlinear hand-eye
solve (`AX = XB`). The held-out 2–3 poses are not used for fitting.

PASS requires acceptable observability and conditioning plus held-out limits
for translation, rotation, point-cloud consistency, registration fitness,
table-plane angle/offset and depth validity. A failure or degeneracy keeps
`geometry_verified: false` and prevents publication of a verified transform.

## Launch

```bash
source install/setup.bash
ros2 launch dobot_calibration markerless_calibration.launch.py \
  mount_model:=/path/to/measured_mount.yaml camera_id:=CAMERA_SERIAL
```

The node is passive until requested. Starting calibration can command guarded
robot motion:

```bash
ros2 service call /calibration/recalibrate std_srvs/srv/Trigger '{}'
ros2 topic echo /calibration/status
ros2 service call /calibration/cancel std_srvs/srv/Trigger '{}'
```

Only a fresh markerless multi-pose validation PASS may make the calibration
READY. Saved bundles are revalidated against fresh held-out observations and
do not bypass the live readiness gate.
