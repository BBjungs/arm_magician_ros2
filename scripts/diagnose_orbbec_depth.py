#!/usr/bin/env python3
"""Inspect raw Orbbec ROS depth frames without changing or normalizing values."""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


ENCODINGS = {
    '16UC1': (np.dtype('uint16'), 2, 1.0),
    'mono16': (np.dtype('uint16'), 2, 1.0),
    '32FC1': (np.dtype('float32'), 4, 1000.0),
}


def decode_depth(message, depth_scale_mm=None):
    """Return the unmodified numeric image and its values converted to mm."""
    if message.encoding not in ENCODINGS:
        raise ValueError(
            f'Unsupported depth encoding {message.encoding!r}; '
            f'expected one of {sorted(ENCODINGS)}')
    dtype, bytes_per_pixel, default_scale = ENCODINGS[message.encoding]
    expected_step = int(message.width) * bytes_per_pixel
    expected_size = int(message.step) * int(message.height)
    if int(message.step) < expected_step:
        raise ValueError(
            f'Invalid step={message.step}; at least {expected_step} bytes are required')
    if len(message.data) != expected_size:
        raise ValueError(
            f'Invalid data length={len(message.data)}; expected step*height={expected_size}')

    byte_order = '>' if message.is_bigendian else '<'
    wire_dtype = dtype.newbyteorder(byte_order)
    row_items = int(message.step) // bytes_per_pixel
    array = np.frombuffer(message.data, dtype=wire_dtype).reshape(
        int(message.height), row_items)
    array = array[:, :int(message.width)]
    if not array.dtype.isnative:
        array = array.astype(dtype, copy=False)
    scale = default_scale if depth_scale_mm is None else float(depth_scale_mm)
    return array, array.astype(np.float64) * scale, scale


def frame_statistics(values_mm, minimum_mm, maximum_mm):
    finite = np.isfinite(values_mm)
    nonzero = finite & (values_mm != 0.0)
    valid = finite & (values_mm >= minimum_mm) & (values_mm <= maximum_mm)
    samples = values_mm[finite]
    histogram = {
        '0': int(np.count_nonzero(finite & (values_mm == 0.0))),
        '1-100': int(np.count_nonzero(finite & (values_mm > 0.0) & (values_mm < 100.0))),
        '100-500': int(np.count_nonzero(finite & (values_mm >= 100.0) & (values_mm < 500.0))),
        '500-1000': int(np.count_nonzero(finite & (values_mm >= 500.0) & (values_mm < 1000.0))),
        '1000-2000': int(np.count_nonzero(finite & (values_mm >= 1000.0) & (values_mm <= 2000.0))),
        '>2000': int(np.count_nonzero(finite & (values_mm > 2000.0))),
        'nonfinite': int(values_mm.size - np.count_nonzero(finite)),
    }
    return {
        'min_mm': None if not samples.size else float(np.min(samples)),
        'max_mm': None if not samples.size else float(np.max(samples)),
        'mean_mm': None if not samples.size else float(np.mean(samples)),
        'median_mm': None if not samples.size else float(np.median(samples)),
        'nonzero_count': int(np.count_nonzero(nonzero)),
        'valid_count': int(np.count_nonzero(valid)),
        'valid_ratio': float(np.mean(valid)),
        'zero_ratio': float(np.mean(finite & (values_mm == 0.0))),
        'histogram': histogram,
    }


class DepthDiagnostic(Node):
    def __init__(self, arguments):
        super().__init__('diagnose_orbbec_depth')
        self.arguments = arguments
        self.started = time.monotonic()
        self.arrivals = []
        self.results = []
        self.metadata = None
        self.last_raw = None
        self.color_frames = 0
        self.error = ''
        self.create_subscription(
            Image, arguments.topic, self._depth_callback, qos_profile_sensor_data)
        if arguments.color_topic:
            self.create_subscription(
                Image, arguments.color_topic, self._color_callback,
                qos_profile_sensor_data)

    def _color_callback(self, _message):
        self.color_frames += 1

    def _depth_callback(self, message):
        if len(self.results) >= self.arguments.frames:
            return
        try:
            raw, values_mm, scale = decode_depth(
                message, self.arguments.depth_scale_mm)
            stats = frame_statistics(
                values_mm, self.arguments.minimum_mm,
                self.arguments.maximum_mm)
        except ValueError as exc:
            self.error = str(exc)
            return
        self.arrivals.append(time.monotonic())
        self.last_raw = raw.copy()
        self.metadata = {
            'topic': self.arguments.topic,
            'encoding': message.encoding,
            'resolution': [int(message.width), int(message.height)],
            'step': int(message.step),
            'data_length': len(message.data),
            'expected_data_length': int(message.step) * int(message.height),
            'is_bigendian': int(message.is_bigendian),
            'dtype': str(raw.dtype),
            'depth_scale_mm': scale,
            'frame_id': message.header.frame_id,
        }
        self.results.append(stats)
        index = len(self.results)
        print(json.dumps({'frame': index, **stats}, separators=(',', ':')))

    @property
    def complete(self):
        return len(self.results) >= self.arguments.frames or bool(self.error)

    def summary(self):
        elapsed = max(time.monotonic() - self.started, 1e-9)
        fps = 0.0
        if len(self.arrivals) > 1:
            fps = (len(self.arrivals) - 1) / (self.arrivals[-1] - self.arrivals[0])
        aggregate = {
            'frames': len(self.results),
            'elapsed_sec': round(elapsed, 3),
            'fps': round(fps, 3),
            'color_frames': self.color_frames,
            'error': self.error,
        }
        if self.results:
            aggregate.update({
                'minimum_observed_mm': min(
                    value['min_mm'] for value in self.results
                    if value['min_mm'] is not None),
                'maximum_observed_mm': max(
                    value['max_mm'] for value in self.results
                    if value['max_mm'] is not None),
                'median_of_frame_medians_mm': float(np.median([
                    value['median_mm'] for value in self.results
                    if value['median_mm'] is not None])),
                'mean_nonzero_count': float(np.mean([
                    value['nonzero_count'] for value in self.results])),
                'mean_valid_ratio': float(np.mean([
                    value['valid_ratio'] for value in self.results])),
                'mean_zero_ratio': float(np.mean([
                    value['zero_ratio'] for value in self.results])),
            })
        return {'metadata': self.metadata, 'summary': aggregate}

    def save_raw(self):
        if not self.arguments.save or self.last_raw is None:
            return
        if self.last_raw.dtype != np.uint16:
            raise ValueError(
                '--save supports only unmodified uint16 depth frames; '
                f'got {self.last_raw.dtype}')
        destination = Path(self.arguments.save).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(destination), self.last_raw):
            raise OSError(f'Unable to save raw depth PNG to {destination}')
        print(f'raw_depth_png={destination}')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Report raw ROS Orbbec depth statistics without normalization.')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--topic', default='/camera/depth/image_raw')
    parser.add_argument('--color-topic', default='')
    parser.add_argument('--min-mm', dest='minimum_mm', type=float, default=100.0)
    parser.add_argument('--max-mm', dest='maximum_mm', type=float, default=2000.0)
    parser.add_argument(
        '--depth-scale-mm', type=float, default=None,
        help='Millimetres per raw unit. Defaults to 1 for 16UC1/mono16 and 1000 for 32FC1.')
    parser.add_argument(
        '--save', default='', metavar='PNG',
        help='Save the final unmodified uint16 depth frame as a 16-bit PNG.')
    parser.add_argument('--timeout', type=float, default=15.0)
    arguments = parser.parse_args(argv)
    if arguments.frames <= 0:
        parser.error('--frames must be greater than zero')
    if arguments.minimum_mm < 0 or arguments.maximum_mm <= arguments.minimum_mm:
        parser.error('--min-mm/--max-mm specify an invalid range')
    if arguments.timeout <= 0 or not math.isfinite(arguments.timeout):
        parser.error('--timeout must be a finite positive number')
    return arguments


def main(argv=None):
    arguments = parse_args(argv)
    rclpy.init()
    node = DepthDiagnostic(arguments)
    deadline = time.monotonic() + arguments.timeout
    try:
        while rclpy.ok() and not node.complete and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.25)
        if not node.complete and not node.error:
            node.error = (
                f'Timed out after {arguments.timeout}s with '
                f'{len(node.results)}/{arguments.frames} depth frames')
        report = node.summary()
        print(json.dumps(report, indent=2, sort_keys=True))
        node.save_raw()
        return 0 if not node.error and len(node.results) == arguments.frames else 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
