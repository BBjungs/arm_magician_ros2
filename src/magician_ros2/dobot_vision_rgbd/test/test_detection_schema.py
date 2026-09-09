import pytest
from dobot_vision_rgbd.detection_schema import validate_detection


def test_valid_ineligible_detection_requires_reason():
    item = {'id': 0, 'detector': 'rgbd_shape', 'class_name': 'unknown', 'shape': 'circle',
            'color': 'unknown', 'classification_score': 0.5, 'bbox': [0, 0, 10, 10],
            'center_pixel': [5, 5], 'pick_eligible': False, 'rejection_reason': 'invalid_depth'}
    assert validate_detection(item)
    item['rejection_reason'] = ''
    with pytest.raises(ValueError):
        validate_detection(item)
