# โหลด Production Runtime ใหม่

ผู้ใช้อนุญาตให้แก้ไขต่อหลังได้รับแผน Stop → Build → Start ที่ปิด startup motion
งานนี้ไม่ได้ส่ง Calibration/PTP motion goal, ไม่เรียก authorize และไม่เริ่มรอบสิบท่า

## ปัญหาที่พิสูจน์และแก้แล้ว

Web และ Calibration ล่มด้วย `ImportError: cannot import name 'AuthorizeCalibration'
from 'dobot_msgs.srv'`: source ใหม่แต่ generated production messages เก่า
หยุด user `dobot-magician.service` จน inactive/dead และไม่พบ process stack เดิม
แล้ว build เฉพาะ dobot_msgs/dobot_calibration/dobot_web_interface ผ่านครบ 3 packages
ใน 53.3 วินาที ตรวจ import และ ROS type support ของ AuthorizeCalibration ใน
canonical install ผ่าน โดยไม่ลบ build/install/log หรือ dirt ของ Orbbec เดิม

ติดตั้ง `/home/bbcontact/.config/systemd/user/dobot-magician.service.d/90-commissioning.conf`
ซึ่งอ่าน environment เพิ่มจาก `docs/commissioning-runtime-staging/startup-disabled.env`
หลัง environment เดิม ตรวจ process และ ROS parameters ยืนยัน:

- STARTUP_AUTO=false และ web startup_auto=false
- STARTUP_AUTO_MOTION=false และ web startup_auto_motion=false
- STARTUP_AUTO_RECALIBRATE=false และ calibration recalibrate_on_failure=false
- calibration auto_start=false

ครั้งแรกหลัง build ยังพบ launcher เริ่มใหม่ซ้ำ เพราะ START_OBJECT_FUSION=true
ทำให้ monitor รอ `vision_running` สำหรับ production admission ก่อน calibration พร้อม
log: `Vision runtime did not become ready before its deadline`
หยุด service ก่อนปรับ commissioning profile เป็น START_OBJECT_FUSION=false
ตาม option เดิมที่ launcher รองรับสำหรับ calibration; คง START_VISION=true,
camera/RGB-D/calibration ทำงาน ไม่มีการแก้ controller หรือ threshold

## การตรวจและทดสอบ

HTTP กลับมาและ automatic_calibration.authorization_protocol=2
startup software_source_digest ตรงกับ hash ของ source calibration ทั้ง package
พบ `/calibration/autonomous/commission [std_srvs/srv/Trigger]` และ
`/calibration/autonomous/authorize [dobot_msgs/srv/AuthorizeCalibration]` จริง
services เหล่านี้พร้อมใช้งาน แต่ไม่มีการเรียกเพื่อ authorize/เคลื่อนที่ในงานนี้

รันชุด Commissioning ใหม่กับ production-generated messages ใน ROS_DOMAIN_ID=173
แยกจาก hardware domain 0: **147 passed, 0 failures, 0 errors, 0 skipped**
เวลา 45.053 วินาที ครอบคลุม unit/mock/ROS service/web และ safety regressions เดิม
ไม่ใช้ผล test นี้เป็นหลักฐาน real motion
ดู [JUnit](commissioning-runtime-repair-2026-10-11/tests.xml) และ
[หลักฐาน runtime](commissioning-runtime-repair-2026-10-11/live-evidence.json)

## Blockers ที่ยังเหลือ

Production Workspace `~/.ros/dobot/calibration_workspace.yaml` ยังไม่มี
แบบฟอร์มมีคำยืนยันจากผู้ดูแลและตัวเลขที่หารือ แต่ installation_verified และ
whole_robot_environment_verified ยังคง false; วิธีวัด/physical survey,
camera/mount binding และ validated whole-robot plan ยังไม่ครบ
ไม่มี target/fingerprint ที่ได้รับอนุญาตสำหรับ Commissioning รอบใหม่

หลัง restart ครั้งแรก readiness พบ DEPTH_ERROR/DEPTH_UNSTABLE
TCP ที่อ่านจริง [190.760590, -2.027094, 9.663727] mm, J4 -0.608824°
เป็น preflight telemetry ไม่ใช่ผล motion ของงานนี้ ตำแหน่งนี้แตกต่างจาก historical
Z≈100 mm จึงต้องใช้ feedback ปัจจุบันตรวจ anchor ใหม่ ห้ามสรุปว่าเกิด autonomous motion
หรือถือว่าแขนอยู่ช่วงตัวอย่าง Z180–220 mm จากคำยืนยันตัวเลข
snapshot ต่อเนื่องหลังเปิด commissioning profile อยู่ในหลักฐาน JSON
readiness/sensor health ต้องผ่านใหม่ทันทีที่เตรียมแผนและก่อน dispatch

ตรวจท้ายงาน MainPID 15899 ทำงานต่อเนื่อง 181 วินาที, NRestarts=0,
active/running และเว็บ protocol 2 ยังตอบ จึงผ่าน startup deadline 90 วินาที
กล้อง transport มี CameraInfo heartbeat สด แต่ SENSOR_INGEST_STATE=IDLE และ
RGB_SUBSCRIPTION_ACTIVE/DEPTH_SUBSCRIPTION_ACTIVE=false
camera health ในโหมดนี้ delegate pixel quality ให้ demand-driven calibration ingest
จึงยังไม่มี `valid`/`valid_ratio` จาก payload ให้ calibration gate ผ่าน
DEPTH_HEALTH_REJECTED/ratio default 0 ณ ตอนนี้ไม่พิสูจน์ว่ากล้องเสียหรือภาพ depth เป็นศูนย์
ต้องเปิด acquisition ผ่าน workflow เดิมและตรวจข้อมูลจริงก่อน motion โดยไม่ bypass gate

โต๊ะ Z=0 ตามคำยืนยันยังต้องตรวจ datum และ envelope กับเครื่องจริง
config envelope 152.6 mm + translation bound 1 mm + clearance 25 mm
ทำให้ TCP ต่ำกว่า 178.6 mm ไม่ผ่าน table clearance ปัจจุบัน
ห้ามสั่งยกแขนเพื่อบังคับให้ผ่านโดยไม่มีเส้นทางที่ตรวจและอนุญาตแล้ว

SOFTWARE PASS: YES สำหรับชุด Commissioning ที่รัน
RUNTIME: protocol/service/build ตรงกันแล้ว; preflight admission แยกจาก runtime startup
GEOMETRY VERIFIED: NO; MOTION VERIFIED: NO; COMMISSIONING COMPLETE: NO
Motion Command Sent by task: FALSE; PTP Restore: NOT_REQUIRED
มี E-stop ตามผู้ควบคุม แต่การทดสอบ stop จริง/round authorization ยังต้องยืนยันแยก

## ทดสอบ Acquisition จริงแบบไม่เคลื่อนแขนต่อจาก Runtime Repair

หลังผู้ใช้ขอให้ปลด blockers ไม่ได้ลบ Safety Gate หรือแก้ผลเป็น PASS
เรียก service เดิม `/calibration/passive_capture_test` ซึ่งไม่มี motion path
เพื่อเปิด demand-driven ingest และอ่าน RGB-D จริง SENSOR_INGEST_STATE เปลี่ยนเป็น ACTIVE
แต่ capture test success=false: `Capture timeout: DEPTH_ALL_ZERO`
ตรวจ payload ได้ 307,200 pixels, valid_count=0, zero_count=307,200,
depth_valid_ratio=0.0 และ finite_cloud_points=0 จึงยังไม่มี measured depth/scene
ก่อนหน้านี้ ratio default 0 จาก inactive ingest ไม่พิสูจน์ sensor fault;
ผลใหม่นี้เป็นการตรวจ Image payload จริงและยืนยันว่าเป็นศูนย์ทั้งหมด
ดู [หลักฐานทดสอบ](commissioning-runtime-repair-2026-10-11/nonmoving-rgbd-preflight-test.json)
Motion Command Sent by task=FALSE ไม่มีการทดลองเคลื่อนที่หรือ retry motion
ต้องตรวจ depth sensor/IR, การตั้งค่า และระยะฉากจริงก่อนเก็บใหม่
ไม่สั่งยกหรือขยับแขนจากตำแหน่งต่ำเพื่อแก้ scene โดยไม่มีแผน/authorization
Workspace, Collision และ commissioning authorization ยังคงจำเป็น
