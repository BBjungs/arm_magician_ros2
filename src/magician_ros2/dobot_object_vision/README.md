# RGB-D circular suction targets

Detects **black, white and yellow** circular targets using OpenCV contours,
color, metric size, depth and a robust table plane. No trained model or YOLO
is required. This package never sends robot commands.

## Build and run

```bash
source /opt/ros/jazzy/setup.bash
colcon build --packages-up-to dobot_object_vision
source install/setup.bash
ros2 launch dobot_object_vision object_vision.launch.py
ros2 topic echo /object_vision/detections
# View /object_vision/annotated with an Image viewer.
```

The default configuration expects rectified RGB, depth registered into the
same color optical frame/raster, and fresh stamped CameraInfo. Depth supports
`16UC1` in millimetres or `32FC1` in metres. All outputs use **metres**.
Configuration parameters are read-only after startup.

For the Orbbec driver with `depth_registration:=true`, use a copy of
[`config/orbbec_registered.yaml`](config/orbbec_registered.yaml):

```bash
ros2 launch dobot_object_vision object_vision.launch.py \
  config:=/absolute/path/to/orbbec_registered.yaml
```

This preset reads `/camera/color/image_raw`, `/camera/depth/image_raw`, and
`/camera/color/camera_info`. `input_rectified: false` undistorts both registered
images using CameraInfo; depth uses nearest-neighbour remapping to avoid
blending object and table depths. It supports plumb-bob/rational distortion
with identity rectification rotation. It does not register native depth-camera
pixels into the color camera. Misaligned frames, mismatched dimensions,
unsupported cropping/binning, stale messages and invalid intrinsics are rejected.

## Detection and suction checks

1. Fit a broad table plane with orientation-constrained RANSAC and SVD using
   spatially distributed depth. Require boundary support to reduce confusion
   with a large object's top. The view must contain exposed table around the
   targets, with its normal within 50 degrees of the negative optical Z axis.
2. Combine HSV color masks with height above the table. This separates
   same-color targets from their table background. Reject clipped, small,
   noncircular and merged contours.
3. Sample an interior region, excluding the contour edge. Use the median and
   median absolute deviation of plane-relative depth, rejecting outliers;
   a missing single center pixel does not invalidate an otherwise supported top.
4. Fit a robust circle in the estimated object-top plane. This produces a
   metric diameter and center even in tilted views. Intersect the center ray
   with the robust top plane to obtain camera XYZ and optical Z depth.
5. Check the suction disk at that center for valid depth, consistent height,
   color and clearance from the contour. Rings/holes and another surface under
   the center are rejected. Sparse/noisy surfaces or low confidence are never
   marked pickable.

Default deployment bounds are **15–80 mm diameter**, **3–60 mm height**, and
**4 mm suction radius**. These are configurable starting ranges, not measured
properties of the user's targets. HSV thresholds are also `rules.*` parameters;
lighting/white balance must leave the three classes distinguishable.

The confidence value is a bounded rule score, not a learned probability. It
combines contour circularity, color purity, interior depth support and metric
circle residual. `pickable` additionally requires at least 80% valid interior
and suction-patch depth, top MAD at most 2 mm, and confidence at least 0.75.

`pickable` means **visually suitable for suction**. It does not establish robot
reachability, collision clearance, calibration validity or an object identity
across frames. The picking application must also enforce Phase 5's calibration
readiness lease and its motion checks. Camera-space detections remain usable
for inspection while calibration is unavailable.

## Published contract

`/object_vision/detections` uses `dobot_msgs/msg/CircleTargetArray`:

- `header`: RGB exposure timestamp and registered camera optical frame.
- `valid`, `reason`: validity of this RGB-D result. On failure/staleness the
  array is empty and `valid=false`; previous targets are never reused.
- `table_plane`: unit-normal `[nx, ny, nz, d]`, where `n dot X + d = 0`.
  Normal points towards the camera. `table_inlier_ratio` and `table_rmse`
  expose table quality.
- `detections`: `dobot_msgs/msg/CircleTarget` entries below.

| Requested output | ROS field | Meaning |
| --- | --- | --- |
| id | `id` | Frame-local ID; use `(header.stamp, id)` as the observation key |
| class | `class_name` | `black`, `white`, or `yellow` |
| center_uv | `center_uv` | Subpixel `[u, v]` in the rectified annotated image |
| camera_xyz | `camera_xyz` | Point in the optical frame, metres |
| depth | `depth` | Optical Z, equal to `camera_xyz.z`; not Euclidean range |
| size | `size` | Circle diameter in its top plane, metres |
| confidence | `confidence` | Rule score in `[0, 1]` |
| pickable | `pickable` | Visual suction suitability |

Each target also includes `top_height`, `depth_valid_ratio`, `depth_mad`, and
`rejection_reason`. Entries always contain finite, depth-supported XYZ; an
unmeasurable image candidate is filtered rather than assigned an invented point.
Targets with measurable XYZ but insufficient suction quality can remain in
the array with `pickable=false` and an explanation.

`/object_vision/annotated` is a `sensor_msgs/msg/Image` (`bgr8`) with the same
exposure timestamp. Green targets pass suction checks; orange targets are not
pickable, and rejected contours appear in red. The annotation includes ID,
class, diameter and depth. Camera coordinates are X right, Y down, Z forward.

Processing keeps the latest synchronized frame, at up to 5 Hz by default.
Maximum input skew is 50 ms and maximum exposure age is 500 ms. Results are
rechecked after processing, and a watchdog publishes empty invalid arrays when
the stream stops. Consumers must check `valid` and exposure age themselves;
no retained ROS message grants an indefinite permission to pick.

## Validation

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
OPENBLAS_NUM_THREADS=1 ROS_DOMAIN_ID=191 python3 -m pytest dobot_object_vision/test -q
```

Tests render metric targets with known XYZ on flat and tilted tables, and cover
three-color classification, same-color backgrounds, missing center depth,
interior outliers, sparse depth, printed circles, rings, rectangles, clipped
and oversized objects, bad table geometry, input units, rectification, ROS
publication and stale-stream clearing. Synthetic tests measure geometry
accuracy; they do not certify reliability on the physical targets.

During the September 8, 2026 live check, the connected Orbbec camera provided
synchronized 640x480 RGB and registered depth with matching optical frames.
The RGB image showed circular targets, but **all 307,200 depth pixels were zero**.
The detector rejects this frame and publishes no valid XYZ or pickable targets.
Real-target acceptance remains pending usable depth from the camera.
