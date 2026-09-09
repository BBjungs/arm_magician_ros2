from pathlib import Path
import cv2
import numpy as np
import pytest
import yaml
from dobot_vision_rgbd.object_fusion_node import ObjectFusion

ROOT = Path(__file__).parents[1] / 'config'


def fusion():
    return ObjectFusion(
        yaml.safe_load((ROOT / 'shape_rules.yaml').read_text()),
        yaml.safe_load((ROOT / 'color_rules.yaml').read_text()),
        yaml.safe_load((ROOT / 'object_classes.yaml').read_text()))


def scene(color, object_depth=500, table_depth=530):
    image = np.full((300, 300, 3), (120, 120, 120), np.uint8)
    cv2.circle(image, (150, 150), 28, color, -1)
    depth = np.full((300, 300), table_depth, np.float32)
    cv2.circle(depth, (150, 150), 26, object_depth, -1)
    return image, depth


@pytest.mark.parametrize('color,expected', [
    ((0, 255, 255), 'yellow_cap'), ((10, 10, 10), 'black_cap'),
    ((245, 245, 245), 'white_cap')])
def test_cap_fusion(color, expected):
    image, depth = scene(color)
    detections, _ = fusion().process(image, depth, {'fx': 600, 'fy': 600, 'cx': 150, 'cy': 150})
    item = detections[0]
    assert item['class_name'] == expected
    assert item['pick_eligible']
    assert 20 < item['diameter_mm'] < 70
    assert item['object_height_mm'] == 30


def test_flat_pattern_rejected():
    image, depth = scene((0, 255, 255), object_depth=530, table_depth=530)
    item = fusion().process(image, depth, {'fx': 600, 'fy': 600, 'cx': 150, 'cy': 150})[0][0]
    assert not item['pick_eligible']
    assert item['rejection_reason'] == 'height_out_of_range'


def test_invalid_depth_and_unknown_color_rejected():
    image, depth = scene((255, 0, 255))
    image[:] = (230, 230, 230)
    cv2.circle(image, (150, 150), 28, (255, 0, 255), -1)
    depth[:] = 0
    item = fusion().process(image, depth, {'fx': 600, 'fy': 600, 'cx': 150, 'cy': 150})[0][0]
    assert item['color'] == 'unknown'
    assert not item['pick_eligible']
    assert item['rejection_reason'] == 'invalid_depth'
