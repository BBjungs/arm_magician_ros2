from types import SimpleNamespace

import numpy as np

from dobot_vision_yolo.yolo_detector_node import YoloDetectorNode


class Logger:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)


def _detector(names=None):
    logger = Logger()
    detector = SimpleNamespace(
        model=SimpleNamespace(names=names or {}),
        get_logger=lambda: logger,
    )
    detector._normalize_model_names = YoloDetectorNode._normalize_model_names
    return detector, logger


def _box(xyxy, confidence, class_id):
    return SimpleNamespace(
        xyxy=np.asarray([xyxy], dtype=float),
        conf=np.asarray([confidence], dtype=float),
        cls=np.asarray([class_id], dtype=float),
    )


def test_multiple_boxes_include_class_id_and_center():
    detector, _ = _detector({0: 'yellow_cap', 1: 'black_cap'})
    result = SimpleNamespace(
        names=detector.model.names,
        boxes=[_box([10, 20, 30, 40], 0.91, 0), _box([40, 50, 80, 90], 0.82, 1)],
    )
    detections = YoloDetectorNode._detections_from_result(detector, result)
    assert detections[0] == {
        'id': 0,
        'class_id': 0,
        'class_name': 'yellow_cap',
        'confidence': 0.91,
        'bbox': [10, 20, 30, 40],
        'center_pixel': [20, 30],
    }
    assert detections[1]['id'] == 1
    assert detections[1]['class_name'] == 'black_cap'
    assert detections[1]['center_pixel'] == [60, 70]


def test_empty_result_returns_empty_list():
    detector, _ = _detector()
    assert YoloDetectorNode._detections_from_result(
        detector, SimpleNamespace(boxes=None)
    ) == []


def test_malformed_box_is_ignored_and_logged():
    detector, logger = _detector({0: 'yellow_cap'})
    result = SimpleNamespace(names=detector.model.names, boxes=[SimpleNamespace()])
    assert YoloDetectorNode._detections_from_result(detector, result) == []
    assert logger.warnings


def test_model_names_normalization():
    assert YoloDetectorNode._normalize_model_names(['yellow_cap', 'black_cap']) == {
        0: 'yellow_cap',
        1: 'black_cap',
    }
