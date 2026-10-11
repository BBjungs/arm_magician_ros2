# ตรวจ Collision โดยไม่เคลื่อนแขน

เรียก ROS `/dobot_calibration_validation_service` ที่รันจริงด้วย EvaluatePTPTrajectory
motion_type=2 (MOVL) ไม่เรียก PTP action และไม่ส่ง motion/authorization
Anchor จาก robot feedback สด age ≤0.3 s และ web ไม่มี active goal/vision sequence:
XYZ [149.930038, -0.000000044, 99.888992] mm, J4≈0°

ใช้ automatic_plan(anchor) เดิมเพื่อสร้าง nominal candidate เท่านั้น
Pose 2 target [184.930038, -0.000000044, 99.888992] mm, J4≈0°
ไม่ได้แทนด้วย Passive X185 และไม่ได้ถือว่า candidate เป็นแผนที่ได้รับอนุญาต
ROS validator Anchor→Pose 2 ให้ valid=true:
`Trajectory passed kinematics, limits, and collision checks`

อ่าน policy จาก validator ที่รันจริง: collision enabled=true, ground=true,
joint limits J1 [-120,120], J2 [-5,90], J3 [-15,90], J4 [-140,140] deg,
step 2 mm / 2 deg ใช้ suction_cup URDF ตามการติดตั้งใน process
ตรวจ nominal sequential segments ทั้ง 10 ด้วย PyBulletCollisionServer เดิม
และ analytic IK/hard limits: ผ่าน 10/10 ทั้งสอง checks
การตรวจเพิ่มนี้เป็น computation ของเส้นทางสมมติบนโมเดล โดยใช้ anchor จริง
ไม่ใช่ feedback จากการเคลื่อน 10 ท่า และไม่ใช่ ROS execution ของ 10 goals
ตรวจแบบ sampled ตาม policy ไม่อ้างว่าเป็น mathematical proof ของ continuous collision-free
ไม่ให้สิทธิ์ motion และไม่ทดแทน backend soft limits/scene/workspace/authorization checks

## ภาพรวมยัง BLOCKED

Production Workspace ยังไม่มี; แบบฟอร์มยัง verified=false และยังไม่มี authorized plan
ทดลอง check_segment(anchor, anchor) กับค่าขอบเขตในแบบฟอร์ม โดยสร้าง workspace
เพื่อคำนวณ offline เท่านั้น ไม่ใช้ load ข้าม verified flags และไม่ติดตั้ง configuration
ผล `WORKSPACE_SWEPT_ENVELOPE_CLEARANCE_FAILED`

Envelope padding = 152.6 + 1 + 25 = 178.6 mm
ขอบเขตปัจจุบันอนุญาตให้ TCP center อยู่ X170–230, Y−70–70, Z180–220 mm
แต่ Anchor จริง X149.93/Z99.89 อยู่นอกช่วง X และ Z
นอกจากนี้ table Z=0 ต้องมี TCP Z≥178.6 mm จึงไม่ผ่านที่ Anchor จริง
การสั่งขยับจากตำแหน่งที่ยังไม่ผ่านเพื่อเข้า bounds ไม่ใช่วิธี bypass ที่อนุญาต
ต้องตรวจ datum/mount envelope และพื้นที่จริงของ anchor/เส้นทางก่อน

Collision model เดิมมีเพียง suction URDF/self/ground pairs ที่กำหนด ไม่ได้ตรวจ
camera/bracket/cables/คน/สิ่งกีดขวางภายนอกทั้งหมดโดยอัตโนมัติ
ผล collision model PASS จึงไม่ใช่ whole-robot environment verification หรือ Commissioning PASS

Motion Command Sent=FALSE; plan authorization=false; ไม่มี action terminal result,
Pose 2 actual, position error, motion duration, commissioning RGB-D หรือ PTP restore ใหม่
ไม่มีการเริ่มรอบสิบท่า หรือสร้าง controller ใหม่/ลด threshold
ดู [หลักฐานและ nominal targets ทั้ง 10](collision-inspection-2026-10-11/validation.json)
