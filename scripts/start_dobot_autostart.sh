#!/usr/bin/env bash
set -eo pipefail

DOBOT_WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${DOBOT_WS_DIR}"

: "${ROS_DISTRO:=jazzy}"
: "${ORBBEC_WS:=${DOBOT_WS_DIR}}"
: "${START_CAMERA:=true}"

set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [[ ! -r "${DOBOT_WS_DIR}/install/setup.bash" ]]; then
  echo "Canonical workspace is not built: ${DOBOT_WS_DIR}" >&2
  exit 1
fi
if [[ "${START_CAMERA,,}" =~ ^(1|true|yes|on)$ && "${ORBBEC_WS}" != "${DOBOT_WS_DIR}" ]]; then
  echo "Refusing non-canonical Orbbec workspace: ${ORBBEC_WS}" >&2
  exit 1
fi
source "${DOBOT_WS_DIR}/install/setup.bash"
set -u

: "${MAGICIAN_TOOL:=suction_cup}"
: "${VISION_MODE:=eye_in_hand}"
: "${DOBOT_SERIAL_PORT:=/dev/ttyUSB0}"
: "${DOBOT_SERIAL_TIMEOUT:=1.0}"
: "${WEB_HOST:=127.0.0.1}"
: "${WEB_PORT:=8080}"
: "${DOBOT_WEB_API_TOKEN:=}"
: "${ORBBEC_CAMERA_NAME:=camera}"
: "${ORBBEC_SERIAL_NUMBER:=}"
: "${ORBBEC_DEPTH_REGISTRATION:=true}"
: "${CAMERA_DEVICE:=}"
: "${CAMERA_WIDTH:=640}"
: "${CAMERA_HEIGHT:=480}"
: "${CAMERA_FPS:=30.0}"
: "${STREAM_FPS:=12.0}"
: "${START_BRINGUP:=true}"
: "${START_VISION:=true}"
: "${VISION_ENGINE:=rgbd_shape}"
: "${DOBOT_TOOL_MAPPING:=canonical}"
: "${ROS_LOG_DIR:=/tmp/dobot_ros_logs}"

export MAGICIAN_TOOL
export DOBOT_SERIAL_PORT DOBOT_SERIAL_TIMEOUT
export ROS_LOG_DIR
export WEB_HOST WEB_PORT
export DOBOT_WEB_API_TOKEN
export ORBBEC_WS ORBBEC_CAMERA_NAME ORBBEC_SERIAL_NUMBER ORBBEC_DEPTH_REGISTRATION
export CAMERA_DEVICE CAMERA_WIDTH CAMERA_HEIGHT CAMERA_FPS STREAM_FPS
export START_BRINGUP
export START_CAMERA
export START_VISION
export VISION_ENGINE
export VISION_MODE
export DOBOT_TOOL_MAPPING

mkdir -p "${ROS_LOG_DIR}"

launch_args=(
  tool:="${MAGICIAN_TOOL}"
  host:="${WEB_HOST}"
  port:="${WEB_PORT}"
  camera_width:="${CAMERA_WIDTH}"
  camera_height:="${CAMERA_HEIGHT}"
  camera_fps:="${CAMERA_FPS}"
  stream_fps:="${STREAM_FPS}"
  start_bringup:="${START_BRINGUP}"
  start_camera:="${START_CAMERA}"
  orbbec_camera_name:="${ORBBEC_CAMERA_NAME}"
  orbbec_depth_registration:="${ORBBEC_DEPTH_REGISTRATION}"
  start_vision:="${START_VISION}"
  vision_engine:="${VISION_ENGINE}"
  vision_mode:="${VISION_MODE}"
  tool_mapping:="${DOBOT_TOOL_MAPPING}"
)
if [[ -n "${CAMERA_DEVICE}" ]]; then
  launch_args+=(camera_device:="${CAMERA_DEVICE}")
fi
if [[ -n "${ORBBEC_SERIAL_NUMBER}" ]]; then
  launch_args+=(orbbec_serial_number:="${ORBBEC_SERIAL_NUMBER}")
fi
exec ros2 launch dobot_web_interface dobot_auto.launch.py "${launch_args[@]}"
