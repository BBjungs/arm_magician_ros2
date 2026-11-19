# รายงาน Hardware-Only Reset

## ขอบเขต

Branch `reset/hardware-only` เริ่มจาก Production commit `e200b73d34620602df33acaca1e6e3de0e3766f4` และอยู่ใน clone แยกที่ `.hardware-only-reset/` ภายใน Workspace เดิม สิทธิ์ของงานนี้อนุญาตให้อ่าน Git metadata ของ Production จึงสร้าง Branch และทำงานใน Git metadata ของ clone แยก ไม่มีการเปิดอุปกรณ์จริง ไม่มีการเปลี่ยน Firmware หรือการตั้งค่าของระบบ Production

## ไฟล์และแพ็กเกจที่นำออก

เมื่อนับตาม path เทียบกับ Production มี 7,003 path เดิมที่นำออกหรือย้าย รวมถึงไฟล์ใน `build/` (2,908), `install/` (1,383), `log/` (2,043) และ `Log/` (1) ต้นไม้ Reset ตัด `docs/`, `scripts/`, `systemd/`, ไฟล์ผลทดสอบ รายงาน Debug และ Simulation, การตั้งค่า Application เดิม, Cache และไฟล์ Python ที่คอมไพล์แล้ว ผล Build และ Log สำหรับการตรวจสอบอยู่ในไดเรกทอรีชั่วคราวแยกจาก checkout

แพ็กเกจที่นำออกทั้งชุด ได้แก่

| กลุ่ม | แพ็กเกจ |
| --- | --- |
| การเคลื่อนที่และระบบป้องกันเดิม | `dobot_motion`, `dobot_kinematics`, `dobot_homing`, `dobot_end_effector` |
| Bringup และการประมวลผลสถานะเดิม | `dobot_bringup`, `dobot_state_updater`, `dobot_diagnostics` |
| Calibration, Vision และ Automation | `dobot_calibration`, `dobot_object_vision`, `dobot_vision_rgbd`, `dobot_vision_yolo` |
| UI, Visualization และตัวอย่าง | `dobot_control_panel`, `dobot_web_interface`, `dobot_visualization_tools`, `dobot_demos` |

เอา Motion Guards, การตรวจเส้นทางและการชน, Workspace/Joint Limit Validation, การอนุญาตและยืนยันคำสั่ง, Recovery, PTP Restoration และชุดทดสอบเดิมออก พร้อม Calibration, AI, RGB-D Object Processing และ Automation ของระบบเดิม

ลบไฟล์ requirements ของ Application และการเทรนโมเดล พร้อม dependencies เฉพาะงานเดิม เช่น PyBullet, Ultralytics และชุดเทรน YOLO, PyQt5 และ Python Qt bindings, RQt/RViz tooling ของ Application, PyKDL และ transforms3d ฝั่ง Dobot ยังคงใช้ PySerial ผ่าน rosdep ส่วน OpenCV และ dependencies ด้านภาพที่อยู่ใน Orbbec ยังใช้กับไดรเวอร์ทางการ

## ส่วนที่เก็บและโครงสร้างใหม่

- `src/dobot_hardware/driver/` เก็บแพ็กเกจ `dobot_driver` และนำโครงสร้างเฟรม Checksum, Command ID และรูปแบบข้อมูลอ่านกลับของ Magician มาจัดใหม่ใน `dobot_driver/protocol/` การเปิดพอร์ตและการรับส่งอยู่ใน `serial_driver.py` การเผยแพร่สถานะอยู่ใน `dobot_driver/state/`
- `src/dobot_hardware/interfaces/` เก็บแพ็กเกจ `dobot_msgs` กับ `DeviceStatus`, `AlarmState` และ `ToolState` สำหรับข้อมูลอ่านกลับ
- `src/dobot_hardware/description/` เก็บแพ็กเกจ `dobot_description` พร้อม URDF ของแขนและ Mesh ที่ URDF อ้างอิง
- `src/OrbbecSDK_ROS2/` เก็บ `orbbec_camera`, `orbbec_camera_msgs` และ `orbbec_description` ใน submodule ทางการที่ commit `0ea4ab68f5b8ddf22998b7c45d251dc58ea2779e` (v1.5.22) ตาม pin ของ Production
- `config/` และ `launch/` มี YAML และ Launch แยกตามอุปกรณ์ `tests/hardware_protocol/` มีการทดสอบแบบ Offline และเก็บ `LICENSE` เดิม

## ผล Build และการทดสอบ

- Build ด้วย Colcon จากต้นไม้ใหม่บน ARM64 และ ROS 2 Jazzy ผ่านครบ 6 แพ็กเกจ โดยสร้างผลลัพธ์นอก checkout ใช้เวลา 17 นาที 12 วินาที
- ตรวจ type support ของข้อความ Dobot และบริการ `GetDeviceInfo` ของ Orbbec จาก install overlay ตรวจ Launch ทั้งสองด้วย `--show-args` และตรวจด้วย `ldd` ว่า executable `orbbec_camera_node` และ `list_devices_node` พบ shared libraries ครบ
- `rosdep check --from-paths src --ignore-src --rosdistro jazzy` ยืนยันว่า dependencies ทั้งหมดที่ประกาศไว้ติดตั้งแล้ว รวมถึง dependencies ของ Orbbec
- การทดสอบ Offline ผ่าน 8 รายการ ครอบคลุม Frame Encoding, Checksum, Fragmentation, การตรวจความถูกต้องของ Payload, USB Device Selection, Timeout, Readback และ Reconnect ด้วย Serial จำลอง
- ตรวจ ROS graph ในโปรเซสทดสอบโดยใช้ ROS messages ที่ generate แล้ว ขอบเขตของการทดสอบนี้คือการสื่อสารในโปรเซสเดียว โหนด Dobot มี publishers สำหรับข้อมูลอ่านกลับ ไม่มี subscriber, command service หรือ action server การส่ง Serial ทุกเฟรมที่ทดสอบเป็น GET แบบไม่เข้าคิว จากชุด ID `0, 1, 2, 10, 20, 62, 63`
- ตรวจ Python syntax และ Imports จาก install overlay รวมถึง URDF, path ของ Mesh และ YAML ทั้งสองไฟล์
- ทดสอบ Launch ของ Dobot ด้วยค่าเริ่มต้นที่ไม่ได้ระบุพอร์ต โหนดเริ่มและจบด้วย SIGINT ตามปกติ
- ตรวจไฟล์ต้นทางและ Manifest ของส่วน Dobot แล้ว ไม่พบการอ้างถึงระบบเดิมในโค้ดที่รันหรือ Launch ไฟล์ข้อความของ Dobot มีเฉพาะ `.msg`

## ข้อจำกัดของฮาร์ดแวร์

- การตอบกลับของ Dobot และการสตรีมของ Orbbec ถูกตรวจในระดับโปรโตคอลจำลองและการ Build ตามลำดับ การเปิดพอร์ตจริง รุ่น Firmware ที่ใช้งานได้ โปรไฟล์กล้อง และความถูกต้องของ Registered Depth ต้องตรวจบนอุปกรณ์ในงานแยกต่างหาก
- สถานะ Suction/Gripper เป็นข้อมูลจากตัวควบคุม เครื่องมือที่ไม่ตอบคำขอ GET จะรายงาน `valid=false` ค่าดังกล่าวไม่วัดแรงดูดหรือการจับชิ้นงาน
- การอ่านสถานะมีผลกับไดรเวอร์ใน Branch นี้ ส่วนซอฟต์แวร์ภายนอกที่เปิดพอร์ต Serial หรือควบคุมอุปกรณ์ทางอื่นอยู่ภายนอกขอบเขตของไดรเวอร์

## ระบบที่จะต้องพัฒนาและตรวจสอบก่อนเปิดการเคลื่อนที่

1. สร้างการอนุญาตคำสั่งและสิทธิ์ควบคุมเพียงแหล่งเดียว กำหนดสถานะที่อนุญาตให้เคลื่อนที่และขั้นตอนยืนยันจากผู้ปฏิบัติ
2. ตรวจ Soft Joint Limits, Workspace Limits, ความเร็ว ความเร่ง และเส้นทางทั้งหมด รวมถึงการชนกับตัวแขน เครื่องมือ และสิ่งแวดล้อมตามการติดตั้งจริง
3. ตรวจความสดของข้อมูล ตัวตนอุปกรณ์ สถานะ Alarm และสถานะการอ้างอิงพิกัดก่อนอนุญาตให้เคลื่อนที่ ออกแบบ Startup, Homing และ Reconnect ให้เริ่มในสถานะไม่เคลื่อนที่
4. กำหนดพฤติกรรมหยุดเมื่อ Timeout, การสื่อสารขาดหาย หรือเกิด Alarm จัดการคิวและ Recovery แบบที่ผู้ปฏิบัติควบคุมได้
5. ตรวจการทำงานร่วมกับ Hardware Emergency Stop และระบบป้องกันของ Firmware ผู้ผลิต คงการป้องกันเหล่านั้นไว้ และยืนยันผลด้วยการทดสอบซอฟต์แวร์และการทดสอบฮาร์ดแวร์ในพื้นที่ควบคุมก่อนเปิดใช้จริง
