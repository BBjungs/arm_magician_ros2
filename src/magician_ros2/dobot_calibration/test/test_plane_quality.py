"""Deterministic geometry, real voxel filtering and RANSAC; no ROS or motion."""

from dataclasses import replace
import json

import numpy as np
import pytest

from dobot_calibration.geometry import (
    CalibrationError, Limits, finite_cloud, scene_geometry, table_plane,
)
from dobot_calibration.registration import dominant_plane, make_capture


def cloud_with_plane(count, total=1000):
    rng = np.random.default_rng(42)
    xx, yy = np.meshgrid(np.linspace(-.5, .5, 60), np.linspace(-.5, .5, 60))
    xy = np.column_stack((xx.ravel(), yy.ravel()))
    plane = np.column_stack((xy[rng.choice(len(xy), count, replace=False)],
                             np.full(count, 0.4)))
    clutter = rng.uniform([-1., -1., 0.7], [1., 1., 1.4], (total - count, 3))
    points = np.vstack((plane, clutter))
    # The tested ratio is AFTER finite/depth/voxel filtering, as in production.
    assert len(finite_cloud(points)) == total
    return points


@pytest.mark.parametrize('count,accepted', [(249, False), (250, True), (280, True), (300, True)])
@pytest.mark.parametrize('gate', [dominant_plane, table_plane])
def test_ratio_boundary(count, accepted, gate):
    points = cloud_with_plane(count)
    args = (points,) if gate is dominant_plane else (points, [0., 0., -1.])
    if accepted:
        plane, quality = gate(*args)
        assert abs(plane[2]) == pytest.approx(1.)
        assert abs(plane[3]) == pytest.approx(0.4)
        assert quality['plane_rejection_reason'] == ''
    else:
        with pytest.raises(CalibrationError, match='No sufficiently supported') as caught:
            gate(*args)
        quality = caught.value.diagnostics
        assert quality['plane_rejection_reason'] == str(caught.value)
    assert quality['plane_inlier_count'] == count
    assert quality['plane_inlier_ratio'] == count / 1000
    assert quality['min_plane_ratio'] == 0.25
    assert quality['plane_rms_m'] < 1e-12
    assert quality['plane_table_identity'] == 'UNVERIFIED'
    json.dumps(quality, allow_nan=False)


def test_explicit_threshold_override_remains_effective():
    with pytest.raises(CalibrationError, match='supported') as caught:
        dominant_plane(cloud_with_plane(280), replace(Limits(), min_plane_ratio=0.30))
    assert caught.value.diagnostics['min_plane_ratio'] == 0.30


@pytest.mark.parametrize('gate', [dominant_plane, table_plane])
def test_passing_ratio_does_not_bypass_minimum_inlier_count(gate):
    points = cloud_with_plane(199, total=600)
    args = (points,) if gate is dominant_plane else (points, [0., 0., -1.])
    with pytest.raises(CalibrationError, match='supported') as caught:
        gate(*args)
    assert caught.value.diagnostics['plane_inlier_ratio'] >= 0.25
    assert caught.value.diagnostics['plane_inlier_count'] == 199


@pytest.mark.parametrize('gate', [dominant_plane, table_plane])
def test_passing_ratio_does_not_bypass_spatial_extent(gate):
    rng = np.random.default_rng(7)
    points = np.column_stack((np.linspace(-0.8, 0.8, 400),
                              rng.uniform(-0.001, 0.001, 400), np.full(400, 0.4)))
    args = (points,) if gate is dominant_plane else (points, [0., 0., -1.])
    with pytest.raises(CalibrationError, match='extent') as caught:
        gate(*args)
    assert caught.value.diagnostics['plane_inlier_ratio'] == 1.0


def test_flat_scene_still_fails_scene_quality_despite_supported_plane():
    points = cloud_with_plane(1000)
    assert dominant_plane(points)[1]['plane_inlier_ratio'] == 1.
    with pytest.raises(CalibrationError, match='flat, narrow or featureless'):
        scene_geometry(points)


@pytest.mark.parametrize('count', [250, 280, 300])
def test_supported_plane_does_not_bypass_depth_validity(count):
    points = cloud_with_plane(count)
    assert dominant_plane(points)[1]['plane_inlier_ratio'] >= .25
    depth = np.zeros((100, 100))
    depth[:34] = .4  # 34% remains below the unchanged 35% depth threshold.
    with pytest.raises(CalibrationError, match='Insufficient depth-valid ratio'):
        make_capture(1., np.eye(4), np.zeros((100, 100, 3), dtype=np.uint8),
                     depth, np.eye(3), points, np.eye(4), arbitrary_plane=True)


def test_cloud_without_plane_still_fails_distance_support():
    points = np.random.default_rng(9).uniform([-1., -1., .2], [1., 1., 1.4], (1000, 3))
    with pytest.raises(CalibrationError, match='supported'):
        dominant_plane(points)


@pytest.mark.parametrize('points', [np.full((1000, 3), np.nan),
                                   np.tile([0., 0., 0.4], (1000, 1)),
                                   np.zeros((1000, 3))])
def test_invalid_or_duplicate_depth_points_still_fail(points):
    with pytest.raises(CalibrationError, match='Insufficient'):
        dominant_plane(points)


def test_orientation_gate_selects_table_instead_of_larger_background_wall():
    points = cloud_with_plane(250)
    rng = np.random.default_rng(12)
    points[250:850] = np.column_stack((np.full(600, 0.8),
                                      rng.uniform(-.5, .5, 600),
                                      rng.uniform(.7, 1.4, 600)))
    wall, quality = dominant_plane(points)
    assert abs(wall[0]) > .99
    assert quality['plane_table_identity'] == 'UNVERIFIED'
    table, quality = table_plane(points, [0., 0., -1.])
    np.testing.assert_allclose(table, [0., 0., -1., .4], atol=1e-12)
    assert quality['plane_inlier_count'] == 250


def test_parallel_object_surface_is_not_claimed_to_be_verified_table():
    points = cloud_with_plane(300)
    points[:300, 2] = .3  # A broad object top also satisfies support/orientation.
    _, quality = table_plane(points, [0., 0., -1.])
    assert quality['plane_table_identity'] == 'UNVERIFIED'


def test_other_quality_limits_unchanged():
    limits = Limits()
    assert limits.min_depth_valid_ratio == .35
    assert limits.plane_inlier_m == .004
    assert limits.min_points == 200
