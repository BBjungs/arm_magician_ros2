"""Bounded coarse-to-fine suction-pick controller.

This module deliberately has no ROS dependencies.  The web node and any ROS
action node supply the small set of callbacks needed to select targets, move
the robot, operate suction, and inspect a new camera frame.  Keeping the
state machine here makes the safety behaviour directly unit-testable and
prevents a transport detail from becoming a motion policy.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence


class PickState(str, Enum):
    """States reported by an automatic suction-pick attempt."""

    TARGET = "TARGET"
    APPROACH = "APPROACH"
    FINE_ALIGN = "FINE_ALIGN"
    DESCEND = "DESCEND"
    SUCTION_ON = "SUCTION_ON"
    LIFT = "LIFT"
    VERIFY_PICK = "VERIFY_PICK"
    DONE_OR_RETRY = "DONE_OR_RETRY"


class AutomaticPickError(RuntimeError):
    """A deliberate, safe rejection of an automatic pick."""


@dataclass(frozen=True)
class AutomaticPickConfig:
    """Limits for an automatic pick, in millimetres unless noted otherwise.

    ``max_attempts`` counts the initial try.  Every motion remains within the
    workspace/reachability callback supplied by the caller; these limits add
    the tighter bounds appropriate for visual servoing.
    """

    max_attempts: int = 2
    approach_clearance_mm: float = 30.0
    max_reacquire_distance_mm: float = 20.0
    max_fine_correction_mm: float = 8.0
    max_fine_correction_axis_mm: float = 6.0
    fine_deadband_mm: float = 0.75
    descend_step_mm: float = 5.0
    depth_minimum_mm: float = 180.0
    min_depth_valid_ratio: float = 0.60
    max_depth_stddev_mm: float = 12.0
    coarse_velocity_ratio: float = 0.25
    coarse_acceleration_ratio: float = 0.20
    fine_velocity_ratio: float = 0.12
    fine_acceleration_ratio: float = 0.10
    descend_velocity_ratio: float = 0.08
    descend_acceleration_ratio: float = 0.08

    def __post_init__(self):
        if isinstance(self.max_attempts, bool):
            raise ValueError("max_attempts must be an integer in [1, 5]")
        try:
            max_attempts = float(self.max_attempts)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_attempts must be an integer in [1, 5]") from exc
        if (
            not math.isfinite(max_attempts)
            or not max_attempts.is_integer()
            or not 1 <= int(max_attempts) <= 5
        ):
            raise ValueError("max_attempts must be in [1, 5]")
        # Callers may originate this value from JSON.  Normalize an integral
        # float/string once so the bounded ``range`` in ``execute`` is always
        # safe and deterministic.
        object.__setattr__(self, "max_attempts", int(max_attempts))
        for name in (
            "approach_clearance_mm",
            "max_reacquire_distance_mm",
            "max_fine_correction_mm",
            "max_fine_correction_axis_mm",
            "fine_deadband_mm",
            "descend_step_mm",
            "depth_minimum_mm",
            "min_depth_valid_ratio",
            "max_depth_stddev_mm",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name in (
            "coarse_velocity_ratio",
            "coarse_acceleration_ratio",
            "fine_velocity_ratio",
            "fine_acceleration_ratio",
            "descend_velocity_ratio",
            "descend_acceleration_ratio",
        ):
            value = float(getattr(self, name))
            if not 0.0 < value <= 0.5:
                raise ValueError(f"{name} must be within (0.0, 0.5]")


def bounded_xy_correction(
    correction_mm: Sequence[float],
    max_axis_mm: float,
    max_norm_mm: float,
) -> List[float]:
    """Clamp a visual correction by both axis and Euclidean limits.

    The double limit avoids a diagonal correction exceeding the physical
    motion bound after individual X/Y clipping.
    """

    if len(correction_mm) != 2:
        raise ValueError("correction_mm must contain [x, y]")
    if max_axis_mm <= 0.0 or max_norm_mm <= 0.0:
        raise ValueError("correction limits must be positive")
    try:
        x, y = (float(correction_mm[0]), float(correction_mm[1]))
    except (TypeError, ValueError) as exc:
        raise ValueError("correction_mm must be numeric") from exc
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("correction_mm must be finite")

    x = max(-float(max_axis_mm), min(float(max_axis_mm), x))
    y = max(-float(max_axis_mm), min(float(max_axis_mm), y))
    magnitude = math.hypot(x, y)
    if magnitude > float(max_norm_mm):
        scale = float(max_norm_mm) / magnitude
        x *= scale
        y *= scale
    return [round(x, 3), round(y, 3)]


def depth_is_reliable(
    target: Dict[str, Any],
    config: AutomaticPickConfig,
) -> bool:
    """Return true only for a stable depth observation at a safe distance."""

    try:
        depth = float(target.get("depth_mm"))
        ratio = float(target.get("depth_valid_ratio"))
        stddev = float(target.get("depth_stddev"))
    except (TypeError, ValueError):
        return False
    return bool(
        target.get("depth_valid") is True
        and math.isfinite(depth)
        and math.isfinite(ratio)
        and math.isfinite(stddev)
        and depth >= config.depth_minimum_mm
        and config.min_depth_valid_ratio <= ratio <= 1.0
        and 0.0 <= stddev <= config.max_depth_stddev_mm
    )


class AutomaticSuctionPickController:
    """Execute one bounded automatic suction pick through injected callbacks.

    Callbacks:

    * ``redetect_target(request)`` returns a freshly selected, base-frame
      target of the requested class.
    * ``move(pose, velocity, acceleration, label)`` performs a blocking,
      reachability-checked Cartesian move and returns a response mapping.
    * ``set_suction(enabled)`` returns a response mapping.
    * ``verify_pick(target)`` returns ``{"picked": bool, ...}`` after lift.
    * ``current_pose()`` returns fresh robot kinematics as ``[x, y, z, r]``.
    * ``validate_pose(pose)`` may raise or return false to reject a target
      before a motion command is sent.

    The controller does not infer that a failed verification is a success.
    It turns suction off and returns to the recorded safe approach pose before
    retrying, then reports a safe abort after the bounded retry budget.
    """

    def __init__(
        self,
        *,
        config: Optional[AutomaticPickConfig] = None,
        redetect_target: Callable[[Dict[str, Any]], Dict[str, Any]],
        move: Callable[[Sequence[float], float, float, str], Dict[str, Any]],
        set_suction: Callable[[bool], Dict[str, Any]],
        verify_pick: Callable[[Dict[str, Any]], Dict[str, Any]],
        current_pose: Callable[[], Optional[Sequence[float]]],
        validate_pose: Callable[[Sequence[float]], Any],
        cancel_requested: Optional[Callable[[], bool]] = None,
    ):
        self.config = config or AutomaticPickConfig()
        self._redetect_target = redetect_target
        self._move_callback = move
        self._set_suction = set_suction
        self._verify_pick = verify_pick
        self._current_pose = current_pose
        self._validate_pose = validate_pose
        self._cancel_requested = cancel_requested or (lambda: False)

    def execute(
        self,
        request: Dict[str, Any],
        initial_target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run all attempts and return a complete audit trail.

        A normal failed pick is returned as ``executed:false`` rather than an
        exception.  Transport failures, invalid transforms, cancellation, and
        out-of-bounds motion are handled identically: suction is disabled and
        the last known safe approach pose is attempted before returning.
        """

        if not isinstance(request, dict):
            raise ValueError("automatic pick request must be an object")
        requested_class = str(request.get("object_class", "") or "").strip()
        if not requested_class:
            raise ValueError("object_class is required for automatic pick")

        attempts = []
        cleanup_safe = True
        first_target = dict(initial_target) if isinstance(initial_target, dict) else None
        for attempt_number in range(1, self.config.max_attempts + 1):
            attempt = {
                "attempt": attempt_number,
                "state": PickState.TARGET.value,
                "states": [],
                "motions": [],
                "correction": None,
                "depth_mode": None,
                "verification": None,
            }
            safe_pose = None
            suction_active = False
            try:
                self._check_cancel()
                target = first_target if attempt_number == 1 and first_target else self._fresh_target(request)
                target = self._require_target(target, requested_class)
                self._record_state(attempt, PickState.TARGET, target=target)
                self._validate(target["pick_pose"])

                approach = self._approach_pose(target)
                self._validate(approach)
                safe_pose = list(approach)
                self._record_state(attempt, PickState.APPROACH, pose=approach)
                self._move(
                    attempt,
                    approach,
                    self.config.coarse_velocity_ratio,
                    self.config.coarse_acceleration_ratio,
                    "move_to_safe_approach",
                )

                # A target must be re-observed after the coarse move.  This is
                # intentionally required even when depth is unavailable.
                observed = self._require_target(
                    self._fresh_target(request, reference=target),
                    requested_class,
                )
                self._ensure_same_target(target, observed)
                target = observed

                self._record_state(attempt, PickState.FINE_ALIGN, target=target)
                fine_pose, correction, depth_mode = self._fine_pose(target, approach)
                attempt["correction"] = correction
                attempt["depth_mode"] = depth_mode
                if correction != [0.0, 0.0]:
                    self._validate(fine_pose)
                    self._move(
                        attempt,
                        fine_pose,
                        self.config.fine_velocity_ratio,
                        self.config.fine_acceleration_ratio,
                        "bounded_fine_xy_correction",
                    )
                else:
                    fine_pose = self._fresh_current_pose(fine_pose[3])

                # Lift vertically at the corrected X/Y rather than traversing
                # sideways near the object to the original coarse approach.
                safe_pose = [
                    fine_pose[0],
                    fine_pose[1],
                    approach[2],
                    fine_pose[3],
                ]
                self._validate(safe_pose)

                self._record_state(attempt, PickState.DESCEND, pose=fine_pose)
                for descend_pose in self._descent_poses(fine_pose, target):
                    self._validate(descend_pose)
                    self._move(
                        attempt,
                        descend_pose,
                        self.config.descend_velocity_ratio,
                        self.config.descend_acceleration_ratio,
                        "slow_descend",
                    )

                self._record_state(attempt, PickState.SUCTION_ON)
                # Treat a submitted tool command as potentially active until
                # cleanup proves otherwise; a lost response must not skip the
                # suction-off safety command.
                suction_active = True
                tool_response = self._set_suction(True)
                if tool_response.get("success") is False:
                    raise AutomaticPickError(
                        tool_response.get("message", "suction-on command failed")
                    )

                self._record_state(attempt, PickState.LIFT, pose=safe_pose)
                self._move(
                    attempt,
                    safe_pose,
                    self.config.fine_velocity_ratio,
                    self.config.fine_acceleration_ratio,
                    "lift_to_safe_approach",
                )

                self._record_state(attempt, PickState.VERIFY_PICK)
                verification = dict(self._verify_pick(target) or {})
                attempt["verification"] = verification
                if verification.get("picked") is True:
                    self._record_state(attempt, PickState.DONE_OR_RETRY, result="picked")
                    attempts.append(attempt)
                    return {
                        "accepted": True,
                        "executed": True,
                        "picked": True,
                        "state": PickState.DONE_OR_RETRY.value,
                        "attempts": attempts,
                        "attempt_count": attempt_number,
                        "config": asdict(self.config),
                    }
                raise AutomaticPickError(
                    verification.get("reason", "pick verification did not confirm suction")
                )
            except Exception as exc:  # Cleanup is required for all failure paths.
                cleanup = self._recover(safe_pose, suction_active)
                attempt["error"] = str(exc)
                attempt["cleanup"] = cleanup
                cleanup_safe = self._cleanup_succeeded(cleanup) and cleanup_safe
                self._record_state(
                    attempt,
                    PickState.DONE_OR_RETRY,
                    result="retry" if attempt_number < self.config.max_attempts else "abort",
                )
                attempts.append(attempt)
                if self._is_canceled(exc):
                    return self._aborted_result(
                        attempts,
                        "automatic pick canceled",
                        cleanup_safe,
                    )

        return self._aborted_result(
            attempts,
            "pick verification/retry limit reached; suction disabled at safe approach",
            cleanup_safe,
        )

    def _fresh_target(
        self,
        request: Dict[str, Any],
        reference: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._check_cancel()
        fresh_request = dict(request)
        # This private field is intentionally carried in the callback payload
        # rather than changing the public callback signature.  Existing
        # transports can keep accepting a single request object, while a
        # capable selector can bind the new observation to the coarse target.
        if reference is not None:
            fresh_request["_automatic_reference_target"] = dict(reference)
        target = self._redetect_target(fresh_request)
        if not isinstance(target, dict):
            raise AutomaticPickError("re-detection did not return a target object")
        return target

    def _require_target(self, target: Dict[str, Any], requested_class: str) -> Dict[str, Any]:
        if not target.get("selected"):
            raise AutomaticPickError(target.get("reason", "target was not selected"))
        actual_class = str(target.get("class_name", "") or "")
        if requested_class not in ("all", "*") and actual_class != requested_class:
            raise AutomaticPickError(
                f"re-detected class '{actual_class}' does not match '{requested_class}'"
            )
        pose = self._pose(target.get("pick_pose"), "pick_pose")
        normalized = dict(target)
        normalized["pick_pose"] = pose
        normalized["robot_xy"] = pose[:2]
        return normalized

    def _approach_pose(self, target: Dict[str, Any]) -> List[float]:
        pick = self._pose(target["pick_pose"], "pick_pose")
        try:
            safe_z = float(target.get("safe_z"))
        except (TypeError, ValueError):
            safe_z = pick[2] + self.config.approach_clearance_mm
        safe_z = max(safe_z, pick[2] + self.config.approach_clearance_mm)
        if not math.isfinite(safe_z):
            raise AutomaticPickError("safe_z must be finite")
        return [pick[0], pick[1], safe_z, pick[3]]

    def _fine_pose(
        self,
        target: Dict[str, Any],
        approach_pose: Sequence[float],
    ) -> tuple[List[float], List[float], str]:
        current = self._fresh_current_pose(float(approach_pose[3]))
        target_pose = self._pose(target["pick_pose"], "pick_pose")

        if depth_is_reliable(target, self.config):
            raw = [target_pose[0] - current[0], target_pose[1] - current[1]]
            mode = "depth_base_transform"
        else:
            # At close range/unreliable depth, never manufacture a Z estimate.
            # Current TCP coordinates are the kinematic reference; the updated
            # 2-D detection contributes only a lateral error from the coarse
            # base-frame target.
            visual = target.get("visual_xy_correction_mm")
            if visual is None:
                visual = [
                    target_pose[0] - float(approach_pose[0]),
                    target_pose[1] - float(approach_pose[1]),
                ]
            raw = self._xy(visual, "visual_xy_correction_mm")
            mode = "robot_kinematics_2d_visual"

        raw_magnitude = math.hypot(raw[0], raw[1])
        if raw_magnitude > self.config.max_fine_correction_mm:
            raise AutomaticPickError(
                "fine correction exceeds bounded limit "
                f"({raw_magnitude:.3f} mm > {self.config.max_fine_correction_mm:.3f} mm)"
            )
        correction = bounded_xy_correction(
            raw,
            self.config.max_fine_correction_axis_mm,
            self.config.max_fine_correction_mm,
        )
        if math.hypot(*correction) < self.config.fine_deadband_mm:
            correction = [0.0, 0.0]
        return [
            current[0] + correction[0],
            current[1] + correction[1],
            current[2],
            current[3],
        ], correction, mode

    def _descent_poses(
        self,
        fine_pose: Sequence[float],
        target: Dict[str, Any],
    ) -> List[List[float]]:
        current = self._fresh_current_pose(float(fine_pose[3]))
        target_pose = self._pose(target["pick_pose"], "pick_pose")
        if target_pose[2] >= current[2]:
            raise AutomaticPickError("pick_z must be below the current approach pose")
        z_values = []
        z = current[2]
        while z - target_pose[2] > self.config.descend_step_mm:
            z -= self.config.descend_step_mm
            z_values.append(z)
        z_values.append(target_pose[2])
        return [[fine_pose[0], fine_pose[1], z, fine_pose[3]] for z in z_values]

    def _ensure_same_target(
        self,
        coarse_target: Dict[str, Any],
        observed_target: Dict[str, Any],
    ) -> None:
        if coarse_target.get("class_name") != observed_target.get("class_name"):
            raise AutomaticPickError("target class changed after approach")
        first = self._pose(coarse_target["pick_pose"], "pick_pose")
        second = self._pose(observed_target["pick_pose"], "pick_pose")
        distance = math.hypot(first[0] - second[0], first[1] - second[1])
        if distance > self.config.max_reacquire_distance_mm:
            raise AutomaticPickError(
                "re-detected target moved too far after approach "
                f"({distance:.3f} mm > {self.config.max_reacquire_distance_mm:.3f} mm)"
            )

    def _move(
        self,
        attempt: Dict[str, Any],
        pose: Sequence[float],
        velocity: float,
        acceleration: float,
        label: str,
    ) -> None:
        self._check_cancel()
        response = self._move_callback(pose, velocity, acceleration, label) or {}
        attempt["motions"].append(
            {
                "label": label,
                "pose": [round(float(value), 3) for value in pose],
                "velocity_ratio": velocity,
                "acceleration_ratio": acceleration,
                "response": dict(response),
            }
        )
        if response.get("accepted") is False or response.get("success") is False:
            raise AutomaticPickError(response.get("message", f"{label} was rejected"))
        self._check_cancel()

    def _recover(self, safe_pose: Optional[Sequence[float]], suction_active: bool) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "suction_off": None,
            "safe_lift": None,
            "suction_off_required": suction_active,
            "safe_lift_required": safe_pose is not None,
        }
        # Lift before releasing an object whenever we have a validated lift
        # pose.  If a move failed, the endpoint may be unknown, but the
        # controller still asks the lower layer to validate the recovery move.
        if safe_pose is not None:
            try:
                self._validate(safe_pose)
                result["safe_lift"] = self._move_callback(
                    safe_pose,
                    self.config.fine_velocity_ratio,
                    self.config.fine_acceleration_ratio,
                    "recovery_lift_to_safe_approach",
                )
            except Exception as exc:
                result["safe_lift"] = {"error": str(exc)}
        if suction_active:
            try:
                result["suction_off"] = self._set_suction(False)
            except Exception as exc:
                result["suction_off"] = {"error": str(exc)}
        return result

    @staticmethod
    def _cleanup_succeeded(cleanup: Dict[str, Any]) -> bool:
        for key, required_key in (
            ("safe_lift", "safe_lift_required"),
            ("suction_off", "suction_off_required"),
        ):
            if not cleanup.get(required_key):
                continue
            response = cleanup.get(key)
            if not isinstance(response, dict):
                return False
            if "error" in response:
                return False
            if response.get("accepted") is False or response.get("success") is False:
                return False
        return True

    def _validate(self, pose: Sequence[float]) -> None:
        self._pose(pose, "pose")
        decision = self._validate_pose(pose)
        if decision is False:
            raise AutomaticPickError("pose failed reachability/workspace validation")
        if isinstance(decision, dict) and decision.get("allowed") is False:
            raise AutomaticPickError(decision.get("reason", "pose validation failed"))
        if hasattr(decision, "allowed") and not decision.allowed:
            raise AutomaticPickError(getattr(decision, "reason", "pose validation failed"))

    def _fresh_current_pose(self, fallback_r: float) -> List[float]:
        pose = self._current_pose()
        if pose is None:
            raise AutomaticPickError("fresh robot kinematics are required for fine alignment")
        result = self._pose(pose, "current_pose")
        if not math.isfinite(result[3]):
            result[3] = fallback_r
        return result

    def _check_cancel(self) -> None:
        if self._cancel_requested():
            raise AutomaticPickError("automatic pick canceled")

    @staticmethod
    def _is_canceled(exc: Exception) -> bool:
        return "canceled" in str(exc).lower() or "cancelled" in str(exc).lower()

    @staticmethod
    def _record_state(attempt: Dict[str, Any], state: PickState, **details: Any) -> None:
        attempt["state"] = state.value
        entry = {"state": state.value}
        entry.update(details)
        attempt["states"].append(entry)

    @staticmethod
    def _pose(value: Any, name: str) -> List[float]:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise AutomaticPickError(f"{name} must be [x, y, z, r]")
        try:
            result = [float(item) for item in value]
        except (TypeError, ValueError) as exc:
            raise AutomaticPickError(f"{name} must contain numeric values") from exc
        if not all(math.isfinite(item) for item in result):
            raise AutomaticPickError(f"{name} must contain finite values")
        return result

    @staticmethod
    def _xy(value: Any, name: str) -> List[float]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise AutomaticPickError(f"{name} must be [x, y]")
        try:
            result = [float(value[0]), float(value[1])]
        except (TypeError, ValueError) as exc:
            raise AutomaticPickError(f"{name} must contain numeric values") from exc
        if not all(math.isfinite(item) for item in result):
            raise AutomaticPickError(f"{name} must contain finite values")
        return result

    def _aborted_result(
        self,
        attempts: List[Dict[str, Any]],
        reason: str,
        cleanup_safe: bool,
    ) -> Dict[str, Any]:
        if not cleanup_safe:
            reason = f"{reason}; recovery command failed—operator intervention required"
        return {
            "accepted": True,
            "executed": False,
            "picked": False,
            "aborted_safely": cleanup_safe,
            "state": PickState.DONE_OR_RETRY.value,
            "reason": reason,
            "attempts": attempts,
            "attempt_count": len(attempts),
            "config": asdict(self.config),
        }
