"""ROS sensor adapters shared by simulation, passive monitoring and readiness."""

from collections import Counter, deque
from contextlib import nullcontext
import math
import time
import traceback

import cv2
from cv_bridge import CvBridge, CvBridgeError
from dobot_msgs.msg import AlarmState, DeviceStatus, ToolState
from geometry_msgs.msg import PoseStamped
import numpy as np
from orbbec_camera_msgs.srv import GetDeviceInfo
from rclpy.qos import qos_profile_sensor_data
from rclpy.utilities import get_rmw_implementation_identifier
from sensor_msgs.msg import CameraInfo, Image, JointState

from .rgbd_sync import append_sample, calibration_signature, header_ns, select_frame
from .motion import Readback
from .vision import Observation


JOINT_NAMES = [f'magician_joint_{index}' for index in range(1, 5)]


def live_camera_status(rgb, depth):
    if depth:
        return 'LIVE ORBBEC RGB-D'
    return 'LIVE ORBBEC RGB · Depth unavailable' if rgb else 'Camera Offline'


def stamp_seconds(header):
    return header.stamp.sec + header.stamp.nanosec / 1e9


def local_stamp(node, header, clock):
    stamp = stamp_seconds(header)
    if not stamp:
        return float('-inf')
    return clock() - (node.get_clock().now().nanoseconds / 1e9 - stamp)


class CameraReceiver:
    def __init__(self, node, config, clock, *, simulated=False, trace=False):
        self.node, self.config, self.clock = node, config, clock
        self.bridge = CvBridge()
        self.device = None if simulated else node.create_client(GetDeviceInfo, config['device_info_service'])
        self.device_name = None
        self.endpoints = {}
        self.pending_info = None
        self.source_generation = 0
        self.invalid_info = False
        self.overflow = dict(rgb=0, depth=0, info=0)
        self.last_info_eviction = None
        self.trace = deque(maxlen=2048) if trace else None
        self.trace_sequence = 0
        self.valid_generation = None
        self.valid_until = float('-inf')
        self.last_match = None
        self.next_check = 0.
        self.info = None
        self.info_stamps = deque(maxlen=12)
        self.rgb = deque(maxlen=8)
        self.depth = deque(maxlen=8)
        self.last_stamp = 0.
        self.rgb_issue = 'Waiting for RGB frames'
        self.depth_issue = 'Waiting for a registered depth frame'
        self.subscriptions = {}
        self.counts = {}
        self.rejections = {}
        self.callback_times = {}
        self.callback_timing = {}
        self.last_failure = {}
        self.health_started = clock()
        for kind, msg, handler in (('rgb', Image, self.on_rgb), ('depth', Image, self.on_depth),
                                   ('info', CameraInfo, self.on_info)):
            self.counts[kind] = dict(raw=0, validated=0, rejected=0, enqueued=0,
                                     duplicates=0, capacity_rejected=0, exceptions=0)
            self.rejections[kind] = Counter()
            self.callback_times[kind] = deque()
            self.callback_timing[kind] = dict(rmw_receive_to_callback_ms=None, duration_ms=None)
            self.subscriptions[kind] = node.create_subscription(
                msg, config[f'{kind}_topic'], self.subscription_callback(kind, handler),
                qos_profile_sensor_data)

    def subscription_callback(self, kind, handler):
        counts = self.counts[kind]
        times = self.callback_times[kind]
        timing = self.callback_timing[kind]

        def receive(message, message_info):
            counts['raw'] += 1
            received = self.clock()
            times.append(received)
            while times[0] < received - 5:
                times.popleft()
            generation = self.source_generation
            try:
                # RMW receive time is a system timestamp. This interval includes
                # take/deserialization and scheduling, not just executor wait.
                stamp = message_info.get('received_timestamp') if isinstance(message_info, dict) else None
                latency = time.time_ns() - stamp if stamp else -1
                timing['rmw_receive_to_callback_ms'] = latency / 1e6 if latency >= 0 else None
                reason = handler(message, received)
                if reason:
                    self.rejections[kind][reason] += 1
                    counts['rejected'] += 1
                    self.last_failure[kind] = dict(reason=reason, monotonic=received,
                                                   generation=generation, header_ns=header_ns(message.header),
                                                   frame_id=message.header.frame_id, width=message.width,
                                                   height=message.height, encoding=getattr(message, 'encoding', None))
            except Exception as error:
                counts['exceptions'] += 1
                self.last_failure[kind] = dict(reason='callback_exception',
                                               exception=type(error).__name__,
                                               function=traceback.extract_tb(error.__traceback__)[-1].name,
                                               monotonic=received, generation=generation)
                if kind == 'info':
                    self.invalid_info = True
                    self.info = None
                    self.source_generation += 1
                    self.rgb.clear()
                    self.depth.clear()
                    self.info_stamps.clear()
                if counts['exceptions'] == 1:
                    self.node.get_logger().error(f'{kind} callback failed: {type(error).__name__}')
            finally:
                timing['duration_ms'] = (self.clock() - received) * 1000

        return receive

    def callback_health(self, now):
        topics = {}
        for kind, subscription in self.subscriptions.items():
            times = self.callback_times[kind].copy()
            window = min(5., now - self.health_started)
            topic = self.config[f'{kind}_topic']
            publishers = self.node.get_publishers_info_by_topic(topic)
            topics[kind] = dict(topic=topic, **self.counts[kind],
                                reasons=dict(self.rejections[kind]),
                                rate_hz=(sum(now - 5 <= t <= now for t in times) / window
                                         if window > 0 else None),
                                last_callback_monotonic=times[-1] if times else None,
                                last_receive_age_s=max(0., now-times[-1]) if times else None,
                                **self.callback_timing[kind],
                                last_failure=self.last_failure.get(kind),
                                matched_publishers=subscription.get_publisher_count(),
                                publishers=[dict(node=entry.node_namespace.rstrip('/') + '/' + entry.node_name,
                                                 gid=bytes(entry.endpoint_gid).hex(),
                                                 reliability=entry.qos_profile.reliability.name,
                                                 history=entry.qos_profile.history.name,
                                                 depth=entry.qos_profile.depth) for entry in publishers])
        return dict(topics=topics, monotonic=now, generation=self.source_generation,
                    expected_driver=self.config['driver_node'], device=self.device_name,
                    subscriber_qos=dict(reliability=qos_profile_sensor_data.reliability.name,
                                        history=qos_profile_sensor_data.history.name,
                                        depth=qos_profile_sensor_data.depth),
                    rmw=get_rmw_implementation_identifier(), last_match=self.last_match,
                    queues=dict(rgb=len(self.rgb), depth=len(self.depth), info=len(self.info_stamps)))

    def publisher(self, kind):
        entries = self.node.get_publishers_info_by_topic(self.config[f'{kind}_topic'])
        if not entries:
            return b''  # No publisher. RGB preview can continue without depth or CameraInfo.
        if len(entries) == 1:
            entry = entries[0]
            if entry.node_namespace.rstrip('/') + '/' + entry.node_name == self.config['driver_node']:
                return bytes(entry.endpoint_gid)
        return None  # A competing or unexpected publisher invalidates the source.

    def refresh_source(self, now):
        if self.device is None:
            return True
        if now >= self.next_check:
            endpoints = {kind: self.publisher(kind) for kind in ('rgb', 'depth', 'info')}
            if endpoints != self.endpoints:
                self.source_generation += 1
            ready = self.device.service_is_ready()
            if (endpoints['rgb'] != self.endpoints.get('rgb') or not ready
                    or None in endpoints.values()):
                self.device_name = self.info = None
                self.info_stamps.clear()
                self.rgb.clear()
                self.depth.clear()
                self.last_stamp = 0.
                if self.pending_info is not None:
                    self.pending_info.cancel()
                    self.pending_info = None
            else:
                # A depth or calibration publisher can restart independently of RGB.
                if any(endpoints[k] and endpoints[k] != self.endpoints.get(k)
                       for k in ('depth', 'info')):
                    self.rgb.clear()
                    self.depth.clear()
                    self.info_stamps.clear()
                if endpoints['depth'] != self.endpoints.get('depth'):
                    self.depth.clear()
                if endpoints['info'] != self.endpoints.get('info'):
                    self.info = None
                    self.info_stamps.clear()
            self.endpoints = endpoints
            self.next_check = now + .25
            if (endpoints['rgb'] and None not in endpoints.values() and ready
                    and not self.device_name and self.pending_info is None):
                self.pending_info = self.device.call_async(GetDeviceInfo.Request())
                self.request_time = now
        if self.pending_info is not None:
            future = self.pending_info
            if future.done():
                self.pending_info = None
                if not future.cancelled() and future.exception() is None:
                    response = future.result()
                    if response.success and response.info.serial_number:
                        self.device_name = response.info.name
            elif now - self.request_time > 2:
                future.cancel()
                self.pending_info = None
        return bool(self.device_name)

    def rejection_reason(self, kind, message):
        if self.device is not None:
            if not self.device_name:
                return 'unverified_device'
            current = self.publisher(kind)
            if not current:
                return 'publisher_identity_mismatch' if current is None else 'missing_publisher'
            if current != self.endpoints.get(kind):
                return 'source_generation_mismatch'
        age = self.node.get_clock().now().nanoseconds / 1e9 - stamp_seconds(message.header)
        if not self.dimensions_match(message):
            if kind == 'rgb':
                self.rgb_issue = f'Unexpected RGB geometry: {message.width}x{message.height}, {message.header.frame_id}'
            return ('frame_id' if message.header.frame_id != self.config['frame'] else 'dimensions')
        if not 0 <= age <= self.config['freshness']:
            if kind == 'rgb':
                self.rgb_issue = f'RGB timestamp outside freshness window (age {age:.3f} s)'
            return 'future_header' if age < 0 else 'stale_header'
        return None

    def offline_reason(self):
        missing = [self.config[f'{kind}_topic'] for kind in ('rgb', 'depth', 'info')
                   if self.endpoints.get(kind) is None or (kind == 'rgb' and not self.endpoints[kind])]
        if missing:
            return 'Waiting for a unique Orbbec publisher on ' + ', '.join(missing)
        if not self.device_name:
            return 'Waiting for Orbbec device identity from ' + self.config['device_info_service']
        return self.rgb_issue

    def dimensions_match(self, msg):
        return (msg.width == self.config['width'] and msg.height == self.config['height']
                and msg.header.frame_id == self.config['frame'])

    def record(self, event, **fields):
        if self.trace is not None:
            self.trace_sequence += 1
            self.trace.append(dict(seq=self.trace_sequence, event=event,
                                   generation=self.source_generation,
                                   queues=(len(self.rgb), len(self.depth), len(self.info_stamps)),
                                   **fields))

    def enqueue(self, kind, queue, value):
        evicted = append_sample(kind, queue, value, self.rgb,
                                round(self.config['max_depth_skew'] * 1e9))
        # append_sample leaves a retained incoming sample at the tail, including
        # when rebuilding the protected CameraInfo history at capacity.
        if queue[-1] is value:
            self.counts[kind]['enqueued'] += 1
        elif evicted is None:
            self.counts[kind]['duplicates'] += 1
        else:
            self.counts[kind]['capacity_rejected'] += 1
        if self.trace is not None:
            self.record('arrival', topic=kind, header_ns=value[0],
                        received=value[3 if kind == 'depth' else 2],
                        evicted_ns=evicted, eviction_reason='capacity' if evicted is not None else None)
        if evicted is not None:
            if kind == 'info':
                self.last_info_eviction = dict(header_ns=evicted, incoming_ns=value[0],
                                               incoming_received_monotonic=value[2])
            self.overflow[kind] += 1

    def on_info(self, message, received=None):
        received = self.clock() if received is None else received
        age_ns = self.node.get_clock().now().nanoseconds - header_ns(message.header)
        if not 0 <= age_ns <= round(self.config['freshness'] * 1e9):
            self.record('rejected_info', header_ns=header_ns(message.header), received=received,
                        reason='header_age')
            return 'future_header' if age_ns < 0 else 'stale_header'
        reason = self.rejection_reason('info', message)
        if not reason and not (all(map(math.isfinite, message.k)) and message.k[0] > 0 and message.k[4] > 0):
            reason = 'invalid_intrinsics'
        calibrated = reason is None
        signature = calibration_signature(message)
        if self.info is not None and (not calibrated or self.info != signature):
            self.source_generation += 1
            self.info_stamps.clear()
            self.rgb.clear()
            self.depth.clear()
        self.invalid_info = not calibrated
        self.info = signature if calibrated else None
        if calibrated:
            self.counts['info']['validated'] += 1
            self.enqueue("info", self.info_stamps, (header_ns(message.header),
                                     local_stamp(self.node, message.header, self.clock), received))
        else:
            self.record('rejected_info', header_ns=header_ns(message.header), received=received,
                        reason=reason)
            self.info_stamps.clear()
            return reason

    def on_rgb(self, message, received=None):
        received = self.clock() if received is None else received
        reason = self.rejection_reason('rgb', message)
        if reason:
            return reason
        if message.encoding.lower() not in ('rgb8', 'bgr8', 'rgba8', 'bgra8'):
            self.rgb_issue = f'Unsupported RGB encoding: {message.encoding}'
            return 'unsupported_encoding'
        stamp = header_ns(message.header)
        if stamp <= self.last_stamp:
            return 'superseded_rgb'
        self.counts['rgb']['validated'] += 1
        try:
            pixels = self.bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
        except (ValueError, TypeError, CvBridgeError, cv2.error):
            self.rgb_issue = 'RGB frame could not be decoded'
            return 'decode_failure'
        self.rgb_issue = 'No fresh RGB frame'
        self.enqueue("rgb", self.rgb, (stamp, local_stamp(self.node, message.header, self.clock),
                         received, pixels))

    def on_depth(self, message, received=None):
        received = self.clock() if received is None else received
        reason = self.rejection_reason('depth', message)
        if reason:
            return reason
        if message.encoding not in ('16UC1', '32FC1'):
            return 'unsupported_encoding'
        self.counts['depth']['validated'] += 1
        try:
            values = self.bridge.imgmsg_to_cv2(message, desired_encoding='passthrough')
        except (ValueError, TypeError, CvBridgeError, cv2.error):
            return 'decode_failure'
        if message.encoding == '16UC1':
            values = values.astype(np.float32) / 1000.
        sample = values[::16, ::16]
        coverage = np.mean(np.isfinite(sample) & (sample > 0))
        if not coverage >= self.config['minimum_valid_depth_fraction']:
            self.record('rejected_depth', header_ns=header_ns(message.header), received=received,
                        reason='insufficient_valid_depth')
            return 'insufficient_valid_depth'
        self.enqueue("depth", self.depth, (header_ns(message.header),
                           local_stamp(self.node, message.header, self.clock), values, received))

    def pending_preview(self, now):
        timeout = self.config['freshness']
        sample = max((r for r in self.rgb if 0 <= now-r[1] <= timeout
                      and 0 <= now-r[2] <= timeout), key=lambda r: r[0], default=None)
        if sample is not None:
            stamp, local, received, pixels = sample
            return Observation(local, received, pixels, None, source_stamp=stamp / 1e9, source_ns=stamp)

    def take(self, now):
        if not self.refresh_source(now) or not self.rgb:
            return None

        def evaluated(r, d, i, reason):
            self.record('evaluate', rgb_ns=r[0], depth_ns=d[0] if d else None,
                        info_ns=i[0] if i else None, rgb_received=r[2],
                        depth_received=d[3] if d else None, info_received=i[2] if i else None,
                        depth_skew_ns=d[0]-r[0] if d else None,
                        info_skew_ns=i[0]-r[0] if i else None, now=now,
                        waited_ms=(now-r[2])*1000, reason=reason or 'matched')

        r, d, info, reason = select_frame(self.rgb, self.depth, self.info_stamps, now,
                                          self.config['freshness'], self.config['max_depth_skew'],
                                          self.invalid_info,
                                          retain_fresh_triplet=(self.valid_generation == self.source_generation
                                                              and now <= self.valid_until),
                                          trace=evaluated if self.trace is not None else None)
        if r is None:
            if reason == 'stale_rgb':
                self.rgb_issue = 'Stale RGB in receiver queue'
                self.record('expiry', headers=[r[0] for r in self.rgb], now=now)
                self.rgb.clear()
            return None
        stamp, local, received, rgb = r
        self.last_match = dict(reason=reason or 'matched', rgb_ns=stamp,
                               depth_ns=d[0] if d else None, info_ns=info[0] if info else None,
                               rgb_received=received, depth_received=d[3] if d else None,
                               info_received=info[2] if info else None,
                               last_info_eviction=self.last_info_eviction,
                               queues=(len(self.rgb), len(self.depth), len(self.info_stamps)))
        self.record('emit', rgb_ns=stamp, now=now, reason=reason or 'matched',
                    superseded=[r[0] for r in self.rgb if r[0] < stamp])
        self.valid_generation = None
        self.last_stamp = stamp
        self.rgb = deque((entry for entry in self.rgb if entry[0] > stamp), maxlen=self.rgb.maxlen)
        self.depth_issue = reason or 'Waiting for fresh registered depth'
        if reason:
            return Observation(local, received, rgb, None, source_stamp=stamp / 1e9, source_ns=stamp)
        depth_source, depth_stamp, depth, _ = d
        self.valid_generation = self.source_generation
        self.valid_until = min(local, received, depth_stamp, info[1]) + self.config['freshness']
        return Observation(local, received, rgb, depth, depth_stamp,
                           True, stamp / 1e9, depth_source / 1e9, info[1],
                           header_skew_ns=abs(stamp-depth_source), source_ns=stamp)


class RobotReceiver:
    def __init__(self, node, config, clock, *, lock=None):
        self.lock = lock if lock is not None else nullcontext()
        self.node, self.clock = node, clock
        self.timeout = config['telemetry_timeout']
        self.samples = {}
        self.disconnected_at = None
        for key, kind in (('device', DeviceStatus), ('alarms', AlarmState),
                          ('joints', JointState), ('tcp', PoseStamped),
                          ('suction', ToolState), ('gripper', ToolState)):
            node.create_subscription(kind, config['topics'][key],
                                     lambda msg, name=key: self.receive(name, msg), 10)

    def receive(self, key, message):
        with self.lock:
            stamp = stamp_seconds(message.header)
            if self.disconnected_at is not None and stamp <= self.disconnected_at:
                return
            if key == 'device' and not message.connected:
                self.disconnected_at = stamp
                self.samples.clear()
            self.samples[key] = local_stamp(self.node, message.header, self.clock), message

    def snapshot(self):
        keys = ('device', 'alarms', 'joints', 'tcp')
        if not all(key in self.samples for key in keys):
            return Readback(0.)
        device, alarm, joints, tcp = [self.samples[key][1] for key in keys]
        stamp = min(self.samples[key][0] for key in keys)
        if (len(joints.name) != len(joints.position)
                or any(name not in joints.name for name in JOINT_NAMES)
                or tcp.header.frame_id != 'magician_base_link'):
            return Readback(stamp)
        angles = tuple(math.degrees(joints.position[joints.name.index(name)]) for name in JOINT_NAMES)
        p, q = tcp.pose.position, tcp.pose.orientation
        if not math.isclose(math.hypot(q.x, q.y, q.z, q.w), 1, abs_tol=0.01):
            return Readback(stamp)
        yaw = math.degrees(math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z)))
        pose = (p.x * 1000, p.y * 1000, p.z * 1000, yaw)
        if not all(map(math.isfinite, (*pose, *angles))):
            return Readback(stamp)
        return Readback(stamp, device.connected, alarm.valid, tuple(alarm.codes), pose, angles)


    def device_status(self, now):
        def fresh(topic):
            sample = self.samples.get(topic)
            return sample[1] if sample and 0 <= now - sample[0] <= self.timeout else None

        device = fresh('device')
        connected = bool(device and device.connected)
        alarm = fresh('alarms') if connected else None
        result = {
            'device_connected': connected,
            'device_status_stale': device is None and 'device' in self.samples
                                   and self.samples['device'][1].connected,
            'device_name': device.device_name if connected else None,
            'firmware_version': list(device.firmware_version) if connected else [],
            'alarms': list(alarm.codes) if alarm and alarm.valid else [],
            'alarm_valid': bool(alarm and alarm.valid),
        }
        for key in ('suction', 'gripper'):
            tool = fresh(key) if connected else None
            result[key] = {'control_enabled': tool.control_enabled, 'active': tool.active} if tool and tool.valid else None
        return result


class CameraPublisher:
    def __init__(self, node, config, camera, pose):
        self.node, self.camera, self.pose = node, camera, pose
        self.config, self.bridge = config, CvBridge()
        self.rgb = node.create_publisher(Image, config['rgb_topic'], qos_profile_sensor_data)
        self.depth = node.create_publisher(Image, config['depth_topic'], qos_profile_sensor_data)
        self.info = node.create_publisher(CameraInfo, config['info_topic'], qos_profile_sensor_data)
        self.enabled = True
        node.create_timer(1 / config['mock_fps'], self.publish)

    def publish(self):
        if not self.enabled:
            return
        bgr, depth = self.camera.render(self.pose())
        color = self.bridge.cv2_to_imgmsg(bgr, encoding='bgr8')
        color.header.stamp = self.node.get_clock().now().to_msg()
        color.header.frame_id = self.config['frame']
        camera_info = CameraInfo(header=color.header, width=color.width, height=color.height)
        camera_info.k = [520., 0., color.width/2, 0., 520., color.height/2, 0., 0., 1.]
        self.info.publish(camera_info)
        if self.camera.depth_enabled:
            depth_msg = self.bridge.cv2_to_imgmsg(depth, encoding='16UC1')
            depth_msg.header = color.header
            self.depth.publish(depth_msg)
        self.rgb.publish(color)
