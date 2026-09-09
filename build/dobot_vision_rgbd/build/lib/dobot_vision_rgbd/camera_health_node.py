"""Read-only RGB-D health and explicit USB SuperSpeed readiness."""
from collections import deque
import json
from pathlib import Path
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, PointCloud2
from orbbec_camera_msgs.srv import GetBool
from std_msgs.msg import String


def usb_status(root=Path('/sys/bus/usb/devices')):
    expected = {'0614', '0511'}
    devices = []
    for path in root.iterdir():
        try:
            if (path / 'idVendor').read_text().strip() != '2bc5':
                continue
            product = (path / 'idProduct').read_text().strip()
            if product in expected:
                devices.append({'path': path.name, 'product': product,
                                'speed_mbps': float((path / 'speed').read_text())})
        except (OSError, ValueError):
            continue
    ready = (len(devices) == 2 and {d['product'] for d in devices} == expected
             and all(d['speed_mbps'] >= 5000 for d in devices))
    return {'devices': devices, 'superspeed': ready}


def valid_depth_ratio(message):
    types = {'16UC1': 'u2', 'mono16': 'u2', '32FC1': 'f4'}
    dtype = np.dtype(('>' if message.is_bigendian else '<') + types[message.encoding])
    if message.height <= 0 or message.width <= 0 or message.step < message.width * dtype.itemsize:
        raise ValueError('Invalid depth dimensions or stride')
    values = np.ndarray((message.height, message.width), dtype=dtype,
                        buffer=message.data, strides=(message.step, dtype.itemsize))
    return float(np.mean(np.isfinite(values) & (values > 0)))


def valid_cloud_ratio(message):
    if message.height <= 0 or message.width <= 0 or message.row_step < message.width * message.point_step:
        raise ValueError('Invalid point cloud dimensions or stride')
    valid = np.ones((message.height, message.width), dtype=bool)
    for axis in ('x', 'y', 'z'):
        field = next(f for f in message.fields if f.name == axis)
        if field.datatype != 7 or field.count != 1 or field.offset + 4 > message.point_step:
            raise ValueError('Unsupported point cloud coordinate field')
        values = np.ndarray((message.height, message.width),
                            dtype=('>' if message.is_bigendian else '<') + 'f4',
                            buffer=message.data, offset=field.offset,
                            strides=(message.row_step, message.point_step))
        valid &= np.isfinite(values)
        if axis == 'z':
            valid &= values > 0
    return float(np.mean(valid))


def stream_metrics(samples, now, expected_fps):
    if not samples:
        return {'fresh': False, 'frames': 0}
    arrivals = [x[0] for x in samples]
    stamps = [x[1] for x in samples]
    gaps = np.diff(stamps)
    return {'fresh': now - arrivals[-1] < 1.0, 'frames': len(samples),
            'age_ms': round((now - arrivals[-1]) * 1000, 2),
            'fps': round((len(samples) - 1) / (arrivals[-1] - arrivals[0]), 2)
            if len(samples) > 1 and arrivals[-1] > arrivals[0] else 0.0,
            'timestamp_valid': all(s > 0 for s in stamps) and bool(np.all(gaps > 0)),
            'estimated_missing_frames': int(sum(max(0, round(g * expected_fps) - 1) for g in gaps)),
            'frame_id': samples[-1][2]}


class CameraHealthNode(Node):
    def __init__(self):
        super().__init__('camera_health')
        self.declare_parameter('expected_fps', 30.0)
        self.expected_fps = float(self.get_parameter('expected_fps').value)
        if not np.isfinite(self.expected_fps) or self.expected_fps <= 0:
            raise ValueError('expected_fps must be finite and positive')
        self.samples = {key: deque(maxlen=300) for key in ('rgb', 'depth', 'rgb_info', 'depth_info', 'cloud')}
        self.latest = {}
        self.validity = {}
        self.checked = {}
        self.subscriptions_ = []
        for key, kind, topic in [('rgb', Image, '/camera/color/image_raw'),
                                 ('depth', Image, '/camera/depth/image_raw'),
                                 ('rgb_info', CameraInfo, '/camera/color/camera_info'),
                                 ('depth_info', CameraInfo, '/camera/depth/camera_info'),
                                 ('cloud', PointCloud2, '/camera/depth/points')]:
            self.declare_parameter(key + '_topic', topic)
            self.subscriptions_.append(self.create_subscription(
                kind, str(self.get_parameter(key + '_topic').value),
                lambda msg, key=key: self.receive(key, msg), qos_profile_sensor_data))
        self.protection_client = self.create_client(GetBool, '/camera/get_ldp_protection_status')
        self.protection_future = None
        self.protection_active = None
        self.protection_checked_at = None
        self.create_timer(1.0, self.poll_protection)
        self.publisher = self.create_publisher(String, '/camera/health', 10)
        self.create_timer(1.0, self.publish_health)

    def receive(self, key, msg):
        now = time.monotonic()
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
        self.samples[key].append((now, stamp, msg.header.frame_id))
        self.latest[key] = msg
        if key in ('depth', 'cloud') and now - self.checked.get(key, 0) > 0.5:
            self.checked[key] = now
            try:
                ratio = valid_depth_ratio(msg) if key == 'depth' else valid_cloud_ratio(msg)
                self.validity[key] = {'valid_ratio': ratio, 'valid': ratio > 0.01}
            except (KeyError, ValueError, TypeError, StopIteration, BufferError) as exc:
                self.validity[key] = {'valid': False, 'error': str(exc)}

    def poll_protection(self):
        if self.protection_future is not None:
            if not self.protection_future.done():
                if time.monotonic() - self.protection_requested_at > 2.0:
                    self.protection_client.remove_pending_request(self.protection_future)
                    self.protection_future.cancel()
                    self.protection_future = None
                    self.protection_active = None
                return
            try:
                result = self.protection_future.result()
                self.protection_active = bool(result.data) if result.success else None
                self.protection_checked_at = time.monotonic()
            except Exception as exc:
                self.protection_active = None
                self.get_logger().warning(f'Protection status unavailable: {exc}')
            self.protection_future = None
        if self.protection_client.service_is_ready():
            self.protection_future = self.protection_client.call_async(GetBool.Request())
            self.protection_requested_at = time.monotonic()

    def publish_health(self):
        now = time.monotonic()
        status = {'usb': usb_status(), 'streams': {}, 'ready': False, 'blockers': []}
        protection_fresh = (self.protection_checked_at is not None
                            and now - self.protection_checked_at < 3.0)
        status['ldp_protection_active'] = self.protection_active if protection_fresh else None
        if status['ldp_protection_active'] is not False:
            status['blockers'].append('ldp_protection_active_or_unverified')
        if not status['usb']['superspeed']:
            status['blockers'].append('usb_not_superspeed_or_device_ambiguous')
        for key, samples in self.samples.items():
            metrics = stream_metrics(samples, now, self.expected_fps)
            metrics.update(self.validity.get(key, {}))
            status['streams'][key] = metrics
            if not metrics['fresh']:
                status['blockers'].append(key + '_stale_or_missing')
            elif not metrics['timestamp_valid'] or not metrics['frame_id']:
                status['blockers'].append(key + '_timestamp_or_frame_invalid')
            missing = metrics.get('estimated_missing_frames', 0)
            rate_ok = (metrics['frames'] >= 30 and metrics.get('fps', 0) >= self.expected_fps * 0.8
                       and missing / max(1, metrics['frames'] + missing) <= 0.05)
            metrics['rate_ok'] = rate_ok
            if not rate_ok:
                status['blockers'].append(key + '_rate_unverified_or_degraded')
            if key in ('depth', 'cloud') and not metrics.get('valid', False):
                status['blockers'].append(key + '_data_invalid')
        for key, image_key in [('rgb_info', 'rgb'), ('depth_info', 'depth')]:
            info, image = self.latest.get(key), self.latest.get(image_key)
            valid = (info is not None and image is not None and info.width == image.width
                     and info.height == image.height and info.header.frame_id == image.header.frame_id
                     and np.all(np.isfinite(info.k)) and info.k[0] > 0 and info.k[4] > 0)
            status['streams'][key]['intrinsics_valid'] = bool(valid)
            if not valid:
                status['blockers'].append(key + '_intrinsics_invalid')
        rgb, depth = self.latest.get('rgb'), self.latest.get('depth')
        aligned = (rgb is not None and depth is not None and rgb.width == depth.width
                   and rgb.height == depth.height and rgb.header.frame_id == depth.header.frame_id)
        rgb_info, depth_info = self.latest.get('rgb_info'), self.latest.get('depth_info')
        aligned = (aligned and rgb_info is not None and depth_info is not None
                   and np.allclose(rgb_info.k, depth_info.k, rtol=1e-5, atol=1e-5))
        status['alignment_metadata_consistent'] = bool(aligned)
        channels = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4, 'mono8': 1}
        rgb_valid = (rgb is not None and rgb.width > 0 and rgb.height > 0
                     and rgb.encoding in channels and rgb.step >= rgb.width * channels[rgb.encoding]
                     and len(rgb.data) == rgb.height * rgb.step)
        status['rgb_payload_valid'] = bool(rgb_valid)
        if not rgb_valid:
            status['blockers'].append('rgb_payload_invalid')
        if self.samples['rgb'] and self.samples['depth']:
            skew = abs(self.samples['rgb'][-1][1] - self.samples['depth'][-1][1]) * 1000
            status['rgb_depth_skew_ms'] = round(skew, 2)
            if skew > 100:
                status['blockers'].append('rgb_depth_timestamps_unsynchronized')
        cloud = self.latest.get('cloud')
        if cloud is not None and depth is not None and cloud.header.frame_id != depth.header.frame_id:
            status['blockers'].append('point_cloud_frame_mismatch')
        if not aligned:
            status['blockers'].append('alignment_unverified')
        status['ready'] = not status['blockers']
        self.publisher.publish(String(data=json.dumps(status, separators=(',', ':'))))


def main(args=None):
    rclpy.init(args=args)
    node = CameraHealthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
