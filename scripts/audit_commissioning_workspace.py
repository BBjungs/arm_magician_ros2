#!/usr/bin/env python3
"""Read-only geometry audit of a commissioning form; never authorizes motion."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.request import urlopen

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/magician_ros2/dobot_calibration'))
from dobot_calibration.calibration_workspace import CalibrationWorkspace, automatic_plan
from dobot_calibration.geometry import CalibrationError, fingerprint, transform
from scipy.spatial.transform import Rotation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--form', type=Path,
                        default=ROOT / 'docs/commissioning-workspace-measurement-form.yaml')
    parser.add_argument('--mount', type=Path, default=ROOT /
                        'src/magician_ros2/dobot_calibration/config/mount_model.yaml')
    parser.add_argument('--status-json', type=Path,
                        help='Use a recorded /api/status response instead of a live GET')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    form = yaml.safe_load(args.form.read_text())
    mount_data = yaml.safe_load(args.mount.read_text())
    if args.status_json:
        status = json.loads(args.status_json.read_text())
    else:
        with urlopen('http://127.0.0.1:8080/api/status', timeout=5) as response:
            status = json.load(response)
    motion = status['motion']
    pose = np.asarray(motion['current_tcp_pose'], dtype=float)
    if pose.shape != (4,) or not np.isfinite(pose).all():
        raise ValueError('Finite XYZ/J4 feedback is required')
    anchor = transform(Rotation.from_euler('z', pose[3], degrees=True).as_matrix(),
                       pose[:3] / 1000)
    mount = SimpleNamespace(envelope_radius_m=float(mount_data['envelope_radius_m']),
                            translation_error_bound_m=float(mount_data['translation_error_bound_m']))
    # Deliberately a diagnostic object, not CalibrationWorkspace.load(): an
    # incomplete form must be inspectable without certifying or installing it.
    workspace = CalibrationWorkspace(np.asarray(form['free_volume_min_m'], dtype=float),
        np.asarray(form['free_volume_max_m'], dtype=float), float(form['table_surface_z_m']),
        float(form['minimum_clearance_m']), fingerprint(form))
    if (workspace.lower.shape != (3,) or workspace.upper.shape != (3,)
            or not np.isfinite([workspace.lower, workspace.upper]).all()
            or np.any(workspace.lower >= workspace.upper)
            or not np.isfinite([workspace.table_z, workspace.clearance]).all()
            or workspace.clearance < .025):
        raise ValueError('Invalid form geometry; no default values are substituted')
    variants = []
    for scale in (1., .85):
        for xs, zs in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            current = anchor
            segments = []
            for index, target in enumerate(automatic_plan(anchor, x_sign=xs,
                                                         z_sign=zs, scale=scale), 1):
                error = None
                try:
                    workspace.check_segment(current, target, mount)
                except CalibrationError as exc:
                    error = str(exc)
                segments.append({'pose_index': index, 'target_xyz_mm':
                    (target[:3, 3] * 1000).tolist(), 'error': error,
                    'clearance': workspace.clearance_diagnostics(current, target, mount)})
                current = target
            variants.append({'scale': scale, 'x_sign': xs, 'z_sign': zs,
                             'segments': segments})
    report = {
        'utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'UNVERIFIED_FORM_DIAGNOSTIC_ONLY',
        'telemetry_source': str(args.status_json) if args.status_json else 'LIVE_HTTP_GET',
        'motion': motion,
        'form_fingerprint': workspace.digest,
        'mount_fingerprint': fingerprint(mount_data),
        'form_installation_verified': form.get('installation_verified'),
        'form_whole_robot_environment_verified': form.get('whole_robot_environment_verified'),
        'anchor_clearance': workspace.clearance_diagnostics(anchor, anchor, mount),
        'variants': variants,
        'feasible_geometry_variants': sum(all(s['error'] is None for s in v['segments'])
                                           for v in variants),
        'collision_checked': False,
        'plan_authorized': False,
        'motion_command_sent': False,
        'runtime_workspace_written': False,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ('anchor_clearance', 'feasible_geometry_variants',
                                          'motion_command_sent')}, indent=2))
    return 0 if report['feasible_geometry_variants'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
