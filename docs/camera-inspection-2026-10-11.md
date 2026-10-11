# ผลตรวจกล้องจริง 11 ตุลาคม 2026

ตรวจ Orbbec แบบ read-only และ service passive_capture_test เดิมที่ไม่ส่ง motion
ไม่ได้เปลี่ยนค่ากล้อง/laser/LDP, restart stack ด้วยคำสั่งของงานนี้,
ลด threshold หรือส่ง PTP goal การตรวจครั้งนี้ไม่ใช่ Commissioning

## Hardware และภาพจริง

- Device SV1301S_U3, serial AY2A760003E, firmware RD3013
- SDK 1.10.37, ROS SDK 1.5.22 อ่านจาก getter ของอุปกรณ์จริง
- Depth USB SuperSpeed 5000 Mbps; RGB UVC 480 Mbps; identity ตรง
- RGB และ Depth CameraInfo heartbeat สดประมาณ 30 FPS
- Depth topic /camera/depth/image_raw: 640×480, 16UC1, step 1280,
  little-endian, 614400 bytes, frame camera_color_optical_frame
- อ่าน Image payload จริง 5 เฟรม: nonzero counts
  163904, 164172, 164048, 163784, 163672 จาก 307200 pixels ต่อเฟรม
- เฟรมแรก nonzero depth 181–229 mm, median 213 mm; RGB มีข้อมูลภาพจริง
  และตรวจภาพเห็นโต๊ะกับวัตถุ ไม่มีการอนุมาน Workspace จากภาพนี้
- Laser getter=true; LDP enabled=false และ protection status=false
- exposure/gain getter: depth exposure=1052, gain=2000 (raw device units)
- ROS enable_ir=false หมายถึงไม่ได้เปิด IR topic; depth มีข้อมูลจริงอยู่

## Nonmoving Capture Test

เรียก /calibration/passive_capture_test หลังตรวจ raw depth ว่ามีข้อมูลจริง
service success=true, ACCEPTED ครบ 3 captures แบบ non-persistent

| Capture | Depth valid ratio | Filtered finite points | Plane RMS (mm) | RGB/depth skew (ms) |
| --- | --- | --- | --- | --- |
| 1 | 0.5321875 | 4000 | 0.557228 | 4.552126 |
| 2 | 0.5332292 | 4000 | 0.545737 | 36.784172 |
| 3 | 0.5335156 | 4000 | 0.546077 | 2.564192 |

ทันทีหลัง capture readiness ยัง DEPTH_UNSTABLE แต่ sampling ต่อมา 3 ครั้ง
ห่างครั้งละ 2 วินาทีให้ READY และ blockers=[] ทั้งสามครั้ง โดยไม่แก้ threshold
ผลนี้พิสูจน์ data path และ readiness เฉพาะเวลาตรวจ ไม่ใช่ long-duration reliability
และไม่ใช่หลักฐาน Calibration/Commissioning สำเร็จ

## เทียบผลก่อนหน้าและข้อจำกัด

ก่อนหน้านี้ passive test อ่าน depth ทุก pixel เป็นศูนย์จริง แต่ผลล่าสุดกลับมามีระยะ
ไม่ได้เปลี่ยนกล้องหรือค่า software ในการตรวจนี้ จึงไม่อ้างว่าซ่อม hardware แล้ว
journal พบ Orbbec identity/SuperSpeed path changed และ camera heartbeat lost
จน launcher restart; systemd ที่ตรวจระหว่างงานมี NRestarts=1, MainPID=26320
หลักฐานชี้ว่ามีการขาดช่วง แต่ยังไม่พิสูจน์ว่าความผิดปกติ USB เป็นสาเหตุเดียวของ
all-zero depth ต้องเฝ้าดูสัญญาณและตรวจสาย/connector/power ทางกายภาพหากเกิดซ้ำ

TCP ล่าสุด [149.930038, ~0, 99.888992] mm, J4≈0° จาก feedback;
ต่างจาก snapshot ก่อนหน้า ห้ามถือว่าเป็น motion ที่ AI ส่งในงานนี้
Motion Command Sent by task=FALSE; ไม่มี action result หรือ PTP restore จาก motion
Workspace/whole-robot collision/round authorization ยังต้องผ่านก่อน Commissioning

หลักฐาน: [device](camera-inspection-2026-10-11/device.json),
[parameters](camera-inspection-2026-10-11/parameters.json),
[raw pixel statistics](camera-inspection-2026-10-11/pixels.json),
[captures](camera-inspection-2026-10-11/capture-test.json),
[readiness](camera-inspection-2026-10-11/readiness.json)
