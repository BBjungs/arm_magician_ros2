#!/usr/bin/env bash
set -eo pipefail

DOBOT_WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${DOBOT_WS_DIR}"

: "${ROS_DISTRO:=jazzy}"
: "${ORBBEC_WS:=${DOBOT_WS_DIR}}"
: "${START_CAMERA:=true}"
: "${DEVICE_WAIT_TIMEOUT_SEC:=45}"

if [[ "${ROS_DISTRO}" != "jazzy" ]]; then
  echo "[BOOT] Refusing ROS distribution ${ROS_DISTRO}; Jazzy is required" >&2
  exit 1
fi

lock_file="/run/user/$(id -u)/dobot-magician.lock"
exec 9>"${lock_file}"
if ! flock -n 9; then
  echo "[BOOT] Another production stack already owns ${lock_file}" >&2
  exit 1
fi

set +u
source "/opt/ros/jazzy/setup.bash"
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
: "${START_CALIBRATION:=true}"
: "${CALIBRATION_CARRIER_FRAME:=}"
: "${CALIBRATION_MOUNT_MODEL:=}"
: "${REQUIRE_INTEGRATED_STARTUP:=true}"
: "${STARTUP_AUTO:=false}"
: "${STARTUP_AUTO_RECALIBRATE:=false}"
: "${STARTUP_AUTO_MOTION:=false}"
: "${ROS_LOG_DIR:=/tmp/dobot_ros_logs}"
: "${WEB_START_TIMEOUT_SEC:=90}"
: "${MONITOR_INTERVAL_SEC:=1}"
: "${MONITOR_FAILURE_GRACE_SEC:=5}"
: "${STACK_STOP_TIMEOUT_SEC:=20}"

if [[ "${WEB_PORT}" != "8080" ]]; then
  echo "[BOOT] Production web port must be 8080, got ${WEB_PORT}" >&2
  exit 1
fi

wait_for_path() {
  local path="$1"
  local label="$2"
  local deadline=$((SECONDS + DEVICE_WAIT_TIMEOUT_SEC))
  while [[ ! -e "${path}" ]]; do
    if (( SECONDS >= deadline )); then
      echo "[BOOT] Timed out waiting for ${label}: ${path}" >&2
      return 1
    fi
    sleep 1
  done
}

detect_orbbec() {
  local path vendor product serial speed
  local -a rgb_serials=()
  local depth_count=0
  local depth_superspeed_count=0
  for path in /sys/bus/usb/devices/*; do
    [[ -r "${path}/idVendor" && -r "${path}/idProduct" ]] || continue
    read -r vendor <"${path}/idVendor" || continue
    [[ "${vendor}" == "2bc5" ]] || continue
    read -r product <"${path}/idProduct" || continue
    if [[ "${product}" == "0511" && -r "${path}/serial" ]]; then
      read -r serial <"${path}/serial" || true
      [[ -n "${serial}" ]] && rgb_serials+=("${serial}")
    elif [[ "${product}" == "0614" && -r "${path}/speed" ]]; then
      depth_count=$((depth_count + 1))
      read -r speed <"${path}/speed" || speed=0
      if [[ "${speed%%.*}" =~ ^[0-9]+$ ]] && (( ${speed%%.*} >= 5000 )); then
        depth_superspeed_count=$((depth_superspeed_count + 1))
      fi
    fi
  done
  if (( ${#rgb_serials[@]} != 1 || depth_count != 1 || depth_superspeed_count != 1 )); then
    return 1
  fi
  DETECTED_ORBBEC_SERIAL="${rgb_serials[0]}"
}

wait_for_orbbec() {
  local deadline=$((SECONDS + DEVICE_WAIT_TIMEOUT_SEC))
  until detect_orbbec; do
    if (( SECONDS >= deadline )); then
      echo "[BOOT] Orbbec identity is ambiguous or depth data path is not SuperSpeed" >&2
      return 1
    fi
    sleep 1
  done
  if [[ -n "${ORBBEC_SERIAL_NUMBER}" && "${ORBBEC_SERIAL_NUMBER}" != "${DETECTED_ORBBEC_SERIAL}" ]]; then
    echo "[BOOT] Configured Orbbec identity does not match connected camera" >&2
    return 1
  fi
  ORBBEC_SERIAL_NUMBER="${DETECTED_ORBBEC_SERIAL}"
}

if [[ "${START_BRINGUP,,}" =~ ^(1|true|yes|on)$ ]]; then
  wait_for_path "${DOBOT_SERIAL_PORT}" "Dobot serial device"
  DOBOT_SERIAL_TARGET="$(readlink -f "${DOBOT_SERIAL_PORT}")"
  if [[ ! -c "${DOBOT_SERIAL_TARGET}" ]]; then
    echo "[BOOT] Dobot serial target is not a character device: ${DOBOT_SERIAL_TARGET}" >&2
    exit 1
  fi
fi
if [[ "${START_CAMERA,,}" =~ ^(1|true|yes|on)$ ]]; then
  wait_for_orbbec
fi

echo "[BOOT] Workspace=${DOBOT_WS_DIR} ROS=jazzy"
echo "[BOOT] Dobot=${DOBOT_SERIAL_PORT} Orbbec=${ORBBEC_SERIAL_NUMBER:-disabled}"

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
export START_CALIBRATION REQUIRE_INTEGRATED_STARTUP STARTUP_AUTO
export STARTUP_AUTO_RECALIBRATE STARTUP_AUTO_MOTION

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
  start_calibration:="${START_CALIBRATION}"
  require_integrated_startup:="${REQUIRE_INTEGRATED_STARTUP}"
  startup_auto:="${STARTUP_AUTO}"
  startup_auto_recalibrate:="${STARTUP_AUTO_RECALIBRATE}"
  startup_auto_motion:="${STARTUP_AUTO_MOTION}"
)
if [[ -n "${CAMERA_DEVICE}" ]]; then
  launch_args+=(camera_device:="${CAMERA_DEVICE}")
fi
if [[ -n "${ORBBEC_SERIAL_NUMBER}" ]]; then
  launch_args+=(orbbec_serial_number:="${ORBBEC_SERIAL_NUMBER}")
fi
if [[ -n "${CALIBRATION_CARRIER_FRAME}" ]]; then
  launch_args+=(calibration_carrier_frame:="${CALIBRATION_CARRIER_FRAME}")
fi
if [[ -n "${CALIBRATION_MOUNT_MODEL}" ]]; then
  launch_args+=(calibration_mount_model:="${CALIBRATION_MOUNT_MODEL}")
fi

stack_pid=''
shutdown_stack() {
  [[ -n "${stack_pid}" ]] || return 0
  if kill -0 "${stack_pid}" 2>/dev/null; then
    kill -TERM "${stack_pid}" 2>/dev/null || true
    local deadline=$((SECONDS + STACK_STOP_TIMEOUT_SEC))
    while kill -0 "${stack_pid}" 2>/dev/null && (( SECONDS < deadline )); do
      sleep 0.2
    done
    if kill -0 "${stack_pid}" 2>/dev/null; then
      echo "[BOOT] ROS launch did not stop within ${STACK_STOP_TIMEOUT_SEC}s; killing it" >&2
      kill -KILL "${stack_pid}" 2>/dev/null || true
    fi
  fi
  wait "${stack_pid}" 2>/dev/null || true
  stack_pid=''
}

stop_requested() {
  echo "[BOOT] Shutdown requested"
  shutdown_stack
  exit 0
}
trap stop_requested INT TERM HUP

validate_runtime_status() {
  python3 -c '
import json, sys
required = {
    "robot_connected", "robot_state_fresh", "camera_connected",
    "camera_health_fresh", "rgb_fresh", "depth_fresh", "depth_valid",
    "camera_identity_valid",
    "calibration_available", "calibration_verified", "vision_running",
    "web_running", "port_8080", "no_critical_alarm",
}
payload = json.load(sys.stdin)
runtime = payload.get("runtime", {})
missing = required.difference(runtime)
if missing:
    raise SystemExit("missing runtime fields: " + ",".join(sorted(missing)))
if payload.get("motion_mode") not in {"DRY_RUN", "REAL"}:
    raise SystemExit("invalid motion_mode")
' >/dev/null
}

echo "[BOOT] Starting the single production launch"
ros2 launch dobot_web_interface dobot_auto.launch.py "${launch_args[@]}" &
stack_pid=$!

web_verified=false
robot_verified=false
camera_verified=false
vision_verified=false
web_deadline=$((SECONDS + WEB_START_TIMEOUT_SEC))
failure_reason=''
failure_since=0
hardware_failure_latched=false

while kill -0 "${stack_pid}" 2>/dev/null; do
  sleep "${MONITOR_INTERVAL_SEC}"
  current_failure=''

  if [[ "${START_BRINGUP,,}" =~ ^(1|true|yes|on)$ ]]; then
    current_serial_target="$(readlink -f "${DOBOT_SERIAL_PORT}" 2>/dev/null || true)"
    if [[ ! -c "${current_serial_target}" || "${current_serial_target}" != "${DOBOT_SERIAL_TARGET}" ]]; then
      current_failure='Dobot serial device disappeared or re-enumerated'
      hardware_failure_latched=true
    fi
  fi

  if [[ -z "${current_failure}" && "${START_CAMERA,,}" =~ ^(1|true|yes|on)$ ]]; then
    if ! detect_orbbec || [[ "${DETECTED_ORBBEC_SERIAL:-}" != "${ORBBEC_SERIAL_NUMBER}" ]]; then
      current_failure='Orbbec identity or SuperSpeed depth path changed'
      hardware_failure_latched=true
    fi
  fi

  status_payload=''
  if [[ -z "${current_failure}" ]]; then
    status_payload="$(curl --noproxy '*' -fsS --max-time 2 \
      "http://127.0.0.1:${WEB_PORT}/api/system/status" 2>/dev/null || true)"
    if [[ -n "${status_payload}" ]] && validate_runtime_status <<<"${status_payload}"; then
      if [[ "${web_verified}" != true ]]; then
        echo "[BOOT] Web readiness API is online with the required runtime schema"
        web_verified=true
      fi
      if [[ "${status_payload}" == *'"robot_connected":true'* ]]; then
        robot_verified=true
      elif [[ "${robot_verified}" == true ]]; then
        current_failure='Robot runtime connectivity was lost'
      fi
      if [[ -z "${current_failure}" && "${START_CAMERA,,}" =~ ^(1|true|yes|on)$ ]]; then
        if [[ "${status_payload}" == *'"camera_health_fresh":true'* \
              && "${status_payload}" == *'"rgb_fresh":true'* \
              && "${status_payload}" == *'"depth_fresh":true'* \
              && "${status_payload}" == *'"depth_valid":true'* ]]; then
          camera_verified=true
        elif [[ "${camera_verified}" == true ]]; then
          current_failure='Camera health heartbeat or live RGB-D stream was lost'
        elif (( SECONDS >= web_deadline )); then
          current_failure='Camera health heartbeat and live RGB-D did not become ready before their deadline'
        fi
      fi
      if [[ -z "${current_failure}" && "${START_VISION,,}" =~ ^(1|true|yes|on)$ ]]; then
        if [[ "${status_payload}" == *'"vision_running":true'* ]]; then
          vision_verified=true
        elif [[ "${vision_verified}" == true ]]; then
          current_failure='Vision runtime status was lost'
        elif (( SECONDS >= web_deadline )); then
          current_failure='Vision runtime did not become ready before its deadline'
        fi
      fi
    elif [[ "${web_verified}" == true ]]; then
      current_failure='Web readiness API became unavailable or invalid'
    elif (( SECONDS >= web_deadline )); then
      current_failure='Web readiness API did not start before its deadline'
    fi
  fi

  # A detected USB topology loss is not recoverable in-place: ROS processes
  # may retain stale descriptors even if udev recreates the same paths. Keep
  # the grace period for safety cancellation, then restart the complete stack.
  if [[ -z "${current_failure}" && "${hardware_failure_latched}" == true ]]; then
    current_failure="${failure_reason}"
  fi

  if [[ -n "${current_failure}" ]]; then
    if [[ "${current_failure}" != "${failure_reason}" ]]; then
      failure_reason="${current_failure}"
      failure_since=${SECONDS}
      echo "[BOOT] Monitoring failure: ${failure_reason}" >&2
    elif (( SECONDS - failure_since >= MONITOR_FAILURE_GRACE_SEC )); then
      echo "[BOOT] Restarting the complete stack after persistent failure: ${failure_reason}" >&2
      shutdown_stack
      exit 1
    fi
  else
    failure_reason=''
    failure_since=0
  fi
done

launch_status=0
wait "${stack_pid}" || launch_status=$?
stack_pid=''
echo "[BOOT] Production launch exited unexpectedly with status ${launch_status}" >&2
exit 1
