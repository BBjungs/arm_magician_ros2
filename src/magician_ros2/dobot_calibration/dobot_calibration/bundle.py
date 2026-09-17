"""Read-only consumer for a verified markerless hand-eye bundle.

The calibration node remains the only authority which may declare a bundle
usable.  Consumers must supply its fresh ``/calibration/status`` payload; a
file on disk is deliberately insufficient to authorize a transform.
"""

import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .geometry import CalibrationError, apply, checked_transform, transform


def normalize_tcp_pose(value, *, xyz_unit="m"):
    """Return a rigid base_T_tool from [x, y, z, yaw] telemetry."""
    try:
        pose = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise CalibrationError("TCP pose must be numeric") from error
    if pose.shape != (4,) or not np.isfinite(pose).all():
        raise CalibrationError("TCP pose must be finite [x, y, z, yaw]")
    if xyz_unit == "mm":
        pose[:3] *= 0.001
    elif xyz_unit != "m":
        raise CalibrationError("TCP xyz_unit must be m or mm")
    return transform(Rotation.from_euler("z", np.deg2rad(pose[3])).as_matrix(), pose[:3])


class VerifiedBundle:
    """Fail-closed markerless point transformer bound to live node status."""

    def __init__(self, path):
        self.path = Path(path).expanduser()

    @staticmethod
    def require_authoritative_status(status):
        if not isinstance(status, dict):
            raise CalibrationError("Markerless /calibration/status is unavailable")
        blockers = status.get("blockers") or []
        if (status.get("state") != "READY" or status.get("result") != "PASS"
                or status.get("ready") is not True or blockers):
            reason = status.get("reason") or "; ".join(map(str, blockers))
            raise CalibrationError(reason or "Markerless calibration is not READY")
        required = {
            "bundle_loaded": True,
            "geometry_verified": True,
            "verification_status": "PASS",
            "reload_verification_status": "PASS",
        }
        for name, expected in required.items():
            if status.get(name) != expected:
                raise CalibrationError(f"Markerless status rejected: {name} != {expected}")
        return status

    def load_transform(self, status):
        status = self.require_authoritative_status(status)
        status_path = Path(str(status.get("bundle_path", ""))).expanduser()
        if not status_path or status_path != self.path:
            raise CalibrationError("Calibration status and configured bundle path differ")
        try:
            with np.load(self.path, allow_pickle=False) as bundle:
                metadata = json.loads(str(bundle["metadata"]))
                value = checked_transform(bundle["tool_T_camera"]).copy()
        except (OSError, KeyError, TypeError, ValueError, EOFError) as error:
            raise CalibrationError(f"Cannot load markerless calibration bundle: {error}") from error
        if metadata.get('schema') == 2 or metadata.get('context', {}).get('carrier_frame'):
            raise CalibrationError('Camera-carrier calibration requires synchronized carrier pose; TCP-only consumer cannot use it')
        if metadata.get("schema") != 1:
            raise CalibrationError("Unsupported markerless calibration bundle schema")
        if metadata.get("verification", {}).get("result") != "PASS":
            raise CalibrationError("Saved markerless calibration is not verified")
        if metadata.get("context_digest") != status.get("context_digest"):
            raise CalibrationError("Markerless bundle identity differs from live calibration status")
        return value

    def camera_point_to_base(self, camera_xyz_mm, tcp_pose_m_deg, status):
        if isinstance(camera_xyz_mm, dict):
            camera_xyz_mm = [camera_xyz_mm.get(key) for key in ("x", "y", "z")]
        point = np.asarray(camera_xyz_mm, dtype=float)
        if point.shape != (3,) or not np.isfinite(point).all() or point[2] <= 0:
            raise CalibrationError("A valid registered-depth camera_xyz_mm point is required")
        base_T_tool = normalize_tcp_pose(tcp_pose_m_deg, xyz_unit="m")
        base_point_m = apply(base_T_tool @ self.load_transform(status), point * 0.001)
        return (base_point_m * 1000.0).tolist()
