#!/usr/bin/env python3
"""Train the project-specific cap detector after real data is collected."""

import argparse
from pathlib import Path
import sys

from validate_caps_dataset import CLASS_NAMES, print_report, validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--device', default=None)
    parser.add_argument('--data', default='datasets/caps/data.yaml')
    parser.add_argument('--model', default='yolo11n.pt')
    parser.add_argument('--batch', type=int, default=16)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--project', default='runs/caps')
    parser.add_argument('--name', default='caps_yolo11n')
    args = parser.parse_args()

    data = Path(args.data)
    if not data.is_file():
        print(f'ERROR: dataset config not found: {data}', file=sys.stderr)
        return 2
    report = validate_dataset(data.parent)
    print_report(report)
    if not report.ok:
        print('ERROR: fatal dataset validation errors block training.', file=sys.stderr)
        return 2
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        print(f'ERROR: Ultralytics is required to train ({exc})', file=sys.stderr)
        return 2

    model = YOLO(args.model)
    train_args = {
        'data': str(data),
        'epochs': args.epochs,
        'imgsz': args.imgsz,
        'batch': args.batch,
        'workers': args.workers,
        'project': args.project,
        'name': args.name,
    }
    if args.device is not None:
        train_args['device'] = args.device
    result = model.train(**train_args)
    save_dir = Path(getattr(result, 'save_dir', Path(args.project) / args.name))
    best_path = save_dir / 'weights' / 'best.pt'
    if not best_path.is_file():
        print(f'ERROR: training finished without best.pt at {best_path}', file=sys.stderr)
        return 3

    trained_model = YOLO(str(best_path))
    names = dict(trained_model.names)
    if names != CLASS_NAMES:
        print(
            f'ERROR: trained model class names are {names}; expected {CLASS_NAMES}',
            file=sys.stderr,
        )
        return 3
    print(f'Training complete. Verified best.pt: {best_path.resolve()}')
    print(f'Model classes: {names}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
