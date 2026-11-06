"""Stationary RGB-D workspace suggestions, never a motion authorization."""
from copy import deepcopy
import base64
import threading
import time

import cv2
import numpy as np

from .geometry import CalibrationError, Limits, checked_transform, pose_distance
from .registration import dominant_plane
from .workflow import settled_pose


def largest_valid_rectangle(mask):
    """Return [left, top, right, bottom], with exclusive upper pixel bounds."""
    heights = np.zeros(mask.shape[1], dtype=int)
    best, area = None, 0
    for y, row in enumerate(mask):
        heights = np.where(row, heights + 1, 0)
        stack = []
        for x, height in enumerate([*heights, 0]):
            start = x
            while stack and stack[-1][1] > height:
                left, previous = stack.pop()
                candidate_area = (x - left) * previous
                if candidate_area > area:
                    best, area = [left, y + 1 - int(previous), x, y + 1], candidate_area
                start = left
            if height and (not stack or stack[-1][1] < height):
                stack.append((start, height))
    return best


def propose_workspace(depth_frames, intrinsics, *, limits=Limits(), clearance_m=.025,
                      depth_margin_m=.010, base_T_camera=None, envelope_radius_m=None):
    """Propose a box inside observed depth rays, preserving every unknown pixel.

    This sampled view cannot certify unobserved space or the entire robot.
    The 10 mm depth allowance is a proposal policy, not sensor certification.
    """
    depths = np.asarray(depth_frames, dtype=float)
    k = np.asarray(intrinsics, dtype=float)
    if (depths.ndim != 3 or depths.shape[0] < 3 or min(depths.shape[1:]) < 4
            or k.shape != (3, 3) or not np.isfinite(k).all()
            or min(k[0, 0], k[1, 1]) <= 0
            or not np.allclose(k[2], [0, 0, 1]) or k[0, 1] != 0 or k[1, 0] != 0
            or not np.isfinite([clearance_m, depth_margin_m]).all()
            or clearance_m < .025 or depth_margin_m <= 0):
        raise CalibrationError('WORKSPACE_OBSERVATION_INVALID')
    finite = np.isfinite(depths)
    valid = (finite & (depths >= limits.min_depth_m) & (depths <= limits.max_depth_m)).all(axis=0)
    safe_depths = np.where(finite, depths, 0.)
    valid &= np.ptp(safe_depths, axis=0) <= depth_margin_m
    report = {
        'schema_version': 1, 'state': 'PROPOSED', 'motion_authorized': False,
        'installation_verified': False, 'whole_robot_environment_verified': False,
        'frame': 'camera_optical', 'image_size': [depths.shape[2], depths.shape[1]],
        'frame_count': len(depths), 'stable_valid_ratio': float(valid.mean()),
        'unknown_or_unstable_ratio': float(1 - valid.mean()),
        'minimum_clearance_m': clearance_m, 'assumed_depth_margin_m': depth_margin_m,
        'camera_volume': None, 'base_volume': None, 'dominant_surface': None, 'observed_surface': None,
        'blockers': ['WHOLE_ROBOT_ENVIRONMENT_NOT_OBSERVED', 'OPERATOR_REVIEW_REQUIRED'],
    }
    if base_T_camera is None:
        report['blockers'].insert(0, 'CAMERA_TO_BASE_UNVERIFIED')
    else:
        base_T_camera = checked_transform(np.asarray(base_T_camera, dtype=float))
    if envelope_radius_m is None:
        report['blockers'].append('ATTACHMENT_ENVELOPE_UNVERIFIED')
    roi = largest_valid_rectangle(valid)
    report['observed_roi_px'] = roi
    if roi is None:
        report['state'] = 'INSUFFICIENT_OBSERVATION'
        report['blockers'].append('NO_CONTIGUOUS_VALID_DEPTH')
        return report
    left, top, right, bottom = roi
    yy_roi, xx_roi = np.mgrid[top:bottom, left:right]
    roi_depth = depths[:, top:bottom, left:right].min(axis=0)
    surface = np.stack(((xx_roi - k[0, 2]) * roi_depth / k[0, 0],
                        (yy_roi - k[1, 2]) * roi_depth / k[1, 1], roi_depth), axis=-1)
    surface_min, surface_max = surface.min(axis=(0, 1)), surface.max(axis=(0, 1))
    report['observed_surface'] = {
        'frame': 'camera_optical', 'min_m': surface_min.tolist(), 'max_m': surface_max.tolist(),
        'size_mm': ((surface_max - surface_min) * 1000).tolist(),
        'depth_range_m': [float(roi_depth.min()), float(depths[:, top:bottom, left:right].max())],
        'classification': 'MEASURED_SURFACE_NOT_FREE_VOLUME',
    }
    margin = clearance_m + depth_margin_m
    near = limits.min_depth_m + margin
    far = float(depths[:, top:bottom, left:right].min()) - margin
    # Intersection of the ROI frustum over the entire depth interval. The
    # outer AABB of a frustum would include unobserved space at its near end.
    x0, x1 = (left - k[0, 2]) / k[0, 0], (right - 1 - k[0, 2]) / k[0, 0]
    y0, y1 = (top - k[1, 2]) / k[1, 1], (bottom - 1 - k[1, 2]) / k[1, 1]
    lower = np.array([max(x0 * near, x0 * far) + margin,
                      max(y0 * near, y0 * far) + margin, near])
    upper = np.array([min(x1 * near, x1 * far) - margin,
                      min(y1 * near, y1 * far) - margin, far])
    if np.any(upper <= lower):
        report['state'] = 'INSUFFICIENT_OBSERVATION'
        report['blockers'].append('OBSERVED_REGION_TOO_SMALL_FOR_CLEARANCE')
        if far <= near:
            report['blockers'].append('DEPTH_CLEARANCE_TOO_SMALL')
    else:
        report['camera_volume'] = {'min_m': lower.tolist(), 'max_m': upper.tolist(),
                                   'size_mm': ((upper - lower) * 1000).tolist()}
        if base_T_camera is not None:
            center = base_T_camera[:3, :3] @ ((lower + upper) / 2) + base_T_camera[:3, 3]
            # An INSCRIBED cube, not the rotated box's unsafe outer bounds.
            half = float(np.min((upper - lower) / 2 / np.abs(base_T_camera[:3, :3].T).sum(axis=1)))
            report['base_volume'] = {'min_m': (center - half).tolist(),
                                     'max_m': (center + half).tolist(), 'size_mm': [2000 * half] * 3}
        volume = report['base_volume'] or report['camera_volume']
        if envelope_radius_m is not None:
            if not np.isfinite(envelope_radius_m) or envelope_radius_m <= 0:
                raise CalibrationError('WORKSPACE_MOUNT_ENVELOPE_INVALID')
            report['attachment_diameter_mm'] = float(envelope_radius_m * 2000)
            if min(volume['size_mm']) < report['attachment_diameter_mm']:
                report['blockers'].append('ATTACHMENT_ENVELOPE_DOES_NOT_FIT')
    # A dominant surface is not automatically the tabletop.
    yy, xx = np.mgrid[0:depths.shape[1]:4, 0:depths.shape[2]:4]
    z = safe_depths.min(axis=0)[::4, ::4]
    points = np.stack(((xx - k[0, 2]) * z / k[0, 0],
                       (yy - k[1, 2]) * z / k[1, 1], z), axis=-1)[valid[::4, ::4]]
    try:
        if len(points) >= limits.min_points:
            plane, quality = dominant_plane(points, limits)
            report['dominant_surface'] = {'plane_camera': plane.tolist(), 'quality': quality,
                                          'confirmed_table': False}
    except CalibrationError:
        pass
    return report


class WorkspaceProposal:
    """Read-only sensor worker; never clears the global STOP or writes config."""
    def __init__(self, node):
        self.node = node
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.worker = None
        self.value = {'state': 'IDLE', 'motion_command_sent': False}

    def snapshot(self):
        with self.lock:
            return deepcopy(self.value)

    def update(self, **fields):
        with self.lock:
            self.value.update(fields)

    def start(self):
        node = self.node
        with self.lock:
            if self.worker is not None and self.worker.is_alive():
                return False, 'Workspace observation already running'
            if not node.operation_lock.acquire(blocking=False):
                return False, 'Calibration is already running'
            if node.active_goal is not None or node.real_motion_arm is not None:
                node.operation_lock.release()
                return False, 'Robot motion/authorization is active'
            self.cancelled.clear()
            self.value = {'state': 'OBSERVING', 'motion_command_sent': False,
                          'started_unix_s': time.time(), 'reason': 'Waiting for stationary RGB-D'}
            self.worker = threading.Thread(target=self.run, daemon=True)
            try:
                self.worker.start()
            except Exception:
                node.operation_lock.release()
                raise
            return True, 'Stationary sensor observation started; no motion requested'

    def cancel(self):
        self.cancelled.set()

    def observe(self):
        node = self.node
        start_stamp = node.now_s()
        node.ensure_camera_sync('workspace_proposal')
        deadline = time.monotonic() + node.settings['capture_timeout_s']
        frames, stamps, anchor, k, rgb_image, info_key = [], [], None, None, None, None
        reason = 'Waiting for synchronized RGB-D'
        while time.monotonic() < deadline:
            if self.cancelled.wait(.03):
                raise CalibrationError('WORKSPACE_OBSERVATION_CANCELLED')
            fresh = node.camera_freshness()
            hardware = node.hardware_readiness()
            if not hardware.ready or not fresh.synchronized:
                reason = hardware.reason or 'RGB_DEPTH_CAMERAINFO_NOT_SYNCHRONIZED'
                self.update(reason=reason)
                continue
            with node.lock:
                bundle, history = node.bundle, list(node.history)
            if bundle is None:
                continue
            rgb, depth, info = bundle
            times = [msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9 for msg in bundle[:2]]
            now = node.now_s()
            if (any(msg.header.frame_id != node.settings['camera_frame'] for msg in bundle)
                    or not 0 <= now - times[0] <= node.settings['rgb_stale_timeout_s']
                    or not 0 <= now - times[1] <= node.settings['depth_stale_timeout_s']
                    or abs(times[0] - times[1]) > .1):
                reason = 'RGB_DEPTH_FRAME_OR_TIMESTAMP_INVALID'
                continue
            if min(times) < start_stamp or (stamps and times[1] - stamps[-1] < .1):
                continue
            try:
                pose = settled_pose(history, min(times), 0.)
                settled_pose(history, max(times), 0.)
            except CalibrationError as error:
                reason = str(error)
                continue
            if anchor is not None:
                distance, angle = pose_distance(anchor, pose)
                if distance > .001 or angle > .3:
                    raise CalibrationError('ROBOT_MOVED_DURING_WORKSPACE_OBSERVATION')
            if anchor is None:
                anchor = pose.copy()
            key = node.intrinsics_fingerprint(info)
            if info_key is not None and key != info_key:
                raise CalibrationError('CAMERA_INTRINSICS_CHANGED')
            info_key = key
            values = np.asarray(node.bridge.imgmsg_to_cv2(depth, 'passthrough'), dtype=float)
            if depth.encoding == '16UC1':
                values *= .001
            elif depth.encoding != '32FC1':
                raise CalibrationError('DEPTH_ENCODING_UNSUPPORTED')
            if values.shape != (info.height, info.width):
                raise CalibrationError('DEPTH_CAMERAINFO_DIMENSIONS_MISMATCH')
            k = np.asarray(info.p).reshape(3, 4)[:, :3]
            if k[0, 0] <= 0:
                if np.any(np.abs(info.d) > 1e-8):
                    raise CalibrationError('RECTIFIED_DEPTH_REQUIRED')
                k = np.asarray(info.k).reshape(3, 3)
            frames.append(values.copy())
            stamps.append(times[1])
            self.update(frame_count=len(frames))
            if len(frames) == 3:
                rgb_image = node.bridge.imgmsg_to_cv2(rgb, 'bgr8')
                return frames, k, pose, info, stamps, rgb_image
        raise CalibrationError('WORKSPACE_OBSERVATION_TIMEOUT: ' + reason)

    def run(self):
        node = self.node
        try:
            frames, k, pose, info, stamps, rgb = self.observe()
            base_T_camera, transform_source = None, 'UNVERIFIED'
            workflow = node.workflow
            if (workflow is not None and workflow.solution is not None and workflow.reload_verified
                    and workflow.state in ('READY', 'AWAITING_LIVE_VALIDATION')
                    and not node.settings['carrier_frame']
                    and node.camera_context(info) == workflow.context):
                base_T_camera = pose @ workflow.solution.tool_T_camera
                transform_source = 'RELOAD_VERIFIED_CALIBRATION'
            mount = node.mount
            envelope = (mount.envelope_radius_m + mount.translation_error_bound_m
                        if mount is not None else None)
            bootstrap = getattr(node, 'bootstrap_geometry', None)
            if envelope is None and bootstrap is not None and bootstrap.eligible:
                envelope = bootstrap.conservative_envelope_radius_m + bootstrap.translation_error_bound_m
            report = propose_workspace(frames, k, limits=node.limits,
                clearance_m=float(node.settings['calibration_minimum_clearance_m']),
                base_T_camera=base_T_camera, envelope_radius_m=envelope)
            if self.cancelled.is_set():
                raise CalibrationError('WORKSPACE_OBSERVATION_CANCELLED')
            report.update(camera_frame=node.settings['camera_frame'], base_frame=node.settings['base_frame'],
                camera_id=node.settings['camera_id'], transform_source=transform_source,
                depth_stamps=stamps, intrinsics_fingerprint=node.intrinsics_fingerprint(info),
                observed_unix_s=time.time(), motion_command_sent=False)
            preview = cv2.resize(rgb, (320, 240))
            ok, encoded = cv2.imencode('.jpg', preview, [cv2.IMWRITE_JPEG_QUALITY, 65])
            if ok:
                report['preview_jpeg'] = base64.b64encode(encoded).decode('ascii')
            # No calibration workspace, verified flag or baseline is written.
            with self.lock:
                self.value = report
        except Exception as error:
            self.update(state='CANCELLED' if self.cancelled.is_set() else 'FAILED', reason=str(error))
        finally:
            node.operation_lock.release()
