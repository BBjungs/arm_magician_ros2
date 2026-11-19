# Dobot Eye-in-Hand Auto Center

ระบบ ROS 2 Jazzy สำหรับจัดกึ่งกลางชิ้นงานในภาพ RGB ของกล้องที่ติดปลายแขน Dobot Magician ระบบจำลองใช้ OpenCV ตรวจและติดตามชิ้นงาน วัดการตอบสนองของภาพจาก TCP ที่อ่านกลับ และแก้ตำแหน่ง X/Y ทีละช่วงโดยตรึง Z/R เมื่อผ่านเกณฑ์ครบห้าเฟรม ระบบจะแสดง `CENTERED` และค้างตำแหน่ง

Branch นี้สร้างจาก hardware-only commit `1095058` และใช้ซอฟต์แวร์จำลองสำหรับทุกคำสั่งเคลื่อนที่ ไดรเวอร์ Dobot แบบ GET และ Orbbec v1.5.22 ยังเป็นส่วนของ workspace เดิม สามารถดูข้อมูล RGB-D และ Robot Readback ผ่าน ROS แบบ passive ได้

## ติดตั้งและ build

ใช้ Ubuntu 24.04 ARM64, ROS 2 Jazzy, Python 3.12, Colcon และ rosdep ใน checkout ของ branch พัฒนา

```bash
git submodule update --init --recursive
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro jazzy -r -y
colcon build --base-paths src --cmake-args -DBUILD_TESTING=OFF
source install/setup.bash
```

## เริ่ม simulation

ใน terminal ที่ source overlay ของ branch นี้แล้ว ให้กำหนด token อย่างน้อย 24 ตัวอักษรและใช้ ROS domain แยกสำหรับ simulation

```bash
export ROS_DOMAIN_ID=42
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
read -rsp 'New operator token (at least 24 characters): ' DOBOT_OPERATOR_TOKEN
export DOBOT_OPERATOR_TOKEN
printf '\n'
ros2 launch dobot_auto_center auto_center.launch.py config:="$PWD/config"
```

เปิด `http://127.0.0.1:8080` บน Jetson และใส่ token เดียวกัน จากเครื่องอื่นให้ใช้ authenticated tunnel ตาม [คู่มือ Dashboard](docs/WEB_DASHBOARD.md)

1. กด **Take control** และ **Start camera** รอให้ RGB และ Registered Depth พร้อม
2. กด **HOME** และยืนยัน รอให้ระบบตรวจสอบตำแหน่ง
3. กด **Observation pose** และยืนยันแยก รอให้ตำแหน่งสังเกตการณ์พร้อม
4. กด **Start detection** เลือกชิ้นงานจากรายการแล้วกด **Lock target** หรือลาก ROI ครอบชิ้นเดียวบนภาพ
5. กด **AUTO CENTER** และยืนยัน ดูค่าคลาดเคลื่อนและ TCP เปลี่ยนระหว่างการแก้ทีละช่วง
6. เมื่อขึ้น **CENTERED** ระบบเข้าสู่ HOLDING ใช้ **STOP** ได้ทุกช่วงที่มี operator token

กำหนด `mock_scenario` เป็น `left`, `right`, `up`, `down`, `corner`, `centered`, `lost` หรือ `multiple` ใน `config/visual_servo.yaml` ก่อนเริ่ม node รองรับ `mock_jacobian` แบบ `normal`, `reversed`, `coupled` และ `singular`

## ใช้งานผ่าน LAN บน Jetson

ใช้ startup script และ unit แยกสำหรับ `172.30.10.101:8080` ตาม [คู่มือ LAN Deployment](docs/LAN_DEPLOYMENT.md) คู่มือมีขั้นตอนทดสอบพอร์ต 18080 ก่อนเปิด service และวิธีเปิดโหมด Read-Only เพื่ออ่านข้อมูลจาก drivers ที่รันอยู่แล้ว

## ตรวจความพร้อมแบบ passive

คัดลอก config ไปอีก directory ตั้ง `simulation_mode: false` และรัน launch ด้วย `config:=<directory>` เพื่ออ่าน topics ที่มีอยู่ โหมดนี้ไม่มี ROS action server หรือ motion transport ให้ใช้คำสั่งด้านล่างเพื่อตรวจ topics โดยไม่เปิดอุปกรณ์

```bash
ros2 run dobot_auto_center auto_center_readiness --config "$PWD/config" --seconds 5
```

ผล Software Tests และข้อจำกัดอยู่ใน [รายงานทดสอบ](docs/TEST_REPORT.md) การยืนยัน Firmware, การจัดแนวภาพจริง, HOME, clearance, E-STOP และพฤติกรรมหยุดต้องทำตาม [Hardware Commissioning](docs/HARDWARE_COMMISSIONING.md) โดยผู้ควบคุมอุปกรณ์

## เอกสาร

- [Architecture](docs/ARCHITECTURE.md)
- [Web Dashboard](docs/WEB_DASHBOARD.md)
- [Vision Pipeline](docs/VISION_PIPELINE.md)
- [Visual Servo](docs/VISUAL_SERVO.md)
- [Motion and Safety](docs/MOTION_SAFETY.md)
- [Hardware Commissioning](docs/HARDWARE_COMMISSIONING.md)
- [Test Report](docs/TEST_REPORT.md)
