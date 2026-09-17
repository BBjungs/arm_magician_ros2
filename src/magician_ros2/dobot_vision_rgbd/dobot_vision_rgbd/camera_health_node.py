"""Read-only RGB-D health and explicit USB SuperSpeed readiness."""
from collections import deque
import json
from pathlib import Path
import threading
import time
import traceback

import numpy as np
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image, PointCloud2
from orbbec_camera_msgs.srv import GetBool
from std_msgs.msg import String


# Health must describe the newest sensor state, not spend CPU draining stale
# multi-megabyte image and point-cloud samples after a scheduling delay.
HEALTH_SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)


def usb_status(root=Path('/sys/bus/usb/devices')):
    # Gemini exposes two USB functions: 0614 carries the high-bandwidth depth
    # data on SuperSpeed, while the 0511 UVC RGB function intentionally
    # enumerates on the companion High-Speed bus.  Requiring 5 Gb/s from the
    # UVC function rejects the vendor's normal topology and hides the status of
    # the data path that actually matters.
    expected = {'0614', '0511'}
    roles = {'0614': 'depth_data', '0511': 'rgb_uvc'}
    devices = []
    for path in root.iterdir():
        try:
            if (path / 'idVendor').read_text().strip() != '2bc5':
                continue
            product = (path / 'idProduct').read_text().strip()
            if product in expected:
                serial_path = path / 'serial'
                serial = serial_path.read_text().strip() if serial_path.is_file() else ''
                devices.append({
                    'path': path.name,
                    'product': product,
                    'role': roles[product],
                    'serial': serial,
                    'speed_mbps': float((path / 'speed').read_text()),
                })
        except (OSError, ValueError):
            continue
    products = {device['product'] for device in devices}
    depth_paths = [
        device for device in devices
        if device['product'] == '0614' and device['speed_mbps'] >= 5000
    ]
    identities = {
        device['serial'] for device in devices
        if device['product'] == '0511' and device['serial']
    }
    unambiguous = len(devices) == 2 and products == expected
    return {
        'devices': devices,
        'superspeed': bool(unambiguous and len(depth_paths) == 1),
        'camera_identity': next(iter(identities)) if len(identities) == 1 else '',
        'identity_valid': bool(unambiguous and len(identities) == 1),
    }


def valid_depth_ratio(message):
    types = {'16UC1': 'u2', 'mono16': 'u2', '32FC1': 'f4'}
    dtype = np.dtype(('>' if message.is_bigendian else '<') + types[message.encoding])
    if message.height <= 0 or message.width <= 0 or message.step < message.width * dtype.itemsize:
        raise ValueError('Invalid depth dimensions or stride')
    values = np.ndarray((message.height, message.width), dtype=dtype,
                        buffer=message.data, strides=(message.step, dtype.itemsize))
    return float(np.mean(np.isfinite(values) & (values > 0)))


def valid_cloud_ratio(message):
    if message.height <= 0 or message.width <= 0 or message.point_step <= 0:
        raise ValueError('Invalid point cloud dimensions or stride')
    packed_row_step = message.width * message.point_step
    advertised_size = message.row_step * (message.height - 1) + packed_row_step
    if message.row_step >= packed_row_step and len(message.data) >= advertised_size:
        row_step = message.row_step
    elif len(message.data) >= packed_row_step * message.height:
        # Some Orbbec firmware publishes a packed cloud with a stale row_step.
        # Accept it only when the buffer proves that every point is present.
        row_step = packed_row_step
    else:
        raise ValueError('Invalid point cloud dimensions or stride')
    valid = np.ones((message.height, message.width), dtype=bool)
    for axis in ('x', 'y', 'z'):
        field = next(f for f in message.fields if f.name == axis)
        if field.datatype != 7 or field.count != 1 or field.offset + 4 > message.point_step:
            raise ValueError('Unsupported point cloud coordinate field')
        values = np.ndarray((message.height, message.width),
                            dtype=('>' if message.is_bigendian else '<') + 'f4',
                            buffer=message.data, offset=field.offset,
                            strides=(row_step, message.point_step))
        valid &= np.isfinite(values)
        if axis == 'z':
            valid &= values > 0
    return float(np.mean(valid))


def stream_metrics(samples, now, expected_fps, freshness_s=1.5):
    """Report current health separately from lifetime timestamp diagnostics.

    An old duplicate remains useful audit evidence but cannot permanently
    stale a stream whose timestamps have advanced correctly during its lease.
    """
    if not samples:
        return {'fresh': False, 'frames': 0}
    arrivals = [x[0] for x in samples]
    stamps = [x[1] for x in samples]
    gaps = np.diff(stamps)
    positive_gaps = gaps[gaps > 0]
    duplicate_timestamps = int(np.sum(gaps == 0))
    regressed_timestamps = int(np.sum(gaps < 0))
    active = [item for item in samples if 0.0 <= now - item[0] <= freshness_s]
    active_stamps = [item[1] for item in active]
    active_gaps = np.diff(active_stamps)
    current_duplicates = int(np.sum(active_gaps == 0))
    current_regressions = int(np.sum(active_gaps < 0))
    current_timestamp_valid = (bool(active_stamps)
                               and all(stamp > 0 for stamp in active_stamps)
                               and current_duplicates == 0
                               and current_regressions == 0)
    return {'fresh': now - arrivals[-1] < freshness_s, 'frames': len(samples),
            'age_ms': round((now - arrivals[-1]) * 1000, 2),
            'fps': round((len(samples) - 1) / (arrivals[-1] - arrivals[0]), 2)
            if len(samples) > 1 and arrivals[-1] > arrivals[0] else 0.0,
            'timestamp_fps': round((len(stamps) - 1) / (stamps[-1] - stamps[0]), 2)
            if len(stamps) > 1 and stamps[-1] > stamps[0] else 0.0,
            'timestamp_valid': current_timestamp_valid,
            'current_timestamp_valid': current_timestamp_valid,
            'active_window_frames': len(active),
            'current_duplicate_timestamps': current_duplicates,
            'current_regressed_timestamps': current_regressions,
            'duplicate_timestamps': duplicate_timestamps,
            'regressed_timestamps': regressed_timestamps,
            'historical_duplicate_timestamps': duplicate_timestamps,
            'historical_regressed_timestamps': regressed_timestamps,
            'median_timestamp_delta_ms': (round(float(np.median(positive_gaps)) * 1000, 3)
                                          if len(positive_gaps) else None),
            'max_stamp_gap_ms': float(np.max(gaps) * 1000.0) if len(gaps) else None,
            'estimated_missing_frames': int(sum(max(0, round(g * expected_fps) - 1) for g in gaps)),
            'frame_id': samples[-1][2]}


def synchronized_skew_ms(first, second, now, horizon_s=1.0):
    """Return the closest live timestamp pair, not unrelated latest frames."""
    first_stamps = [stamp for arrival, stamp, _ in first if 0 <= now - arrival < horizon_s]
    second_stamps = [stamp for arrival, stamp, _ in second if 0 <= now - arrival < horizon_s]
    if not first_stamps or not second_stamps:
        return None
    return min(abs(a - b) for a in first_stamps for b in second_stamps) * 1000.0


class CameraHealthNode(Node):
    def __init__(self):
        super().__init__('camera_health')
        self.declare_parameter('expected_fps', 30.0)
        self.declare_parameter('minimum_fps', 2.0)
        self.declare_parameter('freshness_timeout_s', 1.5)
        self.expected_fps = float(self.get_parameter('expected_fps').value)
        self.minimum_fps = float(self.get_parameter('minimum_fps').value)
        self.freshness_timeout_s = float(self.get_parameter('freshness_timeout_s').value)
        if not np.isfinite(self.expected_fps) or self.expected_fps <= 0:
            raise ValueError('expected_fps must be finite and positive')
        if (not np.isfinite(self.minimum_fps) or self.minimum_fps <= 0
                or self.minimum_fps > self.expected_fps):
            raise ValueError('minimum_fps must be within (0, expected_fps]')
        if not np.isfinite(self.freshness_timeout_s) or self.freshness_timeout_s <= 0:
            raise ValueError('freshness_timeout_s must be finite and positive')
        self.samples = {key: deque(maxlen=300) for key in ('rgb', 'depth', 'rgb_info', 'depth_info', 'cloud')}
        self.latest = {}
        self.validity = {}
        self.checked = {}
        self.data_lock = threading.Lock()
        # Raw callback counters are deliberately updated before the data lock.
        # They distinguish a DDS/executor delivery failure from any later health
        # processing failure; image freshness must never wait for synchronization
        # or payload inspection.
        self.callback_diagnostics = {
            key: {'enter_count': 0, 'exit_count': 0, 'exception_count': 0,
                  'last_enter_monotonic': None, 'last_exit_monotonic': None,
                  'last_exception': ''}
            for key in ('rgb', 'depth', 'rgb_info', 'depth_info', 'cloud')
        }
        # CameraInfo is emitted by the C++ Orbbec frame callback for every
        # RGB/depth frame and carries the timestamp, frame id, dimensions and
        # intrinsics needed for transport liveness.  Using it as the transport
        # heartbeat avoids deserializing two full Image payloads in Python.
        self.direct_image_health = False
        self.sensor_callback_groups = []
        self.subscriptions_ = []
        for key, topic in [('rgb', '/camera/color/camera_info'),
                           ('depth', '/camera/depth/camera_info')]:
            self.declare_parameter(key + '_topic', topic)
            callback_group = MutuallyExclusiveCallbackGroup()
            self.sensor_callback_groups.append(callback_group)
            self.subscriptions_.append(self.create_subscription(
                CameraInfo, str(self.get_parameter(key + '_topic').value),
                lambda msg, key=key: self.receive(key, msg), HEALTH_SENSOR_QOS,
                callback_group=callback_group))
        # These aliases make the status contract explicit without adding a
        # second DDS subscription for the same small CameraInfo message.
        self.latest['rgb_info'] = None
        self.latest['depth_info'] = None
        self.declare_parameter('cloud_topic', '/camera/depth/points')
        self.cloud_topic = str(self.get_parameter('cloud_topic').value)
        # Point-cloud usability belongs to calibration.  Subscribing here
        # duplicates large DDS deserialization and full-cloud scans, which can
        # starve RGB-D transport on the passive profile.
        self.declare_parameter('enable_cloud_health_validation', False)
        self.enable_cloud_health_validation = bool(
            self.get_parameter('enable_cloud_health_validation').value)
        self.cloud_sample_period_s = 0.5
        self.cloud_last_sample = None
        cloud_callback_group = MutuallyExclusiveCallbackGroup()
        self.sensor_callback_groups.append(cloud_callback_group)
        # Keep this entity alive for the lifetime of the node. Destroying and
        # recreating a subscription while a MultiThreadedExecutor is building
        # its wait set races with rclpy and can terminate the health process
        # with "InvalidHandle: destruction was requested".
        self.cloud_subscription = None
        if self.enable_cloud_health_validation:
            self.cloud_subscription = self.create_subscription(
                PointCloud2, self.cloud_topic, self.receive_cloud,
                HEALTH_SENSOR_QOS, callback_group=cloud_callback_group)
        self.vision_health = {}
        self.vision_health_time = None
        self.create_subscription(String, '/dobot_vision/status',
                                 self.receive_vision_health, 10)
        self.protection_client = self.create_client(GetBool, '/camera/get_ldp_protection_status')
        self.protection_future = None
        self.protection_active = None
        self.protection_checked_at = None
        self.create_timer(1.0, self.poll_protection)
        # Payload checks are intentionally off the image callback path.  They
        # examine only the latest retained sample and cannot stall raw receipt.
        self.create_timer(0.5, self.process_payloads)
        self.publisher = self.create_publisher(String, '/camera/health', 10)
        # Keep both health hops inside calibration's 0.5 s lease.
        self.create_timer(0.1, self.publish_health)

    def receive(self, key, msg):
        """O(1) raw stream receipt: metadata only, no image/cloud processing."""
        now = time.monotonic()
        diagnostic = self.callback_diagnostics[key]
        diagnostic['enter_count'] += 1
        diagnostic['last_enter_monotonic'] = now
        try:
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
            with self.data_lock:
                self.samples[key].append((now, stamp, msg.header.frame_id))
                self.latest[key] = msg
                if key in ('rgb', 'depth'):
                    self.samples[key + '_info'].append((now, stamp, msg.header.frame_id))
                    self.latest[key + '_info'] = msg
        except Exception:
            diagnostic['exception_count'] += 1
            diagnostic['last_exception'] = traceback.format_exc()
            self.get_logger().error(
                f"camera_health raw {key} callback failed:\n{diagnostic['last_exception']}")
        finally:
            diagnostic['exit_count'] += 1
            diagnostic['last_exit_monotonic'] = time.monotonic()
        if key == 'cloud':
            self.cloud_last_sample = now

    def receive_cloud(self, msg):
        """Retain low-rate cloud evidence without changing executor entities."""
        now = time.monotonic()
        with self.data_lock:
            previous = self.cloud_last_sample
        if previous is not None and now - previous < self.cloud_sample_period_s:
            return
        self.receive('cloud', msg)

    def process_payloads(self):
        """Validate only optional cloud evidence outside raw callbacks.

        Pixel/depth quality belongs to calibration when its demand-driven
        sensor ingest is active; transport health must not scan image payloads.
        """
        now = time.monotonic()
        with self.data_lock:
            candidates = {
                key: self.latest.get(key)
                for key in ('cloud',)
                if self.latest.get(key) is not None
                and (key != 'cloud' or getattr(self, 'enable_cloud_health_validation', True))
                and now - self.checked.get(key, 0) >= 0.5
            }
            for key in candidates:
                self.checked[key] = now
        for key, msg in candidates.items():
            try:
                ratio = valid_cloud_ratio(msg)
                validity = {'valid_ratio': ratio, 'valid': ratio > 0.01}
            except Exception:
                validity = {'valid': False, 'error': traceback.format_exc()}
                self.get_logger().error(
                    f"camera_health {key} payload validation failed:\n{validity['error']}")
            with self.data_lock:
                self.validity[key] = validity

    def receive_vision_health(self, message):
        try:
            payload = json.loads(message.data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        with self.data_lock:
            self.vision_health = payload
            self.vision_health_time = time.monotonic()

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
        cloud_validation_enabled = bool(getattr(self, 'enable_cloud_health_validation', True))
        with self.data_lock:
            samples = {key: list(value) for key, value in self.samples.items()}
            latest = dict(self.latest)
            validity = {key: dict(value) for key, value in self.validity.items()}
            vision_health = dict(getattr(self, 'vision_health', {}) or {})
            vision_health_time = getattr(self, 'vision_health_time', None)
        delegated_streams = bool(
            not getattr(self, 'direct_image_health', False)
            and vision_health_time is not None and now - vision_health_time < 1.0
            and vision_health.get('rgb_stream') and vision_health.get('depth_stream')
        )
        status = {'usb': usb_status(), 'streams': {}, 'ready': False,
                  'blockers': [], 'warnings': [],
                  'cloud_health_validation_enabled': cloud_validation_enabled,
                  'cloud_health_state': ('enabled' if cloud_validation_enabled
                                         else 'delegated_to_calibration'),
                  'callback_diagnostics': {
                      key: dict(value)
                      for key, value in getattr(self, 'callback_diagnostics', {}).items()
                  }}
        protection_fresh = (self.protection_checked_at is not None
                            and now - self.protection_checked_at < 3.0)
        status['ldp_protection_active'] = self.protection_active if protection_fresh else None
        if status['ldp_protection_active'] is not False:
            status['blockers'].append('ldp_protection_active_or_unverified')
        if not status['usb']['superspeed']:
            status['blockers'].append('usb_not_superspeed_or_device_ambiguous')
        if not status['usb']['identity_valid']:
            status['blockers'].append('camera_identity_missing_or_ambiguous')
        for key, stream_samples in samples.items():
            if key == 'cloud' and not cloud_validation_enabled:
                continue
            if delegated_streams and key in ('rgb', 'depth'):
                continue
            # Cloud is intentionally sampled at 2 Hz, so allow scheduling
            # jitter without weakening the 1 s RGB/depth freshness contract.
            lease = getattr(self, 'freshness_timeout_s', 1.5)
            freshness_s = (max(lease, self.cloud_sample_period_s * 4)
                           if key == 'cloud' else lease)
            metrics = stream_metrics(
                stream_samples, now, self.expected_fps, freshness_s)
            metrics.update(validity.get(key, {}))
            status['streams'][key] = metrics
            if not metrics['fresh']:
                status['blockers'].append(key + '_stale_or_missing')
            elif not metrics['timestamp_valid'] or not metrics['frame_id']:
                status['blockers'].append(key + '_timestamp_or_frame_invalid')
            missing = metrics.get('estimated_missing_frames', 0)
            if key in ('rgb', 'depth'):
                rate_ok = metrics['frames'] >= 10 and metrics.get('fps', 0) > self.minimum_fps
            else:
                # CameraInfo and point-cloud evidence must be live and valid,
                # but the >20 Hz acceptance threshold applies to RGB/depth.
                rate_ok = metrics['frames'] >= 1 and metrics['fresh']
            metrics['rate_ok'] = rate_ok
            metrics['state'] = ('STALE' if not metrics['fresh'] else
                                ('READY' if rate_ok else 'DEGRADED_RATE'))
            if not rate_ok:
                status['warnings'].append(key + '_rate_unverified_or_degraded')
            expected_rate_ok = (key not in ('rgb', 'depth') or (
                metrics['frames'] >= 30
                and metrics.get('fps', 0) >= self.expected_fps * 0.8
                and missing / max(1, metrics['frames'] + missing) <= 0.05
            ))
            metrics['expected_rate_ok'] = expected_rate_ok
            if key in ('rgb', 'depth') and rate_ok and not expected_rate_ok:
                status['warnings'].append(key + '_below_requested_rate')
            if key == 'cloud' and not metrics.get('valid', False):
                status['blockers'].append(key + '_data_invalid')
        if delegated_streams:
            for key, source_key, age_key in (
                    ('rgb', 'rgb_stream', 'rgb_age_ms'),
                    ('depth', 'depth_stream', 'depth_age_ms')):
                source = dict(vision_health[source_key])
                try:
                    age_ms = float(vision_health.get(age_key))
                    if not np.isfinite(age_ms) or age_ms < 0:
                        raise ValueError('Invalid source image age')
                    age_ms += max(0.0, now - vision_health_time) * 1000.0
                except (TypeError, ValueError):
                    age_ms = None
                metrics = {
                    'fresh': age_ms is not None and age_ms < 1000.0,
                    'frames': int(source.get('count', 0)),
                    'age_ms': age_ms,
                    'fps': float(source.get('fps', 0.0)),
                    'max_stamp_gap_ms': source.get('max_gap_ms'),
                    'timestamp_valid': bool(source.get('timestamp_valid')),
                    'frame_id': str(source.get('frame_id') or ''),
                }
                metrics['rate_ok'] = metrics['frames'] >= 10 and metrics['fps'] > self.minimum_fps
                metrics['state'] = ('STALE' if not metrics['fresh'] else
                                    ('READY' if metrics['rate_ok'] else 'DEGRADED_RATE'))
                metrics['expected_rate_ok'] = (
                    metrics['frames'] >= 30 and metrics['fps'] >= self.expected_fps * 0.8
                )
                if key == 'depth':
                    metrics['valid_ratio'] = vision_health.get('depth_valid_ratio', 0.0)
                    metrics['valid'] = bool(vision_health.get('depth_data_valid'))
                status['streams'][key] = metrics
                if not metrics['fresh']:
                    status['blockers'].append(key + '_stale_or_missing')
                if not metrics['timestamp_valid'] or not metrics['frame_id']:
                    status['blockers'].append(key + '_timestamp_or_frame_invalid')
                if not metrics['rate_ok']:
                    status['warnings'].append(key + '_rate_unverified_or_degraded')
                if key == 'depth' and not metrics['valid']:
                    status['blockers'].append('depth_data_invalid')
        for key, image_key in [('rgb_info', 'rgb'), ('depth_info', 'depth')]:
            info, image = latest.get(key), latest.get(image_key)
            delegated_frame = status['streams'].get(image_key, {}).get('frame_id')
            valid = (info is not None
                     and (delegated_streams or image is not None)
                     and (delegated_streams or info.width == image.width)
                     and (delegated_streams or info.height == image.height)
                     and info.header.frame_id == (delegated_frame if delegated_streams else image.header.frame_id)
                     and np.all(np.isfinite(info.k)) and info.k[0] > 0 and info.k[4] > 0)
            status['streams'][key]['intrinsics_valid'] = bool(valid)
            if not valid:
                status['blockers'].append(key + '_intrinsics_invalid')
        rgb, depth = latest.get('rgb'), latest.get('depth')
        aligned = (bool(vision_health.get('registered_depth'))
                   and status['streams']['rgb'].get('frame_id') == status['streams']['depth'].get('frame_id')) if delegated_streams else (
                       rgb is not None and depth is not None and rgb.width == depth.width
                       and rgb.height == depth.height and rgb.header.frame_id == depth.header.frame_id)
        rgb_info, depth_info = latest.get('rgb_info'), latest.get('depth_info')
        aligned = (aligned and rgb_info is not None and depth_info is not None
                   and np.allclose(rgb_info.k, depth_info.k, rtol=1e-5, atol=1e-5))
        status['alignment_metadata_consistent'] = bool(aligned)
        channels = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4, 'mono8': 1}
        if delegated_streams:
            rgb_valid = bool(vision_health.get('rgb_payload_valid'))
        elif hasattr(rgb, 'k'):
            rgb_valid = (rgb.width > 0 and rgb.height > 0
                         and np.all(np.isfinite(rgb.k)) and rgb.k[0] > 0 and rgb.k[4] > 0)
        else:
            # Compatibility for direct-image unit fixtures; runtime uses the
            # CameraInfo branch above and never needs pixel payload validation.
            rgb_valid = (rgb is not None and rgb.width > 0 and rgb.height > 0
                         and rgb.encoding in channels
                         and rgb.step >= rgb.width * channels[rgb.encoding]
                         and len(rgb.data) == rgb.height * rgb.step)
        status['rgb_payload_valid'] = bool(rgb_valid)
        status['depth_quality_state'] = 'delegated_to_calibration'
        if not rgb_valid:
            status['blockers'].append('rgb_payload_invalid')
        skew = (vision_health.get('sync_delta_ms') if delegated_streams else
                synchronized_skew_ms(samples['rgb'], samples['depth'], now))
        if skew is None:
            status['blockers'].append('rgb_depth_timestamps_unsynchronized')
        else:
            status['rgb_depth_skew_ms'] = round(skew, 2)
            if skew > 100:
                status['blockers'].append('rgb_depth_timestamps_unsynchronized')
        # This is a closest pair from live samples only, not arbitrary latest
        # frames.  The markerless node may retain it as synchronizer evidence.
        status['rgb_depth_sync_valid'] = bool(skew is not None and skew <= 100)
        cloud = latest.get('cloud')
        depth_frame = status['streams'].get('depth', {}).get('frame_id')
        if cloud is not None and depth_frame and cloud.header.frame_id != depth_frame:
            status['blockers'].append('point_cloud_frame_mismatch')
        if not aligned:
            status['blockers'].append('alignment_unverified')
        status['ready'] = not status['blockers']
        self.publisher.publish(String(data=json.dumps(status, separators=(',', ':'))))


def main(args=None):
    rclpy.init(args=args)
    node = CameraHealthNode()
    # Separate Gemini RGB, depth and cloud readers must all make progress.
    # A single executor starves depth/cloud on this live hardware while RGB
    # keeps arriving, so use bounded parallel callback execution.
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown(timeout_sec=2)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
