#!/usr/bin/env python3
"""Deterministically split reviewed raw cap images and YOLO labels."""

import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path


IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def class_signature(label_path: Path) -> tuple[int, ...]:
    classes = set()
    for line in label_path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if fields:
            try:
                classes.add(int(fields[0]))
            except ValueError:
                pass
    return tuple(sorted(classes))


def allocate(count: int, ratios: tuple[float, float, float]) -> list[int]:
    exact = [count * ratio for ratio in ratios]
    sizes = [int(value) for value in exact]
    for index in sorted(range(3), key=lambda i: exact[i] - sizes[i], reverse=True)[:count - sum(sizes)]:
        sizes[index] += 1
    return sizes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-images', default='datasets/caps/raw')
    parser.add_argument('--raw-labels', default='datasets/caps/raw_labels')
    parser.add_argument('--dataset', default='datasets/caps')
    parser.add_argument('--train', type=float, default=0.70)
    parser.add_argument('--val', type=float, default=0.20)
    parser.add_argument('--test', type=float, default=0.10)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    ratios = (args.train, args.val, args.test)
    if any(ratio < 0 for ratio in ratios) or abs(sum(ratios) - 1.0) > 1e-9:
        raise SystemExit('train/val/test ratios must be non-negative and sum to 1.0')

    raw_images = Path(args.raw_images)
    raw_labels = Path(args.raw_labels)
    dataset = Path(args.dataset)
    images = [
        path for path in raw_images.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ] if raw_images.is_dir() else []
    if not images:
        raise SystemExit(f'no raw images found in {raw_images}')

    grouped = defaultdict(list)
    for image in images:
        label = raw_labels / f'{image.stem}.txt'
        if not label.is_file():
            raise SystemExit(f'missing reviewed label for {image}: expected {label}')
        grouped[class_signature(label)].append((image, label))

    destinations = []
    for split in ('train', 'val', 'test'):
        image_dir = dataset / 'images' / split
        label_dir = dataset / 'labels' / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        existing = [path for path in (*image_dir.iterdir(), *label_dir.iterdir()) if path.name != '.gitkeep']
        if existing:
            raise SystemExit(f'destination is not empty: {image_dir} or {label_dir}')
        destinations.append((image_dir, label_dir))

    rng = random.Random(args.seed)
    split_counts = [0, 0, 0]
    for signature in sorted(grouped):
        items = grouped[signature]
        rng.shuffle(items)
        sizes = allocate(len(items), ratios)
        cursor = 0
        for split_index, size in enumerate(sizes):
            for image, label in items[cursor:cursor + size]:
                image_dir, label_dir = destinations[split_index]
                shutil.copy2(image, image_dir / image.name)
                shutil.copy2(label, label_dir / label.name)
                split_counts[split_index] += 1
            cursor += size

    print(f'Split complete with seed {args.seed}:')
    for split, count in zip(('train', 'val', 'test'), split_counts):
        print(f'  {split}: {count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
