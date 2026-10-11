# ตรวจ Autonomous Calibration — 11 ตุลาคม 2026

อ้างอิง `main` ที่ commit `da873298b23a6b44b5a8cc5749e7f74bbbc1d9bd` ก่อนแก้
Working tree เดิมมี build/log และการแก้ไดรเวอร์ Orbbec ใน repository แยก
เก็บการเปลี่ยนแปลงเหล่านี้ไว้ทั้งหมด งานนี้ไม่ได้ส่งคำสั่งเคลื่อนแขนจริง

## 1. Root cause และหลักฐาน

สถานะสด 8 ครั้งจาก `GET /api/vision/calibration` พบ Autonomous `IDLE`,
Passive `GUIDE_TO_TARGET`, Passive accepted 1 ท่า และ Supervised dry-run `IDLE`
ทั้งสอง controller ยังไม่ commissioned ดู [หลักฐานสด](autonomous-audit-2026-10-11/live-evidence.json)
ไม่มีหลักฐาน runtime ว่าปุ่ม Autonomous ถูกกดในรอบที่ตรวจนี้ จึงไม่อ้างว่า
execution ผ่าน `move()` แล้ว หรือว่า Passive Guidance เป็นความผิดของ Autonomous

ไม่พบ `~/.ros/dobot/calibration_workspace.yaml` และ ROS parameter
`/markerless_calibration.automatic_workspace_file` ชี้มาที่ไฟล์นี้จริง
`CalibrationWorkspace.load()` ปฏิเสธด้วย `WORKSPACE_NOT_CONFIGURED`
เมื่อ `AutomaticBackend.prepare()` ถูกเรียก จึงยังเลือกแผนและส่ง motion ไม่ได้
Integration test เรียก ROS service จริงใน domain แยก ยืนยัน blocker นี้
พร้อม sentinel ที่ห้ามเข้า transport และห้ามเปลี่ยนค่า PTP

| จุดที่พบจาก source audit | ฟังก์ชัน/ไฟล์ | การแก้ไข |
| --- | --- | --- |
| Autonomous ไม่มีการยืนยันเฉพาะรอบก่อน dispatch | `automatic_start_service`, `AutomaticBackend.prepare/move` | Start ตรวจแผนก่อน; อนุญาตผ่าน typed service และ token ที่ผูกกับ run/plan/scope |
| Collision ตรวจตอน dispatch ทีละท่า; ทั้งแผนมีเพียง workspace/IK checks | `AutomaticBackend.validate/select_plan` | ตรวจ collision ของทุก segment รวม anchor ก่อนรออนุญาต; ตรวจซ้ำตอน dispatch |
| Planner ใช้ J3/J4 สูงกว่าค่า validator (`105/150` เทียบกับ `90/140`) | `AutomaticBackend.validate` | อ่าน axis limits และ collision policy จาก validator ที่รันจริง; ผูก policy กับแผน |
| คืนค่า PTP ล้มเหลวคืน `(False, error)` แต่ caller ไม่ตรวจ | `AutomaticBackend.close`, `_restore_arm_ptp` | ตรวจค่า return, latch uncertainty, ไม่รายงาน success/commissioned เมื่อ restore ล้มเหลว |
| เรียก `activate()` บน token ซึ่งไม่มี method นี้ | `_start_smoke_test_service_locked` | เรียก `TokenLifecycle.activate(token)` และทดสอบกับ lifecycle จริง |
| Token ACTIVE_RUN เคยไม่ตรวจ deadline ใน `validate()` | `TokenLifecycle.validate` | ตรวจ expiry ทุก state; supervisor สั่ง safe stop ก่อน disarm เมื่อหมดอายุ |
| รายงาน Motion Sent อาจเป็น false หากส่ง goal แล้วเกิด exception | `_execute_guarded_motion_locked`, smoke report | บันทึกทันทีที่เรียก `send_goal_async` รวมกรณี acceptance/result ล้มเหลว |
| Smoke settling เปรียบเทียบ monotonic กับ ROS timestamp | `_run_atomic_smoke_test` | ใช้ clock เดียวกับ `after_motion_stamp` |
| Test carrier clearance ขาด `rotation_seed_verified` | `check_path`, `test_carrier_frames.py` | Missing field ปฏิเสธอย่างชัดเจน; fixture ที่ทดสอบ clearance ระบุ verified orientation เฉพาะข้อมูลจำลอง |

## 2. เส้นทางและสถานะที่แยกกัน

`automaticStart` → `POST /api/calibration/autonomous/start` →
`/calibration/autonomous/start` → `automatic_start_service()` →
`AutomaticCalibration.start()` → `AutomaticBackend.prepare()` →
เลือกและตรวจแผน MOVL ทั้ง 10 ท่า → `WAITING_FOR_OPERATOR_AUTHORIZATION`

ผู้ควบคุมตรวจแผนและยืนยัน ณ หน้าเครื่อง →
`POST /api/calibration/autonomous/authorize` → typed ROS service
`/calibration/autonomous/authorize` → ตรวจ confirmation ทุกข้อและ fingerprint →
ตรวจ commissioning/live gates → ตั้งและอ่านกลับ PTP 5/5 →
`AutomaticBackend.move()` → `_execute_guarded_motion()`

ปุ่ม Commissioning ใช้ `/calibration/autonomous/commission` เตรียมแผนด้วย planner
เดียวกันและตรวจครบ 10 segments แต่ scope การเก็บจริงจำกัดสองท่า
Pose 1 คือ anchor ปัจจุบัน จึงอาจไม่ต้องส่ง goal; Pose 2 ต้องมี goal และ
feedback ถึงเป้าหมายก่อนบันทึก commissioning หลักฐานนี้ใช้ได้เฉพาะ process
และ installation เดิม รอบสิบท่าต้อง Start และ authorize ใหม่แยกต่างหาก

`PASSIVE_GUIDANCE` อ่านจาก `passive_guidance`; `SUPERVISED_DRY_RUN` อ่านจาก
`supervised_auto`; `REAL_AUTONOMOUS_CALIBRATION` อ่านจาก
`automatic_calibration`; legacy `TWO_POSE_SMOKE_TEST` ใช้ RealMotionAdapter
และ token scope `(1,2)` ผล dry-run ไม่ให้สิทธิ์ motion

แผนและ `target_xyz_mm` มาจาก Autonomous planner จริงที่ผ่านการตรวจ
ไม่ได้ใช้ Passive target `[185,0,100,0]` แทนแผน ในการตรวจครั้งนี้
**ยังไม่มีแผนที่ได้รับอนุญาต** เพราะ workspace จริงยังขาด จึงไม่มี
Autonomous target ที่ผ่าน commissioning ให้รายงาน

หน้าเว็บแสดง plan และสถานะ controller โดยตรง ล้างคำยืนยันเมื่อแผนเปลี่ยน
และปิดปุ่มเริ่มหาก backend ยังไม่มี `authorization_protocol: 2`

## 3. Safety และการหยุด

Authorization อยู่ใน RAM มี run ID, plan fingerprint, scope, expiry และ revocation
ต้องยืนยันการอยู่หน้าเครื่อง, E-stop, พื้นที่ว่าง, mount, workspace,
collision review และความสามารถหยุดจริงทุกครั้ง ค่าคอนฟิกตัวเดียวไม่ให้สิทธิ์
เริ่ม motion หลักฐาน `stop_tested_by_operator` เป็นคำยืนยันการทดสอบจริงของ
ผู้ควบคุม ไม่ใช่ผลทดสอบ Abort บนฮาร์ดแวร์จากงานนี้

Start ซ้ำถูกปฏิเสธ; transaction lock แยก legacy smoke กับ Autonomous;
motion lock ปฏิเสธ goal ซ้อน; Pause ถูกตรวจอีกครั้งตรงจุดส่ง goal;
Abort latch ก่อน cancel และยกเลิก goal ที่ตอบรับล่าช้า การรอ action ตรวจ
authorization, workspace/mount, sensor health, robot feedback และ alarm
Timeout/fault ส่ง cancel; PTP server เดิมมี stop/clear queue watchdog
ยังต้องพิสูจน์การหยุดและ feedback นี้กับเครื่องจริง

Pre-dispatch snapshot เก็บ readiness blockers ทุกตัว, อายุ depth/TCP/joints/alarms,
PTP readback, policy, scene comparison และ trace ของจุดส่ง goal
Legacy smoke เก็บ failure-time snapshot เพิ่มด้วย ส่วน Autonomous บันทึก
ผลและ trace ที่ `automatic_audit.yaml` ใน session ใหม่ การคืน PTP มี
original/readback และ fail-closed latch ไม่มีการเพิ่ม timeout หรือลด threshold

หากเคยส่ง goal แล้วต้อง Cancel จะไม่คืนค่า PTP จาก cancel ACK เพียงอย่างเดียว
ต้องมี terminal action result และ robot feedback สดที่นิ่งตลอด window เดิม
ถ้ายังรอ goal acceptance หรือพิสูจน์การหยุดไม่ได้ cleanup ปฏิเสธการคืนค่า
PTP และ latch `PTP_PARAM_STATE_UNCERTAIN` ใช้ settling bound เดิม 5 วินาที
เป็นขอบเขตของขั้นตรวจการหยุดใหม่นี้ ไม่เปลี่ยน motion/sensor/service timeouts

Workspace bounding sphere รวม tool/camera envelope, translation uncertainty
และ clearance ตลอด segment; ตรวจ closest XY radius แบบ continuous;
ตรวจ IK/soft joint limits และ collision ก่อนทุก dispatch
Collision model เดิมครอบคลุมคู่ self/ground ที่ URDF/server กำหนด
ไม่ได้เป็นระบบตรวจบุคคลหรือสร้าง obstacle map ทั้งพื้นที่โดยอัตโนมัติ
จึงยังต้องมีหลักฐานการสำรวจ whole-robot environment และ collision-model
validation ณ หน้าเครื่องตาม workspace policy ห้ามถือ ground datum ใน URDF
เป็นค่าระดับโต๊ะที่วัดจริง

## 4. ผลทดสอบซอฟต์แวร์

ก่อนแก้ ชุด Calibration และ Web ที่เลือก: **267 ผ่าน, 1 ไม่ผ่าน**
รายการไม่ผ่านคือ `test_carrier_frames::test_clearance_uses_carrier_scene_and_tcp_swept_center`
จาก fixture ที่ขาด `rotation_seed_verified`

หลังแก้ชุด functional: **347 ผ่าน, 0 ไม่ผ่าน, 0 skipped**
Regression การหยุดและคืนค่า PTP อีกชุด: **55 ผ่าน** (มีรายการซ้ำกับชุดรวม)
รายละเอียดและจำนวน test cases ดู
[test-results.json](autonomous-audit-2026-10-11/test-results.json)
มีทั้ง unit/mocked motion, HTTP → typed ROS request,
ROS service integration และการ execute JavaScript กับ DOM/HTTP จำลอง
รวม Start/Pause/Resume/Abort, expiry/replay, two-pose scope, hardware faults,
collision rejection, delayed acceptance cancellation และ PTP restore failure
ผลจำลองเหล่านี้ไม่ใช่ผลการเคลื่อนแขนจริง

Build `dobot_msgs`, `dobot_calibration`, `dobot_web_interface` ใน
`/tmp/autonomous-audit-build` และ `/tmp/autonomous-audit-install`
โดยไม่เปลี่ยน production install ผ่าน การทดสอบใช้ `ROS_DOMAIN_ID=173/174`
แยกจากฮาร์ดแวร์ domain 0 และ httpx ติดตั้งเฉพาะ `/tmp/autonomous-testdeps`
เพิ่ม test dependency ใน `package.xml` แล้ว

การรันทดสอบกว้างพบ lint เดิมสามรายการของ `dobot_motion`
(`copyright`, `flake8`, `pep257`) ซึ่ง scan ทั้ง workspace รวม build/install
ตัวอย่าง flake8 รายงาน 8,367 รายการ ไม่แก้ไฟล์ Motion ที่ไม่เกี่ยวกับปัญหา
ชุด functional หลังแก้จึงแยก lint สามรายการนี้ไว้อย่างชัดเจน
ไม่ได้อ้างว่า lint ทั้ง repository ผ่าน

## 5. Hardware / Commissioning / Calibration

| รายการ | หลักฐานในงานนี้ |
| --- | --- |
| Hardware readiness สด | READY 8/8 samples; เป็นผล readiness gate ณ เวลาที่อ่าน |
| E-stop | status PRESENT / OPERATOR VERIFIED; software monitoring NOT CONNECTED; ยังไม่ได้ทดสอบ E-stop จริงในงานนี้ |
| Motion Command Sent | **FALSE** สำหรับเครื่องจริง |
| Pose 1 → Pose 2 จริง | ไม่ได้ดำเนินการ; ไม่มี operator authorization ในงานนี้ |
| 10 poses จริง | ไม่ได้ดำเนินการ; Passive เดิมมี 1 accepted pose และ Autonomous เดิม 0 |
| Calibration metrics | ยังไม่มี residual/held-out/reload metrics จากรอบจริงใหม่ |
| Calibration / Production | ไม่รายงาน Calibration PASS หรือ PRODUCTION_READY |

`HARDWARE_NOT_READY` ที่เคยเกิดใน Smoke รอบเก่ายังระบุ transient blocker
ย้อนหลังไม่ได้ เพราะไม่มี failure-time snapshot ของรอบนั้นให้พิสูจน์
READY ในปัจจุบันไม่ได้หักล้าง fault เก่า

## 6. สิ่งที่ต้องทำก่อนการอนุญาตจริง

ต้องวัดและบันทึกระดับโต๊ะใน `magician_base_link`, free-volume min/max
ที่ครอบคลุม swept envelope, clearance, camera identity, mount fingerprint
และหลักฐาน whole-robot environment/การยึดติดตั้งใน
`~/.ros/dobot/calibration_workspace.yaml` ตัวอย่าง repository ยังคง
`installation_verified: false`, `whole_robot_environment_verified: false`
และค่าที่ไม่ทราบเป็น null ไม่ได้สร้างค่าติดตั้งจริงหรือเปลี่ยน verified ให้ true

Live nodes ก่อนแก้ใช้ symlink จาก build ไป source จริง และมี Autonomous services
แต่ Python process ที่เริ่มก่อนแก้ยังใช้ class ที่โหลดเดิม การแก้ source
ไม่ได้ upgrade process ที่รันอยู่ งานนี้ไม่ restart hardware stack
จึงต้องโหลด build ใหม่อย่างควบคุมเมื่อเครื่องหยุดและผู้ควบคุมพร้อม
ปิด automatic startup/auto-start ของ workflow เดิมก่อนโหลดใหม่
แล้วตรวจ `software_source_digest`, `authorization_protocol: 2` และ typed
authorize/commission services ก่อนทดสอบจริง

เมื่อข้อมูลติดตั้งและ live gates ผ่าน แผนจึงเข้าสู่
`WAITING_FOR_OPERATOR_AUTHORIZATION` ผู้ควบคุมทดสอบ E-stop/Abort และตรวจ
พื้นที่/mount/เส้นทางหน้าเครื่อง จากนั้นอนุญาต Commissioning สองท่าที่ 5/5
เก็บหลักฐาน goal, feedback, stopping และ PTP restore เมื่อผ่านแล้วจึงตรวจ
แผนใหม่ครบสิบท่าและอนุญาตรอบ Autonomous แยกอีกครั้ง ไม่มีการอนุญาต
หรือส่ง motion ใดโดยอัตโนมัติจาก prompt นี้

## 7. การทดสอบซ้ำและ Git diff

```bash
source /opt/ros/jazzy/setup.bash
source install/local_setup.bash
source /tmp/autonomous-audit-install/local_setup.bash
export ROS_DOMAIN_ID=173
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export PYTHONPATH="/tmp/autonomous-testdeps:$PWD/src/magician_ros2/dobot_calibration:$PWD/src/magician_ros2/dobot_web_interface:$PWD/src/magician_ros2/dobot_kinematics:$PWD/src/magician_ros2/dobot_motion:$PYTHONPATH"
python3 -m pytest -o addopts='' --junitxml=/tmp/autonomous-final-tests.xml -q \
  src/magician_ros2/dobot_calibration/test \
  src/magician_ros2/dobot_web_interface/test \
  src/magician_ros2/dobot_motion/test \
  --ignore=src/magician_ros2/dobot_motion/test/test_copyright.py \
  --ignore=src/magician_ros2/dobot_motion/test/test_flake8.py \
  --ignore=src/magician_ros2/dobot_motion/test/test_pep257.py
git diff da873298b23a6b44b5a8cc5749e7f74bbbc1d9bd -- src/magician_ros2 docs
```

JUnit XML, full console output และ build logs อยู่ใน `/tmp/autonomous-*.xml/txt`
ส่วนหลักฐานที่ตรวจอ่านได้ใน repository เก็บในโฟลเดอร์รายงานข้างต้น
