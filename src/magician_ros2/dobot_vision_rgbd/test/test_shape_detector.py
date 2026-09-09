from pathlib import Path
import cv2
import numpy as np
import yaml
from dobot_vision_rgbd.shape_detector import ShapeDetector

RULES = yaml.safe_load((Path(__file__).parents[1] / 'config' / 'shape_rules.yaml').read_text())


def detect(draw):
    image = np.full((300, 300, 3), 220, np.uint8)
    draw(image)
    return ShapeDetector(RULES).detect(image)


def test_circle():
    assert detect(lambda image: cv2.circle(image, (150, 150), 45, (0, 0, 0), -1))[0]['shape'] == 'circle'


def test_triangle():
    points = np.array([[150, 70], [80, 210], [220, 210]])
    assert detect(lambda image: cv2.fillPoly(image, [points], (0, 0, 0)))[0]['shape'] == 'triangle'


def test_square_and_rectangle():
    square = detect(lambda image: cv2.rectangle(image, (90, 90), (210, 210), (0, 0, 0), -1))[0]
    rectangle = detect(lambda image: cv2.rectangle(image, (60, 110), (240, 190), (0, 0, 0), -1))[0]
    assert square['shape'] == 'square'
    assert rectangle['shape'] == 'rectangle'


def test_noise_rejection():
    assert detect(lambda image: cv2.circle(image, (150, 150), 3, (0, 0, 0), -1)) == []
