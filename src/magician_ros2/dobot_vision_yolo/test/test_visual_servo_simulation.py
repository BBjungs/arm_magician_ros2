"""Deterministic closed-loop RGB-D simulation; no ROS node or hardware access.

The simulated pinhole camera knows its orientation. The controller receives only
image/depth observations and measured TCP poses, never this camera transform.
"""
from dataclasses import replace

import numpy as np
import pytest

from dobot_vision_yolo.visual_servo_controller import AdaptiveIBVS, Observation, SafeStop, ServoConfig


class CameraSimulation:
    def __init__(self, rotation=None, fault=None):
        self.rotation = np.eye(3) if rotation is None else rotation
        self.origin = np.array([220., 0., 160., 0.])
        self.tcp = self.origin.copy()
        self.target = np.array([14., -9., 245.])
        self.time = 10.
        self.commands = []
        self.observations = []
        self.checks = []
        self.cancelled = False
        self.fault = fault
        self.config = replace(ServoConfig(), geometry_confirmed=True, assembly_radius_mm=20.,
                              free_volume_min_mm=[100., -150., 0.],
                              free_volume_max_mm=[400., 150., 400.])

    def observe(self, after_stamp):
        self.time = max(self.time + .1, after_stamp + .1)
        xyz = self.target - self.rotation @ (self.tcp[:3] - self.origin[:3])
        feature = np.r_[np.array([320., 240.]) + 500. * xyz[:2] / xyz[2], xyz[2]]
        if self.fault == 'no_response':
            feature = np.array([340., 250., 245.])
        if self.fault == 'no_depth_response':
            feature[2] = 245.
        if self.fault == 'target_lost' and self.commands:
            raise SafeStop('Target lost')
        if self.fault == 'direction_changed' and len(self.commands) > 3:
            feature[:2] += [50., 50.]
        if (self.fault == 'depth_reversed' and len(self.commands) > 3
                and np.max(np.abs(self.observations[-1].feature[:2] - [320., 240.])) <= 8):
            feature[2] = self.observations[-1].feature[2] + 1.
        stamp = after_stamp if self.fault == 'stale' and self.commands else self.time
        tcp = self.origin.copy() if self.fault == 'bad_feedback' else self.tcp.copy()
        obs = Observation(feature, np.array([320., 240.]), tcp, stamp, stamp,
                          .95, [300., 220., 340., 260.])
        self.observations.append(obs)
        return obs

    def check(self, observation, target):
        self.config.check_geometry(observation.tcp, target)
        if self.fault == 'collision' and len(self.commands) == 1:
            raise SafeStop('Trajectory/collision rejected')
        if self.fault == 'stop' and len(self.commands) == 1:
            raise SafeStop('Operator STOP')
        self.checks.append(target.copy())

    def move(self, target, velocity, acceleration):
        assert not self.cancelled
        np.testing.assert_array_equal(target, self.checks[-1])
        assert velocity <= .1 and acceleration <= .1
        assert np.linalg.norm(target[:3] - self.tcp[:3]) <= 3.000001
        assert target[3] == self.tcp[3]
        self.commands.append(target.copy())
        self.tcp = self.tcp + .9 * (target - self.tcp) if self.fault == 'partial_move' else target.copy()
        self.time += .05
        return self.time

    def cancel(self):
        self.cancelled = True


def rotation(seed):
    # Uniform orthonormal orientations, including optical axes along -X/-Y.
    q, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q[:, 0] *= np.linalg.det(q)
    return q


@pytest.mark.parametrize('seed', range(12))
def test_unknown_camera_orientation_converges_without_extrinsics(seed):
    sim = CameraSimulation(rotation(seed))
    controller = AdaptiveIBVS(sim.config, sim)
    controller.run()
    assert controller.state == 'STOP', controller.reason
    assert not sim.cancelled
    assert len(sim.commands) <= 80
    assert controller.model_updates > 0
    assert np.max(np.abs(controller.latest.feature[:2] - controller.latest.reference)) <= 8
    assert 200 <= controller.latest.feature[2] <= 202
    assert min(o.feature[2] for o in sim.observations) >= 200
    assert {'DETECT', 'DEPTH', 'CHECK', 'LEARN', 'ALIGN', 'VERIFY', 'APPROACH', 'STOP'} <= set(controller.history)
    # A known simulator orientation is used only for this independent assertion.
    assert np.dot(controller.direction, sim.rotation[2]) > .95


@pytest.mark.parametrize('fault,max_commands', [('collision', 1), ('stop', 1),
    ('no_response', 1), ('no_depth_response', 3), ('bad_feedback', 1),
    ('target_lost', 1), ('stale', 1), ('direction_changed', 4)])
def test_failure_stops_without_guessing_reverse_motion(fault, max_commands):
    sim = CameraSimulation(fault=fault)
    controller = AdaptiveIBVS(sim.config, sim)
    controller.run()
    assert controller.state == 'SAFE_STOP'
    assert sim.cancelled
    assert len(sim.commands) <= max_commands
    assert controller.reason


def test_already_at_stop_distance_sends_no_probe():
    sim = CameraSimulation()
    sim.target[2] = 201.
    controller = AdaptiveIBVS(sim.config, sim)
    controller.run()
    assert controller.state == 'STOP'
    assert not sim.commands


def test_iteration_budget_is_enforced():
    sim = CameraSimulation()
    controller = AdaptiveIBVS(replace(sim.config, max_iterations=4), sim)
    controller.run()
    assert controller.state == 'SAFE_STOP'
    assert 'budget' in controller.reason
    assert len(sim.commands) == 4


def test_learning_uses_measured_tcp_displacement_instead_of_command_size():
    sim = CameraSimulation(rotation(3), fault='partial_move')
    controller = AdaptiveIBVS(sim.config, sim)
    controller.run()
    assert controller.state == 'STOP', controller.reason
    assert np.dot(controller.direction, sim.rotation[2]) > .95
    assert 200 <= controller.latest.feature[2] <= 202


def test_approach_stops_when_observed_depth_increases():
    sim = CameraSimulation(fault='depth_reversed')
    controller = AdaptiveIBVS(sim.config, sim)
    controller.run()
    assert controller.state == 'SAFE_STOP'
    assert 'APPROACH' in controller.history
    assert sim.cancelled
