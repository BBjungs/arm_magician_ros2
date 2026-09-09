#!/usr/bin/env python3
"""Validate the three-class cap dataset before YOLO training."""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import cv2


CLASS_NAMES = {0: 'yellow_cap', 1: 'black_cap', 2: 'white_cap'}
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


@dataclass
class DatasetReport:
    images_by_split: Counter = field(default_factory=Counter)
    boxes_by_class: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_images(self):
        return sum(self.images_by_split.values())

    @property
    def total_boxes(self):
        return sum(self.boxes_by_class.values())

    @property
    def ok(self):
        return not self.errors


def _validate_label(path: Path, report: DatasetReport):
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        report.warnings.append(f'empty label (valid only for a reviewed negative image): {path}')
        return
    for line_number, line in enumerate(text.splitlines(), start=1):
        fields = line.split()
        location = f'{path}:{line_number}'
        if len(fields) != 5:
            report.errors.append(f'{location}: expected 5 fields, got {len(fields)}')
            continue
        try:
            class_id = int(fields[0])
            x_center, y_center, width, height = map(float, fields[1:])
        except ValueError:
            report.errors.append(f'{location}: label contains a non-numeric value')
            continue
        if class_id not in CLASS_NAMES:
            report.errors.append(f'{location}: class id {class_id} is outside 0..2')
            continue
        values = (x_center, y_center, width, height)
        if any(value < 0.0 or value > 1.0 for value in values):
            report.errors.append(f'{location}: normalized values must be within 0..1')
            continue
        if width <= 0.0 or height <= 0.0:
            report.errors.append(f'{location}: width and height must be > 0')
            continue
        if x_center - width / 2 < 0 or x_center + width / 2 > 1:
            report.errors.append(f'{location}: bounding box exceeds horizontal image bounds')
            continue
        if y_center - height / 2 < 0 or y_center + height / 2 > 1:
            report.errors.append(f'{location}: bounding box exceeds vertical image bounds')
            continue
        report.boxes_by_class[class_id] += 1


def validate_dataset(root: Path) -> DatasetReport:
    report = DatasetReport()
    filename_locations = defaultdict(list)
    for split in ('train', 'val', 'test'):
        image_dir = root / 'images' / split
        label_dir = root / 'labels' / split
        if not image_dir.is_dir():
            report.errors.append(f'missing image directory: {image_dir}')
            continue
        if not label_dir.is_dir():
            report.errors.append(f'missing label directory: {label_dir}')
            continue
        images = {
            path.stem: path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        }
        labels = {path.stem: path for path in label_dir.glob('*.txt') if path.is_file()}
        report.images_by_split[split] = len(images)
        for path in images.values():
            filename_locations[path.name.lower()].append(path)
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None or image.size == 0:
                report.errors.append(f'corrupt or undecodable image: {path}')
        for stem in sorted(images.keys() - labels.keys()):
            report.errors.append(f'image has no matching label: {images[stem]}')
        for stem in sorted(labels.keys() - images.keys()):
            report.errors.append(f'label has no matching image: {labels[stem]}')
        for stem in sorted(images.keys() & labels.keys()):
            _validate_label(labels[stem], report)

    for name, paths in filename_locations.items():
        if len(paths) > 1:
            report.errors.append(
                f'duplicate image filename across splits ({name}): '
                + ', '.join(str(path) for path in paths)
            )
    if report.total_images == 0:
        report.errors.append('dataset contains no images')
    for split in ('train', 'val'):
        if report.images_by_split[split] == 0:
            report.errors.append(f'{split} split contains no images')
    if report.images_by_split['test'] == 0:
        report.warnings.append('test split contains no images')
    for class_id, class_name in CLASS_NAMES.items():
        if report.boxes_by_class[class_id] == 0:
            report.errors.append(f'class has no bounding boxes: {class_name}')
    return report


def print_report(report: DatasetReport):
    print(f'Total images: {report.total_images}')
    for split in ('train', 'val', 'test'):
        print(f'{split.capitalize()} images: {report.images_by_split[split]}')
    print(f'Bounding boxes: {report.total_boxes}')
    print('Class counts:')
    for class_id, class_name in CLASS_NAMES.items():
        print(f'  {class_name}: {report.boxes_by_class[class_id]}')
    print(f'Errors: {len(report.errors)}')
    for error in report.errors:
        print(f'  ERROR: {error}')
    print(f'Warnings: {len(report.warnings)}')
    for warning in report.warnings:
        print(f'  WARNING: {warning}')
    print('Dataset validation: PASS' if report.ok else 'Dataset validation: FAIL')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default='datasets/caps')
    args = parser.parse_args()
    report = validate_dataset(Path(args.dataset))
    print_report(report)
    return 0 if report.ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
