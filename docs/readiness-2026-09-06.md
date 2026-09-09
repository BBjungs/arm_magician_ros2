# รายงานความพร้อมใช้งาน — 6 กันยายน 2026

โปรเจกต์พร้อมสำหรับพัฒนาและทดสอบซอฟต์แวร์ แต่ **ยังไม่พร้อมสั่งงานฮาร์ดแวร์หรือหยิบวางอัตโนมัติ ณ เวลาตรวจ** จุดติดขัดแรกคือเครื่องไม่เห็น USB ของ Dobot และ Orbbec ขณะที่บริการยังรันและ Web ยังเก็บภาพ/ตำแหน่งเก่าไว้ หลังเชื่อมต่ออุปกรณ์กลับ ยังต้องตรวจ Depth และคาลิเบรตก่อนยืนยันการหยิบวางจริง

การตรวจอ่านโค้ด การตั้งค่า ROS graph และ HTTP GET พร้อม build/test ใน `/tmp/dobot-readiness-20260906` ไม่สั่ง motion, homing, tool, restart หรือเปิดอุปกรณ์โดยตรง ไม่แก้โค้ดหรือ configuration และรักษางานเดิมใน working tree

## สถานะรายส่วน

| ส่วน | สถานะ | หลักฐานและความหมาย |
|---|---|---|
| Workspace / build | [WORKING] | `colcon list` พบ 16 แพ็กเกจ รวม `dobot_vision_rgbd`; build ปัจจุบันผ่านครบ 16 แพ็กเกจใน 1 นาที 18 วินาที |
| Web / HTTP | [WORKING] | `/api/status` และ Vision GET endpoints ตอบได้; snapshot ถอดรหัสเป็น JPEG 640×480 ได้ แต่เป็นภาพค้าง ไม่ใช่หลักฐานกล้อง live |
| Dobot / Orbbec hardware | [UNKNOWN] | `lsusb` ไม่พบทั้ง CP210x ของ Dobot และ Orbbec; `/dev/serial/by-id/` ไม่มี การทำงานทางกายภาพเป็น **UNVERIFIED** ไม่สรุปว่าอุปกรณ์เสีย |
| ROS / ข้อมูลสด | [INCOMPLETE] | พบ camera, PTP, homing, suction, validator, Web และ RGB-D nodes แต่การรับข้อมูล 7.03 วินาทีได้ 0 messages จากภาพสี, depth, CameraInfo, pose, joints, alarms และ Vision status; ไม่พบ state publisher ใน node list |
| RGB-D detection | [INCOMPLETE] | ระบบเลือก `rgbd_shape`; มีโค้ดตรวจสี/รูปทรง/ความสูงและทดสอบผ่าน แต่ API รายงานสถานะค้างประมาณ 153,089 วินาที ข้อมูลที่เก็บไว้มี `depth_valid_ratio=0.0` และ detections ถูกปฏิเสธด้วย `invalid_depth` ค่าดังกล่าวเป็นข้อมูลเก่า ต้องตรวจ Depth สดอีกครั้งเมื่ออุปกรณ์กลับมา |
| YOLO ทางเลือก | [MISSING] | ไม่พบไฟล์ `.pt`, `.engine`, `.onnx` ใน source tree; system Python ที่บริการใช้ไม่มี `torch` และ `ultralytics` โดย config อ้าง `models/best.engine` / `models/best.pt` ข้อนี้ขัดขวางโหมด YOLO แต่ไม่ใช่ dependency ของ `rgbd_shape` |
| Calibration | [INCOMPLETE] | Fixed camera มี `homography: []`; ทั้ง fixed และ eye-in-hand มี `calibration_valid: false` |
| แปลงพิกัด / preview / pick | [INCOMPLETE] | มี implementation และ unit tests แต่ยังไม่ยืนยันการทำงานครบวงจรกับข้อมูลจริง; ไม่มี selected target ที่ใช้ได้, calibration ไม่ผ่าน, homing ไม่ยืนยัน และ `pick_z=-35` ยังไม่มีหลักฐานว่าผ่านการสอนความสูงจริง |
| การปิดกั้น Vision motion | [WORKING] | `/api/vision/safety` ตอบ `allowed=false`; config คง `dry_run_default: true` และ `allow_real_motion: false` การทดสอบนี้ยืนยันการปฏิเสธสถานะปัจจุบัน ไม่ได้รับรองทุกสถานการณ์บนฮาร์ดแวร์ |
| การตรวจคุณภาพทั้ง workspace | [INCOMPLETE] | Functional tests ที่ตรวจผ่านทั้งหมด แต่ชุด colcon ยังมี lint/copyright/docstring และ manifest schema failures รายละเอียดด้านล่าง |

## ข้อค้นพบที่มีผลต่อการใช้งาน

1. **บริการรันอยู่ แต่ข้อมูลฮาร์ดแวร์หยุดไหล** — `systemctl --user show dobot-magician.service` รายงาน `ActiveState=active`, `SubState=running`, `NRestarts=0` แต่ `/api/status` มี frame age ประมาณ 152,981 วินาที และ TCP pose age ประมาณ 152,977 วินาที หรือราว 42.5 ชั่วโมง พร้อม `homing_confirmed=false` สถานะ action/service ready ยืนยันเพียงการมี interface ไม่ยืนยันความพร้อมขยับจริง
2. **Calibration ที่บันทึกไว้กับความพยายามล่าสุดเป็นคนละข้อมูล** — YAML เก่าระบุขาด marker ID 1 แต่ `/api/vision/eye_in_hand/status` มี `last_auto_attempt` วันที่ 4 กันยายน 2026 ซึ่งเห็น IDs 0–3 ครบแล้วแต่ไม่ผ่าน: mean reprojection error 63.721 px, max 64.075 px, ระยะ mount ประมาณ 363.61 mm และ optical axis เอียงจากแนวดิ่งลงประมาณ 177.11° จึงไม่ควรแก้เฉพาะเรื่องจำนวน marker หรือบังคับ calibration valid
3. **ค่า estimated position ยังไม่ใช่ calibrated position** — eye-in-hand เปิด `auto_position.enabled=true` เพื่อประมาณจาก configured mount; source ของ safety guard อนุญาตข้อยกเว้นนี้เฉพาะ dry run อีกทั้ง API safety ยังแสดง `TCP Pose: OK` แม้ TCP เก่าประมาณ 42.5 ชั่วโมง เพราะส่วนนี้ตรวจรูปร่างข้อมูล จึงต้องตรวจอายุ state ร่วมด้วยเสมอ
4. **Web เปิดทุก network interface โดยไม่มี authentication** — `config/dobot-autostart.env` ตั้ง `WEB_HOST=0.0.0.0` และ token ว่าง; `create_app()` เพิ่ม authentication middleware เฉพาะเมื่อ token มีค่า และ GET ในการตรวจนี้ไม่ต้องส่ง credentials ก่อนใช้งานผ่าน LAN ควรตั้ง authentication หรือจำกัด interface ที่เปิดให้เข้าถึง ทั้งนี้ยังไม่ได้ทดสอบการเข้าถึงจากเครื่องอื่น
5. **ROS middleware ของบริการต่างจาก shell/คู่มือเดิม** — Ubuntu 24.04.4, ROS 2 Jazzy, Python 3.12.3 ยืนยันได้จริง แต่ process maps ของบริการหลักโหลด `librmw_fastrtps_cpp.so` ขณะที่ shell ใช้ `rmw_cyclonedds_cpp` เมื่อใช้ Fast DDS ในการตรวจจึงเห็น graph ของบริการหลักครบขึ้น ควรทำ environment สำหรับ deployment และ diagnostics ให้สอดคล้องกัน
6. **ข้อมูลเดิมบางรายการแก้แล้ว** — Config ปัจจุบันมี `yellow_cap`, `black_cap`, `white_cap`, mapping ไป `tray_A/B/C`, มี `tray_C` แล้ว และ `reject_box=[180,-160,-35,0]` อยู่ในกรอบ workspace ที่ตั้งไว้ การตรวจนี้ไม่ได้สอนหรือยืนยันตำแหน่งจริงของถาด

## ผล build และ tests ที่รันใหม่

Build ใช้ underlay Jazzy, Orbbec overlay ที่ค้นพบ และ workspace overlay เดิม จากนั้นแยก build/install ไปยัง `/tmp/dobot-readiness-20260906` จึงเป็นการยืนยันว่า source ปัจจุบัน build ได้ในสภาพแวดล้อมเครื่องนี้ ไม่ใช่การติดตั้งใหม่บนเครื่องเปล่า

```bash
source /opt/ros/jazzy/setup.bash
source /home/bbcontact/orbbec_gemini_ws/install/setup.bash
source install/setup.bash
colcon --log-base /tmp/dobot-readiness-20260906/log build \
  --symlink-install --build-base /tmp/dobot-readiness-20260906/build \
  --install-base /tmp/dobot-readiness-20260906/install --parallel-workers 2
source /tmp/dobot-readiness-20260906/install/setup.bash
colcon --log-base /tmp/dobot-readiness-20260906/log test \
  --build-base /tmp/dobot-readiness-20260906/build \
  --install-base /tmp/dobot-readiness-20260906/install \
  --parallel-workers 2 --return-code-on-test-failure
colcon test-result --test-result-base /tmp/dobot-readiness-20260906/build
python3 -m pytest -q src/magician_ros2/dobot_driver/test/test_message_safety.py \
  --junitxml=/tmp/dobot-readiness-20260906/driver-safety.xml
```

| Functional suite | ผ่าน |
|---|---:|
| Web, authentication helpers, calibration capture/print/concurrency, tool mapping | 34 |
| YOLO pipeline utilities, calibration geometry, intrinsics, dataset tools, cancellation | 42 |
| RGB-D geometry, shape/color, fusion, schema, visualization, depth diagnostic | 18 |
| PTP safety helpers | 5 |
| Kinematics waypoint safety | 3 |
| Serial message/checksum/locking ด้วย FakeSerial | 4 |
| **รวม** | **106** |

Serial tests ต้องรันแยกเพราะ CMake ของ driver ไม่ได้ลงทะเบียน pytest ชุดนี้กับ colcon

ผล `colcon test-result`: **275 tests, 0 errors, 148 failures, 1 skipped** โดยตัวนับนี้รวม lint และ CTest/xUnit จึงไม่ใช่จำนวน functional cases ข้อผิดพลาดที่พบเป็น flake8, copyright, docstring และ `dobot_msgs/package.xml` ซึ่ง XML schema ระบุว่าเจอ `<author>` ในจุดที่คาด `<maintainer>` ทั้งหมดเป็นผลของ source ที่มีอยู่ ณ เวลาตรวจ ไม่มีการแก้หรือปิดการตรวจเพื่อให้ผ่าน

ไฟล์หลักฐานรอบนี้:

- `/tmp/dobot-readiness-20260906/log/` — build/test logs
- `/tmp/dobot-readiness-20260906/test-console.log` — สรุปการรัน colcon test
- `/tmp/dobot-readiness-20260906/build/` — pytest/CTest/xUnit results
- `/tmp/dobot-readiness-20260906/driver-safety.xml` — ผล FakeSerial tests
- `/tmp/dobot-readiness-20260906/live-flow.json` — จำนวน messages และ publishers ที่สังเกต 7 วินาที
- `/tmp/dobot-readiness-20260906/nodes.log`, `topics.log`, `services.log`, `service_state.log` — graph/service discovery

## ลำดับงานก่อนใช้งานจริง

1. เชื่อมต่อ Dobot และ Orbbec ให้เครื่องเห็น USB และตรวจภาพ/Depth/state/alarms ใหม่จนสดและต่อเนื่อง ยืนยันเครื่องมือจริงตรงกับ config `suction_cup`; homing และทดสอบการขยับเป็นงานที่ต้องอนุญาตแยกจากการตรวจครั้งนี้
2. ทำ RGB-D detection กับฝาจริงให้ได้ depth/ขนาด/ความสูงที่ใช้ได้ หรือเตรียม weights และ runtime แล้วตรวจความแม่นยำหากเลือก YOLO; ทดสอบทั้งสามคลาสกับสภาพแสงจริง
3. ทำ calibration จาก geometry ของบอร์ดและการติดตั้งจริงให้ผ่านเกณฑ์ ตรวจพิกัดกับจุดอิสระ สอน pick/place Z และตำแหน่งถาด แล้วผ่าน dry run ทั้งลำดับพร้อม cancellation
4. ก่อนเปิดใช้งานผ่าน LAN ให้กำหนด authentication/binding ให้เหมาะสม แก้ manifest และ quality checks ที่ไม่ผ่าน และปรับคู่มือให้ตรงกับ runtime ล่าสุด
5. ทดสอบ motion/tool แบบควบคุมภายใต้การอนุญาตและ safety checks ครบก่อนประเมิน autonomous pick-and-place เป็นอีกระยะหนึ่ง
