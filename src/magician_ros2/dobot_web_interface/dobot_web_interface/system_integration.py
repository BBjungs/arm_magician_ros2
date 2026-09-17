"""Fail-closed startup and readiness policy for the complete cell.

The web node owns the operator-facing state, but it must not invent a second
set of safety rules for the robot, camera, vision pipeline, and calibration
node.  This module is deliberately ROS-free so that the ordering policy can be
tested without hardware.  ROS adapters only feed it current snapshots and
perform the explicitly returned action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Dict, Mapping, Optional


class StartupState(str, Enum):
    """The only valid ordering for admitting automatic workcell motion."""

    WAITING_FOR_ROBOT = "WAITING_FOR_ROBOT"
    WAITING_FOR_CAMERA = "WAITING_FOR_CAMERA"
    WAITING_FOR_VISION = "WAITING_FOR_VISION"
    VERIFYING_CALIBRATION = "VERIFYING_CALIBRATION"
    WAITING_FOR_HOME = "WAITING_FOR_HOME"
    MOVING_TO_OBSERVATION = "MOVING_TO_OBSERVATION"
    WAITING_FOR_MOTION_ENABLE = "WAITING_FOR_MOTION_ENABLE"
    READY = "READY"
    FAULT = "FAULT"
    STOPPED = "STOPPED"


STARTUP_ORDER = (
    "robot",
    "camera",
    "vision",
    "calibration",
    "home",
    "observation",
)


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite_nonnegative(value: Any, limit: float) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and 0.0 <= number <= limit


def is_pose(value: Any) -> bool:
    """Return true only for a finite Cartesian Dobot pose in millimetres."""

    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    try:
        return all(math.isfinite(float(item)) for item in value)
    except (TypeError, ValueError):
        return False


def calibration_is_ready(payload: Any, *, max_age_sec: float = 2.0) -> bool:
    """Accept only a fresh live calibration PASS, never a saved report alone."""

    status = _mapping(payload)
    return bool(
        status.get("architecture") == "markerless_hand_eye"
        and status.get("ready") is True
        and status.get("state") == "READY"
        and status.get("result") == "PASS"
        and status.get("bundle_loaded") is True
        and status.get("geometry_verified") is True
        and status.get("verification_status") == "PASS"
        and status.get("reload_verification_status") == "PASS"
        and not status.get("blockers")
        and _finite_nonnegative(status.get("age_sec"), max_age_sec)
    )


def aggregate_system_readiness(
    *,
    status: Any,
    vision: Any,
    calibration: Any,
    homed: bool,
    at_observation: bool,
    require_calibration: bool = True,
    fault: str = "",
    camera_health: Any = None,
    real_motion_enabled: bool = True,
) -> Dict[str, Any]:
    """Produce one compact, fail-closed readiness result.

    ``status`` is the web node's robot/camera snapshot, ``vision`` is the
    detector's health message, and ``calibration`` is the live
    ``/calibration/status`` message with a locally added ``age_sec``.  The
    response intentionally contains component booleans and stable blocker
    codes, not raw device or pose data, so it is safe to expose to the operator
    page as well as to motion admission.
    """

    status = _mapping(status)
    ros = _mapping(status.get("ros"))
    camera = _mapping(status.get("camera"))
    motion = _mapping(status.get("motion"))
    vision = _mapping(vision)
    calibration = _mapping(calibration)
    camera_health = _mapping(camera_health)

    robot_connected = bool(
        ros.get("ptp_action_ready")
        and ros.get("homing_ready")
        and ros.get("suction_ready")
    )
    robot_state_fresh = bool(
        _finite_nonnegative(motion.get("joints_age_sec"), 1.0)
        and _finite_nonnegative(motion.get("current_tcp_pose_age_sec"), 1.0)
    )
    no_critical_alarm = bool(ros.get("alarm_state_fresh") and ros.get("no_critical_alarm"))
    robot_ok = bool(robot_connected and robot_state_fresh and no_critical_alarm)
    camera_identity_valid = bool(
        _mapping(camera_health.get("usb")).get("identity_valid")
    )
    camera_health_fresh = _finite_nonnegative(camera_health.get("age_sec"), 2.0)
    camera_transport_ok = bool(
        camera_health.get("ready")
        and camera_health_fresh
    )
    camera_ok = bool(
        camera.get("has_frame")
        and _finite_nonnegative(camera.get("frame_age_sec"), 2.0)
        and camera_transport_ok
    )
    vision_ok = bool(
        vision.get("ok")
        and vision.get("source_ok", vision.get("rgb_ok", False))
        and vision.get("rgb_ok", vision.get("source_ok", False))
        and vision.get("depth_stream_ok", vision.get("depth_ok", False))
        and vision.get("depth_data_valid", vision.get("depth_ok", False))
        and vision.get("sync_ok", False)
    )
    calibration_ok = (
        calibration_is_ready(calibration) if require_calibration else True
    )
    motion_idle = not bool(
        motion.get("active_goal") or motion.get("vision_sequence_active")
    )
    components = {
        "robot": robot_ok,
        "camera": camera_ok,
        "vision": vision_ok,
        "calibration": calibration_ok,
        "home": bool(homed),
        "observation": bool(at_observation),
        "motion_idle": motion_idle,
        "real_motion": bool(real_motion_enabled),
    }
    blockers = [name.upper() + "_NOT_READY" for name, ok in components.items() if not ok]
    if fault:
        blockers.insert(0, "FAULT: " + str(fault))
    runtime = {
        "robot_connected": robot_connected,
        "robot_state_fresh": robot_state_fresh,
        "camera_connected": camera_ok,
        "camera_health_fresh": camera_health_fresh,
        "rgb_fresh": bool(camera.get("has_frame") and _finite_nonnegative(camera.get("frame_age_sec"), 2.0)),
        "depth_fresh": bool(vision.get("depth_stream_ok", vision.get("depth_ok", False))),
        "depth_valid": bool(vision.get("depth_data_valid", vision.get("depth_ok", False))),
        "camera_identity_valid": camera_identity_valid,
        "calibration_available": bool(calibration.get("available") is True),
        "calibration_verified": calibration_ok,
        "vision_running": vision_ok,
        "web_running": True,
        "port_8080": True,
        "no_critical_alarm": no_critical_alarm,
        "real_motion_enabled": bool(real_motion_enabled),
    }
    return {
        "ready": not blockers,
        "components": components,
        "blockers": blockers,
        "calibration_required": bool(require_calibration),
        "runtime": runtime,
    }


@dataclass
class StartupDecision:
    """A transition plus, at most, one idempotent adapter action."""

    state: StartupState
    action: Optional[str] = None
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "action": self.action,
            "reason": self.reason,
        }


class StartupStateMachine:
    """Advance through startup in fixed order and latch unsafe failures.

    The state machine never performs I/O.  ``verify_calibration``, ``home``,
    and ``move_observation`` are actions for a ROS adapter to dispatch once.
    A dispatched action is remembered until either its condition becomes true,
    an explicit failure is reported, or ``reset`` is called.
    """

    def __init__(
        self,
        *,
        auto_home: bool = False,
        auto_observation: bool = False,
    ):
        self.auto_home = bool(auto_home)
        self.auto_observation = bool(auto_observation)
        self.state = StartupState.WAITING_FOR_ROBOT
        self.reason = "waiting for robot services"
        self._dispatched = set()
        self._fault = ""
        self._stopped = False

    @property
    def fault(self) -> str:
        return self._fault

    def reset(self) -> None:
        self.state = StartupState.WAITING_FOR_ROBOT
        self.reason = "startup reset"
        self._dispatched.clear()
        self._fault = ""
        self._stopped = False

    def stop(self, reason: str = "stop requested") -> None:
        self._stopped = True
        self.state = StartupState.STOPPED
        self.reason = str(reason)

    def fail(self, reason: str) -> None:
        self._fault = str(reason) or "startup fault"
        self.state = StartupState.FAULT
        self.reason = self._fault

    def mark_dispatched(self, action: str) -> None:
        self._dispatched.add(str(action))

    def advance(self, readiness: Mapping[str, Any]) -> StartupDecision:
        """Return the next legal action for a component readiness mapping."""

        if self._fault:
            self.state = StartupState.FAULT
            return StartupDecision(self.state, reason=self._fault)
        if self._stopped:
            self.state = StartupState.STOPPED
            return StartupDecision(self.state, reason=self.reason)

        components = _mapping(readiness.get("components"))
        if not components.get("robot", False):
            self.state = StartupState.WAITING_FOR_ROBOT
            self.reason = "waiting for robot services"
            return StartupDecision(self.state, reason=self.reason)
        if not components.get("camera", False):
            self.state = StartupState.WAITING_FOR_CAMERA
            self.reason = "waiting for live camera frame"
            return StartupDecision(self.state, reason=self.reason)
        if not components.get("vision", False):
            self.state = StartupState.WAITING_FOR_VISION
            self.reason = "waiting for valid synchronized RGB-D vision"
            return StartupDecision(self.state, reason=self.reason)
        if not components.get("calibration", False):
            self.state = StartupState.VERIFYING_CALIBRATION
            self.reason = "waiting for live calibration verification"
            action = (
                "verify_calibration"
                if "verify_calibration" not in self._dispatched
                else None
            )
            return StartupDecision(self.state, action, self.reason)
        if not components.get("home", False):
            self.state = StartupState.WAITING_FOR_HOME
            self.reason = "robot must complete HOME"
            action = "home" if self.auto_home and "home" not in self._dispatched else None
            return StartupDecision(self.state, action, self.reason)
        if not components.get("observation", False):
            self.state = StartupState.MOVING_TO_OBSERVATION
            self.reason = "robot must reach observation pose"
            action = (
                "move_observation"
                if self.auto_observation and "move_observation" not in self._dispatched
                else None
            )
            return StartupDecision(self.state, action, self.reason)
        if not components.get("real_motion", False):
            self.state = StartupState.WAITING_FOR_MOTION_ENABLE
            self.reason = "real motion remains explicitly disabled"
            return StartupDecision(self.state, reason=self.reason)
        if not components.get("motion_idle", True):
            # A completed startup is not revoked merely because a permitted
            # job is running, but we never advertise the system as idle-ready.
            self.state = StartupState.READY
            self.reason = "system ready; motion in progress"
            return StartupDecision(self.state, reason=self.reason)
        self.state = StartupState.READY
        self.reason = "all startup checks passed"
        return StartupDecision(self.state, reason=self.reason)
