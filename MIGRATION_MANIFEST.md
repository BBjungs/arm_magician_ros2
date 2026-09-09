# Canonical workspace migration manifest

Date: 2026-09-09  
Canonical workspace: `/home/bbcontact/magician_ros2`

## Pre-migration runtime inventory

- Canonical Git base commit: `6d322f4cc2d752f6bb59c67b4cdb09317a287721`.
- Validated Dobot source: `/home/bbcontact/dobot-ros2-ai/src/magician_ros2`,
  repository commit `db8d5579b1aa57e386358b21c44681133e62d7a2`
  plus uncommitted hardware-validated protocol, motion, state, vision, and
  deployment changes.
- Validated live Dobot install:
  `/tmp/dobot-readiness-20260906/install`.
- The old state publisher owned `/dev/ttyUSB0` and resolved from the temporary
  install. It was stopped only after the canonical build and software tests.
- The official Orbbec checkout was already present in the canonical workspace:
  `src/OrbbecSDK_ROS2`, branch `main`, commit
  `0ea4ab68f5b8ddf22998b7c45d251dc58ea2779e`.
- No old `build/`, `install/`, or `log/` directory was copied.

## Package source decisions

| Package | Source selected | Canonical target | Action |
|---|---|---|---|
| dobot_bringup | validated Dobot tree | `src/magician_ros2/dobot_bringup` | REPLACE; retain tool isolation |
| dobot_control_panel | validated Dobot tree | `src/magician_ros2/dobot_control_panel` | REPLACE |
| dobot_demos | canonical + validated tree | `src/magician_ros2/dobot_demos` | MERGE; retain calibration picking guard |
| dobot_description | validated Dobot tree | `src/magician_ros2/dobot_description` | REPLACE |
| dobot_diagnostics | validated Dobot tree | `src/magician_ros2/dobot_diagnostics` | REPLACE |
| dobot_driver | hardware-validated tree | `src/magician_ros2/dobot_driver` | REPLACE; validated protocol authoritative |
| dobot_end_effector | validated Dobot tree | `src/magician_ros2/dobot_end_effector` | REPLACE; suction/gripper isolated |
| dobot_homing | validated Dobot tree | `src/magician_ros2/dobot_homing` | REPLACE |
| dobot_kinematics | canonical + validated tree | `src/magician_ros2/dobot_kinematics` | MERGE; calibration validation + motion safety |
| dobot_motion | hardware-validated tree | `src/magician_ros2/dobot_motion` | REPLACE |
| dobot_msgs | canonical + validated tree | `src/magician_ros2/dobot_msgs` | MERGE; retain CircleTarget interfaces |
| dobot_state_updater | validated + canonical timestamp fix | `src/magician_ros2/dobot_state_updater` | MERGE |
| dobot_visualization_tools | canonical source | `src/magician_ros2/dobot_visualization_tools` | KEEP/MOVE |
| dobot_vision_rgbd | validated Dobot tree | `src/magician_ros2/dobot_vision_rgbd` | COPY |
| dobot_vision_yolo | validated Dobot tree | `src/magician_ros2/dobot_vision_yolo` | COPY |
| dobot_web_interface | validated Dobot tree | `src/magician_ros2/dobot_web_interface` | COPY |
| dobot_calibration | canonical source | `src/magician_ros2/dobot_calibration` | KEEP/MOVE |
| dobot_object_vision | canonical source | `src/magician_ros2/dobot_object_vision` | KEEP/MOVE |
| orbbec_camera | canonical official checkout | `src/OrbbecSDK_ROS2/orbbec_camera` | KEEP |
| orbbec_camera_msgs | canonical official checkout | `src/OrbbecSDK_ROS2/orbbec_camera_msgs` | KEEP |
| orbbec_description | canonical official checkout | `src/OrbbecSDK_ROS2/orbbec_description` | KEEP |

## Protected protocol files

The following canonical files are byte-for-byte equal to the hardware-tested
source:

| File | SHA-256 |
|---|---|
| `dobot_driver/dobot_driver/message.py` | `fe14df5513b278ba74c1aea1482ddd530a4fd060e1cd263a3bcb737f15c2fc49` |
| `dobot_driver/dobot_driver/interface.py` | `70b8c4b8625e2a7f89f037deda5240b084a6fcb19dbcf1073e37d08a0c9603ef` |
| `dobot_driver/dobot_driver/parsers.py` | `d501508a8e4097590da171cbc389265788bc6b54cda0121d1497bdd39acbe0dd` |
| `dobot_driver/test/test_message_safety.py` | `b64e3b329b245ebd9abe7bb99dcbb848184132df6fcac96df6c520fca0985986` |
| `dobot_driver/test/test_protocol_responses.py` | `bf880dbb9a4e2b42f51c29b0f6f94c94b12dee4c03652f008a82a8c1e6b56bbb` |

These preserve framing/checksum validation, command-ID matching, ACK
consumption, IDs 62/63/80/81/83/84/246, bounded recovery, and cross-process
serial locking.

## Canonical-only normalization

- Relocated ROS packages from repository root into `src/magician_ros2`.
- Migrated source-only `config/`, `scripts/`, `systemd/`, `docs/`, and
  `requirements-yolo-train.txt`.
- Normalized operational documentation and deployment paths.
- Changed the autostart default tool to `suction_cup`.
- Repointed the inactive user systemd service symlink to the canonical unit.
- Added `colcon.meta` to pin only `orbbec_camera` to Ubuntu OpenCV 4.6,
  avoiding the incompatible `/usr/local` OpenCV 4.10 libraries.
- Added safe in-code axis-limit defaults identical to
  `dobot_kinematics/config/axis_limits.yaml`; launch YAML still overrides.
- Pinned the integrated Orbbec launch to LDP OFF. Live evidence showed LDP ON
  produced zero-only depth on this Gemini.
- Vision remains fail-closed: dry-run default true and real motion disabled.

## Verification

- Clean canonical build: 21 packages passed.
- Protocol/motion/kinematics safety suite: 38/38 passed.
- Calibration suite: 64/64 passed.
- Description/object-vision/RGB-D/YOLO/web suite: 158/159 passed.
- Remaining test debt:
  `test_raw_registered_rgbd_is_rectified_before_deprojection` rejects one
  synthetic edge contour under Ubuntu OpenCV 4.6; no live vision behavior was
  changed to hide it.
- Clean-shell prefixes for every project package resolve under
  `/home/bbcontact/magician_ros2/install`.
- Camera: RGB 30.0 Hz, registered depth 30.0 Hz, point cloud approximately
  28-29 Hz; 55.8% non-zero depth, 195/223/230 mm min/median/max; valid
  intrinsics and camera static TF.
- Robot: MOVL Z +10.000000 mm succeeded, return succeeded with zero reported
  Cartesian error; maximum TCP gap 0.0571 s and alarm gap 0.1097 s; no alarms.
- Suction ON/OFF acknowledged; final ID 62 state `(False, False)`, ID 63
  remained `(False, False)`. This is controller state, not vacuum pressure.

## Remaining reproducibility dependencies

`rosdep check` reports these apt keys unsatisfied:

- `ros-jazzy-diagnostic-aggregator`
- `ros-jazzy-tf-transformations`
- `python3-fastapi`
- `python3-uvicorn`

FastAPI and Uvicorn are currently importable from the user Python environment.
Installing the apt dependencies was not possible because sudo requires an
interactive password. The two canonical Python package manifests also expose
an unresolved rosdep key `ament_python`; builds remain successful.

## Retention

- `/home/bbcontact/dobot-ros2-ai`: KEEP_FOR_REFERENCE until a separate archive
  approval; no runtime dependency remains.
- `/tmp/dobot-readiness-20260906`: SAFE_TO_ARCHIVE after review; no runtime
  dependency remains. Do not delete it as part of this migration.
