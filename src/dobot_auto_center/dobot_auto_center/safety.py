"""Fail-closed authorization and continuous swept-volume checks for the mock arm."""

from enum import Enum
import math

import numpy as np


class SafetyState(str, Enum):
    DISABLED = 'DISABLED'
    READY = 'READY'
    ACTIVE = 'ACTIVE'
    STOPPING = 'STOPPING'
    CENTERED = 'CENTERED'
    FAULT = 'FAULT'


def mock_geometry(pose):
    """Affine link model for the simulator, with points and synthetic joints."""
    x, y, z, r = pose
    shoulder = np.array([0., 0., 100.])
    elbow = np.array([0.48 * x, 0.48 * y, 165. + 0.25 * (z - 120.)])
    tcp = np.array([x, y, z])
    joints = (0.45 * y, 0.55 * (z - 120.), 70. + 0.65 * (x - 200.), r)
    return (shoulder, elbow, tcp), joints


class Safety:
    def __init__(self, config):
        self.hardware = config['hardware']
        self.config = config['safety']
        self.motion = config['motion']

    def health(self, snapshot, now):
        if (not snapshot.connected or not snapshot.alarm_valid
                or not 0 <= now - snapshot.stamp <= self.hardware['telemetry_timeout']):
            raise ValueError('Robot telemetry unavailable or stale')
        if snapshot.alarms:
            raise ValueError('Robot alarm active')
        if not all(map(math.isfinite, (*snapshot.pose, *snapshot.joints))):
            raise ValueError('Invalid TCP or joint telemetry')

    def gate(self, snapshot, now, *, authorized, rgbd, homed, operation, target_depth):
        if not self.hardware['simulation_mode']:
            raise ValueError('Motion is disabled in read-only mode')
        if not self.config['simulation_workcell_ready'] or not self.config['simulation_estop_available']:
            raise ValueError('Mock workcell or mock E-stop unavailable')
        if not authorized:
            raise ValueError('Operator lease expired')
        self.health(snapshot, now)
        if not rgbd:
            raise ValueError('Valid registered RGB-D required')
        if operation != 'home' and not homed:
            raise ValueError('HOME must be verified first')
        if operation == 'step' and (target_depth is None or not
                self.config['minimum_depth_m'] <= target_depth <= self.config['maximum_depth_m']):
            raise ValueError('Target depth outside the permitted range')
        if any(value < lo or value > hi for value, lo, hi in
               zip(snapshot.joints, self.config['joint_min_deg'], self.config['joint_max_deg'])):
            raise ValueError('Measured joint limit exceeded')

    def path(self, start, goal, speed, operation):
        config = self.config
        motion = self.motion
        start, goal = np.asarray(start), np.asarray(goal)
        if not np.isfinite(np.r_[start, goal, speed]).all() or not 0 < speed <= motion['max_speed_mm_s']:
            raise ValueError('Invalid motion target or speed')
        if operation == 'step' and not np.array_equal(start[2:], goal[2:]):
            raise ValueError('Auto Center requires fixed Z/R')
        maximum = motion['max_step_mm'] if operation == 'step' else motion['max_setup_travel_mm']
        if np.linalg.norm(goal[:3] - start[:3]) > maximum + 1e-8 or start[3] != goal[3]:
            raise ValueError('Motion distance or rotation limit exceeded')
        for pose in (start, goal):
            if np.any(pose[:3] < config['workspace_min_mm']) or np.any(
                    pose[:3] > config['workspace_max_mm']):
                raise ValueError('TCP workspace violation')
            _, joints = mock_geometry(pose)
            if np.any(np.asarray(joints) < config['joint_min_deg']) or np.any(
                    np.asarray(joints) > config['joint_max_deg']):
                raise ValueError('Path joint limit exceeded')

        # All link endpoints and joints are affine in TCP in this simulator.
        # Each link's complete sweep lies in the hull of its four endpoint
        # positions. The expanded AABB encloses that hull and link thickness.
        a, _ = mock_geometry(start)
        b, _ = mock_geometry(goal)
        radius = config['link_radius_mm']
        bodies = [([a[i], a[i+1], b[i], b[i+1]], radius) for i in range(2)]
        bodies.append(([a[-1], b[-1]], np.asarray(config['assembly_half_extent_mm'])))
        for points, extent in bodies:
            lower = np.min(points, axis=0) - extent
            upper = np.max(points, axis=0) + extent
            if lower[2] <= config['table_height_mm'] + config['clearance_mm']:
                raise ValueError('Swept envelope violates table clearance')
            for obstacle in config['obstacles_mm']:
                if np.all(upper >= obstacle[0]) and np.all(lower <= obstacle[1]):
                    raise ValueError('Swept envelope intersects an obstacle')
