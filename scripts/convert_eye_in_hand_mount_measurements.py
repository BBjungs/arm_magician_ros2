#!/usr/bin/env python3
"""Convert unsigned physical mount measurements to signed TCP-frame XYZ."""

import argparse
from pathlib import Path
import sys

import yaml


try:
    from dobot_calibration.measurement_form import convert, convert_tool_to_suction
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                           / 'src/magician_ros2/dobot_calibration'))
    from dobot_calibration.measurement_form import convert, convert_tool_to_suction


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('form', type=Path)
    parser.add_argument(
        '--tool-to-suction-only', action='store_true',
        help='validate and print the measured tool-to-suction transform while camera fields remain unfilled')
    args = parser.parse_args()
    with args.form.open(encoding='utf-8') as stream:
        document = yaml.safe_load(stream)
    if args.tool_to_suction_only:
        xyz_mm = convert_tool_to_suction(document)
        output = {
            'tool_to_suction_tcp_xyz_mm': xyz_mm,
            'tool_to_suction_tcp_xyz_m': [value / 1000.0 for value in xyz_mm],
        }
    else:
        output = convert(document)
    print(yaml.safe_dump(output, sort_keys=False), end='')


if __name__ == '__main__':
    main()
