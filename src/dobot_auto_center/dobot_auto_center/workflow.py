"""Operator workflow and closed-loop look-and-move sequencing."""

from collections import deque
from enum import Enum

import numpy as np

from .safety import SafetyState
from .vision import Tracker, make_detector, select_roi
from .visual_servo import VisualServo


class State(str, Enum):
    DISCONNECTED = 'DISCONNECTED'
    CONNECTING = 'CONNECTING'
    IDLE = 'IDLE'
    HOMING = 'HOMING'
    READY = 'READY'
    DETECTING = 'DETECTING'
    TARGET_LOCKED = 'TARGET_LOCKED'
    CENTERING = 'CENTERING'
    CENTERED = 'CENTERED'
    STOPPING = 'STOPPING'
    STOPPED = 'STOPPED'
    FAULT = 'FAULT'


class Workflow:
    def __init__(self, config, motion, submit, lease_valid):
        self.config = config
        self.motion = motion
        self.submit = submit
        self.lease_valid = lease_valid
        self.detector = make_detector(config['vision'])
        self.tracker = Tracker(config['vision'])
        self.servo = VisualServo(config['visual_servo'])
        self.state = State.CONNECTING
        self.diagnostic = 'Waiting for telemetry'
        self.camera_on = False
        self.detecting = False
        self.homed = False
        self.at_observation = False
        self.frame = None
        self.frame_id = 0
        self.history = deque(maxlen=90)
        self.images = deque(maxlen=8)
        self.detections = []
        self.target = None
        self.target_id = 0
        self.target_owner = None
        self.run_owner = None
        self.pending = None
        self.operation = None
        self.probe = None
        self.last_processed = 0
        self.measure_after = 0.
        self.started_at = 0.
        self.anchor = None

    def ingest(self, observation, now):
        if not self.camera_on:
            return
        if self.frame is not None and observation.stamp <= self.frame.stamp:
            return
        self.frame = observation
        self.frame_id += 1
        self.images.append((self.frame_id, observation.rgb))
        self.detections = self.detector.detect(observation) if self.detecting else []
        self.history.append((self.frame_id, observation.stamp, self.detections))
        if self.target is not None:
            self.target = self.tracker.update(self.detections)
            if self.target is None:
                if self.state == State.CENTERING:
                    self.stop(now, 'Target lost or identity ambiguous')
                elif self.state == State.TARGET_LOCKED:
                    self.state = State.DETECTING
                    self.diagnostic = 'Target lost or identity ambiguous. Select a new ROI'

    def rgbd(self, now):
        return self.camera_on and self.frame is not None and self.frame.registered(now, self.config['camera'])

    def guard(self, operation, now):
        self.motion.safety.gate(
            self.motion.snapshot, now, authorized=self.lease_valid(self.run_owner, now),
            rgbd=self.rgbd(now), homed=self.homed, operation=operation,
            target_depth=self.target.depth if self.target else None)
        if operation == 'step' and self.state != State.CENTERING:
            raise ValueError('Visual servo is inactive')
        if operation == 'step' and not self.motion.pose_matches(
                (0., 0., *self.motion.snapshot.pose[2:]), (0., 0., *self.anchor[2:])):
            raise ValueError('Measured Z/R drifted during centering')

    def transition(self, state, text):
        self.state = state
        self.diagnostic = text

    def clear_target(self):
        self.tracker.reset()
        self.target = None
        self.target_owner = None

    def command(self, command, data, owner, now):
        if command == 'camera':
            self.camera_on = True
            return
        if self.motion.fault or self.state == State.FAULT:
            raise ValueError('Inspect the fault before restarting the controller')
        if self.pending or self.state in (State.CENTERING, State.STOPPING, State.HOMING):
            raise ValueError('An operation is already active')
        if command == 'home':
            self.issue_setup('home', owner, now)
        elif command == 'observation':
            if self.state != State.READY or not self.homed or self.at_observation:
                raise ValueError('Verified HOME is required before observation')
            self.issue_setup('observation', owner, now)
        elif command == 'detect':
            if self.config['hardware']['simulation_mode'] and not self.at_observation:
                raise ValueError('Move to the observation pose first')
            if not self.rgbd(now):
                raise ValueError('Camera RGB-D is unavailable')
            self.detecting = True
            self.history.clear()
            self.clear_target()
            self.transition(State.DETECTING, 'Select a target with an image ROI')
        elif command == 'select':
            if self.state not in (State.DETECTING, State.TARGET_LOCKED, State.CENTERED, State.STOPPED):
                raise ValueError('Start detection first')
            if not self.rgbd(now) or not self.detecting:
                raise ValueError('Selection frame expired')
            frames = [entry for entry in self.history if entry[0] >= data.get('frame_id', -1)]
            if (not frames or frames[0][0] != data.get('frame_id')
                    or now - frames[0][1] > self.config['camera']['selection_history_seconds']):
                raise ValueError('Selection frame expired')
            selection = Tracker(self.config['vision'])
            selection.lock(select_roi(frames[0][2], data.get('roi', ()),
                                      self.frame.rgb.shape[1], self.frame.rgb.shape[0]))
            if any(selection.update(entry[2]) is None for entry in frames[1:]):
                raise ValueError('Selected object identity changed during selection')
            self.target = selection.target
            self.target_owner = owner
            self.target_id += 1
            self.tracker.lock(self.target)
            self.transition(State.TARGET_LOCKED, 'Target locked for this session')
        elif command == 'center':
            if (self.state != State.TARGET_LOCKED or self.target is None
                    or self.target_owner != owner or not self.at_observation):
                raise ValueError('Select and lock a target in this control session')
            self.run_owner = owner
            self.servo.reset()
            self.probe = None
            self.anchor = self.motion.snapshot.pose
            self.started_at = now
            self.measure_after = now
            self.transition(State.CENTERING, 'Waiting for a new stationary observation')
            try:
                self.guard('step', now)
                if self.motion.fault or self.motion.snapshot.moving:
                    raise ValueError('Robot is not verified stationary')
            except ValueError:
                self.transition(State.TARGET_LOCKED, 'Centering authorization declined')
                raise
        else:
            raise ValueError('Unknown operation')

    def issue_setup(self, operation, owner, now):
        self.run_owner = owner
        self.guard(operation, now)
        self.issue(operation, self.config['motion'][operation], now)
        self.detecting = False
        self.clear_target()
        self.at_observation = False
        if operation == 'home':
            self.homed = False
        self.transition(State.HOMING if operation == 'home' else State.READY,
                        'Verifying HOME' if operation == 'home' else 'Moving to observation pose')

    def issue(self, operation, goal, now):
        if self.pending is not None:
            raise ValueError('Previous action still outstanding')
        speed = self.config['motion']['speed_mm_s']
        self.motion.safety.path(self.motion.snapshot.pose, goal, speed, operation)
        code = self.motion.grant(operation, goal, speed, now)
        self.operation = operation
        try:
            self.pending = self.submit(code, operation, goal, speed, now)
        except RuntimeError as error:
            self.motion.stop(now, 'Action submission could not be verified', fault=True)
            raise ValueError('Action server unavailable') from error

    def stop(self, now, reason='Operator STOP', fault=False):
        self.motion.stop(now, reason, fault=fault)
        self.clear_target()
        self.probe = None
        if self.pending:
            if self.operation != 'step':
                self.homed = self.at_observation = False
            self.pending.cancel()
            self.transition(State.STOPPING, reason)
        else:
            self.transition(State.FAULT if self.motion.fault else State.STOPPED, reason)

    def tick(self, now):
        self.motion.tick(now, self.guard)
        if self.pending:
            if self.state != State.STOPPING and not self.lease_valid(self.run_owner, now):
                self.stop(now, 'Browser control lease expired')
            if self.state != State.STOPPING:
                try:
                    self.guard(self.operation, now)
                    if self.operation == 'step' and now - self.started_at > self.config['visual_servo']['maximum_duration']:
                        raise ValueError('Centering session timed out')
                except ValueError as error:
                    self.stop(now, str(error), fault=True)
            result = self.pending.poll(now)
            if result is None:
                return
            self.pending = None
            if self.state == State.STOPPING:
                fault = self.motion.fault or result.code == 'fault'
                reason = result.reason if result.code == 'fault' else self.diagnostic
                self.transition(State.FAULT if fault else State.STOPPED, reason)
                return
            if result.code != 'ok':
                self.stop(now, result.reason, fault=result.code == 'fault')
                return
            self.measure_after = result.stamp
            if self.operation in ('home', 'observation'):
                self.homed = True
                self.at_observation = self.operation == 'observation'
                self.transition(State.READY, 'Observation pose verified' if self.at_observation
                                else 'HOME verified. Confirm the separate observation move')
                return
        if self.motion.fault:
            if self.state != State.FAULT:
                self.stop(now, 'Controller state requires inspection', fault=True)
            return
        try:
            self.motion.safety.health(self.motion.snapshot, now)
        except ValueError as error:
            if self.state == State.CENTERING:
                self.stop(now, str(error), fault=True)
            elif self.state != State.FAULT:
                self.homed = self.at_observation = self.detecting = False
                self.clear_target()
                self.transition(State.DISCONNECTED, str(error))
            return
        if self.state in (State.CONNECTING, State.DISCONNECTED):
            self.transition(State.IDLE, 'Robot telemetry available')
        if self.state == State.TARGET_LOCKED and not self.lease_valid(self.target_owner, now):
            self.clear_target()
            self.transition(State.DETECTING, 'Control lease expired. Select the target again')
        if self.state == State.CENTERING:
            try:
                if now - self.started_at > self.config['visual_servo']['maximum_duration']:
                    raise ValueError('Centering session timed out')
                self.guard('step', now)
                self.measure(now)
            except (ValueError, np.linalg.LinAlgError) as error:
                self.stop(now, str(error), fault=self.motion.fault)

    def measure(self, now):
        if (self.frame_id == self.last_processed or self.frame.stamp <= self.measure_after
                or self.motion.snapshot.moving):
            return
        self.last_processed = self.frame_id
        width, height = self.frame.rgb.shape[1], self.frame.rgb.shape[0]
        error = self.target.error(width, height)
        pose = self.motion.snapshot.pose
        control = self.config['visual_servo']
        servo = self.servo
        if self.probe is not None:
            before_pose, before_error = self.probe
            servo.record_probe(before_pose, pose, before_error, error)
            self.probe = None
        if max(map(abs, error)) <= control['tolerance_pixels']:
            servo.stable += 1
            if servo.stable >= control['stable_frames']:
                self.transition(State.CENTERED, 'Target centered. Robot holding position')
            return
        servo.stable = 0
        if servo.jacobian is None:
            delta = np.zeros(2)
            delta[len(servo.samples)] = control['probe_mm']
            self.probe = (pose, error)
        else:
            servo.note_correction(error)
            if servo.corrections >= control['maximum_corrections']:
                raise ValueError('Correction attempts exhausted')
            servo.corrections += 1
            delta = servo.step(error, self.config['motion']['max_step_mm'])
        goal = (*tuple(np.asarray(pose[:2]) + delta), *pose[2:])
        if np.linalg.norm(np.subtract(goal[:2], self.anchor[:2])) > control['maximum_xy_excursion_mm']:
            raise ValueError('Correction would leave the local identification region')
        self.issue('step', goal, now)

    def status(self, now):
        snapshot = self.motion.snapshot
        if self.state in (State.HOMING, State.CENTERING) or self.pending:
            safety_state = SafetyState.ACTIVE
        elif self.config['hardware']['simulation_mode'] and self.homed:
            safety_state = SafetyState.READY
        else:
            safety_state = SafetyState.DISABLED
        safety_state = {'FAULT': SafetyState.FAULT, 'STOPPING': SafetyState.STOPPING,
                        'CENTERED': SafetyState.CENTERED}.get(self.state, safety_state)
        camera = self.config['camera']
        target = self.target
        telemetry_fresh = 0 <= now - snapshot.stamp <= self.config['hardware']['telemetry_timeout']
        return {
            'state': self.state, 'safety': safety_state, 'diagnostic': self.diagnostic,
            'simulation': self.config['hardware']['simulation_mode'],
            'connected': snapshot.connected and telemetry_fresh,
            'tcp': snapshot.pose, 'joints': snapshot.joints,
            'alarms': snapshot.alarms, 'alarm_valid': snapshot.alarm_valid and telemetry_fresh,
            'homed': self.homed, 'observation_pose': self.at_observation,
            'detecting': self.detecting, 'motion': ('MOVING' if snapshot.moving else
                'VERIFYING' if self.pending else 'HOLDING' if self.config['hardware']['simulation_mode']
                and snapshot.connected and not self.motion.fault else 'UNKNOWN'),
            'camera': bool(self.camera_on and self.frame and self.frame.fresh(now, camera['freshness'])),
            'depth': bool(self.rgbd(now)), 'frame_id': self.frame_id,
            'width': camera['width'], 'height': camera['height'],
            'detections': [{'box': d.box, 'center': d.center, 'confidence': d.confidence,
                            'depth_m': d.depth} for d in self.detections],
            'target': target.center if target else None,
            'target_depth_m': target.depth if target else None,
            'error': target.error(camera['width'], camera['height']) if target else None,
            'target_id': self.target_id if target else None,
            'stable_frames': self.servo.stable, 'stable_frames_required': self.config['visual_servo']['stable_frames'],
            'corrections': self.servo.corrections,
        }
