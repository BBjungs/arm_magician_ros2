# ผลตรวจข้อมูลเดิมและความขัดแย้ง Workspace

วันที่ 2026-10-11; source ก่อนแก้ `0c494a4` ไม่มีการส่ง Motion Goal ในงานนี้

## ข้อมูลที่มีอยู่แล้ว

ไม่ต้องส่งขนาดชุดเดิมซ้ำ ข้อมูลใน
[`config/eye-in-hand-mount-measurement-form.yaml`](../config/eye-in-hand-mount-measurement-form.yaml)
และ [`config/camera-mount-measurements.yaml`](../config/camera-mount-measurements.yaml)
บันทึก tool → ปากหัวดูด `[0,0,-70]` mm, ปากหัวดูด → camera reference
`[50,0,35]` mm, translation error bound 1 mm และรัศมีครอบชุดติดตั้ง 152.6 mm
ผู้ควบคุมยืนยัน table Z=-58 mm และ datum แล้ว; รับเป็นคำยืนยันผู้ควบคุม
ไม่ได้อ้างว่า AI วัดเอง

องค์ประกอบ X130/Z80 mm ในแบบบันทึกเป็นการแตกองค์ประกอบระยะถึงจุดไกลสุด
เพื่อคำนวณรัศมี ไม่ใช่ signed XYZ min/max ของทุกชิ้นส่วน
จึงยังพิสูจน์ไม่ได้ว่าขอบล่างของชุดติดตั้งทั้งหมดอยู่ไม่เกิน -80 mm
การใช้ทรงกลมเป็น conservative bound ที่ตั้งใจไว้ ไม่ใช่ข้อผิดพลาดทางคณิตศาสตร์
ผลปฏิเสธไม่ได้พิสูจน์ว่าอุปกรณ์ชนโต๊ะจริง แต่ยังรับรอง clearance ไม่ได้

## ผลจากตำแหน่งจริง

อ่าน `/api/status` ด้วย HTTP GET และใช้โค้ดตรวจ Workspace เดิมแบบออฟไลน์
กับแบบฟอร์มที่ยังไม่ verified; ไม่มีการเรียก Commission/Authorize/Move
TCP ประมาณ X149.93 Y0 Z99.89 mm, J4≈0°

| เงื่อนไขที่ไม่ผ่าน | ระยะที่ขาดตามโมเดล |
| --- | ---: |
| ขอบเขต volume X ต่ำสุด | 20.07 mm |
| ขอบเขต volume Z ต่ำสุด | 80.11 mm |
| ระยะห่างโต๊ะ | 20.71 mm |

Padding เดิม = 152.6 + 1 + 25 = 178.6 mm
table Z=-58 mm จึงต้องการ TCP Z≥120.6 mm เฉพาะเงื่อนไขโต๊ะ
แต่ volume ที่บันทึกไว้ต้องการ TCP Z≥180 mm และ X≥170 mm
แก้ระดับโต๊ะอย่างเดียวจึงไม่แก้ความขัดแย้งของ volume
ตัวเลขเหล่านี้ไม่ใช่คำแนะนำให้ขยับแขนหรือเปลี่ยนขอบเขตตามนั้น

ตรวจทั้ง 8 variants และ 10 segments ต่อ variant รวม stationary anchor
ด้วย workspace checker: ไม่มี variant ผ่าน ทั้งหมดปฏิเสธที่ anchor อยู่แล้ว
ไม่มีการตรวจ IK/collision เพิ่มในครั้งนี้ เพราะ geometry gate ไม่ผ่าน;
ห้ามนับผลนี้เป็น validated plan หรือใช้ fingerprint แบบฟอร์มเป็น motion authorization

## สิ่งที่แก้ไข

- เพิ่ม `CalibrationWorkspace.clearance_diagnostics()` เพื่อระบุ signed margins
  และ deficit ของแต่ละขอบเขต; error เดิมแสดงชื่อขอบเขตและระยะที่ขาดแล้ว
- คงเงื่อนไขปฏิเสธ, sphere radius, minimum clearance, reach และ step limits เดิม
- เพิ่ม `scripts/audit_commissioning_workspace.py`: อ่านแบบฟอร์มและ feedback
  แล้วตรวจ variants โดยไม่ติดตั้ง Workspace ไม่เขียน verified flags และไม่ส่ง motion
  Exit 1 หมายถึงไม่มี geometry variant ผ่าน; exit 0 ก็ยังไม่ใช่การอนุญาตเคลื่อนที่
- เพิ่ม regression tests แยก table กับ volume failure และตรวจ extrema สองปลาย segment
- เพิ่มแหล่งอ้างอิงข้อมูลเดิมและข้อจำกัดของหลักฐานในแบบฟอร์ม

รันซ้ำได้ด้วย:

```bash
python3 scripts/audit_commissioning_workspace.py --output /tmp/workspace-audit.json
```

## ผลทดสอบและสถานะ

ก่อนแก้: error ระบุเพียง `WORKSPACE_SWEPT_ENVELOPE_CLEARANCE_FAILED`
หลังแก้: ระบุ `volume_x_min`, `volume_z_min`, `table` พร้อม deficit
ชุดทดสอบ 6 ไฟล์ที่ร้องขอรันกับ ROS Jazzy และ generated messages ใน ROS_DOMAIN_ID=173:
**110 passed, 0 failures, 0 errors, 0 skipped**, 45.468 s รวม regression tests ใหม่ 3 ข้อ
ความพยายามรันทดสอบครั้งแรกระบุ path ของ placement test ผิดและจบก่อนรันทดสอบ;
แก้เป็นไฟล์ใน dobot_web_interface แล้วรันครบตามผลข้างต้น

หลักฐาน: [audit.json](commissioning-geometry-reconciliation-2026-10-11/audit.json),
[tests.xml](commissioning-geometry-reconciliation-2026-10-11/tests.xml)

SOFTWARE PASS เฉพาะชุดทดสอบที่ระบุ; GEOMETRY VERIFIED: FALSE;
MOTION VERIFIED: FALSE; COMMISSIONING COMPLETE: FALSE
Motion Command Sent: FALSE; ไม่มี commissioning RGB-D capture หรือ PTP parameter change
ไม่มี restart หรือ reload runtime ในงานนี้; diagnostics source ใหม่ยังไม่ถือว่าโหลดใน process เดิม

## Blocker ที่ยังแก้จากหลักฐานเดิมไม่ได้

ขอบเขต free volume เดิมมีที่มาจากช่วง TCP สมมติแล้วขยายด้วยรัศมี
คำยืนยันตัวเลขไม่ได้แก้การที่ขอบเขตนั้นไม่ครอบคลุม anchor จริงตามโมเดล
ยังไม่มี signed min/max ครบทุกชิ้นส่วน/สาย/ขายึด หรือ CAD การติดตั้งที่ใช้พิสูจน์
ขอบเขตด้านล่างที่แคบกว่าทรงกลม และไม่มีหลักฐานขอบเขต workcell ที่แก้ความขัดแย้งนี้
การมีระยะศูนย์กลางกล้องและหัวดูดไม่เท่ากับการมีขอบเขตภายนอกทั้งชุด

จึงยังไม่สร้างไฟล์ runtime ที่อ้าง installation/whole_robot_environment_verified=true
ไม่ลด safety threshold ไม่ยกแขนจาก anchor ที่ไม่ผ่าน และไม่ลอง Start ซ้ำ
ต้องคลี่คลายขอบเขตที่ขัดแย้งด้วยแบบการติดตั้งหรือการตรวจหน้างานเฉพาะส่วนนี้
ก่อนให้แผนจริงผ่านและผูกการอนุญาตเข้ากับ fingerprint ของรอบ
