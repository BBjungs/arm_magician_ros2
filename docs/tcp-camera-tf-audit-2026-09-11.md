# TCP and camera commissioning audit — 2026-09-11

Workspace: `/home/bbcontact/magician_ros2`. The running ROS stack uses this
workspace; `/home/bbcontact/dobot-ros2-ai` does not exist. Workspace writes were
successful. The command sandbox failed to configure loopback (Operation not
permitted), so read-only ROS inspection required approved execution outside it.
This did not repair the sandbox itself.

## Recorded measurement defaults

> Superseded on 2026-09-15: the authoritative as-built record is now
> `config/eye-in-hand-mount-measurement-form.yaml`: 50 mm closer to the robot
> base, 0 mm centred, and 35 mm below from suction TCP to camera centre. The
> converter owns the signed-axis mapping. Values below are historical only.

`config/camera-mount-measurements.yaml` records the user's physical directions:
50 mm away from the robot base, 0 mm sideways, 35 mm upward (0.050/0/0.035 m).
These are commissioning inputs, not a validated TCP-to-camera transform.
The physical measurement origin, camera endpoint, mapping to TCP-local axes,
and camera rotation still need confirmation. No runtime mount was activated.

## Live observations

Captured at 2026-09-11 07:27:52 UTC (14:27:52 Asia/Bangkok), using ROS domain 0
and `rmw_fastrtps_cpp`. A 12-second subscriber-only inspection received 185
`/tf` messages and one transient-local `/tf_static` message.

Observed TF edges:

- `magician_base_link -> TCP` (dynamic)
- `camera_link -> camera_depth_frame` (static, identity)
- `camera_depth_frame -> camera_color_frame` (factory extrinsic)
- `camera_color_frame -> camera_color_optical_frame` (static)
- `camera_depth_frame -> camera_depth_optical_frame` (static)

The latest TCP translation was approximately [149.984879, 0, 99.986565] mm.
Its quaternion XYZW was [0, 0, -1.46865508e-10, 1], effectively zero yaw.
The latest transform timestamp was about 0.051 seconds before capture ended.
`/dobot_TCP`, `/dobot_pose_raw`, and TF agreed on the reported pose.
TCP X/Y/Z therefore align with base X/Y/Z at this observed pose. This is a
software-frame observation, not a physical survey of the robot or suction tip.

Both `TCP <- camera_link` and `TCP <- camera_color_optical_frame` lookups
failed because the frames belong to disconnected TF trees. Internal optical
frame rotations do not establish the camera's orientation relative to the arm.

## TCP physical reference remains unresolved

`src/magician_ros2/dobot_state_updater/dobot_state_updater/dobot_state_publ.py`
publishes the controller's `bot.get_pose()` XYZ (converted from mm to m), and
uses its R value as yaw for both TCP topic and TF. No extra suction-tip offset
is applied in that publisher. Agreement between those outputs is therefore
not independent evidence that the reported TCP is the point used for measuring.
The physical suction tip and effective controller tool offset require verification.

## Next steps

1. Confirm the exact physical start/end points of the 50/0/35 mm measurement
   and verify the physical direction of TCP axes.
2. Determine camera rotation relative to TCP from measurement or calibration.
3. Only then construct the mount transform, including any offset between the
   measured housing point and the selected camera frame origin.
4. Verify camera/mount envelope and table clearance, then validate calibration
   against independent measured points before real picking.

No robot movement, homing, tool actuation, calibration run, parameter changes,
or mount TF publication was performed during this audit.
