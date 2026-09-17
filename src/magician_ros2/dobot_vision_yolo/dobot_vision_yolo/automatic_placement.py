"""Fail-closed RGB-D assisted suction-placement controller.

The controller is independent of ROS transport so that its safety behaviour is
unit-testable.  It never interprets a missing placement observation as an empty
zone: an inspected zone must explicitly report a reliable, unoccupied surface
before the tool is allowed to descend.
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


class PlacementState(str, Enum):
    """States reported by one automatic placement."""

    ZONE = "ZONE"
    APPROACH = "APPROACH"
    INSPECT = "INSPECT"
    FINE_ALIGN = "FINE_ALIGN"
    DESCEND = "DESCEND"
    SUCTION_OFF = "SUCTION_OFF"
    LIFT = "LIFT"
    VERIFY_RELEASE = "VERIFY_RELEASE"
    DONE_OR_ABORT = "DONE_OR_ABORT"


class AutomaticPlacementError(RuntimeError):
    """A deliberate fail-closed rejection of an automatic placement."""


@dataclass(frozen=True)
class AutomaticPlacementConfig:
    """Hard limits for visual placement, in millimetres unless noted."""

    approach_clearance_mm: float = 30.0
    release_clearance_mm: float = 2.0
    max_surface_height_delta_mm: float = 12.0
    max_surface_stddev_mm: float = 6.0
    min_surface_valid_ratio: float = 0.70
    max_fine_correction_mm: float = 8.0
    max_fine_correction_axis_mm: float = 6.0
    fine_deadband_mm: float = 0.75
    descend_step_mm: float = 5.0
    coarse_velocity_ratio: float = 0.20
    coarse_acceleration_ratio: float = 0.16
    fine_velocity_ratio: float = 0.10
    fine_acceleration_ratio: float = 0.08
    descend_velocity_ratio: float = 0.06
    descend_acceleration_ratio: float = 0.06

    def __post_init__(self):
        for name in (
            "approach_clearance_mm",
            "release_clearance_mm",
            "max_surface_height_delta_mm",
            "max_surface_stddev_mm",
            "min_surface_valid_ratio",
            "max_fine_correction_mm",
            "max_fine_correction_axis_mm",
            "fine_deadband_mm",
            "descend_step_mm",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not 0.0 < float(self.min_surface_valid_ratio) <= 1.0:
            raise ValueError("min_surface_valid_ratio must be within (0.0, 1.0]")
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


def bounded_placement_xy(
    correction_mm: Sequence[float],
    max_axis_mm: float,
    max_norm_mm: float,
) -> List[float]:
    """Clamp a visual X/Y correction by axis and Euclidean limits."""

    if not isinstance(correction_mm, (list, tuple)) or len(correction_mm) != 2:
        raise ValueError("placement correction must be [x, y]")
    try:
        x, y = float(correction_mm[0]), float(correction_mm[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("placement correction must be numeric") from exc
    if not all(math.isfinite(value) for value in (x, y)):
        raise ValueError("placement correction must be finite")
    if max_axis_mm <= 0.0 or max_norm_mm <= 0.0:
        raise ValueError("placement correction bounds must be positive")

    x = max(-float(max_axis_mm), min(float(max_axis_mm), x))
    y = max(-float(max_axis_mm), min(float(max_axis_mm), y))
    magnitude = math.hypot(x, y)
    if magnitude > float(max_norm_mm):
        scale = float(max_norm_mm) / magnitude
        x *= scale
        y *= scale
    return [round(x, 3), round(y, 3)]


def surface_is_reliable(
    inspection: Dict[str, Any],
    config: AutomaticPlacementConfig,
) -> bool:
    """Require an explicit, stable RGB-D surface estimate."""

    try:
        height = float(inspection.get("surface_height_mm"))
        ratio = float(inspection.get("surface_valid_ratio"))
        stddev = float(inspection.get("surface_stddev_mm"))
    except (TypeError, ValueError):
        return False
    return bool(
        inspection.get("surface_valid") is True
        and math.isfinite(height)
        and math.isfinite(ratio)
        and math.isfinite(stddev)
        and config.min_surface_valid_ratio <= ratio <= 1.0
        and 0.0 <= stddev <= config.max_surface_stddev_mm
    )


class AutomaticSuctionPlacementController:
    """Place a held object only after a fresh, free-zone RGB-D inspection.

    ``resolve_zone(place_id)`` returns a nominal base-frame zone mapping with
    ``pose``/``nominal_pose`` and optional ``zone_id``/``safe_z``.  Every
    ``inspect_zone`` call must return a *fresh* observation mapping with at
    least ``occupied``, ``occupancy_valid``, and the surface fields accepted by
    :func:`surface_is_reliable`.  Missing or malformed data fails closed.
    """

    def __init__(
        self,
        *,
        config: Optional[AutomaticPlacementConfig] = None,
        resolve_zone: Callable[[str], Dict[str, Any]],
        inspect_zone: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
        move: Callable[[Sequence[float], float, float, str], Dict[str, Any]],
        set_suction: Callable[[bool], Dict[str, Any]],
        verify_release: Callable[[Dict[str, Any]], Dict[str, Any]],
        current_pose: Callable[[], Optional[Sequence[float]]],
        validate_pose: Callable[[Sequence[float]], Any],
        cancel_requested: Optional[Callable[[], bool]] = None,
    ):
        self.config = config or AutomaticPlacementConfig()
        self._resolve_zone = resolve_zone
        self._inspect_zone = inspect_zone
        self._move_callback = move
        self._set_suction = set_suction
        self._verify_release = verify_release
        self._current_pose = current_pose
        self._validate_pose = validate_pose
        self._cancel_requested = cancel_requested or (lambda: False)

    def execute(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one placement and return its complete safety audit."""

        if not isinstance(request, dict):
            raise ValueError("automatic placement request must be an object")
        place_id = str(
            request.get("place_id", request.get("zone_id", request.get("zone", "")))
            or ""
        ).strip()
        if not place_id:
            raise ValueError("place_id is required for automatic placement")

        attempt: Dict[str, Any] = {
            "state": PlacementState.ZONE.value,
            "states": [],
            "motions": [],
            "zone": None,
            "inspection": None,
            "correction": None,
            "verification": None,
        }
        return_pose = None
        safe_pose = None
        suction_off_commanded = False
        try:
            self._check_cancel()
            # The pickup controller leaves the held object at a safe pose.
            # Preserve it so a failed pre-release placement can retreat while
            # suction remains enabled.
            return_pose = self._fresh_current_pose(0.0)
            zone = self._require_zone(self._resolve_zone(place_id), place_id)
            nominal_pose = self._pose(
                zone.get("nominal_pose", zone.get("pose")), "zone pose"
            )
            self._validate(nominal_pose)
            self._record_state(attempt, PlacementState.ZONE, zone=zone)
            attempt["zone"] = zone

            approach = self._approach_pose(zone, nominal_pose)
            self._validate(approach)
            safe_pose = list(approach)
            self._record_state(attempt, PlacementState.APPROACH, pose=approach)
            self._move(
                attempt,
                approach,
                self.config.coarse_velocity_ratio,
                self.config.coarse_acceleration_ratio,
                "move_above_selected_zone",
            )

            self._record_state(attempt, PlacementState.INSPECT)
            inspection = self._require_inspection(
                self._inspect_zone(zone, dict(request)), nominal_pose
            )
            attempt["inspection"] = inspection
            if inspection["occupied"]:
                raise AutomaticPlacementError(
                    inspection.get("reason", "placement zone is occupied")
                )

            self._record_state(attempt, PlacementState.FINE_ALIGN, inspection=inspection)
            fine_pose, correction = self._fine_pose(inspection, approach)
            attempt["correction"] = correction
            if correction != [0.0, 0.0]:
                self._validate(fine_pose)
                self._move(
                    attempt,
                    fine_pose,
                    self.config.fine_velocity_ratio,
                    self.config.fine_acceleration_ratio,
                    "bounded_fine_placement_xy",
                )
            else:
                fine_pose = self._fresh_current_pose(fine_pose[3])

            safe_pose = [fine_pose[0], fine_pose[1], approach[2], fine_pose[3]]
            self._validate(safe_pose)
            release_z = self._release_z(inspection, nominal_pose, fine_pose)
            self._record_state(
                attempt,
                PlacementState.DESCEND,
                pose=[fine_pose[0], fine_pose[1], release_z, fine_pose[3]],
            )
            for descend_pose in self._descent_poses(fine_pose, release_z):
                self._validate(descend_pose)
                self._move(
                    attempt,
                    descend_pose,
                    self.config.descend_velocity_ratio,
                    self.config.descend_acceleration_ratio,
                    "slow_place_descend",
                )

            self._record_state(attempt, PlacementState.SUCTION_OFF)
            # A lost tool response may still have released the part.  Never
            # re-enable suction during recovery once this command was issued.
            suction_off_commanded = True
            response = self._set_suction(False) or {}
            if response.get("success") is False or response.get("accepted") is False:
                raise AutomaticPlacementError(
                    response.get("message", "suction-off command failed")
                )

            self._record_state(attempt, PlacementState.LIFT, pose=safe_pose)
            self._move(
                attempt,
                safe_pose,
                self.config.fine_velocity_ratio,
                self.config.fine_acceleration_ratio,
                "lift_from_placement",
            )

            self._record_state(attempt, PlacementState.VERIFY_RELEASE)
            verification = dict(self._verify_release(zone) or {})
            attempt["verification"] = verification
            if verification.get("released") is not True:
                raise AutomaticPlacementError(
                    verification.get("reason", "release was not verified")
                )
            self._record_state(attempt, PlacementState.DONE_OR_ABORT, result="placed")
            return {
                "accepted": True,
                "executed": True,
                "placed": True,
                "released": True,
                "aborted_safely": False,
                "state": PlacementState.DONE_OR_ABORT.value,
                "attempt": attempt,
                "config": asdict(self.config),
            }
        except Exception as exc:
            cleanup = self._recover(safe_pose, return_pose, suction_off_commanded)
            attempt["error"] = str(exc)
            attempt["cleanup"] = cleanup
            self._record_state(attempt, PlacementState.DONE_OR_ABORT, result="abort")
            cleanup_safe = self._cleanup_succeeded(cleanup)
            reason = str(exc)
            if not cleanup_safe:
                reason = f"{reason}; recovery command failed—operator intervention required"
            return {
                "accepted": True,
                "executed": False,
                "placed": False,
                "released": False,
                "suction_retained": not suction_off_commanded,
                "aborted_safely": cleanup_safe,
                "state": PlacementState.DONE_OR_ABORT.value,
                "reason": reason,
                "attempt": attempt,
                "config": asdict(self.config),
            }

    def _require_zone(self, zone: Any, requested_id: str) -> Dict[str, Any]:
        if not isinstance(zone, dict):
            raise AutomaticPlacementError("selected placement zone is unavailable")
        result = dict(zone)
        result["zone_id"] = str(result.get("zone_id", requested_id) or requested_id)
        result["place_id"] = requested_id
        result["pose"] = self._pose(
            result.get("nominal_pose", result.get("pose")), "zone pose"
        )
        return result

    def _approach_pose(
        self,
        zone: Dict[str, Any],
        nominal_pose: Sequence[float],
    ) -> List[float]:
        try:
            safe_z = float(zone.get("safe_z"))
        except (TypeError, ValueError):
            safe_z = nominal_pose[2] + self.config.approach_clearance_mm
        safe_z = max(safe_z, nominal_pose[2] + self.config.approach_clearance_mm)
        if not math.isfinite(safe_z):
            raise AutomaticPlacementError("zone safe_z must be finite")
        return [nominal_pose[0], nominal_pose[1], safe_z, nominal_pose[3]]

    def _require_inspection(
        self,
        observation: Any,
        nominal_pose: Sequence[float],
    ) -> Dict[str, Any]:
        if not isinstance(observation, dict):
            raise AutomaticPlacementError("placement inspection did not return an object")
        result = dict(observation)
        if result.get("fresh") is not True:
            raise AutomaticPlacementError("placement inspection is not fresh")
        if result.get("occupancy_valid") is not True:
            raise AutomaticPlacementError(
                result.get("reason", "placement occupancy is unavailable")
            )
        if not isinstance(result.get("occupied"), bool):
            raise AutomaticPlacementError("placement occupancy must be explicit")
        # Occupancy is the first safety decision.  It is intentionally enough
        # to reject a zone on its own; a blocked zone need not also provide a
        # surface estimate before the controller can refuse to descend.
        if result["occupied"]:
            return result
        if not surface_is_reliable(result, self.config):
            raise AutomaticPlacementError(
                result.get("reason", "placement surface height is unreliable")
            )
        surface_height = float(result["surface_height_mm"])
        if abs(surface_height - nominal_pose[2]) > self.config.max_surface_height_delta_mm:
            raise AutomaticPlacementError(
                "placement surface differs too far from nominal zone height"
            )
        if result.get("alignment_valid") is False:
            raise AutomaticPlacementError(
                result.get("reason", "placement alignment is unavailable")
            )
        return result

    def _fine_pose(
        self,
        inspection: Dict[str, Any],
        approach_pose: Sequence[float],
    ) -> tuple[List[float], List[float]]:
        current = self._fresh_current_pose(float(approach_pose[3]))
        raw = inspection.get(
            "fine_xy_correction_mm",
            inspection.get("placement_xy_correction_mm", [0.0, 0.0]),
        )
        correction = self._xy(raw, "fine_xy_correction_mm")
        magnitude = math.hypot(correction[0], correction[1])
        if magnitude > self.config.max_fine_correction_mm:
            raise AutomaticPlacementError(
                "fine placement correction exceeds bounded limit "
                f"({magnitude:.3f} mm > {self.config.max_fine_correction_mm:.3f} mm)"
            )
        correction = bounded_placement_xy(
            correction,
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
        ], correction

    def _release_z(
        self,
        inspection: Dict[str, Any],
        nominal_pose: Sequence[float],
        fine_pose: Sequence[float],
    ) -> float:
        surface_z = float(inspection["surface_height_mm"])
        release_z = surface_z + self.config.release_clearance_mm
        if not math.isfinite(release_z) or release_z >= fine_pose[2]:
            raise AutomaticPlacementError("placement release height must be below approach")
        if abs(surface_z - nominal_pose[2]) > self.config.max_surface_height_delta_mm:
            raise AutomaticPlacementError("placement surface height is outside allowed delta")
        return release_z

    def _descent_poses(
        self,
        fine_pose: Sequence[float],
        release_z: float,
    ) -> List[List[float]]:
        current = self._fresh_current_pose(float(fine_pose[3]))
        if release_z >= current[2]:
            raise AutomaticPlacementError("placement release height must be below current pose")
        z_values = []
        z = current[2]
        while z - release_z > self.config.descend_step_mm:
            z -= self.config.descend_step_mm
            z_values.append(z)
        z_values.append(release_z)
        return [[fine_pose[0], fine_pose[1], z, fine_pose[3]] for z in z_values]

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
            raise AutomaticPlacementError(response.get("message", f"{label} was rejected"))
        self._check_cancel()

    def _recover(
        self,
        safe_pose: Optional[Sequence[float]],
        return_pose: Optional[Sequence[float]],
        suction_off_commanded: bool,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "safe_lift": None,
            "return_with_part": None,
            "safe_lift_required": safe_pose is not None,
            "return_required": return_pose is not None and not suction_off_commanded,
            "suction_retained": not suction_off_commanded,
        }
        if safe_pose is not None:
            try:
                self._validate(safe_pose)
                result["safe_lift"] = self._move_callback(
                    safe_pose,
                    self.config.fine_velocity_ratio,
                    self.config.fine_acceleration_ratio,
                    "recovery_lift_from_placement",
                )
            except Exception as exc:
                result["safe_lift"] = {"error": str(exc)}
        if return_pose is not None and not suction_off_commanded:
            try:
                self._validate(return_pose)
                result["return_with_part"] = self._move_callback(
                    return_pose,
                    self.config.coarse_velocity_ratio,
                    self.config.coarse_acceleration_ratio,
                    "recovery_return_with_part",
                )
            except Exception as exc:
                result["return_with_part"] = {"error": str(exc)}
        return result

    @staticmethod
    def _cleanup_succeeded(cleanup: Dict[str, Any]) -> bool:
        for key, required_key in (
            ("safe_lift", "safe_lift_required"),
            ("return_with_part", "return_required"),
        ):
            if not cleanup.get(required_key):
                continue
            response = cleanup.get(key)
            if not isinstance(response, dict) or "error" in response:
                return False
            if response.get("accepted") is False or response.get("success") is False:
                return False
        return True

    def _validate(self, pose: Sequence[float]) -> None:
        self._pose(pose, "pose")
        decision = self._validate_pose(pose)
        if decision is False:
            raise AutomaticPlacementError("pose failed reachability/workspace validation")
        if isinstance(decision, dict) and decision.get("allowed") is False:
            raise AutomaticPlacementError(decision.get("reason", "pose validation failed"))
        if hasattr(decision, "allowed") and not decision.allowed:
            raise AutomaticPlacementError(getattr(decision, "reason", "pose validation failed"))

    def _fresh_current_pose(self, fallback_r: float) -> List[float]:
        pose = self._current_pose()
        if pose is None:
            raise AutomaticPlacementError(
                "fresh robot kinematics are required for automatic placement"
            )
        result = self._pose(pose, "current_pose")
        if not math.isfinite(result[3]):
            result[3] = fallback_r
        return result

    def _check_cancel(self) -> None:
        if self._cancel_requested():
            raise AutomaticPlacementError("automatic placement canceled")

    @staticmethod
    def _record_state(
        attempt: Dict[str, Any],
        state: PlacementState,
        **details: Any,
    ) -> None:
        attempt["state"] = state.value
        entry = {"state": state.value}
        entry.update(details)
        attempt["states"].append(entry)

    @staticmethod
    def _pose(value: Any, name: str) -> List[float]:
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise AutomaticPlacementError(f"{name} must be [x, y, z, r]")
        try:
            result = [float(item) for item in value]
        except (TypeError, ValueError) as exc:
            raise AutomaticPlacementError(f"{name} must contain numeric values") from exc
        if not all(math.isfinite(item) for item in result):
            raise AutomaticPlacementError(f"{name} must contain finite values")
        return result

    @staticmethod
    def _xy(value: Any, name: str) -> List[float]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise AutomaticPlacementError(f"{name} must be [x, y]")
        try:
            result = [float(value[0]), float(value[1])]
        except (TypeError, ValueError) as exc:
            raise AutomaticPlacementError(f"{name} must contain numeric values") from exc
        if not all(math.isfinite(item) for item in result):
            raise AutomaticPlacementError(f"{name} must contain finite values")
        return result
