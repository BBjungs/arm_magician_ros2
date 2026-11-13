"""Calibration-free, translation-only IBVS. No ROS or hardware side effects.

The transport must provide fresh stationary observations, guarded blocking
MOVL, and cancellation. Jacobian columns use *measured* TCP displacement in
mm; rows are u pixels, v pixels, optical depth mm. No camera/base transform
or TCP-to-camera alignment is inferred from centering the target.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml


class SafeStop(RuntimeError):
    pass


@dataclass(frozen=True)
class ServoConfig:
    mode: str = 'eye_in_hand'
    calibration_required: bool = False
    controller: str = 'adaptive_ibvs'
    target_class: str = 'black_cap'
    xy_tolerance_px: float = 8.0
    initial_probe_mm: float = 1.0
    max_step_mm: float = 3.0
    velocity_ratio: float = 0.10
    acceleration_ratio: float = 0.10
    target_timeout_sec: float = 1.0
    max_iterations: int = 80
    require_fresh_rgbd: bool = True
    require_robot_feedback: bool = True
    require_trajectory_validation: bool = True
    require_operator_enable: bool = True
    stop_on_target_loss: bool = True
    stop_depth_mm: float = 200.0
    depth_tolerance_mm: float = 2.0
    minimum_confidence: float = 0.70
    damping: float = 0.15
    gain: float = 0.6
    min_response: float = 0.15
    max_condition: float = 80.0
    max_travel_mm: float = 100.0
    feedback_timeout_sec: float = 0.5
    motion_timeout_sec: float = 10.0
    max_sync_delta_sec: float = 0.08
    stationary_samples: int = 3
    track_gate_px: float = 40.0
    enable_timeout_sec: float = 60.0
    # Surveyed obstacle-free volume in base coordinates, including the table.
    # Its erosion by a sphere enclosing camera, carrier and tool bounds MOVL.
    free_volume_min_mm: list = field(default_factory=list)
    free_volume_max_mm: list = field(default_factory=list)
    assembly_radius_mm: float = 0.0
    clearance_mm: float = 10.0
    geometry_confirmed: bool = False

    def __post_init__(self):
        if self.mode != 'eye_in_hand' or self.controller != 'adaptive_ibvs' or self.calibration_required:
            raise ValueError('Only calibration-free adaptive eye-in-hand IBVS is supported')
        for key in ('require_fresh_rgbd', 'require_robot_feedback',
                    'require_trajectory_validation', 'require_operator_enable', 'stop_on_target_loss'):
            if getattr(self, key) is not True:
                raise ValueError(f'{key} cannot be disabled')
        for key, value in vars(self).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not np.isfinite(value) or value < 0:
                    raise ValueError(f'Invalid {key}')
        for key in ('xy_tolerance_px', 'initial_probe_mm', 'max_step_mm', 'target_timeout_sec',
                    'stop_depth_mm', 'depth_tolerance_mm', 'damping', 'gain', 'min_response',
                    'max_travel_mm', 'feedback_timeout_sec', 'motion_timeout_sec',
                    'max_sync_delta_sec', 'enable_timeout_sec', 'track_gate_px'):
            if getattr(self, key) <= 0:
                raise ValueError(f'{key} must be positive')
        if not (.01 <= self.velocity_ratio <= .1 and .01 <= self.acceleration_ratio <= .1
                and 0 < self.gain <= 1 and 0 < self.minimum_confidence <= 1
                and .1 <= self.initial_probe_mm <= self.max_step_mm <= 3
                and self.max_condition > 1 and self.depth_tolerance_mm < self.stop_depth_mm):
            raise ValueError('Invalid controller limits')
        if type(self.max_iterations) is not int or not 1 <= self.max_iterations <= 80:
            raise ValueError('max_iterations must be an integer in [1, 80]')
        if type(self.stationary_samples) is not int or self.stationary_samples < 3:
            raise ValueError('At least three stationary frames are required')

    @classmethod
    def load(cls, path):
        return cls(**yaml.safe_load(Path(path).read_text())['visual_servo'])

    def check_geometry(self, start, target):
        lo, hi = np.asarray(self.free_volume_min_mm), np.asarray(self.free_volume_max_mm)
        radius = self.assembly_radius_mm + self.clearance_mm
        if (self.geometry_confirmed is not True or self.assembly_radius_mm <= 0
                or lo.shape != (3,) or hi.shape != (3,)
                or not np.isfinite(np.r_[lo, hi]).all()
                or np.any(lo + radius >= hi - radius)):
            raise SafeStop('Surveyed free volume and camera/tool envelope are not confirmed')
        # Optical center may be anywhere inside the TCP-centered assembly sphere.
        if self.stop_depth_mm <= 2 * self.assembly_radius_mm + self.clearance_mm + self.max_step_mm:
            raise SafeStop('Stop depth does not cover the camera/tool envelope')
        for pose in (start, target):
            pose = np.asarray(pose, dtype=float)
            if pose.shape != (4,) or not np.isfinite(pose).all():
                raise SafeStop('Invalid TCP pose')
            if np.any(pose[:3] < lo + radius) or np.any(pose[:3] > hi - radius):
                raise SafeStop('Swept camera/tool envelope leaves surveyed free volume')
        # A straight segment lies inside this convex, eroded free volume.


@dataclass
class Observation:
    feature: np.ndarray
    reference: np.ndarray
    tcp: np.ndarray
    rgb_stamp: float
    depth_stamp: float
    confidence: float
    bbox: list


class TargetTracker:
    """Associate by image geometry, never per-frame detector index; fail on ambiguity."""

    def __init__(self, config):
        self.config = config
        self.previous = None
        self.stamps = (0., 0.)
        self.source = None

    def select(self, packet, now_ros, after_stamp=0.):
        c = self.config
        rgb, depth = float(packet.get('rgb_stamp', 0)), float(packet.get('depth_stamp', 0))
        if (not np.isfinite([rgb, depth, now_ros]).all()
                or any(not 0 <= now_ros - s <= c.target_timeout_sec for s in (rgb, depth))
                or rgb <= max(after_stamp, self.stamps[0])
                or depth <= max(after_stamp, self.stamps[1])
                or abs(rgb - depth) > c.max_sync_delta_sec
                or packet.get('registered_depth') is not True or packet.get('error')):
            raise SafeStop('RGB-D is stale, repeated, unregistered or unsynchronized')
        size = np.asarray(packet.get('image_size', []), dtype=float)
        if size.shape != (2,) or not np.isfinite(size).all() or np.any(size <= 0):
            raise SafeStop('Missing RGB image size')
        source = (tuple(size), packet.get('rgb_frame_id'), packet.get('depth_frame_id'))
        if not all(isinstance(frame, str) and frame for frame in source[1:]):
            raise SafeStop('Missing RGB-D optical frame identity')
        if self.source is not None and source != self.source:
            raise SafeStop('RGB-D frame identity or image size changed')
        candidates = []
        for item in packet.get('detections', []):
            if item.get('class_name') != c.target_class or item.get('depth_valid') is not True:
                continue
            try:
                uv = np.asarray(item['center_pixel'], dtype=float)
                box = np.asarray(item['bbox'], dtype=float)
                d, confidence = float(item['depth_mm']), float(item['confidence'])
                if (uv.shape != (2,) or box.shape != (4,)
                        or not np.isfinite(np.r_[uv, box, d, confidence]).all()
                        or d <= 0 or not c.minimum_confidence <= confidence <= 1
                        or np.any(uv < 0) or np.any(uv >= size)
                        or np.any(box[2:] <= box[:2]) or np.any(box[:2] < 0)
                        or np.any(box[2:] > size)
                        or np.any(uv < box[:2]) or np.any(uv > box[2:])):
                    continue
                if self.previous is not None:
                    old_uv, old_box, old_depth = self.previous
                    ratio = np.prod(box[2:] - box[:2]) / np.prod(old_box[2:] - old_box[:2])
                    if (np.linalg.norm(uv - old_uv) > c.track_gate_px
                            or not .5 <= ratio <= 2 or abs(d - old_depth) > 15):
                        continue
                candidates.append((uv, box, d, confidence))
            except (KeyError, TypeError, ValueError):
                continue
        if len(candidates) != 1:
            raise SafeStop('Target lost or ambiguous; cannot establish the same black object')
        uv, box, d, confidence = candidates[0]
        self.previous = (uv, box, d)
        self.stamps = (rgb, depth)
        self.source = source
        return np.r_[uv, d], size / 2, confidence, box.tolist(), rgb, depth


class AdaptiveIBVS:
    def __init__(self, config, transport):
        self.config, self.io = config, transport
        self.jacobian = None
        self.state = 'IDLE'
        self.reason = ''
        self.iterations = 0
        self.travel = 0.
        self.latest = None
        self.direction = None
        self.condition = None
        self.model_updates = 0
        self.history = []

    def transition(self, state):
        self.state = state
        self.history.append(state)

    def _stable_jacobian(self):
        if self.jacobian is None or not np.isfinite(self.jacobian).all():
            raise SafeStop('Jacobian unavailable')
        singular = np.linalg.svd(self.jacobian, compute_uv=False)
        self.condition = float(singular[0] / max(singular[-1], 1e-12))
        if singular[-1] < .05 or self.condition > self.config.max_condition:
            raise SafeStop('Jacobian is singular or ill-conditioned')
        gradient = self.jacobian[2]
        norm = np.linalg.norm(gradient)
        if not .2 <= norm <= 1.5:
            raise SafeStop('Optical depth response is unobservable or physically inconsistent')
        self.direction = (-gradient / norm).tolist()

    def _move(self, before, delta, phase):
        c = self.config
        delta = np.asarray(delta, dtype=float)
        length = np.linalg.norm(delta)
        if delta.shape != (3,) or not np.isfinite(delta).all() or not .05 <= length <= c.max_step_mm + 1e-6:
            raise SafeStop('Invalid or ineffective step')
        if length > before.feature[2] - c.stop_depth_mm:
            raise SafeStop('Step could cross the non-contact depth limit')
        if self.iterations >= c.max_iterations or self.travel + length > c.max_travel_mm:
            raise SafeStop('Iteration/travel budget exhausted')
        target = before.tcp.copy()
        target[:3] += delta
        self.transition('CHECK')
        self.io.check(before, target)
        self.iterations += 1
        self.travel += length
        self.transition(phase)
        stopped_stamp = self.io.move(target, c.velocity_ratio, c.acceleration_ratio)
        self.transition('VERIFY')
        after = self.io.observe(after_stamp=max(stopped_stamp, before.rgb_stamp, before.depth_stamp))
        self.latest = after
        if (after.rgb_stamp <= max(stopped_stamp, before.rgb_stamp)
                or after.depth_stamp <= max(stopped_stamp, before.depth_stamp)
                or not np.array_equal(after.reference, before.reference)):
            raise SafeStop('Observation is not post-motion or image reference changed')
        dx = after.tcp[:3] - before.tcp[:3]
        if (np.linalg.norm(dx) < .1 or np.linalg.norm(dx - delta) > .35
                or abs(after.tcp[3] - before.tcp[3]) > .2):
            raise SafeStop('Measured TCP motion does not match the translation command')
        ds = after.feature - before.feature
        if np.linalg.norm(ds) < c.min_response:
            raise SafeStop('Motion produced insufficient observable RGB-D change')
        if after.feature[2] < c.stop_depth_mm:
            raise SafeStop('Depth crossed the non-contact stop boundary')
        return after, dx, ds

    def run(self):
        try:
            self.transition('DETECT')
            obs = self.io.observe(after_stamp=0.)
            self.latest = obs
            self.transition('DEPTH')
            self.io.check(obs, obs.tcp)
            if obs.feature[2] <= self.config.stop_depth_mm + self.config.depth_tolerance_mm:
                self.reason = 'Already within stop distance; no movement'
                self.transition('STOP')
                return
            displacements, responses = [], []
            # Three independent translations are required to observe optical depth
            # as well as u/v. A rejected probe is never sent or blindly reversed.
            for axis in range(3):
                delta = np.eye(3)[axis] * self.config.initial_probe_mm
                obs, dx, ds = self._move(obs, delta, 'LEARN')
                displacements.append(dx)
                responses.append(ds)
            x = np.column_stack(displacements)
            if np.linalg.cond(x) > 10:
                raise SafeStop('Probe TCP displacements are not independent')
            self.jacobian = np.column_stack(responses) @ np.linalg.inv(x)
            self._stable_jacobian()
            while True:
                c = self.config
                error = obs.feature[:2] - obs.reference
                aligned = np.max(np.abs(error)) <= c.xy_tolerance_px
                if aligned and obs.feature[2] <= c.stop_depth_mm + c.depth_tolerance_mm:
                    self.reason = 'Non-contact approach complete; grasp is not authorized'
                    self.transition('STOP')
                    return
                self._stable_jacobian()
                desired = np.r_[-error, -(obs.feature[2] - c.stop_depth_mm) if aligned else 0.]
                j = self.jacobian
                delta = c.gain * j.T @ np.linalg.solve(j @ j.T + c.damping**2 * np.eye(3), desired)
                # Limit norm, including a worst-case bound on depth reduction.
                bound = min(c.max_step_mm, obs.feature[2] - c.stop_depth_mm)
                delta *= min(1., bound / max(np.linalg.norm(delta), 1e-12))
                if aligned and (j @ delta)[2] >= -.05:
                    raise SafeStop('No measured direction predicts decreasing optical depth')
                before = obs
                obs, dx, ds = self._move(before, delta, 'APPROACH' if aligned else 'ALIGN')
                residual = ds - j @ dx
                self.jacobian = j + np.outer(residual, dx) / np.dot(dx, dx)
                self.model_updates += 1
                self._stable_jacobian()
                # Update from evidence first, then stop. Restart requires a fresh
                # enable and a new local model; there is no guessed reverse move.
                old_error = np.linalg.norm(error)
                new_error = np.linalg.norm(obs.feature[:2] - obs.reference)
                if new_error > old_error + 2:
                    raise SafeStop('Pixel error increased; measured Jacobian updated, re-enable to relearn')
                if not aligned and old_error - new_error < .1:
                    raise SafeStop('Alignment made no measurable progress')
                if aligned and -ds[2] < .1:
                    raise SafeStop('Approach did not reduce measured optical depth')
                if np.linalg.norm(residual) > max(2., .75 * np.linalg.norm(ds)):
                    raise SafeStop('Local model is inconsistent with observed motion')
        except Exception as exc:
            self.reason = str(exc)
            self.transition('SAFE_STOP')
            self.io.cancel()

    def status(self):
        obs = self.latest
        return {
            'servo_state': self.state, 'message': self.reason,
            'iterations': self.iterations, 'travel_mm': self.travel,
            'model_updates': self.model_updates,
            'stop_depth_mm': self.config.stop_depth_mm,
            'pixel_error': None if obs is None else (obs.feature[:2] - obs.reference).tolist(),
            'target_center': None if obs is None else obs.feature[:2].tolist(),
            'reference': None if obs is None else obs.reference.tolist(),
            'depth_mm': None if obs is None else float(obs.feature[2]),
            'confidence': None if obs is None else obs.confidence,
            'rgb_stamp': None if obs is None else obs.rgb_stamp,
            'depth_stamp': None if obs is None else obs.depth_stamp,
            'bbox': None if obs is None else obs.bbox,
            'tcp_pose': None if obs is None else obs.tcp.tolist(),
            'estimated_motion_direction': self.direction,
            'jacobian_status': 'UNLEARNED' if self.jacobian is None else (
                'REJECTED' if self.state == 'SAFE_STOP' else 'OBSERVED'),
            'jacobian': None if self.jacobian is None else self.jacobian.tolist(),
            'jacobian_condition': self.condition,
        }
