from dataclasses import replace
import json

import cv2
import numpy as np
import pytest

from dobot_object_vision.detector import Detector, Rules, VisionError
from scene import K, scene


@pytest.mark.parametrize('tilt', [0., 25., -25.])
def test_all_colors_have_metric_centers_heights_and_sizes(tilt):
    image, depth, truth, plane = scene(tilt)
    result = Detector().process(image, depth, K)
    assert len(result.detections) == 3, result.rejected
    assert np.linalg.norm(result.table_plane - plane) < 0.001
    for detection, expected in zip(result.detections, truth):
        assert detection.class_name == expected['class_name']
        assert np.linalg.norm(np.asarray(detection.center_uv) - expected['uv']) < 1
        assert np.linalg.norm(np.asarray(detection.camera_xyz) - expected['center']) < 0.0015
        assert abs(detection.size - expected['diameter']) < 0.002
        assert abs(detection.top_height - expected['height']) < 0.001
        assert detection.depth == detection.camera_xyz[2]
        assert detection.pickable, detection
        assert 0 <= detection.confidence <= 1
    assert np.any(result.annotated != image)


def test_center_depth_hole_and_interior_outliers_use_robust_region():
    image, depth, truth, _ = scene()
    rng = np.random.default_rng(5)
    for target in truth:
        u, v = target['uv']
        depth[v, u] = np.nan
        indices = np.flatnonzero(target['mask'])
        chosen = rng.choice(indices, int(len(indices) * 0.08), replace=False)
        depth.flat[chosen] += 0.018
    result = Detector().process(image, depth, K)
    assert len(result.detections) == 3, result.rejected
    for detection, target in zip(result.detections, truth):
        assert np.linalg.norm(np.asarray(detection.camera_xyz) - target['center']) < 0.002


@pytest.mark.parametrize('background', [25, 225])
def test_depth_separates_same_color_target_from_table(background):
    image, depth, truth, _ = scene(background=background)
    result = Detector().process(image, depth, K)
    assert {d.class_name for d in result.detections} == {'black', 'white', 'yellow'}, result.rejected


def test_printed_circles_and_unsupported_color_are_filtered():
    image, depth, _, _ = scene(objects=[('yellow', (150, 230), .022, 0.),
                                       ('blue', (320, 240), .022, .015)])
    assert not Detector().process(image, depth, K).detections


def test_rectangles_clipped_and_wrong_sized_objects_are_filtered():
    image, depth, _, _ = scene(objects=[])
    cv2.rectangle(image, (120, 160), (180, 200), (225, 225, 225), -1)
    depth[160:201, 120:181] = 0.58
    cv2.circle(image, (0, 320), 25, (25, 25, 25), -1)
    depth[image[:, :, 0] == 25] = 0.58
    cv2.circle(image, (450, 230), 60, (10, 210, 230), -1)
    depth[image[:, :, 0] == 10] = 0.58
    result = Detector().process(image, depth, K)
    assert not result.detections, result.detections
    assert result.rejected


def test_hollow_ring_is_not_a_suction_target():
    image, depth, truth, _ = scene(objects=[('white', (320, 240), .026, .015)])
    cv2.circle(image, (320, 240), 8, (125, 125, 125), -1)
    yy, xx = np.indices(depth.shape)
    depth[(xx - 320) ** 2 + (yy - 240) ** 2 <= 8 ** 2] = .6
    result = Detector().process(image, depth, K)
    assert not result.detections
    assert 'center is a hole or another surface' in result.rejected


def test_low_depth_support_never_claims_pickable():
    image, depth, truth, _ = scene()
    rng = np.random.default_rng(18)
    for target in truth:
        indices = np.flatnonzero(target['mask'])
        depth.flat[rng.choice(indices, int(len(indices) * .4), replace=False)] = np.nan
    result = Detector().process(image, depth, K)
    assert len(result.detections) == 3, result.rejected
    assert all(not d.pickable and np.isfinite(d.camera_xyz).all() for d in result.detections)


@pytest.mark.parametrize('bad', [0., np.nan, np.inf])
def test_invalid_depth_cannot_produce_xyz(bad):
    image, depth, _, _ = scene()
    depth[:] = bad
    with pytest.raises(VisionError, match='depth-valid ratio'):
        Detector().process(image, depth, K)


def test_no_table_support_is_rejected():
    image, depth, _, _ = scene()
    depth[:] = np.random.default_rng(7).uniform(.25, .9, depth.shape)
    with pytest.raises(VisionError, match='table plane'):
        Detector().process(image, depth, K)


@pytest.mark.parametrize('parameters', [{'min_depth': np.nan}, {'min_diameter': -.01},
                                       {'min_confidence': 2.}, {'min_height': .1}])
def test_invalid_rules_are_rejected(parameters):
    with pytest.raises(VisionError):
        Rules(**parameters)
