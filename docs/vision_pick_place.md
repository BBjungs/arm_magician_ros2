# Vision Pick-and-Place End-to-End Test

This guide runs the Dobot vision flow from camera and YOLO detection through calibration, target selection, dry-run preview, and guarded real pick.

Default safety state:

- `dry_run=true`
- `allow_real_motion=false`
- Real motion is blocked unless explicitly enabled.
- Always use `Preview Pick` and `/api/vision/validate_pick` before real motion.

## Full-system startup order

For a commissioned system, `dobot_auto.launch.py` uses the web integration
gate. The order is fixed: robot services and fresh joints, live camera,
synchronized valid RGB-D, live calibration PASS, HOME, then the configured
observation pose. Check it with:

```bash
curl http://localhost:8080/api/system/status
curl -X POST http://localhost:8080/api/system/startup
```

The startup request verifies calibration but does not issue HOME by default.
Use the operator screen's **HOME และจุดสังเกต** button once the workcell is
clear. Enable automatic startup motion only with both explicit launch options:

```text
startup_auto:=true startup_auto_motion:=true
```

During `pick_all`, the backend verifies the release, returns to observation,
and requests a new frame before selecting each subsequent part. It stops safely
on stale depth, camera/robot loss, calibration loss, an occupied place, an
unreachable pose, or an unverified pick/release. `POST /api/cancel` is a
cell-wide STOP and also cancels live calibration.

## 1. Install Dependencies

```bash
cd /home/bbcontact/magician_ros2
sudo apt update
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-pip \
  python3-fastapi \
  python3-uvicorn \
  python3-opencv \
  ros-jazzy-cv-bridge \
  python3-yaml
python3 -m pip install --user --no-deps ultralytics
```

## 2. Build

```bash
cd /home/bbcontact/magician_ros2
source /opt/ros/jazzy/setup.bash
source /home/bbcontact/magician_ros2/install/setup.bash
rosdep install --from-paths src/magician_ros2 --ignore-src -r -y
pip3 install -r src/magician_ros2/requirements.txt
colcon build
source install/setup.bash
```

## 3. Start Web and Robot Stack

Dry-run web only:

```bash
cd /home/bbcontact/magician_ros2
source /opt/ros/jazzy/setup.bash
source /home/bbcontact/magician_ros2/install/setup.bash
source install/setup.bash
ros2 launch dobot_web_interface dobot_auto.launch.py \
  host:=127.0.0.1 \
  port:=8080 \
  start_bringup:=false \
  start_camera:=true \
  start_vision:=true
```

Full control stack plus web:

```bash
cd /home/bbcontact/magician_ros2
source /opt/ros/jazzy/setup.bash
source /home/bbcontact/magician_ros2/install/setup.bash
source install/setup.bash
ros2 launch dobot_web_interface dobot_auto.launch.py \
  tool:=suction_cup \
  host:=127.0.0.1 \
  port:=8080 \
  start_bringup:=true \
  start_camera:=true \
  start_vision:=true
```

Open:

```text
http://<robot-ip>:8080/
```

## 4. Start Detector

```bash
cd /home/bbcontact/magician_ros2
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run dobot_vision_yolo yolo_detector_node --ros-args \
  -p dry_run:=true \
  -p prefer_tensorrt:=true \
  -p model_path:=models/best.engine \
  -p fallback_model_path:=models/best.pt \
  -p device:=cuda \
  -p imgsz:=640 \
  -p precision:=fp16
```

Detector status:

```bash
ros2 topic echo /dobot_vision/status
```

HTTP status:

```bash
curl http://localhost:8080/api/vision/status
curl http://localhost:8080/api/vision/detections
```

## 5. Test Detection

From the web page, press `Detect Once`.

Or call:

```bash
curl -X POST http://localhost:8080/api/vision/detect_once \
  -H 'Content-Type: application/json' \
  -d '{"dry_run":true,"object_class":"all","place_id":"tray_A"}'
```

Expected result:

- `/api/vision/status` has `ok:true`
- `/api/vision/detections` shows detections
- annotated image appears in the Vision Pick page

## 6. Calibration

Follow [calibration.md](calibration.md). The short version:

1. Prepare a textured, non-planar static tabletop scene without fiducials.
2. Keep the scene unchanged through all training and held-out poses.
3. Start the guarded markerless calibration workflow.
4. Check that markerless multi-pose validation reaches PASS.

The system fits and verifies on separate frame sets. A failed attempt preserves
the last valid calibration.

Check calibration:

```bash
curl http://localhost:8080/api/vision/calibration
```

## 7. Select Target

```bash
curl -X POST http://localhost:8080/api/vision/select_target \
  -H 'Content-Type: application/json' \
  -d '{
    "object_class":"black_cap",
    "place_id":"Zone A",
    "selection_mode":"highest_confidence",
    "manual_id":null,
    "dry_run":true
  }'
```

Expected selected target fields:

- `id`
- `class_name`
- `confidence`
- `center_pixel`
- `robot_xy`
- `pick_pose`
- `place_pose`

If no selected class is found, the API returns `selected:false` and does not publish a pick pose.

## 8. Validate Safety

```bash
curl http://localhost:8080/api/vision/safety
curl -X POST http://localhost:8080/api/vision/validate_pick \
  -H 'Content-Type: application/json' \
  -d '{"dry_run":true}'
```

The Safety Checklist must show:

- Camera OK
- YOLO OK
- Calibration OK
- Target OK
- Workspace OK
- Dry Run ON

## 9. Preview Pick

```bash
curl -X POST http://localhost:8080/api/vision/preview_pick \
  -H 'Content-Type: application/json' \
  -d '{
    "object_class":"black_cap",
    "place_id":"tray_A",
    "selection_mode":"highest_confidence",
    "dry_run":true
  }'
```

The response contains a simulated motion sequence:

1. move above target
2. move down to pick
3. tool on simulated
4. move up to safe Z
5. move above place
6. move down to place
7. tool off simulated
8. move up to safe Z

No `/api/move`, `/PTP_action`, gripper, or suction command is sent by preview.

## 10. Dry-Run Checklist Before Real Pick

Complete this checklist before enabling real motion:

- Robot homing completed.
- Calibration is complete and mean/max error are acceptable.
- Workspace limits match the physical table.
- Dry-run `select_target` works.
- Dry-run `validate_pick` passes.
- Dry-run `preview_pick` sequence is correct.
- Object is inside the reachable workspace.
- No obstacles are in the robot path.
- Operator is ready to press `Cancel`.

## 11. Enable Real Motion

Real motion is disabled by default. To enable it, edit:

```text
src/magician_ros2/dobot_vision_yolo/config/workspace.yaml
```

Set:

```yaml
allow_real_motion: true
```

Keep low speed settings:

```yaml
velocity_ratio: 0.3
acceleration_ratio: 0.2
```

Restart the web/vision process after editing config.

## 12. Pick Real

Only run this after all safety checks pass:

```bash
curl -X POST http://localhost:8080/api/vision/pick_selected \
  -H 'Content-Type: application/json' \
  -d '{
    "object_class":"black_cap",
    "place_id":"tray_A",
    "selection_mode":"highest_confidence",
    "dry_run":false,
    "confirm_real_motion":true,
    "tool_type":"suction",
    "velocity_ratio":0.3,
    "acceleration_ratio":0.2,
    "max_attempts":2
  }'
```

Cancel:

```bash
curl -X POST http://localhost:8080/api/vision/cancel
```

The web page also has `Pick Selected` and `Cancel` buttons. `Pick Selected` stays disabled while `allow_real_motion=false`.

### Automatic pick-and-place behaviour

`/api/vision/pick_selected` performs a suction-only, coarse-to-fine pick. It
selects the requested class and transforms it to the Dobot base frame, checks
the safe approach pose, then executes these states:

```text
TARGET → APPROACH → FINE_ALIGN → DESCEND → SUCTION_ON → LIFT → VERIFY_PICK → DONE_OR_RETRY
```

After the safe approach, the detector must publish a new frame. The controller
matches a same-class candidate by its calibrated base pose rather than its
frame-local detector ID. Reliable depth is used for base-frame fine alignment;
when depth is invalid or too close, the controller holds Z from robot
kinematics and applies only a bounded 2-D X/Y visual correction. Corrections
larger than 8 mm are rejected instead of being commanded.

Descent is segmented into 5 mm moves at a fixed slow speed. After lifting, a
fresh detection must show the target absent from (or moved away from) its pick
location. Otherwise suction is disabled, the robot returns to its safe
approach pose, and the pick is retried. `max_attempts` includes the first try,
defaults to 2, and is capped at 5. The final failed attempt reports
`aborted_safely:true`; it never makes an unsafe placement guess.

After a verified pick, the selected zone is inspected with a fresh RGB-D
observation before any placement descent. The configured canonical zones are
`Zone A`, `Zone B`, `Zone C`, and `Reject`; legacy `tray_A`, `tray_B`,
`tray_C`, and `reject_box` names are aliases. Nominal base-frame coordinates
and safe approach heights are in `config/place_positions.yaml`.

The inspection must explicitly report an unoccupied zone, a stable local
surface height, and (when available) a bounded fine X/Y correction. Missing,
stale, malformed, or occupied zone data is unsafe: the controller lifts and
returns with the part under suction, without descending. A final release is
accepted only after a fresh RGB-D record reports `release_verified:true`, or
both `occupied:true` and `placed_object_detected:true`.

The RGB-D detector payload provides this contract per zone:

```json
{"placement_inspections":{"Zone A":{"occupancy_valid":true,"occupied":false,"surface_valid":true,"surface_height_mm":-35.0,"surface_valid_ratio":0.92,"surface_stddev_mm":1.5,"alignment_valid":true,"fine_xy_correction_mm":[1.2,-0.4]}}}
```

## System Inspection Commands

```bash
ros2 topic list
ros2 service list
ros2 action list
curl http://localhost:8080/api/status
curl http://localhost:8080/api/vision/status
curl http://localhost:8080/api/vision/safety
```

## Troubleshooting

Camera does not show:

- Check `ORBBEC_WS`, `START_CAMERA`, and `/camera/color/image_raw`.
- Run `lsusb` and `ros2 topic hz /camera/color/image_raw`.
- Try `curl http://localhost:8080/api/snapshot --output /tmp/snapshot.jpg`.

YOLO import fails:

- Install Ultralytics explicitly without replacing Jetson PyTorch: `python3 -m pip install --user --no-deps ultralytics`.
- Check the active Python environment used by ROS.

Model not found:

- Place `best.engine` or `best.pt` in `models/`.
- Check `/api/vision/status` field `model_error`.

TensorRT engine fails:

- Fall back to `best.pt`.
- Re-export the engine on the same Jetson/JetPack/TensorRT version.
- See [jetson_tensorrt.md](jetson_tensorrt.md).

Calibration error is high:

- Keep the rigid natural scene, camera, and robot still during every synchronized capture.
- Ensure the scene contains enough non-planar RGB-D texture and valid depth.
- Spread X/Y/Z and J4 yaw across the guarded workspace.
- Retry Auto Calibrate; a failed retry does not overwrite the last valid result.

Coordinates are outside workspace:

- Check `config/workspace.yaml`.
- Confirm calibration did not flip axes.
- Confirm object and place poses are physically reachable.

API move fails:

- Check `curl http://localhost:8080/api/status`.
- Confirm `/PTP_action` appears in `ros2 action list`.
- Confirm homing was completed.
- Keep velocity/acceleration low.
