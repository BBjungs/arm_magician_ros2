import numpy as np
import cv2
import pytest

from dobot_vision_rgbd.visualization import annotate, write_preview


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


def test_preview_reduction_preserves_original_pixels_and_aspect_ratio(tmp_path):
    image = np.random.default_rng(42).integers(0, 256, (480, 640, 3), dtype=np.uint8)
    original = image.copy()
    path = tmp_path / 'preview.jpg'
    write_preview(path, image)
    assert cv2.imread(str(path)).shape == (360, 480, 3)
    np.testing.assert_array_equal(image, original)
    ok, full = cv2.imencode('.jpg', image)
    assert ok and path.stat().st_size < full.nbytes / 2
    assert not path.with_name(path.name + '.tmp').exists()


def test_failed_preview_encoding_keeps_last_complete_frame(tmp_path, monkeypatch):
    path = tmp_path / 'preview.jpg'
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    write_preview(path, image)
    original = path.read_bytes()
    assert cv2.imread(str(path)).shape == image.shape
    monkeypatch.setattr(cv2, 'imencode', lambda *args: (False, None))
    with pytest.raises(ValueError, match='encode'):
        write_preview(path, image)
    assert path.read_bytes() == original
