"""Single-owner guarded motion, readback and stop verification."""

from dataclasses import dataclass
import secrets

import numpy as np

from .safety import mock_geometry


@dataclass(frozen=True)
class Readback:
    stamp: float
    connected: bool = False
    alarm_valid: bool = False
    alarms: tuple = ()
    pose: tuple = (0., 0., 0., 0.)
    joints: tuple = (0., 0., 0., 0.)
    moving: bool = False


class MockTransport:
    """Independent interpolated pose and readback for offline operation."""

    def __init__(self, config):
        self.pose = np.asarray(config['observation'], dtype=float)
        self.travel = None
        self.connected = True
        self.alarms = ()
        self.ignore_stop = False
        self.readback_offset = np.zeros(4)
        self.commands = []

    def update(self, now):
        if self.connected and self.travel is not None:
            start, target, begin, finish = self.travel
            fraction = min(1., max(0., (now - begin) / (finish - begin)))
            self.pose = start + fraction * (target - start)
            if fraction == 1.:
                self.travel = None
        _, joints = mock_geometry(self.pose)
        return Readback(now, self.connected, self.connected, self.alarms,
                        tuple(self.pose + self.readback_offset), joints, self.travel is not None)

    def start(self, goal, speed, now):
        if self.travel is not None or not self.connected:
            raise RuntimeError('Mock controller unavailable or busy')
        target = np.asarray(goal)
        duration = max(0.04, np.linalg.norm(target[:3] - self.pose[:3]) / speed)
        self.travel = self.pose.copy(), target, now, now + duration
        self.commands.append(tuple(goal))

    def stop(self):
        if not self.ignore_stop and self.connected:
            self.travel = None


@dataclass
class Run:
    operation: str
    goal: tuple
    speed: float
    started: float
    stopped: bool = False
    stop_reason: str = ''
    stop_at: float = 0.
    still_since: float | None = None
    still_pose: tuple | None = None


@dataclass(frozen=True)
class Result:
    code: str
    reason: str
    pose: tuple
    stamp: float


class Motion:
    def __init__(self, config, safety, transport):
        self.config = config['motion']
        self.safety = safety
        self.transport = transport
        self.snapshot = Readback(0.)
        self.permit = None
        self.active = None
        self.result = None
        self.fault = False
        self.idle_pose = None

    def grant(self, operation, goal, speed, now):
        if self.permit or self.active or self.fault or self.transport is None:
            raise ValueError('Motion ownership unavailable')
        code = secrets.token_urlsafe(32)
        self.permit = (code, operation, tuple(goal), speed, now + self.config['timeout'])
        return code

    def authorized_goal(self, code, operation, goal, speed, now):
        return bool(self.permit and secrets.compare_digest(code, self.permit[0])
                    and (operation, tuple(goal), speed) == self.permit[1:4]
                    and now <= self.permit[4] and not self.active and not self.fault)

    def begin(self, code, operation, goal, speed, now, guard):
        if not self.authorized_goal(code, operation, goal, speed, now):
            return Result('rejected', 'Motion permit invalid or revoked', self.snapshot.pose, now)
        self.permit = None
        self.result = None
        try:
            guard(operation, now)
            if self.snapshot.moving:
                raise ValueError('Unexpected motion before command')
            self.safety.path(self.snapshot.pose, goal, speed, operation)
        except ValueError as error:
            return Result('rejected', str(error), self.snapshot.pose, now)
        self.active = Run(operation, tuple(goal), speed, now)
        try:
            self.transport.start(goal, speed, now)
        except RuntimeError:
            self.stop(now, 'Uncertain controller response', fault=True)
        return None

    def stop(self, now, reason, fault=False):
        self.permit = None
        if self.active is not None and not self.active.stopped:
            self.active.stopped = True
            self.active.stop_at = now
            self.active.stop_reason = reason
            self.active.still_since = None
            self.transport.stop()
        self.fault |= fault

    def close(self, code, reason, now):
        self.result = Result(code, reason, self.snapshot.pose, now)
        self.active = None
        self.fault |= code == 'fault'
        self.idle_pose = self.snapshot.pose

    def tick(self, now, guard):
        if self.transport is None:
            return
        self.snapshot = self.transport.update(now)
        run = self.active
        if run is None:
            if (self.snapshot.moving or (self.snapshot.connected and self.idle_pose is not None
                    and not self.pose_matches(self.snapshot.pose, self.idle_pose))):
                self.transport.stop()
                self.fault = True
            if self.snapshot.connected and self.idle_pose is None:
                self.idle_pose = self.snapshot.pose
            return
        snapshot = self.snapshot
        if not run.stopped:
            try:
                guard(run.operation, now)
                self.safety.path(snapshot.pose, run.goal, run.speed, run.operation)
                if now - run.started > self.config['timeout']:
                    raise ValueError('Motion timed out')
            except ValueError as error:
                self.stop(now, str(error), fault=True)
                return
        elif now - run.stop_at > self.config['timeout']:
            self.close('fault', 'Physical stop could not be verified in mock readback', now)
            return

        if snapshot.moving or not snapshot.connected or not snapshot.alarm_valid:
            run.still_since = None
            return
        if run.still_since is None or not self.pose_matches(snapshot.pose, run.still_pose):
            run.still_since = now
            run.still_pose = snapshot.pose
            return
        if now - run.still_since < self.config['settle_seconds']:
            return
        if run.stopped:
            self.close('fault' if self.fault else 'stopped', run.stop_reason, now)
        elif self.pose_matches(snapshot.pose, run.goal):
            self.close('ok', 'Settled pose verified', now)
        else:
            self.close('fault', 'TCP readback differs from commanded position', now)

    def pose_matches(self, pose, goal):
        return (np.linalg.norm(np.subtract(pose[:3], goal[:3]))
                <= self.config['position_tolerance_mm']
                and abs(pose[3] - goal[3]) <= self.config['rotation_tolerance_deg'])
