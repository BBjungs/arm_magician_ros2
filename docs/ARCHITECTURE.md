# Dobot Eye-in-Hand Auto Center architecture

Baseline is `1095058`. The read-only driver exposes `/dobot/device_status`, `/joint_states`, `/dobot/tcp_pose` and `/dobot/alarms`. The pinned Orbbec driver publishes `/camera/color/image_raw`, `/camera/depth/image_raw` and `/camera/color/camera_info`; registered depth uses the color optical frame. No motion endpoint exists in the baseline.

The new `dobot_auto_center` package groups five Python modules (vision, visual servo, safety, motion and web) plus ROS adapters. ROS sensor messages form the input boundary for both simulated and read-only operation. The HTTP server calls the workflow under a shared lock. Only the workflow can mint a single-use permit for the guarded ROS action. The action checks the permit against the exact planned operation and revalidates conditions on acceptance and during execution. There is no raw Cartesian API. Browser lease expiration, frame loss and STOP can interrupt an outstanding action.

Simulation supplies registered RGB-D and independent TCP readback from an in-memory robot. HOME and observation are separate operator-authorized operations. Normal corrections and identification probes hold measured Z and R fixed. The simulated collision model covers swept link and tool envelopes over the motion interval; a commissioned hardware model and stop verification are prerequisites for any real transport. Read-only mode accepts existing ROS telemetry and never constructs a motion transport.

The workflow advances only on qualified observations captured after motion and settling. An explicit lock binds a single track ID to a browser session. Five fresh centered observations complete the run. STOP, unstable identity, lost telemetry, invalid depth and watchdog expiration terminate the run. Unknown motion state latches a fault. Startup does not restore a HOME assertion, track, owner or command.

## Runtime interfaces

| Interface | Type | Direction |
| --- | --- | --- |
| `/camera/color/image_raw` | `sensor_msgs/msg/Image` | Passive vision subscribes to BGR/RGB images. |
| `/camera/depth/image_raw` | `sensor_msgs/msg/Image` | Passive vision subscribes to registered depth. |
| `/camera/color/camera_info` | `sensor_msgs/msg/CameraInfo` | Passive vision subscribes to intrinsics. |
| `/dobot/device_status`, `/dobot/alarms` | `dobot_msgs/msg/DeviceStatus`, `dobot_msgs/msg/AlarmState` | Passive mode subscribes. |
| `/joint_states`, `/dobot/tcp_pose` | `sensor_msgs/msg/JointState`, `geometry_msgs/msg/PoseStamped` | Passive mode subscribes. |
| `/dobot_auto_center/guarded_move` | `dobot_auto_center/action/GuardedMove` | Private to the simulation orchestrator. |

The simulation camera publishes and subscribes to the same relative camera topic paths under `/dobot_auto_center/simulation`. This keeps simulated RGB-D separate from official Orbbec topics even if a process shares the hardware ROS domain. Passive telemetry includes fresh firmware information and reported suction and gripper outputs through the GET driver's `/dobot/suction` and `/dobot/gripper` topics.

The Dobot GET driver reports position in metres and joint angles in radians. The passive adapter converts to mm and degrees for the dashboard, and retains the URDF joint convention. Mock transport TCP readback feeds the workflow directly and is independent of the commanded target. Sensor source timestamps are converted to local monotonic time at reception. The web worker never opens a device or sends ROS goals itself.

At boot, healthy telemetry transitions CONNECTING to IDLE. The operator workflow moves through HOMING, READY, DETECTING, TARGET_LOCKED, CENTERING and CENTERED. Loss of telemetry outside a run clears HOME and moves to DISCONNECTED. STOPPING holds new commands until outstanding action and readback settle, then transitions to STOPPED or FAULT. Observation uses the READY state with an independently verified observation-pose flag.

Configuration is split across `hardware.yaml`, `camera.yaml`, `vision.yaml`, `visual_servo.yaml`, `motion.yaml`, `safety.yaml` and `web.yaml`. Camera and hardware files in this list configure the app adapters. `dobot.yaml` and `orbbec.yaml` configure the separate baseline drivers.
