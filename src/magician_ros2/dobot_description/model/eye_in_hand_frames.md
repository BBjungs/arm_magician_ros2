# Eye-in-hand frame geometry

| Frame | Definition and publisher |
| --- | --- |
| `magician_root_link` | Upstream model root. |
| `magician_base_link` | Existing robot kinematic base, 0.131305 m above the model root. |
| `tool` | Identity alias of `magician_link_suction_cup`, the rotating joint-4 carrier. Published by robot_state_publisher. |
| `camera_link` | Orbbec driver's base camera frame. Its measured pose in `tool` is published by robot_state_publisher. It is not an assumed case-centre or optical origin. |
| `camera_depth_optical_frame`, `camera_color_optical_frame` | Factory sensor transforms, published only by the Orbbec driver. Optical axes are +X right, +Y down, +Z forward. |
| `suction_tcp` | Measured suction contact frame relative to `tool`, independently specified from the camera. Published by robot_state_publisher. |
| `TCP` | Existing controller pose frame published by the state updater. Kept separate from the measured suction contact frame. |

The full path is `magician_base_link -> robot joints -> tool -> camera_link -> factory camera frames`.
The suction branch is `tool -> suction_tcp`. Camera attachment to a stationary wrist bracket does not match this rotating-tool model; confirm the physical attachment first.

All translations use metres. RPY uses radians with column vectors and `R = Rz(yaw) Ry(pitch) Rx(roll)`.
Each parent-to-child transform maps coordinates expressed in the child into the parent.
For an optical point, `p_base = T_base_tool T_tool_camera_link T_camera_link_optical p_optical`.

Copy `eye_in_hand_mount.yaml` and fill it from physical measurements or validated CAD/calibration.
The checked-in template is deliberately unverified with empty offsets. It cannot enable camera or suction TF.
Existing invalid camera calibration and legacy RealSense offsets are not imported.

With a verified file, start the single robot-description publisher:

```bash
ros2 launch dobot_description display.launch.py tool:=suction_cup rviz:=false eye_in_hand_config:=/path/to/verified_mount.yaml
```

Run the Orbbec driver with `publish_tf:=true` to provide factory sensor extrinsics and optical rotations.
Do not add competing static optical transforms or a second robot_state_publisher.
Feed `/joint_states` to the model; `/dobot_joint_states` uses different joint-3 semantics.
Use timestamped TF lookups when converting images acquired during motion.

Geometry tests use synthetic offsets solely in the test process. Passing these tests does not verify the physical mount.
