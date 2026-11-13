# Markerless calibration plane support: 30% to 25%

`dobot_calibration.geometry.Limits.min_plane_ratio` now defaults to **0.25**
(previously **0.30**). Both `dominant_plane()` and `table_plane()` consume this
shared limit and reject ratios strictly below it; equality passes the ratio
condition. Ratios are computed after finite/depth filtering, 3 mm voxel
deduplication and the existing 4,000-point cap. An explicit ROS parameter
`quality.min_plane_ratio` override still takes precedence over the default.
No launch/config override was found in the source/configuration search.

The independent object detector's `min_plane_ratio = 0.35` is unchanged.
No unrelated 0.30 constant was changed.

## Status and rejection diagnostics

The `/calibration/status` JSON now exposes the latest candidate under
`plane_diagnostics`, including rejected candidates:

- `plane_inlier_ratio`
- `min_plane_ratio` (default 0.25)
- `plane_inlier_count`
- `plane_rms_m`
- `plane_rejection_reason` (empty when plane checks pass)
- `plane_table_identity` (`UNVERIFIED`)

The same metrics are included in passive capture/test service responses and
accepted-pose metadata. Errors carry diagnostics through the existing retryable
capture error path. Unavailable measurements are JSON `null`, not zero or a
fabricated passing value. Existing `plane_rmse_m`, `plane_inliers` and
`plane_RMS_mm` fields remain available to their existing consumers.

## Preserved checks

Depth-valid ratio remains **0.35**, plane distance **0.004 m**, and minimum
point/inlier count **200**. Plane spatial extent, scene thickness, registration,
workspace/collision, TF/intrinsics, motion/E-stop, final calibration acceptance,
live validation, `dry_run`, and real-motion authorization are unchanged.

The reported real ratios 28.375%, 29.475% and 27.600% clear the new **ratio**
condition. They still need to pass every other capture, registration and
calibration check. No PASS result is forced and no quality gate is bypassed.

## Table identity and recorded-data inspection

The pre-calibration dominant-plane gate deliberately has no world-normal
assumption. A wall or an object top can have sufficient inlier support. The
orientation-constrained table gate retains its expected-normal check, and the
solver retains its inter-pose plane consistency checks. These checks alone
cannot distinguish a tabletop from a broad parallel object surface.

Synthetic tests verify that the orientation gate selects the known table in a
scene containing a larger background wall. A separate test documents that a
parallel object top is **not claimed to be an identified table**. The new
identity field is diagnostic only; it does not alter calibration acceptance.

Read-only offline inspection of
`~/.ros/dobot/passive_pose_1_debug.npz` (modified 2026-11-06) yielded:

- 4,000 filtered points; 1,223 RANSAC inliers; ratio **30.575%**.
- Plane RMS **0.002246555 m**; optical-depth span **1.075–1.131 m**.
- Plane coefficients `[-0.025505, -0.092523, 0.995384, -1.107939]`.

This artifact contains cloud/plane arrays but no synchronized RGB or calibrated
base-frame table reference. The separate annotated image in `/tmp` is from a
different date. Neither establishes the physical surface identity of the three
reported frames. Confirming those frames requires their corresponding inlier
overlay and a measured table reference; this software-only change does not
certify them as tabletop observations.

## Validation

`test_plane_quality.py` contains 24 deterministic tests using the real voxel
filter and RANSAC (no mocked acceptance): 24.9% fails; 25%, 28% and 30% pass
only with adequate geometry; inadequate inlier counts, spatial extent, scene
thickness, depth coverage and invalid clouds remain rejected. Both plane gates
and explicit threshold overrides are covered.

ROS adapter tests exercise rejection diagnostics through `capture()`, the
retryable exception, status serialization, and passive-test response; they
also check that unavailable metrics replace earlier measurements.

Regression commands (all software-only, isolated ROS domains):

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ROS_DOMAIN_ID=187 \
  ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_LOG_DIR=/tmp/plane-ratio-ros-logs \
  .venv/bin/python -m pytest src/magician_ros2/dobot_calibration/test \
  -q --tb=short --junitxml=/tmp/plane-ratio-calibration-tests.xml

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ROS_DOMAIN_ID=188 \
  ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_LOG_DIR=/tmp/plane-ratio-web-logs \
  .venv/bin/python -m pytest \
  src/magician_ros2/dobot_web_interface/test/test_markerless_calibration_api.py \
  src/magician_ros2/dobot_web_interface/test/test_system_integration.py \
  src/magician_ros2/dobot_web_interface/test/test_operator_calibration_ui.py \
  -q --tb=short --junitxml=/tmp/plane-ratio-web-tests.xml
```

Final full calibration regression: **395 passed, 0 failed, 0 skipped**
(196.831 seconds), including the 24 plane-quality cases and ROS adapter tests.
The Web API/integration suite passed 15 tests; its JavaScript UI test was
skipped because Node.js is unavailable. No production services were restarted,
no live calibration was started, and no physical robot motion was commanded.
