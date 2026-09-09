"""Motion planning, settled capture checks, persistence and readiness state."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import time

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from .geometry import (
    CalibrationError, Limits, apply, checked_transform, fingerprint, inverse, pose_distance,
    transform, transform_plane,
)
from .registration import Capture, make_capture
from .solver import Solution, require_mount_agreement, require_quality, solve, verify


def calibration_poses(start, verification=False):
    """Small XYZ/yaw offsets from measured TCP, with disjoint held-out poses."""
    checked_transform(start)
    offsets = (
        [(0.014, 0.017, 0.012, -13), (-0.017, 0.013, 0.023, 13),
         (0.012, -0.018, 0.027, 3)] if verification else
        [(0.022, 0, 0.008, 0), (0, 0.022, 0.015, 18),
         (-0.022, 0, 0.025, -18), (0, -0.022, 0.012, 12),
         (0.016, 0.016, 0.030, -8), (-0.016, -0.016, 0.020, 8)]
    )
    yaw = np.arctan2(start[1, 0], start[0, 0])
    return [transform(Rotation.from_euler('z', yaw + np.deg2rad(r)).as_matrix(),
                      start[:3, 3] + [x, y, z]) for x, y, z, r in offsets]


def check_path(current, target, capture, mount, limits=Limits()):
    """Check a MOVL swept enclosure against the observed table and static scene.

    The enclosure radius comes from the mount model. The robot's trajectory
    service remains responsible for full-arm kinematic/collision validation.
    """
    checked_transform(current)
    checked_transform(target)
    distance, angle = pose_distance(current, target)
    if distance > 0.075 or angle > 40:
        raise CalibrationError('Calibration step exceeds local motion bounds')
    count = max(3, int(np.ceil(distance / 0.002)) + 1)
    points = np.linspace(current[:3, 3], target[:3, 3], count)
    radius = np.linalg.norm(points[:, :2], axis=1)
    if (np.any(radius < 0.14) or np.any(radius > 0.30)
            or np.any(points[:, 2] < 0.07) or np.any(points[:, 2] > 0.23)
            or np.any(points[:, 0] < 0.08)):
        raise CalibrationError('Calibration path leaves the conservative robot workspace')
    scene_transform = capture.base_T_tool @ mount.tool_T_camera
    plane = transform_plane(scene_transform, capture.plane)
    # Registration has not established X yet. Bound displacement of each
    # swept TCP centre in camera coordinates over every allowed mount error.
    # This also covers reload verification when the mount may have changed.
    tool_points = apply(inverse(capture.base_T_tool), points)
    lever = np.linalg.norm(tool_points - mount.tool_T_camera[:3, 3], axis=1)
    uncertainty = (limits.max_mount_deviation_m + 3 * mount.axial_sigma_m
                   + 2 * np.sin(np.deg2rad(limits.max_mount_deviation_deg) / 2) * lever)
    clearance = mount.envelope_radius_m + 0.025 + 0.001 + uncertainty
    if np.any(points @ plane[:3] + plane[3] < clearance):
        raise CalibrationError('Insufficient table clearance for the tool/camera envelope')
    scene = apply(scene_transform, capture.cloud)
    # Table is checked as an infinite plane; above-table geometry is checked
    # against the enclosing sphere along the entire linear path.
    obstacles = scene[scene @ plane[:3] + plane[3] > 0.010]
    if len(obstacles) and np.any(cKDTree(obstacles).query(points)[0] < clearance):
        raise CalibrationError('Observed obstacle intersects the calibration swept envelope')


def settled_pose(history, image_stamp, after_stamp, settle_s=0.6, max_skew_s=0.08):
    """History entries are (ROS stamp, base_T_tool, four joints in radians)."""
    if image_stamp <= after_stamp + settle_s:
        raise CalibrationError('Image was exposed before the post-motion settle interval')
    history = sorted(history, key=lambda entry: entry[0])
    selected = [h for h in history if image_stamp - settle_s - max_skew_s <= h[0]
                <= image_stamp + max_skew_s and h[0] > after_stamp]
    if len(selected) < 6:
        raise CalibrationError('Insufficient fresh TCP/joint samples for settling')
    stamps = np.array([h[0] for h in selected])
    if (stamps[0] > image_stamp - settle_s or stamps[-1] < image_stamp
            or np.max(np.diff(stamps)) > 0.15 or np.any(np.diff(stamps) <= 0)
            or np.min(abs(stamps - image_stamp)) > max_skew_s):
        raise CalibrationError('Robot pose does not bracket the image or has a telemetry gap')
    poses = np.array([checked_transform(h[1]) for h in selected])
    joints = np.array([h[2] for h in selected])
    if joints.shape != (len(selected), 4) or not np.isfinite(joints).all():
        raise CalibrationError('Invalid joint telemetry')
    for pose in poses:
        distance, angle = pose_distance(poses[-1], pose)
        if distance > 0.0007 or angle > 0.25:
            raise CalibrationError('TCP is still moving')
    if np.max(np.ptp(np.unwrap(joints, axis=0), axis=0)) > np.deg2rad(0.25):
        raise CalibrationError('Joints are still moving')
    return poses[np.argmin(abs(stamps - image_stamp))].copy()


def save_bundle(path, solution, anchor, context, verification, limits=Limits()):
    if verification.get('result') != 'PASS':
        raise CalibrationError('Refusing to save an unverified calibration')
    metadata = {
        'schema': 1, 'created_unix_s': time.time(), 'context': context,
        'limits': asdict(limits), 'metrics': solution.metrics,
        'observability': solution.observability, 'verification': verification,
        'anchor_stamp': anchor.stamp, 'anchor_quality': anchor.quality,
    }
    metadata['context_digest'] = fingerprint(context)
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name,
                                         suffix='.tmp', delete=False) as stream:
            name = stream.name
            np.savez_compressed(
                stream, metadata=json.dumps(metadata, allow_nan=False),
                tool_T_camera=solution.tool_T_camera, training_poses=solution.training_poses,
                anchor_pose=anchor.base_T_tool, rgb=anchor.rgb, depth=anchor.depth,
                intrinsics=anchor.intrinsics, cloud=anchor.cloud, plane=anchor.plane)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        name = None
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if name is not None:
            os.unlink(name)


def load_bundle(path, context, mount, limits=Limits()):
    try:
        with np.load(Path(path).expanduser(), allow_pickle=False) as bundle:
            metadata = json.loads(str(bundle['metadata']))
            if (metadata['schema'] != 1 or metadata['context_digest'] != fingerprint(context)
                    or metadata['context'] != context):
                raise CalibrationError('Calibration identity, intrinsics or mount model changed')
            if metadata['verification']['result'] != 'PASS':
                raise CalibrationError('Saved calibration was not verified')
            value = checked_transform(bundle['tool_T_camera']).copy()
            poses = bundle['training_poses'].copy()
            if poses.ndim != 3 or poses.shape[1:] != (4, 4) or len(poses) < 6:
                raise CalibrationError('Invalid saved training poses')
            for pose in poses:
                checked_transform(pose)
            solution = Solution(value, metadata['metrics'], metadata['observability'], poses)
            require_mount_agreement(value, mount, limits)
            require_quality(solution.metrics, limits)
            anchor = Capture(metadata['anchor_stamp'], checked_transform(bundle['anchor_pose']).copy(),
                             bundle['rgb'].copy(), bundle['depth'].copy(),
                             bundle['intrinsics'].copy(), bundle['cloud'].copy(),
                             bundle['plane'].copy(), metadata['anchor_quality'])
        if (anchor.rgb.dtype != np.uint8 or anchor.rgb.shape != (*anchor.depth.shape, 3)
                or anchor.depth.ndim != 2 or anchor.intrinsics.shape != (3, 3)
                or anchor.cloud.ndim != 2 or anchor.cloud.shape[1] != 3
                or anchor.plane.shape != (4,) or not np.isfinite(anchor.plane).all()
                or not np.isclose(np.linalg.norm(anchor.plane[:3]), 1)
                or not np.isfinite(anchor.cloud).all() or not np.isfinite(anchor.stamp)
                or not np.allclose(anchor.base_T_tool, poses[0])):
            raise CalibrationError('Corrupt calibration reference data')
        # Recompute reference quality rather than trusting serialized summaries.
        anchor = make_capture(anchor.stamp, anchor.base_T_tool, anchor.rgb, anchor.depth,
                              anchor.intrinsics, anchor.cloud, mount.tool_T_camera, limits)
        return solution, anchor
    except (OSError, KeyError, TypeError, ValueError, EOFError) as error:
        raise CalibrationError(f'Cannot load calibration: {error}') from error


class Workflow:
    """Backend supplies fresh captures and guarded synchronous movement."""

    def __init__(self, backend, mount, path, context, limits=Limits()):
        self.backend, self.mount, self.path = backend, mount, path
        self.context, self.limits = context, limits
        self.state, self.reason = 'UNCALIBRATED', ''
        self.solution, self.anchor, self.report = None, None, {}
        self.verified_monotonic = None

    def transition(self, state, reason=''):
        self.state, self.reason = state, reason
        if state != 'READY':
            self.verified_monotonic = None
        self.backend.status(state, reason)

    def checkpoint(self):
        """Recheck cancellation/telemetry after potentially slow CPU or disk work."""
        self.backend.checkpoint()

    def capture_at(self, target):
        self.checkpoint()
        self.backend.move(target)
        capture = self.backend.capture()
        distance, angle = pose_distance(target, capture.base_T_tool)
        if distance > 0.002 or angle > 0.5:
            raise CalibrationError('Settled capture does not match the commanded pose')
        self.checkpoint()
        return capture

    def run(self, recalibrate=False, verify_only=False):
        self.report = {}
        self.solution, self.anchor = None, None
        self.transition('CAPTURING')
        try:
            if verify_only and (recalibrate or not Path(self.path).expanduser().is_file()):
                raise CalibrationError('No saved calibration to verify')
            self.checkpoint()
            current = self.backend.capture()
            if not recalibrate and Path(self.path).expanduser().exists():
                self.transition('LOADING')
                self.solution, self.anchor = load_bundle(self.path, self.context, self.mount, self.limits)
            else:
                self.transition('CALIBRATING')
                captures = [current]
                targets = calibration_poses(current.base_T_tool)
                # Reject an unusable local pose set before the first movement.
                previous = current.base_T_tool
                for target in targets + calibration_poses(current.base_T_tool, verification=True):
                    check_path(previous, target, current, self.mount, self.limits)
                    previous = target
                for target in targets:
                    check_path(captures[-1].base_T_tool, target, captures[-1], self.mount, self.limits)
                    captures.append(self.capture_at(target))
                self.transition('SOLVING')
                self.solution = solve(captures, self.mount, self.limits)
                self.anchor = captures[0]
                current = captures[-1]
            self.checkpoint()
            self.transition('VERIFYING')
            fresh = []
            # Reuse the stored safe region on reload, with new exposures.
            # These poses remain independent of every training observation.
            origin = self.anchor.base_T_tool
            targets = calibration_poses(origin, verification=True)
            for target in targets:
                for training in self.solution.training_poses:
                    distance, angle = pose_distance(target, training)
                    if distance < 0.008 and angle < 4:
                        raise CalibrationError('Planned verification pose overlaps training data')
                check_path(current.base_T_tool, target, current, self.mount, self.limits)
                current = self.capture_at(target)
                fresh.append(current)
            self.report = verify(self.solution, self.anchor, fresh, self.mount, self.limits)
            if self.report['result'] != 'PASS':
                raise CalibrationError(self.report['reason'])
            self.checkpoint()
            save_bundle(self.path, self.solution, self.anchor, self.context, self.report, self.limits)
            self.checkpoint()
            self.verified_monotonic = time.monotonic()
            self.transition('READY')
            return self.report
        except Exception as error:
            self.report = {'result': 'FAIL', 'metrics': self.report.get('metrics', {}),
                           'reason': str(error)}
            self.transition('FAIL', str(error))
            return self.report
