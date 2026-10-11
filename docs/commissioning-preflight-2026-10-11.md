# รายงานเตรียม Real Commissioning Pose 1 → Pose 2

ผล **BLOCKED** — งานนี้ไม่ส่งคำสั่งเคลื่อนแขนจริง ไม่เปลี่ยนค่า PTP และไม่เริ่มรอบสิบท่า
ตรวจจาก `main` commit `bcdc766ea357226f21c88f211e07a9eff733f004` เมื่อ 11 ตุลาคม 2026
หลักฐานสดเวลา 09:33:46 UTC / 16:33:46 ไทยอยู่ใน
[live-evidence.json](commissioning-preflight-2026-10-11/live-evidence.json)

## Root cause และสภาพระบบ

1. ไม่มี `/home/bbcontact/.ros/dobot/calibration_workspace.yaml`:
   `CalibrationWorkspace.load()` ใน `calibration_workspace.py` ปฏิเสธด้วย
   `WORKSPACE_NOT_CONFIGURED`; `AutomaticBackend.prepare()` เรียก diagnostics/load
   ก่อนเลือกแผน ไม่มีการสร้างค่า geometry หรือเปลี่ยน verified flags ในงานนี้
2. Runtime ยังเป็นโค้ดเก่า: ROS service discovery พบเพียง autonomous
   start/pause/resume/abort ไม่พบ commission หรือ authorize;
   HTTP ไม่มี `authorization_protocol: 2` และ startup source digest
   Calibration PID 4089148 และ Web PID 4089149 รันมาประมาณ 90 นาที ณ การตรวจ
   จึงยังใช้งาน Commissioning workflow ของ commit ที่อ้างอิงไม่ได้
3. ยังไม่มีผลวัดผิวโต๊ะ/พื้นที่ว่างและคำยืนยัน Safety Checklist เฉพาะรอบจากผู้ควบคุม
   ไม่ถือคำยืนยัน E-stop เดิมใน configuration เป็นผลทดสอบจริงสำหรับรอบนี้

Source และ isolated build ใน `/tmp/autonomous-audit-install` ตรงกันแบบ byte-for-byte
สำหรับ node.py, autonomous.py, autonomous_backend.py และ web_interface.py;
typed AuthorizeCalibration service มีใน isolated build แล้ว
ไม่ได้ restart production stack หรือเปลี่ยน production install ระหว่างงานนี้
production launcher เดิมมี `startup_auto=true`; การโหลดใหม่ต้องใช้ profile
ที่ปิด startup_auto/startup_auto_recalibrate/startup_auto_motion ทั้งหมด
และตรวจว่าไม่มี goal/transaction ก่อนเปลี่ยน process ไม่ควร restart profile เดิมโดยตรง

## กรอบพิกัดโต๊ะและ Mount

ผู้ใช้ยืนยันว่าฐานล่างสุดวางบนโต๊ะโดยตรง แต่ยังไม่ได้ยืนยันตำแหน่ง origin ทางกายภาพ
`magician.urdf.xacro` กำหนด link_base_length = 0.131305 m และ fixed joint
จาก magician_root_link ถึง magician_base_link เป็น +0.131305 m ในแกน Z
collision server วาง ground โมเดลที่ -0.131305 m ในกรอบ base ของ collision model
ส่วน collision suction_cup.urdf ใช้ root→base offset เป็นศูนย์
จึงต้องแยก datum ของแต่ละโมเดลให้ถูกต้อง

`dobot_state_publ.py::timer_callback()` นำ Z จาก `bot.get_pose()` หาร 1000
แล้วประกาศใน magician_base_link และ TF base→TCP โดยไม่มี offset เพิ่ม
นี่เป็นหลักฐานการจับคู่พิกัดในซอฟต์แวร์ ไม่ใช่การตรวจวัด origin ของเครื่องจริง
การอ่าน TF ครั้งนี้พบ base→TCP แต่ไม่รับ static root→base transform
จึงไม่มีหลักฐานสดที่ยืนยันความสูง origin เหนือโต๊ะ

หากวัด origin สูงจากโต๊ะ h เมตร และยืนยันแกน base Z ตั้งฉากขึ้นจริง
จึงใช้ table_surface_z_m = -h ได้; **ยังไม่กำหนด 0.0 หรือ -0.131305 เป็นค่าที่วัดจริง**
ต้องบันทึกวิธีวัดจุด origin/ฐาน/ขารอง และยืนยัน Controller frame กับ model datum
พร้อมสำรวจ free_volume_min_m/free_volume_max_m ในกรอบเดียวกัน
ให้ครอบคลุมแขนทั้งตัว กล้อง bracket และหัวดูดตลอดเส้นทาง
workspace file ต้องผูก camera ID AY2A760003E และ mount fingerprint จริง
ค่า envelope ที่ runtime รายงาน 152.6 mm และ uncertainty 1 mm เป็นค่าในระบบ
ไม่ได้เป็นการตรวจวัด mount ใหม่ในงานนี้

## Workflow และแผน

Source: POST `/api/calibration/autonomous/commission` → ROS
`/calibration/autonomous/commission` → `AutomaticCalibration.start()` purpose
`COMMISSIONING_TWO_POSES` → `AutomaticBackend.prepare()` → select_plan/validate
ครบสิบท่า → `WAITING_FOR_OPERATOR_AUTHORIZATION` → typed authorize ที่ผูก fingerprint
→ low-speed PTP set/readback → guarded MOVL เฉพาะสองท่า → capture/restore/revoke
รอบนี้ยังไปไม่ถึงขั้นเตรียมแผนบน production runtime เพราะ blockers ข้างต้น
ไม่ได้เรียก service motion หรือกด Start/Commission ของ runtime เก่า

Planner ใช้ anchor จริงและเลือก sign/scale ตาม workspace/IK/collision
จึงยังไม่มี Pose 2 target ที่ผ่าน validation ให้แสดง
Passive target [185, 0, 100, 0] ไม่ใช่หลักฐานเป้าหมาย Autonomous
Joint policy, continuous TCP/camera swept envelope, table clearance,
IK และ collision ของทุก segment ต้องผ่านก่อนอนุญาต; collision model
ไม่ได้แทนการสำรวจสิ่งกีดขวาง/บุคคลทั้งพื้นที่

## ผลทดสอบซอฟต์แวร์รอบนี้

**147 passed, 0 failures, 0 errors, 0 skipped** ใช้เวลา 69.859 วินาที
ROS_DOMAIN_ID=173 แยกจาก domain 0 ของเครื่องจริง
รัน test_automatic_calibration, test_autonomous_safety, test_real_motion_adapter,
test_hardware_readiness, test_ros_adapter, test_atomic_smoke_contract,
test_autonomous_api และ test_autonomous_ui กับ typed service ใน isolated build
ดู [JUnit](commissioning-preflight-2026-10-11/tests.xml) และ
[ผลรวม](commissioning-preflight-2026-10-11/test-results.json)

ครอบคลุม no authorization/no dispatch, workspace rejection, whole-plan collision,
expiry, operator abort, two-pose scope, PTP restore failure, delayed acceptance
cancellation, duplicate goal rejection และ terminal-result/stationary-feedback stop checks
มี unit, mock transport, ROS service integration และ web tests
ผลเหล่านี้ไม่ใช่หลักฐานการส่ง goal/หยุด/เคลื่อนถึงเป้าหมายบนเครื่องจริง
ไม่ได้เพิ่ม timeout หรือลด threshold; ไม่มี source code fix ใหม่ในรอบนี้

## ผลเครื่องจริง

| รายการ | ผล |
| --- | --- |
| Pose 1 XYZ/J4 | preflight TCP [149.991776, -0.000000044, 99.998001] mm; J4 ≈ 0°; ยังไม่ได้ capture Commissioning |
| Pose 2 Target | ไม่มีแผน Autonomous ที่ผ่าน validation |
| Pose 2 Actual | ไม่ได้ดำเนินการ |
| Position Error / Motion Duration | N/A — ไม่มี motion |
| Motion Command Sent | FALSE สำหรับงานนี้ |
| ROS Action Result | ไม่มี goal ของงานนี้ จึงไม่มี terminal result |
| Hardware Readiness | READY ณ snapshot; depth/TCP/joints/alarm fresh; ไม่มี readiness blockers |
| Camera | AY2A760003E; depth valid ratio 0.5343; มี warning depth_rate_unverified_or_degraded |
| Alarm | ไม่มี alarm ตาม snapshot; ต้องตรวจใหม่ก่อน dispatch |
| Other Motion Goal | Web active_goal=false และ vision_sequence_active=false; ไม่ได้รับ PTP action status แม้ใช้ transient QoS จึงยังยืนยัน action-server idle อย่างอิสระไม่ได้ |
| E-stop | config/status PRESENT/OPERATOR VERIFIED; software monitoring NOT CONNECTED; ยังไม่ทดสอบจริงเฉพาะรอบนี้ |
| Collision Validation | ยังไม่ตรวจแผนจริง; workspace/survey ขาด |
| RGB-D Capture | มี stream สด; ไม่มีการบันทึก Commissioning Pose 1/2 ใหม่ |
| PTP Restore | NOT_REQUIRED — ไม่เปลี่ยน PTP และไม่ส่ง goal; ไม่อ้าง PASS ของฮาร์ดแวร์ |
| Commissioning | BLOCKED; ไม่เกิด COMMISSIONING_COMPLETE |

Passive pose 1 ACCEPTED เดิมไม่ใช่ capture Pose 1 ของ Commissioning รอบใหม่
สถานะ Autonomous จริงยัง IDLE แยกจาก Passive GUIDE_TO_TARGET
RGB-D readiness ไม่ได้แทน geometry verification หรือ motion authorization

## สิ่งที่ต้องครบก่อนดำเนินการต่อ

ต้องมีผลวัด workspace/table และ mount ที่ตรวจสอบได้ โหลด runtime protocol 2
ด้วย startup motion ปิด ตรวจ action-server idle และเตรียม/ตรวจแผนทั้งสิบท่าใหม่
จึงเข้าสู่ WAITING_FOR_OPERATOR_AUTHORIZATION และแสดงพิกัด Pose 1/2 กับ fingerprint
ให้ผู้ควบคุมหน้าเครื่องยืนยัน E-stop ทดสอบจริง, พื้นที่ว่าง, mount แน่น,
workspace วัดจริง, collision ผ่าน, หยุดแขนจริงได้ และอ่านพิกัดสองท่าแล้ว
AI ไม่ยืนยัน checklist แทนผู้ควบคุม

หลังการอนุญาตเฉพาะรอบจึงส่ง MOVL Pose 2 ผ่าน workflow เดิม
ตรวจ terminal success/TCP tolerance/stationary/RGB-D/telemetry/PTP restore/revocation
หาก fault ต้อง safe stop และไม่ลอง motion ซ้ำเอง ไม่อนุญาตให้ไป Pose 3
ขณะนี้ยังไม่พร้อมเปิดรอบ Auto Calibration 10 ท่า และไม่มี calibration metrics ใหม่

## Git

ก่อนงาน HEAD ตรง reference commit; เก็บ dirt เดิมทั้งหมดใน Log, build, log
และ Orbbec submodule ไว้ ไม่มีการแก้ config เครื่องหรือ verified flags
diff ของงานนี้มีเพียงรายงานและหลักฐาน preflight/tests
