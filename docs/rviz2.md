# RViz2: full Magician model and Orbbec

The model and meshes come from https://github.com/jkaniuka/magician_ros2.
`urdf_full.rviz` shows RobotModel, TF, color and normalized depth images.
It uses `/robot_description` with transient-local durability and `/joint_states`
from the existing Dobot state publisher. `/dobot_joint_states` has different
joint-3 semantics and must not replace `/joint_states` for this URDF.

From a desktop terminal, with the existing camera/robot stack already running:

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
# Match the running deployment (currently Fast DDS).
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 launch dobot_description display.launch.py tool:=suction_cup
```

This launches visualization only. It does not launch hardware drivers or command
motion. `DOF:=auto` selects 3 for none/pen and 4 for the other tools. `tool` defaults
to `MAGICIAN_TOOL`, or suction_cup when unset. `gui:=true` is for offline model
inspection only; do not publish slider states alongside live robot states.
Use `publish_robot_description:=false` if robot_state_publisher is already running.
Use `rviz:=false` to publish only the model and TF on a machine without a desktop.

When starting the combined stack, `dobot_auto.launch.py` also accepts
`start_rviz:=true`, `enable_point_cloud:=true` and
`enable_colored_point_cloud:=true`. Defaults remain false. Do not start another
camera driver if an existing service owns the device. Set these options on the
next planned launch of that service/stack.

For point clouds in the camera's own coordinates:

```bash
ros2 launch dobot_description camera_view.launch.py
```

The installed Orbbec driver publishes depth points on `/camera/depth/points`
and colored points on `/camera/depth_registered/points` when enabled. Enable the
Colored Points display once that stream is available. The default fixed frame
is `camera_link`; it can be overridden with `fixed_frame:=...`. For a custom
camera namespace, change the Image/PointCloud topics in RViz and save a config.

Displaying 2D images beside the robot does not require camera-to-robot TF.
Overlaying a 3D cloud on the robot does require a measured/calibrated transform.
No assumed camera-to-robot transform is published here. `use_camera:=true` is
the upstream RealSense mesh, not an Orbbec model or calibration.

Depth image normalization is for display only and does not repair invalid depth.
If the model is missing, check `/joint_states`, `/robot_description` and the TF
display. If sensor images are missing, check fresh messages and Best Effort QoS.
