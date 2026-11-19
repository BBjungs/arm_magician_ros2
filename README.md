# Dobot Magician และ Orbbec RGB-D บน ROS 2 Jazzy

Workspace นี้มีไดรเวอร์อ่านสถานะ Dobot Magician ผ่าน USB/Serial และไดรเวอร์ Orbbec สำหรับ RGB, Depth และ Camera Info ใช้กับ NVIDIA Jetson Orin Nano (ARM64), Ubuntu 24.04, ROS 2 Jazzy และ Python 3.12

- **Dobot Magician** ใช้พอร์ตอนุกรม 115200 baud, 8N1 อ่านสถานะตัวควบคุมและอุปกรณ์ปลายแขน Suction Cup หรือ Gripper
- **Orbbec RGB-D** ใช้ไดรเวอร์ทางการที่ตรึงไว้ที่รุ่น v1.5.22 การรองรับกล้องและโหมดสตรีมขึ้นกับรุ่นกล้องและ SDK ที่มากับไดรเวอร์ [Orbbec ROS 2 v1.5.22](https://github.com/orbbec/OrbbecSDK_ROS2/releases/tag/v1.5.22)

## ติดตั้งและ Build

ติดตั้ง ROS 2 Jazzy และเครื่องมือพัฒนาบน Ubuntu 24.04 โดยเตรียม `colcon` และ `rosdep` (แพ็กเกจ `ros-dev-tools`) หากเครื่องยังไม่เคยตั้งค่า `rosdep` ให้ initialize และอัปเดตฐานข้อมูลตามคู่มือ จากนั้นเปิดเชลล์ใหม่ใน checkout ของ Branch นี้ [คู่มือติดตั้ง ROS 2 Jazzy](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)

```bash
git submodule update --init --recursive
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro jazzy -r -y
colcon build --base-paths src --cmake-args -DBUILD_TESTING=OFF
source install/setup.bash
```

`rosdep` ติดตั้ง dependencies จาก `package.xml` ฝั่ง Dobot ใช้ `ament_cmake`, `ament_cmake_python`, `rosidl`, `rclpy`, `pyserial` และ ROS message packages ฝั่ง Orbbec ใช้ SDK ที่อยู่ใน submodule และ dependencies ของไดรเวอร์ เช่น `cv_bridge`, `image_transport`, `camera_info_manager`, `tf2` และไลบรารี native ที่เกี่ยวข้อง [คู่มือ rosdep สำหรับ Jazzy](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Rosdep.html)

บัญชีที่รัน Dobot ต้องมีสิทธิ์เปิดพอร์ตอนุกรม สำหรับ Orbbec ให้ตั้งค่า udev บนเครื่องที่จะใช้งานกล้องตามคู่มือผู้ผลิต [คู่มือ Orbbec ROS 2](https://github.com/orbbec/OrbbecSDK_ROS2/tree/v1.5.22)

## โครงสร้างไดรเวอร์

| ตำแหน่ง | หน้าที่ |
| --- | --- |
| `src/dobot_hardware/driver/dobot_driver/` | การเลือกพอร์ต USB การจัดการ Serial โปรโตคอล Dobot ใน `protocol/` และโหนดเผยแพร่สถานะใน `state/` |
| `src/dobot_hardware/interfaces/` | ข้อความ ROS 2 ของ `dobot_msgs` สำหรับอ่านสถานะ |
| `src/dobot_hardware/description/` | URDF และ Mesh ของ Dobot Magician |
| `src/OrbbecSDK_ROS2/` | Submodule ของไดรเวอร์ Orbbec ทางการ |
| `config/`, `launch/` | ค่าเริ่มต้นและ Launch ของทั้งสองอุปกรณ์ |
| `tests/hardware_protocol/` | การทดสอบโปรโตคอลและ ROS graph ด้วย Serial จำลอง |

## Dobot readback

คัดลอก `config/dobot.yaml` แล้วตั้ง `serial_port` เป็นพอร์ตของ Dobot เช่น path ที่ระบุอุปกรณ์ใต้ `/dev/serial/by-id/` หรือใช้ `usb_id` รูปแบบ `VID:PID` พร้อม `usb_serial_number` หากมีหลายอุปกรณ์ชนิดเดียวกัน การค้นหาด้วย USB ID จะเปิดพอร์ตเมื่อพบผลลัพธ์เดียวเท่านั้น ค่าเริ่มต้นจะรอจนกว่าจะกำหนดอุปกรณ์ ใช้พอร์ตนี้กับไดรเวอร์เพียงตัวเดียวในขณะใช้งาน

```bash
ros2 launch dobot_driver dobot_driver.launch.py params_file:="$PWD/config/dobot.yaml"
```

| Topic | ชนิด | ข้อมูล |
| --- | --- | --- |
| `/dobot/device_status` | `dobot_msgs/msg/DeviceStatus` | ผลการตอบสนองจากตัวควบคุม พอร์ต ชื่อ Serial Number และ Firmware Version เมื่ออ่านได้ |
| `/joint_states` | `sensor_msgs/msg/JointState` | มุมข้อต่อสี่แกนเป็นเรเดียน โดยแปลงแกนที่สามเป็นมุมสัมพัทธ์ตาม URDF |
| `/dobot/tcp_pose` | `geometry_msgs/msg/PoseStamped` | พิกัด TCP เป็นเมตรและมุมรอบแกน Z เป็น Quaternion ใน `magician_base_link` |
| `/dobot/alarms` | `dobot_msgs/msg/AlarmState` | ดัชนีบิตที่ติดใน Alarm Bitmap เป็นเลขฐานสิบ |
| `/dobot/suction`, `/dobot/gripper` | `dobot_msgs/msg/ToolState` | สถานะเปิดใช้งานและสถานะเอาต์พุตที่ตัวควบคุมรายงาน |

เมื่อ `connected=false` ให้ถือว่าตัวอย่างก่อนหน้าใช้แทนสถานะสดไม่ได้ โหนดจะลองเปิดพอร์ตใหม่ในการ Poll ถัดไป สำหรับ Alarm และ Tool ให้ใช้ข้อมูลเมื่อ `valid=true` ค่า Tool เป็นสถานะจากตัวควบคุม ข้อมูลนี้ไม่ยืนยันแรงดูด ตำแหน่งจริงของปากจับ หรือการติดตั้งอุปกรณ์

## Orbbec RGB-D

```bash
ros2 launch dobot_driver orbbec_camera.launch.py params_file:="$PWD/config/orbbec.yaml"
```

กำหนด `serial_number` หรือ `usb_port` ในไฟล์ YAML เพื่อเลือกกล้อง เมื่อต้องการใช้สตรีมขนาดหรือรูปแบบอื่น ให้เลือกโปรไฟล์ที่กล้องรองรับ ค่าตั้งต้นเปิด `depth_registration` และตั้ง `align_mode: HW` สำหรับการจัดแนว Depth เข้ากับภาพสี ตามโปรไฟล์ที่กล้องรองรับ

| ROS interface | ข้อมูล |
| --- | --- |
| `/camera/color/image_raw` | ภาพ RGB |
| `/camera/depth/image_raw` | ภาพ Depth ที่จัดแนวกับภาพสีเมื่อเปิด Registration |
| `/camera/color/camera_info`, `/camera/depth/camera_info` | Intrinsics และข้อมูลเฟรมของแต่ละสตรีม |
| `/tf_static` และ `/tf` ตามการตั้งค่าไดรเวอร์ | Camera frames เช่น `camera_link` และ `camera_color_optical_frame` |
| `/camera/get_device_info` | ข้อมูลอุปกรณ์ผ่าน `orbbec_camera_msgs/srv/GetDeviceInfo` เมื่อกล้องพร้อม |

`ros2 run orbbec_camera list_devices_node` ใช้ตรวจการตรวจพบกล้องบนเครื่องที่จะใช้งาน

## การทดสอบและการพัฒนาต่อ

```bash
ROS_AUTOMATIC_DISCOVERY_RANGE=OFF python3 -m unittest discover -s tests/hardware_protocol -v
```

ไดรเวอร์ Dobot ส่งเฉพาะคำขอ GET ที่กำหนดไว้ และเผยแพร่สถานะผ่าน ROS 2 ก่อนเพิ่มการเคลื่อนที่ ให้สร้างตัวควบคุมใหม่และตรวจสอบระบบป้องกันตามรายการใน [RESET_REPORT.md](RESET_REPORT.md) โดยคงระบบป้องกันของตัวควบคุมและอุปกรณ์ผู้ผลิตไว้
