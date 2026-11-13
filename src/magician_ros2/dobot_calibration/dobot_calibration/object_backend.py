"""Object-only acquisition using the existing guarded motion/authorization adapter."""

from pathlib import Path
import json
import time

import numpy as np
import yaml

from .autonomous_backend import AutomaticBackend
from .geometry import CalibrationError, RetryableCaptureError, fingerprint, inverse, pose_distance
from .object_reference import METHOD, combine_stationary, is_object_capture
from .passive_session import PassiveSessionStore
from .passive_solver import solve_session
from .registration import register
from .solver import quality_metrics, require_mount_agreement, require_quality
from .workflow import load_bundle


class ObjectBackend(AutomaticBackend):
    """No scene baseline, dominant plane or plane-angle admission in this path.

    Workspace geometry remains surveyed safety input, never inferred from the
    selected object. All actual dispatch uses AutomaticBackend's guarded MOVL.
    """

    @property
    def restore_without_motion(self):
        if self.node.automatic.force_recalibrate or self.node.automatic.purpose == 'COMMISSIONING_TWO_POSES':
            return False
        try:
            with np.load(Path(self.node.settings['calibration_file']).expanduser(), allow_pickle=False) as data:
                return json.loads(str(data['metadata'])).get('calibration_method') == METHOD
        except (OSError, ValueError, KeyError):
            return False

    def prepare(self, checkpoint):
        node = self.node
        with node.calibration_transaction_lock:
            if not node.operation_lock.acquire(blocking=False):
                raise CalibrationError('Another calibration operation is active')
            self.owned = True
            self.store = None
            self.ptp_before, self.captures = None, []
            self.pending_result = None
            self.authorization = None
            self.validated_segments.clear()
            self.ptp_restore = 'NOT_REQUIRED'
            if node.real_motion_arm is not None:
                raise CalibrationError('MOTION_PERMIT_ALREADY_ACTIVE')
            node.workflow = None
            node.status('AUTO_CALIBRATING', 'ตรวจวัตถุอ้างอิงและข้อมูลกล้อง')
            node.object_capture_active = True
            self.stationary_reuse_verified = False
        if node.supervised_auto.worker and node.supervised_auto.worker.is_alive():
            raise CalibrationError('Another calibration plan is active')
        identity = node._resolve_camera_identity()
        if identity.resolution != 'PASS':
            raise CalibrationError(identity.gate)
        self.workspace = self.load_workspace()
        self._check_attachment()
        with node.automatic.dispatch_lock:
            if node.automatic.abort_event.is_set():
                raise CalibrationError('Calibration cancelled')
            node.stop.clear()
        node.passive_capture_active = True
        try:
            node._prepare_passive_capture()
        finally:
            node.passive_capture_active = False
        deadline = time.monotonic() + node.settings['capture_timeout_s']
        while True:
            blockers = self.diagnostics()['blockers']
            if not blockers:
                break
            node.automatic.update('WARMING_UP', blockers=blockers, reason='; '.join(blockers))
            if node.stop.is_set() or node.automatic.abort_event.is_set():
                raise CalibrationError('Calibration cancelled')
            if time.monotonic() >= deadline:
                raise CalibrationError('OBJECT_SENSOR_NOT_READY: ' + '; '.join(blockers))
            node.stop.wait(.05)
        self.context = dict(node.calibration_context)
        self.check()
        self.validator_policy = node._automatic_validator_policy()
        self.joint_bounds = np.asarray([self.validator_policy[f'axis_{i}_range'] for i in range(1, 5)])
        with node.lock:
            self.anchor = node.history[-1][1].copy()
        self.validate_start_pose(self.anchor)
        self.reusing_saved = False
        saved = Path(node.settings['calibration_file']).expanduser()
        if (saved.is_file() and not node.automatic.force_recalibrate
                and node.automatic.purpose != 'COMMISSIONING_TWO_POSES'):
            with np.load(saved, allow_pickle=False) as bundle:
                metadata = json.loads(str(bundle['metadata']))
            if metadata.get('calibration_method') == METHOD:
                node.automatic.update('LOADING', reason='โหลดค่าที่ผ่านการตรวจรับแล้ว')
                self.saved_solution, self.saved_anchor = load_bundle(saved, self.context, node.mount, node.limits)
                self.saved_report = metadata['verification']
                self.reusing_saved = True
                # Reidentify the saved physical reference by RGB-D features,
                # never by a recycled detector index or a new centroid alone.
                node.object_reference.last = self.saved_anchor
        if not self.reusing_saved:
            if node.automatic.verify_only:
                raise CalibrationError('SAVED_OBJECT_CALIBRATION_REQUIRED')
            # Keep an already selected reference across commissioning/retry
            # runs. Its old screen pixel is not an identity after the camera
            # moves. Only an explicit new selection resets the tracker.
        node.automatic.update('TRACKING_REFERENCE', blockers=[], reason='ตรวจว่าวัตถุอยู่นิ่งและมีข้อมูล 3D เพียงพอ')
        self.reference = self._burst()
        self.scene_pose = self.reference.base_T_tool.copy()
        distance, angle = pose_distance(self.anchor, self.scene_pose)
        if distance > .001 or angle > .3:
            raise CalibrationError('ROBOT_MOVED_SINCE_PLAN_VALIDATION')
        if self.reusing_saved:
            self.targets = []
        else:
            self.targets = self.select_plan(self.anchor)
        self.plan_fingerprint = fingerprint({'run_id': node.automatic.run_id,
            'method': METHOD, 'workspace': self.workspace.digest,
            'mount': node.passive_session.mount_fingerprint,
            'object_identity': self.reference.quality['object_identity'],
            'object_anchor_stamp': self.reference.stamp,
            'targets': [p.tolist() for p in self.targets],
            'purpose': node.automatic.purpose, 'validator_policy': self.validator_policy})
        root = Path(node.settings['passive_session_root']).expanduser() / 'object_based'
        self.store = PassiveSessionStore(root, node.passive_session.mount_fingerprint, node.settings['camera_id'])
        self.store.new(node.intrinsics_fingerprint(node.bundle[2]))
        self.store.ensure_plan([{'pose_index': i, 'xyz_mm': (p[:3, 3] * 1000).tolist(),
            'j4_deg': float(np.rad2deg(np.arctan2(p[1, 0], p[0, 0])))}
            for i, p in enumerate(self.targets, 1)]) if self.targets else None
        node.automatic.update('PREFLIGHT', calibration_method=METHOD,
            object_quality=self.reference.quality, selected_object=self.reference.quality['object_identity'],
            blockers=[], reason='', motion_command_sent=False)
        checkpoint()
        return self.targets

    def _check_attachment(self):
        node = self.node
        config = yaml.safe_load(Path(node.settings['mount_model']).expanduser().read_text())
        evidence = config.get('physical_attachment', {})
        parent = node.settings['carrier_frame'] or node.settings['tool_frame']
        if (evidence.get('exact_parent_frame_verified') is not True
                or evidence.get('candidate_parent_frame') != parent):
            raise CalibrationError('CAMERA_ATTACHMENT_FRAME_NOT_VERIFIED')
        # The existing automatic collision envelope is surveyed about TCP.
        # A different bracket requires its own commissioned kinematic model.
        if node.settings['carrier_frame'] or evidence.get('rotates_with_joint_4') is not True:
            raise CalibrationError('OBJECT_AUTOMATIC_CAMERA_PARENT_UNSUPPORTED')

    def diagnostics(self):
        node = self.node
        hardware = node.hardware_readiness().to_dict()
        blockers = list(hardware['blockers'])
        try:
            workspace = self.load_workspace().digest
        except CalibrationError as error:
            workspace = str(error); blockers.append(workspace)
        if node.ptp_param_state_uncertain:
            blockers.append('PTP_PARAM_STATE_UNCERTAIN')
        identity = node._resolve_camera_identity()
        if identity.resolution != 'PASS':
            blockers.append(identity.gate)
        error = node.health_error()
        if error:
            blockers.append(error)
        return {'hardware_readiness': hardware, 'workspace': workspace,
                'calibration_method': METHOD, 'blockers': list(dict.fromkeys(blockers)),
                'motion_command_sent': bool(node.automatic.snapshot().get('motion_command_sent'))}

    def _burst(self):
        frames = []
        deadline = time.monotonic() + self.node.settings['capture_timeout_s']
        while len(frames) < 3:
            self.check()
            if time.monotonic() >= deadline:
                raise CalibrationError('OBJECT_FRESH_FRAMES_REQUIRED')
            self.node.passive_capture_active = True
            try:
                frames.append(self.node.capture())
            except RetryableCaptureError as error:
                # Only synchronization races may wait for a new exposure.
                # Movement, ambiguity and bad shape are not repaired by motion.
                if 'OBJECT_DETECTION_EXPOSURE_MISMATCH' not in str(error):
                    raise
            finally:
                self.node.passive_capture_active = False
        return combine_stationary(frames, self.node.limits)

    def verify_scene(self, current):
        # Kept as the motion adapter's hook name; this compares object features,
        # depth and kinematic exposure, never a scene signature or plane angle.
        # Acquisition already median-filters three frames at each pose. Before
        # dispatch, compare one fresh exposure with that stationary reference;
        # reacquiring an entire burst here adds latency without new views.
        self.check()
        self.node.passive_capture_active = True
        try:
            capture = self.node.capture()
        finally:
            self.node.passive_capture_active = False
        distance, angle = pose_distance(current, capture.base_T_tool)
        if distance > .002 or angle > .5:
            raise CalibrationError('OBJECT_REFERENCE_VIEWPOINT_CHANGED')
        from .object_reference import stationary_pair
        stationary_pair(self.reference, capture, self.node.limits)
        self.reference = capture
        self.node.automatic.update(self.node.automatic.snapshot()['state'],
            object_quality=capture.quality)
        return capture

    def capture(self, target):
        capture = self._burst()
        distance, angle = pose_distance(target, capture.base_T_tool)
        if distance > .002 or angle > .5:
            raise CalibrationError('Exposure pose differs from the automatic target')
        return capture

    def accept(self, capture, index):
        if not is_object_capture(capture):
            raise CalibrationError('CALIBRATION_METHOD_MISMATCH')
        for old in self.captures:
            distance, angle = pose_distance(old.calibration_pose, capture.calibration_pose)
            if distance < .004 and angle < 2:
                raise CalibrationError('Duplicate automatic observation')
        if self.captures:
            for old in (self.captures[0], self.captures[-1]):
                pair = register(old, capture, self.node.limits)
                a = inverse(old.calibration_pose) @ capture.calibration_pose
                internal = self.node.mount.camera_reference_T_optical
                b = internal @ pair.first_T_second @ inverse(internal)
                t = self.node.mount.tool_T_camera_reference[:3, 3]
                robot_distance = np.linalg.norm((a[:3, :3] - np.eye(3)) @ t + a[:3, 3])
                camera_distance = np.linalg.norm(b[:3, 3])
                robot_angle = pose_distance(np.eye(4), a)[1]
                camera_angle = pose_distance(np.eye(4), b)[1]
                if (abs(robot_distance - camera_distance) > self.node.limits.max_translation_residual_m
                        or abs(robot_angle - camera_angle) > self.node.limits.max_rotation_residual_deg):
                    raise CalibrationError('REFERENCE_OBJECT_MOVED_OR_TRACKING_INCONSISTENT')
        self.check()
        exposure = capture.quality['exposure']
        self.store.save_pose(capture, exposure['joints'],
            {'pose_index': index, 'accepted': True, 'calibration_method': METHOD,
             'J4_yaw_deg': float(np.rad2deg(exposure['joints'][3])),
             'sync_skew_ms': abs(exposure['rgb_stamp'] - exposure['depth_stamp']) * 1000,
             'object_quality': capture.quality}, exposure['rgb_stamp'], exposure['depth_stamp'],
            exposure['intrinsics_fingerprint'], camera_info=exposure['camera_info'],
            joint_names=[f'magician_joint_{i}' for i in range(1, 5)])
        self.captures.append(capture)
        self.reference, self.scene_pose = capture, capture.base_T_tool.copy()

    def solve(self, checkpoint):
        result = solve_session(self.captures, self.node.mount, self.context,
            self.store.session_dir / 'calibration_candidate.npz', self.node.limits,
            checkpoint, phase=self.node.automatic.update, object_only=True)
        result.update(calibration_method=METHOD, source='object_based_rgbd',
                      session_id=self.store.manifest['session_id'],
                      workspace_fingerprint=self.workspace.digest)
        return result

    def verify_saved_stationary(self, checkpoint):
        checkpoint()
        pair = register(self.saved_anchor, self.reference, self.node.limits)
        require_mount_agreement(self.saved_solution.tool_T_camera, self.node.mount, self.node.limits)
        metrics = quality_metrics([self.saved_anchor, self.reference], [(0, 1, pair)],
            self.saved_solution.tool_T_camera, self.node.limits, object_only=True)
        require_quality(metrics, self.node.limits, object_only=True)
        self.stationary_reuse_verified = True
        # Saved mathematical evidence survives reboot; old hardware/live leases
        # do not. The existing admission policy must establish them again.
        from .workflow import save_bundle
        report = dict(self.saved_report)
        report.pop('validation_source', None)
        report['calibration_method'] = METHOD
        report['current_object_readiness'] = {'result': 'PASS', 'metrics': metrics,
            'stamps': self.reference.quality['object_burst_stamps']}
        candidate = self.store.session_dir / 'calibration_candidate.npz'
        save_bundle(candidate, self.saved_solution, self.saved_anchor, self.context, report, self.node.limits)
        return {'state': 'CANDIDATE_VERIFIED', 'candidate_path': str(candidate),
                'production_ready': False, 'reused_saved': True, 'motion_command_sent': False}

    def close(self):
        if self.owned:
            self.node.object_capture_active = False
        super().close()
