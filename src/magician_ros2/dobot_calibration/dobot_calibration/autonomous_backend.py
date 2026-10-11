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
from .motion_authorization import RunAuthorization
from .scene_validation import compare_scene
from .baseline_preflight import validate_authoritative_scene_baseline_for_preflight
from .workflow import settled_pose


class AutomaticBackend:
    def __init__(self, node):
        self.node = node
        self.owned = False
        self.ptp_before = None
        self.workspace = None
        self.captures = []
        self.store = None
        self.authorization = None
        self.plan_fingerprint = None
        self.scene_reference = None
        self.scene_pose = None
        self.ptp_restore = 'NOT_REQUIRED'
        self.validated_segments = set()
        self.validator_policy = None
        self.joint_bounds = np.array([[-120, 120], [-5, 90], [-15, 90], [-140, 140]], dtype=float)

    def load_workspace(self):
        node = self.node
        return CalibrationWorkspace.load(
            node.settings['automatic_workspace_file'], base_frame=node.settings['base_frame'],
            camera_id=node.settings['camera_id'],
            mount_fingerprint=node.passive_session.mount_fingerprint)

    def prepare(self, checkpoint):
        node = self.node
        self.store = None
        if not node.calibration_transaction_lock.acquire(blocking=False):
            raise CalibrationError('CALIBRATION_TRANSACTION_ACTIVE')
        try:
            if not node.operation_lock.acquire(blocking=False):
                raise CalibrationError('Another calibration operation is active')
            self.owned = True
            self.ptp_before, self.captures = None, []
            self.authorization = None
            self.validated_segments.clear()
            self.ptp_restore = 'NOT_REQUIRED'
            self.node.automatic.trace('AutomaticBackend.prepare.enter')
            if node.real_motion_arm is not None:
                raise CalibrationError('MOTION_PERMIT_ALREADY_ACTIVE')
        finally:
            node.calibration_transaction_lock.release()
        if node.supervised_auto.worker and node.supervised_auto.worker.is_alive():
            raise CalibrationError('Dry-run plan is still running')
        if node.settings['carrier_frame']:
            raise CalibrationError('Automatic workcell support requires the TCP-mounted camera model')
        diagnostics = self.diagnostics()
        node.automatic.update('PREFLIGHT', pre_dispatch=diagnostics, blockers=diagnostics['blockers'])
        if diagnostics['blockers']:
            raise CalibrationError('; '.join(diagnostics['blockers']))
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
        self.validator_policy = node._automatic_validator_policy()
        self.joint_bounds = np.asarray([self.validator_policy[f'axis_{i}_range'] for i in range(1, 5)], dtype=float)
        self.anchor = anchor
        # A fresh capture and the authoritative baseline must agree before
        # replacing the reference with this run's measured viewpoint.
        reference = self.initial_scene_reference(anchor)
        self.scene_reference, self.scene_pose = reference
        self.verify_scene(anchor)
        targets = self.select_plan(anchor)
        self.targets = targets
        self.plan_fingerprint = fingerprint({'run_id': node.automatic.run_id,
            'workspace': self.workspace.digest, 'mount': node.passive_session.mount_fingerprint,
            'camera': node.settings['camera_id'], 'targets': [p.tolist() for p in targets],
            'purpose': node.automatic.purpose, 'validator_policy': self.validator_policy})
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
        return targets

    def diagnostics(self):
        node = self.node
        hardware = node.hardware_readiness().to_dict()
        blockers = list(hardware['blockers'])
        try:
            workspace = self.load_workspace()
            workspace_state = workspace.digest
        except CalibrationError as error:
            workspace_state = str(error)
            blockers.append(workspace_state)
        if node.ptp_param_state_uncertain:
            blockers.append('PTP_PARAM_STATE_UNCERTAIN')
        identity = node._resolve_camera_identity()
        if identity.resolution != 'PASS':
            blockers.append(identity.gate)
        baseline = node._authoritative_baseline_record()
        baseline_gate = validate_authoritative_scene_baseline_for_preflight(
            baseline, session_id=(node.passive_session.manifest or {}).get('session_id'),
            mount=node.passive_session.mount_fingerprint, camera=node.settings['camera_id'],
            intrinsics=(baseline or {}).get('intrinsics_fingerprint'),
            live_verified=node.scene_baseline is not None)
        if baseline_gate:
            blockers.append(baseline_gate)
        return {'hardware_readiness': hardware, 'workspace': workspace_state,
                'baseline_gate': baseline_gate, 'blockers': list(dict.fromkeys(blockers)),
                'motion_command_sent': bool(node.automatic.snapshot().get('motion_command_sent')),
                'monotonic': time.monotonic()}

    def wait_for_authorization(self, checkpoint):
        node = self.node
        plan = [{'pose_index': i, 'xyz_mm': (p[:3, 3] * 1000).tolist(),
                 'j4_deg': float(np.rad2deg(np.arctan2(p[1, 0], p[0, 0])))}
                for i, p in enumerate(self.targets, 1)]
        node.automatic.update('WAITING_FOR_OPERATOR_AUTHORIZATION',
            plan=plan, plan_fingerprint=self.plan_fingerprint,
            total_poses=2 if node.automatic.purpose == 'COMMISSIONING_TWO_POSES' else 10,
            collision_validation='PASS', motion_type='MOVL', validator_policy=self.validator_policy,
            commissioning_required=node.automatic.purpose == 'AUTONOMOUS_10_POSES',
            commissioning_available=self.commissioning_valid(),
            reason='No motion or PTP parameter change until this plan is authorized')
        request = node.automatic.wait_authorization(checkpoint, node.settings['real_motion_arm_ttl_s'])
        if node.automatic.purpose == 'AUTONOMOUS_10_POSES':
            if not self.commissioning_valid():
                raise CalibrationError('TWO_POSE_COMMISSIONING_REQUIRED')
        self.authorization = RunAuthorization.issue(request, run_id=node.automatic.run_id,
            plan_fingerprint=self.plan_fingerprint, purpose=node.automatic.purpose,
            ttl=node.settings['real_motion_arm_ttl_s'])
        self.confirmation = request
        self.check()
        with node.lock:
            current = node.history[-1][1].copy()
        distance, angle = pose_distance(self.anchor, current)
        if distance > .001 or angle > .3:
            raise CalibrationError('ROBOT_MOVED_SINCE_PLAN_VALIDATION')
        self.verify_scene(current)
        self.ptp_before = node._get_ptp_common_params()
        node._set_ptp_common_params(5, 5)
        if node._get_ptp_common_params() != {'velocity_percent': 5, 'acceleration_percent': 5}:
            raise CalibrationError('Automatic calibration PTP 5/5 readback failed')
        node.status('AUTO_CALIBRATING', 'Operator-authorized real observations; production disabled')

    def commissioning_valid(self):
        evidence = getattr(self.node, 'automatic_commissioning', None)
        return bool(evidence and evidence.get('state') == 'COMMISSIONING_COMPLETE'
            and evidence.get('workspace_fingerprint') == self.workspace.digest
            and evidence.get('mount_fingerprint') == self.node.passive_session.mount_fingerprint
            and evidence.get('camera_id') == self.node.settings['camera_id']
            and evidence.get('PTP_RESTORE') == 'PASS' and evidence.get('motion_command_sent')
            and evidence.get('stop_tested_by_operator'))

    def authorization_error(self):
        if self.authorization is None:
            return 'OPERATOR_AUTHORIZATION_REQUIRED'
        return self.authorization.error(run_id=self.node.automatic.run_id,
            plan_fingerprint=self.plan_fingerprint, purpose=self.node.automatic.purpose,
            abort=self.node.stop.is_set() or self.node.automatic.abort_event.is_set())

    def initial_scene_reference(self, anchor):
        # After commissioning the camera is at Pose 2. Comparing raw optical
        # signatures with the old Pose 1 viewpoint would reject valid motion.
        # Reuse ONLY the last verified real commissioning observation, with
        # matching installation evidence. This grants no motion authorization.
        capture = getattr(self.node, 'automatic_commissioning_capture', None)
        if self.commissioning_valid() and capture is not None:
            distance, angle = pose_distance(anchor, capture.base_T_tool)
            if distance > .002 or angle > .5:
                raise CalibrationError('SCENE_VERIFY_FAILED: rebaseline required at current viewpoint')
            return self.node._scene_signature(capture), capture.base_T_tool.copy()
        return self.node.scene_baseline, anchor.copy()

    def verify_scene(self, current):
        if self.scene_reference is None:
            raise CalibrationError('SCENE_VERIFY_FAILED: no measured scene reference')
        if self.scene_pose is not None:
            distance, angle = pose_distance(current, self.scene_pose)
            if distance > .002 or angle > .5:
                raise CalibrationError('SCENE_VERIFY_FAILED: reference viewpoint changed')
        self.node.passive_capture_active = True
        try:
            capture = self.node.capture()
        finally:
            self.node.passive_capture_active = False
        comparison = compare_scene(self.scene_reference, self.node._scene_signature(capture))
        self.node.automatic.update(self.node.automatic.snapshot()['state'], scene_verify=comparison)
        if not comparison['passed']:
            raise CalibrationError('SCENE_VERIFY_FAILED: ' + ','.join(comparison['blockers']))
        self.scene_reference = self.node._scene_signature(capture)
        self.scene_pose = capture.base_T_tool.copy()
        return capture

    def commissioning_result(self):
        if len(self.captures) != 2:
            raise CalibrationError('COMMISSIONING_REQUIRES_TWO_REAL_CAPTURES')
        return {'state': 'COMMISSIONING_COMPLETE', 'production_ready': False,
                'run_id': self.node.automatic.run_id, 'plan_fingerprint': self.plan_fingerprint,
                'workspace_fingerprint': self.workspace.digest,
                'mount_fingerprint': self.node.passive_session.mount_fingerprint,
                'camera_id': self.node.settings['camera_id'],
                'motion_command_sent': bool(self.node.automatic.snapshot().get('motion_command_sent')),
                'stop_tested_by_operator': self.confirmation['stop_tested'],
                'stop_evidence_source': 'explicit on-site operator confirmation',
                'session_dir': str(self.store.session_dir),
                'targets': self.node.automatic.snapshot()['plan'][:2]}

    def record_commissioning(self, result):
        if self.ptp_restore != 'PASS' or not result['motion_command_sent']:
            raise CalibrationError('COMMISSIONING_MOTION_OR_RESTORE_NOT_VERIFIED')
        result['PTP_RESTORE'] = self.ptp_restore
        self.node.automatic_commissioning = dict(result)
        self.node.automatic_commissioning_capture = self.captures[-1]

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
        hardware = node.hardware_readiness()
        error = (hardware.reason if not hardware.ready else '') or node.health_error()
        if node.stop.is_set() or error:
            diagnostics = self.diagnostics()
            node.automatic.update(node.automatic.snapshot()['state'], pre_dispatch=diagnostics,
                                  blockers=diagnostics['blockers'])
            raise CalibrationError(error or 'Calibration cancelled')
        if self.authorization is not None and self.authorization_error():
            raise CalibrationError(self.authorization_error())
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
        bounds = self.joint_bounds
        soft = float(self.node.settings['planning_soft_margin_deg'])
        if not np.isfinite(soft) or soft < 0:
            raise CalibrationError('Automatic soft joint margin is invalid')
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

        # The complete sequence, including the anchor, receives full-arm
        # collision validation BEFORE operator authorization and first motion.
        key = fingerprint({'current': current.tolist(), 'target': target.tolist(),
                           'workspace': self.workspace.digest, 'validator_policy': self.validator_policy})
        if key not in self.validated_segments:
            from dobot_kinematics.collision_detection_server import PyBulletCollisionServer
            first = (current[:3, 3] * 1000).tolist() + [float(yaw_start)]
            second = (target[:3, 3] * 1000).tolist() + [float(yaw_end)]
            step = self.validator_policy['collision_step_mm'] if self.validator_policy else 2.
            if not PyBulletCollisionServer().validate_trajectory(2, first, second, True, step_len=step):
                raise CalibrationError('AUTOMATIC_COLLISION_TRAJECTORY_REJECTED')
            self.validated_segments.add(key)

    def move(self, target):
        error = self.authorization_error()
        if error:
            raise CalibrationError(error)
        self.check()
        with self.node.lock:
            current = self.node.history[-1][1].copy()
        self.validate(current, target)
        if pose_distance(current, target)[0] <= .001 and pose_distance(current, target)[1] <= .3:
            return
        if self.node._get_ptp_common_params() != {'velocity_percent': 5, 'acceleration_percent': 5}:
            raise CalibrationError('Automatic calibration PTP settings changed')
        self.verify_scene(current)
        self.check()
        diagnostics = self.diagnostics()
        self.node.automatic.update(self.node.automatic.snapshot()['state'],
                                  pre_dispatch=diagnostics, blockers=diagnostics['blockers'])
        if diagnostics['blockers']:
            raise CalibrationError('; '.join(diagnostics['blockers']))
        self.node._execute_guarded_motion(current, target, self.motion_guard)

    def motion_guard(self, current, target):
        error = self.authorization_error()
        if error:
            raise CalibrationError(error)
        self.check()
        if self.node._automatic_validator_policy() != self.validator_policy:
            raise CalibrationError('TRAJECTORY_VALIDATOR_POLICY_CHANGED')
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
        # Registration has checked static-scene overlap across viewpoints.
        # Subsequent stationary checks compare at this measured viewpoint.
        self.scene_reference = self.node._scene_signature(capture)
        self.scene_pose = capture.base_T_tool.copy()

    def solve(self, checkpoint):
        result = solve_session(self.captures, self.node.mount, self.context,
                               self.store.session_dir / 'calibration_candidate.npz',
                               self.node.limits, checkpoint)
        result.update(source='automatic_real_captures', session_id=self.store.manifest['session_id'],
                      workspace_fingerprint=self.workspace.digest)
        return result

    def persist_status(self, status):
        if self.store is not None and self.store.session_dir is not None:
            path = self.store.session_dir / 'automatic_audit.yaml'
            temporary = path.with_suffix('.tmp')
            temporary.write_text(yaml.safe_dump(status), encoding='utf-8')
            temporary.replace(path)

    def stop(self):
        if self.authorization is not None:
            self.authorization.revoked = True
        if self.owned:
            self.node._adapter_safe_stop()

    def close(self):
        if not self.owned:
            return
        try:
            if self.ptp_before is not None:
                try:
                    restored, detail = self.node._restore_arm_ptp({'ptp_before': self.ptp_before})
                    if not restored:
                        raise CalibrationError('PTP_RESTORE_FAILED: ' + str(detail))
                    self.ptp_restore = 'PASS'
                    self.node.automatic.update(self.node.automatic.snapshot()['state'],
                        PTP_ORIGINAL=dict(self.ptp_before), PTP_RESTORE_READBACK=detail)
                except Exception:
                    self.node.ptp_param_state_uncertain = True
                    self.ptp_restore = 'FAIL'
                    raise
        finally:
            if self.authorization is not None:
                self.authorization.revoked = True
            self.node.automatic.update(self.node.automatic.snapshot()['state'],
                                       PTP_RESTORE=self.ptp_restore, authorization_revoked=True)
            self.ptp_before = None
            self.node.passive_capture_active = False
            self.node.status('UNCALIBRATED', 'Inspect automatic calibration result; production admission pending')
            self.owned = False
            self.node.operation_lock.release()
