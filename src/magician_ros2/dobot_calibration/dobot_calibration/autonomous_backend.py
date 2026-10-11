"""ROS-node adapter for unattended ten-pose acquisition in a surveyed workcell."""

from pathlib import Path
import time

import cv2
import numpy as np
import yaml

from .calibration_workspace import CalibrationWorkspace, automatic_plan
from .geometry import CalibrationError, fingerprint, pose_distance
from .passive_session import PassiveSessionStore
from .passive_solver import solve_session
from .registration import register
from .workflow import settled_pose


class AutomaticBackend:
    def __init__(self, node):
        self.node = node
        self.owned = False
        self.ptp_before = None
        self.workspace = None
        self.captures = []
        self.store = None

    def load_workspace(self):
        node = self.node
        return CalibrationWorkspace.load(
            node.settings['automatic_workspace_file'], base_frame=node.settings['base_frame'],
            camera_id=node.settings['camera_id'],
            mount_fingerprint=node.passive_session.mount_fingerprint)

    def prepare(self, checkpoint):
        node = self.node
        if not node.operation_lock.acquire(blocking=False):
            raise CalibrationError('Another calibration operation is active')
        self.owned = True
        self.ptp_before, self.captures, self.store = None, [], None
        if node.real_motion_arm is not None or node.ptp_param_state_uncertain:
            raise CalibrationError('Existing motion permit or uncertain controller parameters')
        if node.supervised_auto.worker and node.supervised_auto.worker.is_alive():
            raise CalibrationError('Dry-run plan is still running')
        if node.settings['carrier_frame']:
            raise CalibrationError('Automatic workcell support requires the TCP-mounted camera model')
        self.workspace = self.load_workspace()
        identity = node._resolve_camera_identity()
        if identity.resolution != 'PASS':
            raise CalibrationError(identity.gate)
        node.stop.clear()
        node.passive_capture_active = True
        try:
            node._prepare_passive_capture()
        finally:
            node.passive_capture_active = False
        checkpoint()
        stable, _, _ = node._table_touchoff_stability()
        if not stable:
            raise CalibrationError('Robot must be stationary before automatic calibration starts')
        with node.lock:
            anchor = node.history[-1][1].copy()
        targets = self.select_plan(anchor)
        # All sessions remain available for audit; never combine a past scene
        # with the new automatic run, or replace the operator's passive session.
        root = Path(node.settings['passive_session_root']).expanduser() / 'automatic'
        self.store = PassiveSessionStore(root, node.passive_session.mount_fingerprint,
                                         node.settings['camera_id'])
        self.store.new(node.intrinsics_fingerprint(node.bundle[2]))
        self.store.ensure_plan([
            {'pose_index': i, 'xyz_mm': (pose[:3, 3] * 1000).tolist(),
             'j4_deg': float(np.rad2deg(np.arctan2(pose[1, 0], pose[0, 0])))}
            for i, pose in enumerate(targets, 1)])
        self.context = dict(node.calibration_context)
        checkpoint()
        self.ptp_before = node._get_ptp_common_params()
        node._set_ptp_common_params(5, 5)
        if node._get_ptp_common_params() != {'velocity_percent': 5, 'acceleration_percent': 5}:
            raise CalibrationError('Automatic calibration PTP 5/5 readback failed')
        node.status('AUTO_CALIBRATING', 'Collecting and verifying real observations automatically')
        return targets

    def select_plan(self, anchor):
        failures = []
        for scale in (1.0, .85):
            for x_sign, z_sign in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                targets = automatic_plan(anchor, x_sign=x_sign, z_sign=z_sign, scale=scale)
                try:
                    self.validate(anchor, targets[0])
                    for first, second in zip(targets, targets[1:]):
                        self.validate(first, second)
                    return targets
                except CalibrationError as error:
                    failures.append(str(error))
        raise CalibrationError('NO_FEASIBLE_AUTOMATIC_PLAN: ' + '; '.join(dict.fromkeys(failures)))

    def check(self):
        node = self.node
        if not self.owned:
            raise CalibrationError('Automatic calibration does not own the operation lock')
        node.checkpoint()
        if self.workspace is None or self.load_workspace().digest != self.workspace.digest:
            raise CalibrationError('Workcell geometry changed during automatic calibration')
        mount_data = yaml.safe_load(Path(node.settings['mount_model']).expanduser().read_text())
        if fingerprint(mount_data) != node.passive_session.mount_fingerprint:
            raise CalibrationError('Mount configuration changed during automatic calibration')
        if self.ptp_before is not None and node.ptp_param_state_uncertain:
            raise CalibrationError('Controller parameter state is uncertain')

    def validate(self, current, target):
        self.workspace.check_segment(current, target, self.node.mount)
        # Verify soft joint bounds along the same Cartesian segment that MOVL
        # executes. The robot trajectory service additionally checks collision.
        from dobot_kinematics.dobot_inv_kin import calc_inv_kin
        yaw_start = np.rad2deg(np.arctan2(current[1, 0], current[0, 0]))
        yaw_end = np.rad2deg(np.arctan2(target[1, 0], target[0, 0]))
        yaw_delta = (yaw_end - yaw_start + 180) % 360 - 180
        bounds = np.array([[-120, 120], [-5, 90], [-15, 105], [-150, 150]], dtype=float)
        soft = float(self.node.settings['planning_soft_margin_deg'])
        distance = np.linalg.norm(target[:3, 3] - current[:3, 3])
        for ratio in np.linspace(0, 1, max(2, int(np.ceil(distance / .002)) + 1)):
            xyz = (current[:3, 3] * (1 - ratio) + target[:3, 3] * ratio) * 1000
            joints = calc_inv_kin(*xyz, float(yaw_start + ratio * yaw_delta))
            if joints is None or joints is False:
                raise CalibrationError('Automatic MOVL trajectory has no inverse-kinematics solution')
            joints = np.asarray(joints, dtype=float)
            if (joints.shape != (4,) or not np.isfinite(joints).all()
                    or np.any(joints < bounds[:, 0] + soft)
                    or np.any(joints > bounds[:, 1] - soft)):
                raise CalibrationError('Automatic MOVL trajectory violates a soft joint limit')

    def move(self, target):
        self.check()
        with self.node.lock:
            current = self.node.history[-1][1].copy()
        self.validate(current, target)
        if pose_distance(current, target)[0] <= .001 and pose_distance(current, target)[1] <= .3:
            return
        if self.node._get_ptp_common_params() != {'velocity_percent': 5, 'acceleration_percent': 5}:
            raise CalibrationError('Automatic calibration PTP settings changed')
        self.node._execute_guarded_motion(current, target, self.motion_guard)

    def motion_guard(self, current, target):
        self.check()
        self.validate(current, target)

    def settle(self, target, checkpoint):
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            checkpoint()
            with self.node.lock:
                history = list(self.node.history)
            try:
                if not history or self.node.now_s() - history[-1][0] > .08:
                    raise CalibrationError('Fresh robot telemetry is required for settling')
                pose = settled_pose(history, history[-1][0], self.node.after_motion_stamp)
                distance, angle = pose_distance(pose, target)
                if distance <= .002 and angle <= .5:
                    return
            except CalibrationError:
                pass
            self.node.stop.wait(.03)
        raise CalibrationError('Robot did not settle at the automatic target')

    def capture(self, target):
        self.check()
        self.node.passive_capture_active = True
        try:
            capture = self.node.capture()
        finally:
            self.node.passive_capture_active = False
        distance, angle = pose_distance(capture.base_T_tool, target)
        if distance > .002 or angle > .5:
            raise CalibrationError('Exposure pose differs from the automatic target')
        return capture

    def accept(self, capture, index):
        blur = float(cv2.Laplacian(cv2.cvtColor(capture.rgb, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        if blur < 40:
            raise CalibrationError('Automatic image blur exceeds the capture limit')
        if any(distance < .004 and angle < 2 for distance, angle in
               (pose_distance(capture.calibration_pose, old.calibration_pose) for old in self.captures)):
            raise CalibrationError('Duplicate automatic observation')
        quality = {'status': 'ANCHOR'}
        if self.captures:
            quality = register(self.captures[-1], capture, self.node.limits, seed=index).quality
        self.check()
        exposure = capture.quality['exposure']
        metadata = {'pose_index': index, 'accepted': True, 'source': 'automatic_real',
                    'XYZ_mm': (capture.base_T_tool[:3, 3] * 1000).tolist(),
                    'J4_yaw_deg': float(np.rad2deg(exposure['joints'][3])),
                    'sync_skew_ms': abs(exposure['rgb_stamp'] - exposure['depth_stamp']) * 1000,
                    'registration_quality': quality, 'blur_score': blur,
                    'workspace_fingerprint': self.workspace.digest}
        self.store.save_pose(capture, exposure['joints'], metadata,
                             exposure['rgb_stamp'], exposure['depth_stamp'],
                             exposure['intrinsics_fingerprint'], camera_info=exposure['camera_info'],
                             joint_names=[f'magician_joint_{i}' for i in range(1, 5)])
        self.captures.append(capture)

    def solve(self, checkpoint):
        result = solve_session(self.captures, self.node.mount, self.context,
                               self.store.session_dir / 'calibration_candidate.npz',
                               self.node.limits, checkpoint)
        result.update(source='automatic_real_captures', session_id=self.store.manifest['session_id'],
                      workspace_fingerprint=self.workspace.digest)
        return result

    def stop(self):
        if self.owned:
            self.node._adapter_safe_stop()

    def close(self):
        if not self.owned:
            return
        try:
            if self.ptp_before is not None:
                try:
                    self.node._restore_arm_ptp({'ptp_before': self.ptp_before})
                except Exception:
                    self.node.ptp_param_state_uncertain = True
                    raise
        finally:
            self.ptp_before = None
            self.node.passive_capture_active = False
            self.node.status('UNCALIBRATED', 'Inspect automatic calibration result; production admission pending')
            self.owned = False
            self.node.operation_lock.release()
