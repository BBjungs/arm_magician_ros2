import numpy as np

from dobot_vision_rgbd.visualization import annotate


def test_annotation_handles_valid_object_depth_without_table_height():
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    detection = {
        'id': 0,
        'class_name': 'unknown',
        'shape': 'circle',
        'color': 'yellow',
        'bbox': [10, 10, 60, 60],
        'center_pixel': [35, 35],
        'depth_mm': 518.0,
        'object_height_mm': None,
        'pick_eligible': False,
        'rejection_reason': 'invalid_table_depth',
    }
    output = annotate(image, [detection])
    assert output.shape == image.shape
    assert np.any(output != image)
