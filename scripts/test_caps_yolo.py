#!/usr/bin/env python3
"""Run a real cap model against one image before ROS deployment."""

import argparse
from pathlib import Path


EXPECTED_NAMES = {0: 'yellow_cap', 1: 'black_cap', 2: 'white_cap'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--image', default='/tmp/dobot_snapshot.jpg')
    parser.add_argument('--output', default='/tmp')
    parser.add_argument('--device', default=None)
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    names = dict(model.names)
    print(f'Model: {Path(args.model).resolve()}')
    print(f'Classes: {names}')
    if names != EXPECTED_NAMES:
        print(f'FAIL: expected exact classes {EXPECTED_NAMES}')
        return 2

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    passed = False
    for confidence in (0.70, 0.50, 0.30, 0.25, 0.10):
        kwargs = {'source': args.image, 'conf': confidence, 'verbose': False}
        if args.device is not None:
            kwargs['device'] = args.device
        result = model.predict(**kwargs)[0]
        boxes = result.boxes if result.boxes is not None else []
        print(f'CONF {confidence:.2f}: {len(boxes)} detections')
        for box in boxes:
            class_id = int(box.cls.item())
            score = float(box.conf.item())
            print(f'  {class_id} {names[class_id]} {score:.4f} {box.xyxy[0].tolist()}')
        filename = output / f'caps_test_{int(confidence * 100):03d}.jpg'
        result.save(filename=str(filename))
        if confidence >= 0.50 and len(boxes) > 0:
            passed = True
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
