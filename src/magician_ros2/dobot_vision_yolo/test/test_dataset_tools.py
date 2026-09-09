from pathlib import Path
import sys

import cv2
import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT / 'scripts'))

from capture_caps_dataset import hamming_distance, image_fingerprint  # noqa: E402
from split_caps_dataset import allocate  # noqa: E402
from validate_caps_dataset import validate_dataset  # noqa: E402


def _make_image(path):
    image = np.full((40, 60, 3), 128, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _make_complete_dataset(root):
    for split, class_id in zip(('train', 'val', 'test'), (0, 1, 2)):
        image_dir = root / 'images' / split
        label_dir = root / 'labels' / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        _make_image(image_dir / f'{split}.jpg')
        (label_dir / f'{split}.txt').write_text(
            f'{class_id} 0.5 0.5 0.2 0.2\n', encoding='utf-8'
        )


def test_valid_dataset_passes(tmp_path):
    _make_complete_dataset(tmp_path)
    report = validate_dataset(tmp_path)
    assert report.ok
    assert report.total_images == 3
    assert report.total_boxes == 3


def test_missing_label_is_fatal(tmp_path):
    _make_complete_dataset(tmp_path)
    (tmp_path / 'labels' / 'train' / 'train.txt').unlink()
    report = validate_dataset(tmp_path)
    assert not report.ok
    assert any('no matching label' in error for error in report.errors)


def test_out_of_bounds_box_is_fatal(tmp_path):
    _make_complete_dataset(tmp_path)
    (tmp_path / 'labels' / 'train' / 'train.txt').write_text(
        '0 0.95 0.5 0.2 0.2\n', encoding='utf-8'
    )
    report = validate_dataset(tmp_path)
    assert not report.ok
    assert any('horizontal image bounds' in error for error in report.errors)


def test_split_allocation_is_reproducible_and_complete():
    assert allocate(10, (0.7, 0.2, 0.1)) == [7, 2, 1]
    assert sum(allocate(7, (0.7, 0.2, 0.1))) == 7


def test_capture_fingerprint_detects_identical_images():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    first = image_fingerprint(image)
    second = image_fingerprint(image.copy())
    assert hamming_distance(first, second) == 0
