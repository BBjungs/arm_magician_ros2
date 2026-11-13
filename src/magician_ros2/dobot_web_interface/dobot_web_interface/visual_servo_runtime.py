"""ROS/web transport for adaptive IBVS; all physical actions stay behind guards."""

import threading
import time
from pathlib import Path

import numpy as np
from ament_index_python.packages import get_package_share_directory
from dobot_msgs.action import PointToPoint
from dobot_msgs.srv import EvaluatePTPTrajectory

from dobot_vision_yolo.visual_servo_controller import (
    AdaptiveIBVS, Observation, SafeStop, ServoConfig, TargetTracker,
)


OWNER = 'visual_servo'


class VisualServoRuntime:
    def __init__(self, node, config_path=''):
        self.node = node
        path = config_path or str(Path(get_package_share_directory('dobot_vision_yolo'))
                                  / 'config' / 'visual_servo.yaml')
        self.config = ServoConfig.load(path)
        self.validator = node.create_client(
            EvaluatePTPTrajectory, 'dobot_visual_servo_validation_service')
        self.lock = threading.RLock()
        self.worker = None
        self.enabled_until = 0.
        self.controller = AdaptiveIBVS(self.config, self)
        self.tracker = TargetTracker(self.config)
        self.pause_requested = False
        self.uncertain_motion = False
        self.last_packet = None
        self.stop_reason = ''
        self.stop_generation = 0
        self.validated_at = float('-inf')

    @property
    def active(self):
        return self.worker is not None and self.worker.is_alive()

    def ros_now(self):
        return self.node.get_clock().now().nanoseconds / 1e9

    def robot(self, allow_motion=False):
        n, c, now = self.node, self.config, time.monotonic()
        with n._goal_lock:
            tcp = np.asarray(n._latest_tcp_pose, dtype=float)
            joints = np.asarray(n._latest_joints_deg, dtype=float)
            stamps = (n._latest_tcp_pose_time, n._latest_joints_time)
            busy = n._active_goal_handle is not None
            homed = n._homing_confirmed
        with n._integration_lock:
            alarms, alarm_time, fault = n._alarm_codes, n._alarm_time, n._system_fault
            startup = n._startup_action_active
        if (tcp.shape != (4,) or joints.shape != (4,)
                or not np.isfinite(np.r_[tcp, joints]).all()
                or any(s is None or not 0 <= now - s <= c.feedback_timeout_sec
                       for s in (*stamps, alarm_time))):
            raise SafeStop('Robot TCP/joint/alarm feedback is missing or stale')
        if alarms is None or alarms or not homed or fault:
            raise SafeStop('Robot alarm, missing HOME reference, or latched system fault')
        if startup or n._calibration_is_active():
            raise SafeStop('Startup/calibration owns motion')
        if busy and not allow_motion:
            raise SafeStop('A robot motion is still pending')
        if not n._safety().config.allow_real_motion:
            raise SafeStop('Workspace safety config does not authorize real motion')
        if not n._safety().config.workspace.contains(tcp):
            raise SafeStop('Current TCP is outside workspace')
        c.check_geometry(tcp, tcp)
        return tcp, stamps[0]

    def packet(self):
        n = self.node
        with n._vision_lock:
            packet = dict(n._vision_detections or {})
            received = n._vision_detections_time
        if received is None or not 0 <= time.monotonic() - received <= self.config.target_timeout_sec:
            raise SafeStop('RGB-D detection stream timed out')
        return packet

    def health(self, allow_motion=False, require_enable=True):
        n = self.node
        if require_enable:
            if time.monotonic() >= self.enabled_until:
                raise SafeStop('Operator enable expired')
            if n._vision_cancel_event.is_set() or n._operator_cancel_event.is_set():
                raise SafeStop(self.stop_reason or 'STOP/cancel requested')
            if n._control_snapshot()['owner'] != OWNER:
                raise SafeStop('Visual servo does not own robot control')
        tcp, stamp = self.robot(allow_motion=allow_motion)
        packet = self.packet()
        # During a motion the same frame may be seen multiple times. Its source
        # age still has to be fresh, and target association must remain unique.
        probe = TargetTracker(self.config)
        probe.previous = self.tracker.previous
        probe.source = self.tracker.source
        probe.select(packet, self.ros_now())
        return tcp, stamp

    def enable(self, payload):
        with self.lock:
            generation = self.stop_generation
            if self.active:
                raise RuntimeError('Approach is already active')
            if any(payload.get(key) is not True for key in
                   ('workspace_clear', 'estop_tested', 'assembly_envelope_confirmed')):
                raise ValueError('Confirm clear workspace, tested E-STOP and measured assembly envelope')
            if self.node._operation_is_active():
                raise RuntimeError('Another operation owns the robot')
            self.tracker = TargetTracker(self.config)
            self.health(require_enable=False)
            if not self.validator.service_is_ready() or not self.node.ptp_action.server_is_ready():
                raise RuntimeError('Strict trajectory validator or PTP action is unavailable')
            with self.node._control_lock:
                if generation != self.stop_generation:
                    raise SafeStop('STOP arrived during ENABLE')
                control = self.node._control_snapshot()
                if control['state'] != 'IDLE' or control['owner']:
                    raise SafeStop('Robot control is busy or faulted')
                self.enabled_until = time.monotonic() + self.config.enable_timeout_sec
                self.controller = AdaptiveIBVS(self.config, self)
                self.controller.transition('ENABLED')
            return {'accepted': True, 'motion_command_sent': False}

    def start(self):
        with self.lock:
            if self.active or time.monotonic() >= self.enabled_until:
                raise RuntimeError('Explicit ENABLE is required before START APPROACH')
            self.health(require_enable=False)
            with self.node._control_lock:
                if time.monotonic() >= self.enabled_until:
                    raise SafeStop('STOP or enable expiry arrived during START')
                ticket = self.node._begin_control_operation(OWNER)
            self.controller = AdaptiveIBVS(self.config, self)
            self.tracker = TargetTracker(self.config)
            self.pause_requested = False
            self.uncertain_motion = False
            self.stop_reason = ''
            self.worker = threading.Thread(target=self._run, args=(ticket,), daemon=True)
            self.worker.start()
            return {'accepted': True}

    def _run(self, ticket):
        try:
            if not self.node._mark_control_running(ticket):
                raise SafeStop('STOP arrived before START')
            self.controller.run()
        except Exception as exc:
            self.controller.reason = str(exc)
            self.controller.transition('SAFE_STOP')
            self.cancel()
        finally:
            self.enabled_until = 0.
            if self.uncertain_motion:
                self.node._fault_control_operation()
            if self.pause_requested and not self.uncertain_motion:
                self.controller.transition('PAUSED')
            self.node._finish_control_operation(ticket)

    def stop(self, pause=False, reason='Operator STOP'):
        # Never wait on the worker's lock or on a pending send_goal response.
        with self.node._control_lock:
            self.stop_generation += 1
            self.enabled_until = 0.
            self.pause_requested = pause
            self.stop_reason = reason
            self.node._request_control_stop()
        self.cancel()
        self.node._acknowledge_control_stop()
        if not self.active:
            self.controller.reason = reason
            self.controller.transition('PAUSED' if pause else 'STOP')
        return {'requested': True, 'message': 'Pause/stop requested; enable again to restart'}

    def cancel(self):
        n = self.node
        n._vision_cancel_event.set()
        with n._goal_lock:
            handle = n._active_goal_handle
        if handle is not None:
            try:
                handle.cancel_goal_async()
            except Exception:
                self.uncertain_motion = True
                n._fault_control_operation()

    def shutdown(self):
        # Keep ROS spinning until cancellation/result callbacks can complete.
        self.stop(reason='Web interface shutdown')
        worker = self.worker
        if worker is not None:
            worker.join(timeout=self.config.motion_timeout_sec + 3.)
            if worker.is_alive():
                self.uncertain_motion = True
                self.node._fault_control_operation()

    def observe(self, after_stamp):
        # A median across three *post-settle* frames; never mix pre/post-motion
        # depths in a rolling filter, which would corrupt the learned Jacobian.
        deadline = time.monotonic() + self.config.target_timeout_sec
        values, poses = [], []
        prior_stamps = self.tracker.stamps
        while time.monotonic() < deadline:
            tcp, pose_received = self.health()
            packet = self.packet()
            rgb, depth = packet.get('rgb_stamp', 0.), packet.get('depth_stamp', 0.)
            if rgb <= max(after_stamp, prior_stamps[0]) or depth <= max(after_stamp, prior_stamps[1]):
                time.sleep(.01)
                continue
            # Require a new robot feedback sample for every stationary RGB-D frame.
            if poses and pose_received <= poses[-1][1]:
                time.sleep(.01)
                continue
            value = self.tracker.select(packet, self.ros_now(), after_stamp)
            values.append(value)
            poses.append((tcp, pose_received))
            self.last_packet = packet
            prior_stamps = self.tracker.stamps
            if np.max(np.ptp(np.array([p[0] for p in poses]), axis=0)) > .1:
                raise SafeStop('TCP is not stationary while sampling RGB-D')
            if len(values) >= self.config.stationary_samples:
                features = np.array([v[0] for v in values])
                if np.any(np.ptp(features, axis=0) > np.array([2., 2., 2.])):
                    raise SafeStop('Target/depth is unstable while robot is stationary')
                latest = values[-1]
                return Observation(np.median(features, axis=0), latest[1], tcp,
                                   latest[4], latest[5], latest[2], latest[3])
            time.sleep(.01)
        raise SafeStop('No fresh stationary RGB-D batch after motion')

    def check(self, observation, target):
        current, _ = self.health()
        if np.linalg.norm(current - observation.tcp) > .15:
            raise SafeStop('TCP changed since observation')
        if (self.ros_now() - min(observation.rgb_stamp, observation.depth_stamp)
                > self.config.target_timeout_sec):
            raise SafeStop('Observation expired before path validation')
        self.config.check_geometry(current, target)
        if not self.node._safety().config.workspace.contains(target):
            raise SafeStop('Target outside existing workspace limits')
        if not self.validator.service_is_ready():
            raise SafeStop('Strict trajectory/collision validation unavailable')
        request = EvaluatePTPTrajectory.Request()
        request.target = [float(v) for v in target]
        request.motion_type = 2
        result = self.node._wait_for_future(self.validator.call_async(request), 2.)
        if not result.is_valid:
            raise SafeStop('Trajectory/collision rejected: ' + result.message)
        self.health()
        self.validated_target = np.array(target, dtype=float)
        self.validated_start = current.copy()
        self.validated_at = time.monotonic()

    def move(self, target, velocity, acceleration):
        n = self.node
        current, _ = self.health()
        admission_checked_at = time.monotonic()
        validation_time = self.validated_at
        if (time.monotonic() - self.validated_at > .3
                or not np.array_equal(target, self.validated_target)
                or np.linalg.norm(current - self.validated_start) > .15):
            raise SafeStop('Path validation expired or robot moved before dispatch')
        self.validated_at = float('-inf')  # A validation authorizes one dispatch only.
        if (not np.isfinite([velocity, acceleration]).all()
                or not .01 <= velocity <= self.config.velocity_ratio
                or not .01 <= acceleration <= self.config.acceleration_ratio):
            raise SafeStop('Invalid visual servo speed limits')
        goal = PointToPoint.Goal()
        goal.motion_type = 2
        goal.target_pose = [float(v) for v in target]
        goal.velocity_ratio, goal.acceleration_ratio = float(velocity), float(acceleration)
        # Serialize dispatch with the shared STOP flag. A late acceptance is
        # cancelled by the callback below, even if send_goal times out.
        abandoned = threading.Event()
        with n._control_lock:
            # Health was checked immediately above. Do not acquire telemetry or
            # job locks under the control lock: status/startup can take those in
            # the opposite order. Only the atomic STOP/ownership gate lives here.
            if (time.monotonic() - admission_checked_at > .05
                    or time.monotonic() - validation_time > .3
                    or time.monotonic() >= self.enabled_until
                    or n._vision_cancel_event.is_set() or n._operator_cancel_event.is_set()
                    or n._control_snapshot()['owner'] != OWNER):
                raise SafeStop('STOP, enable expiry or ownership loss before dispatch')
            generation = self.stop_generation
            self.uncertain_motion = True
            future = n.ptp_action.send_goal_async(goal)

        def accepted(done):
            try:
                handle = done.result()
            except Exception:
                self.uncertain_motion = True
                n._fault_control_operation()
                return
            if handle.accepted:
                with n._goal_lock:
                    n._active_goal_handle = handle
                if (abandoned.is_set() or generation != self.stop_generation
                        or n._vision_cancel_event.is_set() or time.monotonic() >= self.enabled_until):
                    self.cancel()

        future.add_done_callback(accepted)
        try:
            handle = n._wait_for_future(future, 3.)
        except Exception:
            abandoned.set()
            self.uncertain_motion = True
            self.cancel()
            raise
        if not handle.accepted:
            self.uncertain_motion = False
            raise SafeStop('PTP server rejected the guarded MOVL')
        # Do not rely on ordering between the future's callbacks and the waiting
        # thread: STOP must see the handle before the first motion health check.
        with n._goal_lock:
            n._active_goal_handle = handle
        self.uncertain_motion = True
        with n._integration_lock:
            n._observation_confirmed = False
        result_future = handle.get_result_async()
        deadline = time.monotonic() + self.config.motion_timeout_sec
        failure = None
        while not result_future.done() and time.monotonic() < deadline:
            try:
                self.health(allow_motion=True)
            except Exception as exc:
                if failure is None:
                    failure = exc
                    handle.cancel_goal_async()
            time.sleep(.02)
        if not result_future.done():
            self.uncertain_motion = True
            handle.cancel_goal_async()
            raise SafeStop('Motion result timed out; control fault latched')
        result = result_future.result()
        if result.status not in (4, 5, 6):
            raise SafeStop('Motion result is not terminal; control fault latched')
        with n._goal_lock:
            n._active_goal_handle = None
        self.uncertain_motion = False
        if failure is not None:
            raise failure
        if result.status != 4:
            raise SafeStop(f'PTP did not succeed (status {result.status})')
        # Core checks measured TCP travel after three stationary frames.
        self.health()
        return self.ros_now()

    def status(self):
        result = self.controller.status()
        try:
            tcp, _ = self.robot(allow_motion=self.active)
            result.update(robot_state='MOVING/VERIFYING' if self.active else 'IDLE', tcp_pose=tcp.tolist())
            blocker = ''
        except Exception as exc:
            result['robot_state'] = 'NOT_READY'
            blocker = str(exc)
        try:
            packet = self.packet()
            tracker = TargetTracker(self.config)
            tracker.previous = self.tracker.previous
            tracker.source = self.tracker.source
            feature, reference, confidence, bbox, rgb, depth = tracker.select(packet, self.ros_now())
            result.update(pixel_error=(feature[:2] - reference).tolist(), depth_mm=float(feature[2]),
                          target_center=feature[:2].tolist(), reference=reference.tolist(),
                          confidence=confidence, bbox=bbox, rgb_stamp=rgb, depth_stamp=depth,
                          image_size=packet['image_size'])
        except Exception as exc:
            blocker = blocker or str(exc)
            result.update(pixel_error=None, depth_mm=None, bbox=None, target_center=None)
        result.update(active=self.active, enabled=time.monotonic() < self.enabled_until,
                      enable_remaining_sec=max(0., self.enabled_until - time.monotonic()),
                      control=self.node._control_snapshot(),
                      blocker=blocker, calibration_required=False, grasp_enabled=False)
        return result
