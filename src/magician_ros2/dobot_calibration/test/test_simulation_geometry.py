"""Offline audit regressions; no ROS node, service or action is created."""
import importlib.util
from pathlib import Path

import numpy as np
import pybullet as pb
import pytest

spec = importlib.util.spec_from_file_location('simulation_geometry',
    Path(__file__).resolve().parents[4] / 'scripts/simulate_calibration_geometry.py')
simulation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulation)


def test_stationary_translation_still_samples_yaw_sweep():
    start = np.array([190., 0., 85., 170.])
    target = np.array([190., 0., 85., -170.])
    points = np.array(list(simulation.samples(start, target, 2., 2.)))
    assert len(points) == 11
    np.testing.assert_allclose(points[:, :3], np.tile(start[:3], (11, 1)))
    assert points[-1, 3] == pytest.approx(190.)
    assert np.max(np.abs(np.diff(points[:, 3]))) <= 2.


def test_movl_samples_include_both_endpoints_and_bound_step():
    start = np.array([190., 0., 85., 0.])
    target = np.array([225., 15., 100., 20.])
    points = np.array(list(simulation.samples(start, target, 2., 2.)))
    np.testing.assert_allclose(points[0], start)
    np.testing.assert_allclose(points[-1], target)
    assert np.max(np.linalg.norm(np.diff(points[:, :3], axis=0), axis=1)) <= 2. + 1e-10
    assert np.max(np.abs(np.diff(points[:, 3]))) <= 2. + 1e-10


def test_real_scenario_rejected_before_connecting(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('A non-simulation scenario must not connect')
    monkeypatch.setattr(pb, 'connect', forbidden)
    with pytest.raises(ValueError, match='Only simulation'):
        simulation.run({'simulation_only': False})


def test_distance_query_preserves_separation_and_penetration_sign():
    client = pb.connect(pb.DIRECT)
    try:
        box = pb.createCollisionShape(pb.GEOM_BOX, halfExtents=[.01, .01, .01], physicsClientId=client)
        body = pb.createMultiBody(baseMass=0, baseCollisionShapeIndex=box,
                                  basePosition=[0, 0, .03], physicsClientId=client)
        plane = pb.createCollisionShape(pb.GEOM_PLANE, planeNormal=[0, 0, 1], physicsClientId=client)
        table = pb.createMultiBody(baseMass=0, baseCollisionShapeIndex=plane, physicsClientId=client)
        assert simulation.closest(client, body, table, -1, -1) == pytest.approx(20., abs=.001)
        pb.resetBasePositionAndOrientation(table, [0, 0, .04], [0, 0, 0, 1], physicsClientId=client)
        assert simulation.closest(client, body, table, -1, -1) == pytest.approx(-20., abs=.001)
    finally:
        pb.disconnect(client)
