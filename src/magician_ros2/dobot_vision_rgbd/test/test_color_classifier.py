from pathlib import Path
import cv2
import numpy as np
import yaml
from dobot_vision_rgbd.color_classifier import ColorClassifier

RULES = yaml.safe_load((Path(__file__).parents[1] / 'config' / 'color_rules.yaml').read_text())
CONTOUR = np.array([[[10, 10]], [[90, 10]], [[90, 90]], [[10, 90]]])


def classify(bgr):
    image = np.full((100, 100, 3), bgr, np.uint8)
    return ColorClassifier(RULES).classify(image, CONTOUR)['color']


def test_yellow_black_white_unknown():
    assert classify((0, 255, 255)) == 'yellow'
    assert classify((15, 15, 15)) == 'black'
    assert classify((240, 240, 240)) == 'white'
    assert classify((100, 100, 100)) == 'unknown'


def test_configured_priority_resolves_overlapping_color_ranges():
    image = np.full((100, 100, 3), (132, 226, 226), np.uint8)
    result = ColorClassifier(RULES).classify(image, CONTOUR)
    assert result['color'] == 'yellow'
    assert result['color_distribution']['yellow'] >= RULES['minimum_matching_ratio']
