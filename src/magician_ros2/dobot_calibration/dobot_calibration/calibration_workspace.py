"""Installation geometry used before the camera rotation is calibrated."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .geometry import CalibrationError, checked_transform, fingerprint, pose_distance


@dataclass(frozen=True)
class CalibrationWorkspace:
    lower: np.ndarray
    upper: np.ndarray
    table_z: float
    clearance: float
    digest: str

    @classmethod
    def load(cls, path, *, base_frame, camera_id, mount_fingerprint):
        path = Path(path).expanduser()
        if not path.is_file():
            raise CalibrationError('WORKSPACE_NOT_CONFIGURED: ' + str(path))
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema_version') != 1:
                raise ValueError('schema_version must be 1')
            if (data.get('installation_verified') is not True
                    or not isinstance(data.get('measurement_source'), str)
                    or not data['measurement_source'].strip()
                    or data.get('whole_robot_environment_verified') is not True):
                raise ValueError('installation and whole-robot environment require measured evidence')
            expected = {'base_frame': base_frame, 'camera_id': camera_id,
                        'mount_fingerprint': mount_fingerprint}
            if any(not value or data.get(key) != value for key, value in expected.items()):
                raise ValueError('workspace identity/frame/mount mismatch')
            lower = np.asarray(data['free_volume_min_m'], dtype=float)
            upper = np.asarray(data['free_volume_max_m'], dtype=float)
            table_z = float(data['table_surface_z_m'])
            clearance = float(data['minimum_clearance_m'])
            if (lower.shape != (3,) or upper.shape != (3,)
                    or not np.isfinite([lower, upper]).all() or np.any(lower >= upper)
                    or not np.isfinite([table_z, clearance]).all() or clearance < 0.025):
                raise ValueError('invalid measured volume/table/clearance')
            return cls(lower, upper, table_z, clearance, fingerprint(data))
        except (OSError, TypeError, ValueError, KeyError, yaml.YAMLError) as error:
            raise CalibrationError('WORKSPACE_INVALID: ' + str(error)) from error

    def check_segment(self, current, target, mount):
        """Bound a straight MOVL using the rotation-independent attachment sphere.

        Full-arm IK/collision checks are additionally required at dispatch.
        This volume must have been surveyed in the controller's base frame.
        """
        checked_transform(current)
        checked_transform(target)
        distance, angle = pose_distance(current, target)
        if distance > 0.075 or angle > 40:
            raise CalibrationError('WORKSPACE_STEP_EXCEEDS_LOCAL_BOUNDS')
        radius = float(mount.envelope_radius_m + mount.translation_error_bound_m)
        if not np.isfinite(radius) or radius <= 0:
            raise CalibrationError('WORKSPACE_MOUNT_ENVELOPE_INVALID')
        margin = radius + self.clearance
        points = np.linspace(current[:3, 3], target[:3, 3],
                             max(2, int(np.ceil(distance / 0.002)) + 1))
        if (np.any(points - margin < self.lower) or np.any(points + margin > self.upper)
                or np.any(points[:, 2] - margin < self.table_z)):
            raise CalibrationError('WORKSPACE_SWEPT_ENVELOPE_CLEARANCE_FAILED')
        radial = np.linalg.norm(points[:, :2], axis=1)
        if (np.any(radial < 0.14) or np.any(radial > 0.30)
                or np.any(points[:, 0] < 0.08) or np.any(points[:, 2] < 0.07)
                or np.any(points[:, 2] > 0.23)):
            raise CalibrationError('WORKSPACE_ROBOT_REACH_EXCEEDED')


def automatic_plan(anchor, *, x_sign=1, z_sign=1, scale=1.0):
    """Fresh relative targets: seven fit poses and three held-out poses."""
    from scipy.spatial.transform import Rotation
    checked_transform(anchor)
    yaw = float(np.rad2deg(np.arctan2(anchor[1, 0], anchor[0, 0])))
    offsets = [(0, 0, 0, 0), (35, 0, 0, 0), (15, 30, 10, 0),
               (15, -30, 15, 0), (30, 20, 20, 15), (30, -20, 25, -15),
               (-5, 25, 10, 10), (10, -25, 30, -10), (35, 15, 15, 20),
               (-5, -25, 25, -20)]
    targets = []
    for dx, dy, dz, dyaw in offsets:
        target = np.eye(4)
        target[:3, 3] = anchor[:3, 3] + scale * np.array([x_sign * dx, dy, z_sign * dz]) / 1000.0
        target[:3, :3] = Rotation.from_euler('z', yaw + dyaw, degrees=True).as_matrix()
        targets.append(target)
    return targets
