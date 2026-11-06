"""ROS-node adapter for unattended ten-pose acquisition in a surveyed workcell."""

from pathlib import Path
from types import SimpleNamespace
import json
import time

import cv2
import numpy as np
import yaml

from .calibration_workspace import CalibrationWorkspace, automatic_plan
from .geometry import CalibrationError, Limits, RetryableCaptureError, checked_transform, fingerprint, pose_distance
from .passive_session import PassiveSessionStore
from .passive_solver import solve_session
from .registration import register
from .motion_authorization import RunAuthorization
from .scene_validation import compare_scene
from .baseline_preflight import validate_authoritative_scene_baseline_for_preflight
from .baseline_admission import AuthoritativeBaselineAdmissionGate
from .workflow import Workflow, calibration_poses, load_bundle, save_bundle, settled_pose
from .solver import excitation, verify
from .validation_status import live_acceptance_error


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
        self.reusing_saved = False
        self.pending_result = None
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
            node.workflow = None
            node.status('AUTO_CALIBRATING', 'Validating calibration; picking disabled')
            self.ptp_before, self.captures = None, []
            self.pending_result = None
            self.reusing_saved = False
            self.authorization = None
            self.scene_reference = self.scene_pose = None
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
        node.automatic.update('PREFLIGHT', pre_dispatch=diagnostics, blockers=diagnostics['blockers'], reason='')
        # Validate installation evidence before enabling capture. Camera warm-up
        # and the first scene baseline are acquisition work, not prerequisites
        # for activating the lazy RGB-D subscriptions.
        self.workspace = self.load_workspace()
        if node.ptp_param_state_uncertain:
            raise CalibrationError('PTP_PARAM_STATE_UNCERTAIN')
        identity = node._resolve_camera_identity()
        if identity.resolution != 'PASS':
            raise CalibrationError(identity.gate)
        with node.automatic.dispatch_lock:
            if node.automatic.abort_event.is_set():
                raise CalibrationError('Calibration cancelled')
            node.stop.clear()
        self.prepare_observations()
        diagnostics = self.diagnostics()
        node.automatic.update('PREFLIGHT', pre_dispatch=diagnostics, blockers=diagnostics['blockers'], reason='')
        if diagnostics['blockers']:
            raise CalibrationError('; '.join(diagnostics['blockers']))
        self.context = dict(node.calibration_context)
        saved = Path(node.settings['calibration_file']).expanduser()
        if node.automatic.purpose != 'COMMISSIONING_TWO_POSES' and not node.automatic.force_recalibrate:
            if saved.is_file():
                node.automatic.update('LOADING')
                try:
                    self.saved_solution, self.saved_anchor = load_bundle(saved, self.context, node.mount, node.limits)
                    with np.load(saved, allow_pickle=False) as bundle:
                        metadata = json.loads(str(bundle['metadata']))
                        self.saved_report = metadata['verification']
                    node.automatic.update('LOADING', last_completed_unix_s=metadata.get('created_unix_s'))
                    self.reusing_saved = True
                except (CalibrationError, ValueError, KeyError, OSError) as error:
                    if node.automatic.verify_only:
                        raise
                    node.automatic.update('PREFLIGHT', previous_bundle_error=str(error))
            elif node.automatic.verify_only:
                raise CalibrationError('No saved calibration to verify')
        checkpoint()
        stable, _ = node._table_touchoff_stability()
        if not stable:
            raise CalibrationError('Robot must be stationary before automatic calibration starts')
        with node.lock:
            anchor = node.history[-1][1].copy()
        self.validator_policy = node._automatic_validator_policy()
        self.joint_bounds = np.asarray([self.validator_policy[f'axis_{i}_range'] for i in range(1, 5)], dtype=float)
        self.anchor = anchor
        # A stale scene must not mask an inadmissible starting pose. Planning
        # cannot repair an entry segment whose starting envelope is outside
        # the measured workspace.
        self.validate_start_pose(anchor)
        reference = self.initial_scene_reference(anchor)
        self.scene_reference, self.scene_pose = reference
        self.verify_scene(anchor)
        if self.reusing_saved:
            poses = self.saved_report.get('verification_poses')
            targets = ([checked_transform(np.asarray(p, dtype=float)) for p in poses]
                       if poses else calibration_poses(self.saved_anchor.base_T_tool, verification=True))
            if len(targets) != 3:
                raise CalibrationError('Saved verification plan must contain three independent poses')
            self.validate(anchor, targets[0])
            for target in targets:
                for training in self.saved_solution.training_poses:
                    distance, angle = pose_distance(target, training)
                    if distance < .008 and angle < 4:
                        raise CalibrationError('Saved verification pose overlaps training data')
        else:
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
        baseline_path = self.store.session_dir / 'automatic_scene_reference.yaml'
        baseline_path.write_text(yaml.safe_dump({
            'run_id': node.automatic.run_id, 'workspace_fingerprint': self.workspace.digest,
            'mount_fingerprint': node.passive_session.mount_fingerprint,
            'camera_id': node.settings['camera_id'],
            'base_T_tool': self.scene_pose.tolist(), 'signature': self.scene_reference,
        }), encoding='utf-8')
        self.store.ensure_plan([
            {'pose_index': i, 'xyz_mm': (pose[:3, 3] * 1000).tolist(),
             'j4_deg': float(np.rad2deg(np.arctan2(pose[1, 0], pose[0, 0])))}
            for i, pose in enumerate(targets, 1)])
        self.context = dict(node.calibration_context)
        checkpoint()
        return targets

    def prepare_observations(self):
        """Bootstrap stationary inputs; never replace an existing scene baseline."""
        node = self.node
        node.automatic.update('WARMING_UP', reason='Waiting for synchronized RGB-D and stable robot feedback')
        node.passive_capture_active = True
        try:
            node._prepare_passive_capture()
            if node.passive_session_error:
                raise CalibrationError('SESSION_INCOMPATIBLE: ' + node.passive_session_error)
            if node.passive_session.manifest is None:
                node.passive_session.new(node.intrinsics_fingerprint(node.bundle[2]))
            path = node._scene_baseline_path()
            missing = node.scene_baseline is None and not path.exists()
            deadline = time.monotonic() + node.settings['capture_timeout_s']
            while True:
                if node.stop.is_set() or node.automatic.abort_event.is_set():
                    raise CalibrationError('Calibration cancelled')
                hardware = node.hardware_readiness()
                reason = (hardware.reason if not hardware.ready else '') or node.health_error()
                if missing:
                    now = time.monotonic()
                    node.authoritative_baseline_gate.update(node._authoritative_baseline_snapshot(), now)
                    admission = node.authoritative_baseline_gate.evaluate_for_baseline(now)
                    if not admission['accepted']:
                        reason = reason or admission['exact_gate']
                    node.automatic.update('WARMING_UP', baseline_readiness=admission)
                if not reason:
                    break
                node.automatic.update('WARMING_UP', reason=reason, blockers=[reason])
                if time.monotonic() >= deadline:
                    raise CalibrationError('OBSERVATION_WARMUP_TIMEOUT: ' + reason)
                node.stop.wait(.05)
            if missing:
                node.automatic.checkpoint()
                node.automatic.update('PREPARING_BASELINE', reason='Capturing the initial stationary scene',
                                      blockers=[])
                capture = node.capture()
                node.automatic.checkpoint()
                # Capture performs the real cloud/plane/exposure validation.
                # Recheck admission after it, before marking anything valid.
                now = time.monotonic()
                node.authoritative_baseline_gate.update(node._authoritative_baseline_snapshot(), now)
                admission = node.authoritative_baseline_gate.evaluate_for_baseline(now)
                if not admission['accepted']:
                    raise CalibrationError(admission['exact_gate'])
                previous = node.scene_baseline
                try:
                    node.scene_baseline = node._scene_signature(capture)
                    node._persist_scene_baseline()
                except Exception:
                    node.scene_baseline = previous
                    raise
        finally:
            node.passive_capture_active = False

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
            total_poses=2 if node.automatic.purpose == 'COMMISSIONING_TWO_POSES' else len(self.targets),
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
        if not self.reusing_saved:
            # A new fit uses observations from this run. Optical signatures
            # from an earlier run/viewpoint cannot establish scene stability
            # here. Keep the passive baseline intact and independently compare
            # a second capture in verify_scene before validating/authorizing.
            return self.capture_run_reference(anchor)
        return self.node.scene_baseline, anchor.copy()

    def capture_run_reference(self, anchor):
        node = self.node
        gate = AuthoritativeBaselineAdmissionGate()
        deadline = time.monotonic() + node.settings['capture_timeout_s']
        node.passive_capture_active = True
        try:
            while True:
                node.automatic.checkpoint()
                now = time.monotonic()
                gate.update(node._authoritative_baseline_snapshot(), now)
                admission = gate.evaluate_for_baseline(now)
                node.automatic.update('PREPARING_BASELINE', baseline_readiness=admission,
                    reason='Measuring the scene at the current calibration viewpoint')
                if admission['accepted']:
                    break
                if now >= deadline:
                    raise CalibrationError('OBSERVATION_WARMUP_TIMEOUT: ' + admission['exact_gate'])
                node.stop.wait(.05)
            capture = node.capture()
            node.automatic.checkpoint()
            now = time.monotonic()
            gate.update(node._authoritative_baseline_snapshot(), now)
            admission = gate.evaluate_for_baseline(now)
            if not admission['accepted']:
                raise CalibrationError(admission['exact_gate'])
            distance, angle = pose_distance(anchor, capture.base_T_tool)
            if distance > .001 or angle > .3:
                raise CalibrationError('ROBOT_MOVED_SINCE_PLAN_VALIDATION')
            return node._scene_signature(capture), capture.base_T_tool.copy()
        finally:
            node.passive_capture_active = False

    def validate_start_pose(self, anchor):
        report = self.workspace.clearance_diagnostics(anchor, anchor, self.node.mount)
        report['current_xyz_mm'] = (anchor[:3, 3] * 1000).tolist()
        self.node.automatic.update('PREFLIGHT', start_pose_check=report)
        try:
            self.workspace.check_segment(anchor, anchor, self.node.mount)
        except CalibrationError as error:
            raise CalibrationError('START_POSE_OUTSIDE_WORKSPACE: ' + str(error)) from error

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
        # Check the pose of the acquired image too: capture may have waited
        # after the caller sampled current feedback.
        distance, angle = pose_distance(current, capture.base_T_tool)
        if distance > .002 or angle > .5:
            raise CalibrationError('SCENE_VERIFY_FAILED: reference viewpoint changed during capture')
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
        # Settling accepts a 2 mm position error. Plan at least 2 mm inside
        # the measured bounds instead of requiring exact boundary tracking.
        reserve = .002
        # Keep current-pose plans first. If none fit, translate a whole plan
        # into the surveyed volume. Smaller candidates must still satisfy the
        # original training/held-out excitation and independence thresholds.
        for translate in (False, True):
            for scale in ((1.0, .85, .75, .70) if translate else (1.0, .85)):
                for x_sign, z_sign in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                    targets = automatic_plan(anchor, x_sign=x_sign, z_sign=z_sign, scale=scale)
                    try:
                        if translate:
                            translated = self.workspace.translate_plan_into_volume(
                                targets, self.node.mount, reserve_m=reserve)
                            if scale in (1.0, .85) and all(
                                    np.array_equal(first, second) for first, second in zip(targets, translated)):
                                continue  # The unchanged plan was already rejected above.
                            targets = translated
                        for target in targets:
                            margins = self.workspace.clearance_diagnostics(
                                target, target, self.node.mount)['signed_margins_m']
                            if min(margins.values()) < reserve - 1e-12:
                                raise CalibrationError('AUTOMATIC_TARGET_TRACKING_RESERVE_REQUIRED')
                        # Synthetic poses are only for planned geometry checks;
                        # actual exposures are independently checked by solve.
                        planned = [SimpleNamespace(calibration_pose=p, base_T_carrier=None, stamp=i)
                                   for i, p in enumerate(targets)]
                        limits = getattr(self.node, 'limits', Limits())
                        excitation(planned[:7], limits)
                        excitation(planned[7:], limits, min_count=3)
                        for target in targets[7:]:
                            for training in targets[:7]:
                                distance, angle = pose_distance(target, training)
                                if distance < .008 and angle < 4:
                                    raise CalibrationError('Planned verification pose overlaps training data')
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
            raise RetryableCaptureError('Automatic image blur exceeds the capture limit')
        if any(distance < .004 and angle < 2 for distance, angle in
               (pose_distance(capture.calibration_pose, old.calibration_pose) for old in self.captures)):
            raise CalibrationError('Duplicate automatic observation')
        quality = {'status': 'ANCHOR'}
        if self.captures:
            try:
                quality = register(self.captures[-1], capture, self.node.limits, seed=index).quality
            except CalibrationError as error:
                if 'intrinsics/resolution' in str(error).lower():
                    raise
                raise RetryableCaptureError(str(error)) from error
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
        node = self.node
        candidate = self.store.session_dir / 'calibration_candidate.npz'
        if self.reusing_saved:
            node.automatic.update('VERIFYING')
            checkpoint()
            report = verify(self.saved_solution, self.saved_anchor, self.captures, node.mount, node.limits)
            if report['result'] != 'PASS':
                raise CalibrationError('Saved calibration live verification failed: ' + report['reason'])
            report['verification_poses'] = [capture.base_T_tool.tolist() for capture in self.captures]
            checkpoint()
            node.automatic.update('SAVING')
            save_bundle(candidate, self.saved_solution, self.saved_anchor, self.context, report, node.limits)
            restored, anchor = load_bundle(candidate, self.context, node.mount, node.limits)
            node.automatic.update('VERIFYING')
            reloaded = verify(restored, anchor, self.captures, node.mount, node.limits)
            if reloaded['result'] != 'PASS':
                raise CalibrationError('Saved calibration reload verification failed: ' + reloaded['reason'])
            result = {'state': 'CANDIDATE_VERIFIED', 'candidate_path': str(candidate),
                      'independent_verification': report, 'reload_verification': reloaded,
                      'production_ready': False, 'reused_saved': True}
        else:
            result = solve_session(self.captures, node.mount, self.context, candidate,
                                   node.limits, checkpoint, phase=node.automatic.update)
        result.update(source='automatic_real_captures', session_id=self.store.manifest['session_id'],
                      workspace_fingerprint=self.workspace.digest)
        return result

    def finalize(self, result, checkpoint):
        """Persist verified geometry; production admission still requires full live evidence."""
        node = self.node
        checkpoint()
        solution, anchor = load_bundle(result['candidate_path'], self.context, node.mount, node.limits)
        with np.load(result['candidate_path'], allow_pickle=False) as bundle:
            report = json.loads(str(bundle['metadata']))['verification']
        node.automatic.update('SAVING')
        checkpoint()
        save_bundle(node.settings['calibration_file'], solution, anchor, self.context, report, node.limits)
        restored, anchor = load_bundle(node.settings['calibration_file'], self.context, node.mount, node.limits)
        checkpoint()
        workflow = Workflow(node, node.mount, node.settings['calibration_file'], self.context, node.limits)
        workflow.solution, workflow.anchor, workflow.report = restored, anchor, report
        workflow.bundle_loaded = workflow.reload_verified = True
        workflow.samples_collected = workflow.samples_accepted = len(self.captures)
        result.update(saved_path=str(Path(node.settings['calibration_file']).expanduser()),
                      completed_unix_s=time.time())
        self.pending_result = (result, workflow)

    def persist_status(self, status):
        if self.store is not None and self.store.session_dir is not None:
            path = self.store.session_dir / 'automatic_audit.yaml'
            temporary = path.with_suffix('.tmp')
            temporary.write_text(yaml.safe_dump(status), encoding='utf-8')
            temporary.replace(path)

    def failed(self, reason):
        self.node.status('FAIL', reason)

    def stop(self):
        self.pending_result = None
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
            try:
                if (self.pending_result is not None and self.ptp_restore == 'PASS'
                        and not self.node.stop.is_set() and not self.node.automatic.abort_event.is_set()):
                    result, workflow = self.pending_result
                    error = (self.node.health_error()
                             or ('' if self.node.mount.rotation_seed_verified else 'MOUNT_ROTATION_UNVERIFIED')
                             or live_acceptance_error(workflow.report))
                    self.node.workflow = workflow
                    workflow.state = 'AWAITING_LIVE_VALIDATION' if error else 'READY'
                    workflow.verified_monotonic = None if error else time.monotonic()
                    result.update(state=workflow.state, production_ready=not bool(error), reason=error)
                    self.node.status(workflow.state, error)
                else:
                    self.node.status('UNCALIBRATED', 'Inspect automatic calibration result; production admission pending')
            finally:
                self.pending_result = None
                self.owned = False
                self.node.operation_lock.release()
