# เตรียมแก้ Blocker Commissioning

อ้างอิง HEAD `4418cd9`; ตรวจ Production ใหม่ 11 ตุลาคม 2026 เวลา
09:41:20 UTC / 16:41:20 ไทย ดู [หลักฐาน runtime](commissioning-blocker-resolution-2026-10-11/live-evidence.json)
งานนี้ยังไม่ Restart, ไม่ติดตั้ง drop-in, ไม่ส่ง motion, ไม่เปลี่ยน PTP
และไม่ยืนยัน Safety Checklist แทนผู้ควบคุม

| สถานะ | ผลและขอบเขต |
| --- | --- |
| SOFTWARE PASS | ชุด Commissioning เดิมที่ commit 4418cd9: 147 ผ่าน ไม่มี fail/error/skipped; ไม่แก้ controller ในรอบนี้ |
| GEOMETRY VERIFIED | NO — ไม่มี workspace ที่วัดจริง; จัดเตรียมแบบฟอร์มแล้ว |
| RUNTIME READY | NO — process เก่า ไม่มี protocol 2/Commission/Authorize; เตรียม profile และขั้นตอนเปลี่ยนแล้ว |
| MOTION VERIFIED | NO — ไม่ส่ง goal ของงานนี้ |
| COMMISSIONING COMPLETE | NO — BLOCKED ก่อนการเตรียมแผนจริง |

## A. จุดอ้างอิงและแบบฟอร์ม Geometry

[แบบบันทึกหน้างาน](commissioning-workspace-measurement-form.yaml) เว้นค่าที่ต้องวัดเป็น null
และ verified flags เป็น false ไม่ติดตั้งลง `~/.ros/dobot/` อัตโนมัติ
แบบฟอร์มเก็บ robot/camera/mount identity, datum, วิธีวัด/เครื่องมือ/uncertainty,
table points, ขอบเขตพื้นที่ว่างทั้งหกด้าน และหลักฐาน sweep ทุก segment

ใน `magician.urdf.xacro` origin ของ J1 และ J2 อยู่ที่ magician_base_link
โมเดลใช้แกนหมุนฐาน J1 เป็น Z และแกนไหล่ J2 เป็น Y
จุดอ้างอิงที่ต้องตรวจบนเครื่องคือ **จุดตัดแกนหมุนฐาน J1 กับแนวศูนย์แกนไหล่ J2**
หรือ datum ที่คู่มือ/แบบเครื่องระบุว่าสัมพันธ์กับจุดนี้ ไม่ใช่ขอบฝาครอบหรือยอดฐาน
ต้องยืนยันแนวแกนและระยะ offset จริงก่อนระบุว่าเป็น Controller origin
ถ้าจุดตัดเข้าถึงไม่ได้ ให้ใช้ datum ภายนอกที่วัดได้พร้อม offset ที่มีหลักฐาน
ห้ามเคลื่อนแขนเพื่อหาระดับโต๊ะระหว่างการสำรวจนี้โดยไม่มี workflow/authorization แยก

URDF ให้ root→base สูง 0.131305 m แต่ collision model ใช้ root→base ศูนย์
และ ground -0.131305 m; ตัวเลขเหล่านี้เป็น model datum
`dobot_forward_kin.py::calc_FwdKin()` เริ่ม chain ที่ J1/J2 แล้วใช้ links 135/147 mm
ไม่มี base-height offset ส่วน `dobot_state_publ.py::timer_callback()` ใส่ Controller
get_pose XYZ/1000 ลง TCP และ base→TCP ตรง ๆ จึงอธิบาย datum ในซอฟต์แวร์ได้
แต่ยังไม่พิสูจน์ความสูงจากโต๊ะของเครื่องจริง

เมื่อวัด h = ความสูง origin เหนือโต๊ะและยืนยัน base Z ตั้งฉากขึ้นจริง
จึง derive table_surface_z_m = -h ได้ ต้องบันทึกผลวัดและ uncertainty
หากโต๊ะเอียง/ไม่เรียบ loader ปัจจุบันรับ scalar Z เท่านั้น ต้องใช้ upper bound
ที่มีหลักฐานและ conservative ต่อ swept clearance หรือคง BLOCKED หากแทนพื้นที่ไม่ได้
ไม่ใช้ nominal -0.131305 หรือ 0.0 เป็นผลวัด

ก่อนระบุ cup-mouth/TCP offset ต้องอ่าน Controller end-effector parameters จริง:
bringup เดิม `set_tool_null.py` ตั้ง end_effector_params(0,0,0) และ clear alarms
เมื่อเริ่ม stack ใหม่ ทำให้ต้องตรวจ datum และ alarms ซ้ำหลัง Restart
ข้อมูล mount เดิมใน config ไม่แทนการวัด/ตรวจความแน่นของการติดตั้งรอบนี้
รวมกล้อง bracket หัวดูด สาย/ท่อ และแขนทุก link ในการสำรวจ
bounding sphere ของ workspace code เป็น TCP/tool/camera envelope;
การยืนยัน whole_robot_environment ต้องมีหลักฐานแขนทั้งตัวด้วย
Collision model self/ground เดิมไม่ได้สร้างแผนที่คน/สิ่งกีดขวางทั้งหมด

ให้กรอก free_volume_min/max เป็นพื้นที่ที่วัดว่าว่างจริงใน Controller base frame
จากขอบเขต X-/X+/Y-/Y+/Z-/Z+ และเหตุผลของแต่ละขอบเขต ไม่ประมาณจาก RGB ภาพเดียว
การวาง robot บนโต๊ะโดยตรงเป็นหลักฐาน support placement เท่านั้น
หลังกรอกและ review จึงสร้าง workspace file ที่ผูก camera ID และ mount fingerprint
ของ runtime จริง โดยไม่ลด clearance 0.025 m หรือ threshold เดิม

## B. Production Runtime และแผน Restart ที่รออนุมัติ

user systemd: `dobot-magician.service`, MainPID 4089082, unit
`/home/bbcontact/.config/systemd/user/dobot-magician.service`
EnvironmentFile คือ `config/dobot-autostart.env`; ExecStart คือ
`scripts/start_dobot_autostart.sh`; KillMode=control-group, Restart=on-failure
ไม่มี drop-in ณ snapshot; environment ตั้ง startup_auto=true,
startup_auto_recalibrate=false, startup_auto_motion=false
จึงปิดทั้งสามก่อนการโหลด runtime ใหม่ แม้ profile เดิมปิด HOME/observation motion แล้ว

เตรียม [environment ปิด startup](commissioning-runtime-staging/startup-disabled.env)
และ [systemd drop-in](commissioning-runtime-staging/90-commissioning.conf) ไว้ใน repository
**ยังไม่ติดตั้งลง systemd**; EnvironmentFile ตัวหลังจะ override สามค่าจากไฟล์เดิม
ไม่เปลี่ยนกล้อง/tool/threshold หรือสร้าง Motion Controller ใหม่

ขั้นตอนที่เสนอให้ผู้ควบคุมอนุมัติเฉพาะ Restart มีดังนี้:

1. อยู่หน้าเครื่อง มี physical stop พร้อมใช้งาน บันทึก TCP/joints/alarm/PTP เดิม
   ตรวจ web active_goal/vision_sequence, calibration/smoke/transaction state
   และ action server ไม่มี executing/accepted/canceling goal
   ต้องมีหลักฐานอิสระจาก server/queue หรือ status; status stream ที่ไม่ตอบไม่ถือเป็น idle
   ถ้ามี goal/fault ให้หยุดผ่าน workflow เดิมและตรวจ terminal/stationary ก่อน
   ห้ามถือ service restart เป็นวิธีหยุด robot
2. หลังผู้ควบคุมอนุมัติและ pre-stop checks ผ่าน ให้ stop systemd unit
   (explicit stop ไม่ trigger Restart=on-failure) รอ cgroup ทุก process หยุด
   และตรวจไม่มี serial/camera/PTP/calibration stack ซ้อน
3. ติดตั้ง drop-in, daemon-reload และตรวจ EnvironmentFiles ordering
   แล้ว build เฉพาะ msgs/calibration/web ลง canonical install ขณะ production หยุด
   ไม่ลบ build/install/log หรือ dirt เดิม หาก build ล้มเหลวให้คง service หยุดและรายงาน
4. start service ด้วย override ปิด startup ทั้งสาม บันทึก PID/เวลาที่เริ่มใหม่
   ตรวจ launch command และ ROS web parameters ยืนยัน false ทั้งสามจริง
   ห้ามเรียก HOME, observation, legacy smoke หรือ autonomous start ระหว่างตรวจ
5. ยืนยัน protocol=2, startup software_source_digest ตรง modules ที่ build,
   typed AuthorizeCalibration และ Commission services พร้อม โดยไม่เรียก authorize
   ตรวจ E-stop/status/alarms/controller datum/camera/PTP/feedback ใหม่หลัง bringup
   หากไม่ผ่านให้คง motion ไม่ได้รับอนุญาต; ห้าม rollback ไป profile automatic โดยเงียบ ๆ

คำสั่งด้านล่างเป็น runbook เท่านั้น ยังไม่ได้ execute ในงานนี้:

```bash
cd /home/bbcontact/magician_ros2
# หลังอนุมัติและตรวจ idle/stop/stationary ผ่านเท่านั้น
systemctl --user stop dobot-magician.service
systemctl --user show dobot-magician.service -p ActiveState -p MainPID -p ControlGroup
# ตรวจว่า process ใน cgroup และ stack เดิมหมดแล้วก่อนขั้นต่อไป
mkdir -p /home/bbcontact/.config/systemd/user/dobot-magician.service.d
cp docs/commissioning-runtime-staging/90-commissioning.conf /home/bbcontact/.config/systemd/user/dobot-magician.service.d/
systemctl --user daemon-reload
systemctl --user show dobot-magician.service -p EnvironmentFiles -p DropInPaths
source /opt/ros/jazzy/setup.bash
source install/local_setup.bash
colcon build --packages-select dobot_msgs dobot_calibration dobot_web_interface --symlink-install
# ทำต่อเมื่อ build exit 0 เท่านั้น; ใช้ shell ใหม่เพื่อ source install ที่ build แล้ว
systemctl --user start dobot-magician.service
```

หลังโหลดใหม่ตรวจแบบ read-only:

```bash
source /opt/ros/jazzy/setup.bash
source /home/bbcontact/magician_ros2/install/local_setup.bash
ros2 service list -t
ros2 param get /dobot_web_interface startup_auto
ros2 param get /markerless_calibration recalibrate_on_failure
ros2 param get /markerless_calibration auto_start
ros2 param get /dobot_web_interface startup_auto_motion
curl --noproxy '*' -fsS http://127.0.0.1:8080/api/vision/calibration
```

startup_auto_recalibrate ถูก launch map เป็น recalibrate_on_failure ของ calibration node;
auto_start ของ calibration ต้อง false เช่นกัน ชื่อ node ต้องตรวจจาก `ros2 node list` อีกครั้ง;
protocol อยู่ใน
automatic_calibration.authorization_protocol และ startup source digest อยู่ที่ top-level
ต้องเห็น `/calibration/autonomous/commission [std_srvs/srv/Trigger]` และ
`/calibration/autonomous/authorize [dobot_msgs/srv/AuthorizeCalibration]`
การมีไฟล์ service ใน build อย่างเดียวไม่พิสูจน์ runtime พร้อม

## C. Preflight ล่าสุดและแผนที่ยังเตรียมไม่ได้

workspace path จริงจาก ROS parameter `~/.ros/dobot/calibration_workspace.yaml` ยังไม่มี
camera_id=AY2A760003E; carrier_frame ว่าง; mount_model คือ canonical config เดิม
Hardware readiness READY: depth/TCP/joints/alarms fresh, depth stable, robot connected
software safety monitoring NOT CONNECTED; operator_safety_verified เป็น status เดิม
ไม่ใช่การทดสอบ physical E-stop หรือการอนุญาตเฉพาะรอบนี้
TCP snapshot [149.950455, ~0, 100.030876] mm, J4≈0° เป็น preflight reading
ยังไม่ใช่ capture Commissioning Pose 1

Runtime มีเฉพาะ autonomous start/pause/resume/abort; protocol/digest ไม่ปรากฏ
Web ไม่มี active_goal/vision_sequence แต่ไม่ได้รับ PTP status แม้ใช้ transient QoS
จึงยังไม่ยืนยัน server idle อย่างอิสระ
ค่าจำกัดอ้างอิงจาก axis_limits.yaml คือ J1 [-120,120], J2 [-5,90],
J3 [-15,90], J4 [-140,140] deg; collision และ ground enabled; path steps 2 mm/2 deg
นี่เป็น source policy ไม่ใช่ผลอ่าน policy ที่ runtime validated plan ใช้
หลัง Restart backend ต้องอ่าน policy จริงจาก validator และผูกกับ fingerprint

เมื่อ workspace/mount/sensors/scene/idle ผ่านแล้วเท่านั้น ใช้ POST
`/api/calibration/autonomous/commission` เพื่อเตรียมแผนเดิม purpose
COMMISSIONING_TWO_POSES ซึ่งตรวจทั้งสิบ segments แต่ execute/capture เฉพาะสองท่า
แสดง Pose 1/2 XYZ/J4, full validated plan, fingerprint และ safety diagnostics
แล้วหยุดที่ WAITING_FOR_OPERATOR_AUTHORIZATION ไม่มี motion/PTP change ก่อน authorize
ตอนนี้ยังไม่มี target หรือ fingerprint ที่ผ่าน validation จึงไม่แทนด้วย Passive X185

## D. การอนุญาตและหลักฐาน Real Motion

การอนุมัติ Restart ไม่ใช่ motion authorization ต้องขอเฉพาะรอบ/แผนใหม่อีกครั้ง
ผู้ควบคุมหน้าเครื่องต้องทดสอบ E-stop, ตรวจพื้นที่และ mount, ยืนยันผลวัด
และ collision, ความสามารถหยุดจริง และทบทวนพิกัด Pose 1/2 กับ fingerprint
หลัง typed authorize จึงใช้ guarded MOVL low-speed เดิมเฉพาะ Pose 2
Pose 1 เป็น current anchor ตรวจนิ่งและ capture จริง ไม่จำเป็นต้องส่ง goal ถ้าอยู่เป้าหมาย
ตรวจ terminal success, actual TCP/J4, error/tolerance, stationary ก่อน capture,
บันทึก RGB-D/telemetry, PTP restore/readback และ revoke authorization
fault → safe stop ตามระบบเดิม ไม่มี automatic retry หรือ Pose 3

Motion Command Sent=FALSE; Terminal Result/Actual Pose 2/Error/Duration/Capture=N/A
PTP restore=NOT_REQUIRED; ไม่มี COMMISSIONING_COMPLETE และไม่พร้อมเริ่มรอบสิบท่า
คง BLOCKED จนได้ measurement evidence, restart approval, runtime checks และ round authorization
