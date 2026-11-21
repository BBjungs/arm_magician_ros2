"""Native ROS sensor/action integration and HTTP requests using in-memory sockets."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from http.client import HTTPResponse
from io import BytesIO
import json
from pathlib import Path
from threading import Event
import time
import unittest
import uuid
from unittest.mock import Mock, patch

import cv2
from cv_bridge import CvBridge
import numpy as np
from orbbec_camera_msgs.srv import GetDeviceInfo
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image

from dobot_msgs.msg import AlarmState, DeviceStatus, ToolState
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
import rclpy

from dobot_auto_center.action import GuardedMove
from dobot_auto_center.config import load
from dobot_auto_center.node import AutoCenterNode
from dobot_auto_center.ros_sensors import JOINT_NAMES
from dobot_auto_center.ros_motion import PendingAction
from dobot_auto_center.web import NetworkPolicy, load_assets, make_handler

from test_core import CONFIG


HOST = '172.30.10.101:8080'
PEER = '172.30.10.42'
WEB = Path(__file__).resolve().parents[2] / 'src' / 'dobot_auto_center' / 'web'


class Connection:
    def __init__(self, request=b''):
        self.input = BytesIO(request)
        self.output = BytesIO()

    def makefile(self, *_):
        return self.input

    def settimeout(self, _):
        pass

    def sendall(self, data):
        self.output.write(data)


class Integration(unittest.TestCase):
    def setUp(self):
        rclpy.init()
        self.addCleanup(rclpy.try_shutdown)
        self.config = load(CONFIG)
        self.config['hardware']['simulation_mode'] = True
        self.config['web'].update(bind='172.30.10.101', allowed_clients=['172.30.10.0/24'])
        self.node = AutoCenterNode(self.config)
        self.addCleanup(self.node.destroy_node)
        self.addCleanup(self.node.close)
        self.handler = make_handler(self.node, load_assets(WEB))
        self.lease = ''
        self.next_heartbeat = 0.

    def http(self, path, body=None, request_id=None, *, host=HOST, peer=PEER,
             origin=None, handler=None):
        headers = {'Host': host}
        if origin is not None:
            headers['Origin'] = origin
        command = 'GET'
        payload = b''
        if body is not None:
            command = 'POST'
            payload = json.dumps(body).encode()
            headers.update({'Content-Type': 'application/json', 'Content-Length': str(len(payload)),
                            'X-Control-Lease': self.lease,
                            'Idempotency-Key': request_id or str(uuid.uuid4())})
        request = f'{command} {path} HTTP/1.1\r\n'
        request += ''.join(f'{k}: {v}\r\n' for k, v in headers.items()) + '\r\n'
        connection = Connection(request.encode() + payload)
        (handler or self.handler)(connection, (peer, 0), None)
        reply = HTTPResponse(Connection(connection.output.getvalue()))
        reply.begin()
        data = reply.read()
        if reply.getheader('Content-Type') == 'application/json':
            data = json.loads(data)
        return reply.status, data

    def post(self, path, body=None, expected=200):
        status, data = self.http('/api/' + path, body if body is not None else {})
        self.assertEqual(status, expected, data)
        return data

    def status(self):
        status, data = self.http('/api/status')
        self.assertEqual(status, 200)
        return data

    def wait(self, condition, seconds=12, heartbeat=True):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if heartbeat and self.lease and time.monotonic() >= self.next_heartbeat:
                self.post('heartbeat')
                self.next_heartbeat = time.monotonic() + .45
            rclpy.spin_once(self.node, timeout_sec=.035)
            state = self.status()
            if condition(state):
                return state
        self.fail(self.status())

    def acquire(self):
        self.lease = self.post('control')['lease']

    def confirmed(self, action):
        nonce = self.post('confirm', {'action': action})['confirmation']
        payload = {'action': action, 'confirmation': nonce}
        key = str(uuid.uuid4())
        status, data = self.http('/api/command', payload, request_id=key)
        self.assertEqual(status, 200, data)
        self.assertEqual(self.http('/api/command', payload, request_id=key), (status, data))
        self.post('command', payload, expected=409)

    def prepare(self):
        self.acquire()
        self.post('command', {'action': 'camera'})
        frame = self.wait(lambda s: s['camera'] and s['depth'])
        status, data = self.http('/api/frame/' + str(frame['frame_id']) + '.jpg')
        self.assertEqual(status, 200)
        self.assertTrue(data.startswith(b'\xff\xd8'))
        self.assertEqual(frame['camera_source'], 'mock')
        self.assertEqual(frame['camera_status'], 'MOCK RGB')
        self.assertGreater(frame['camera_timestamp'], 0)
        self.confirmed('home')
        self.wait(lambda s: s['state'] == 'READY' and s['homed'])
        self.assertFalse(self.status()['observation_pose'])
        self.confirmed('observation')
        self.wait(lambda s: s['observation_pose'])
        self.post('command', {'action': 'detect'})
        frame = self.wait(lambda s: bool(s['detections']))
        x, y, w, h = frame['detections'][0]['box']
        self.post('command', {'action': 'select', 'frame_id': frame['frame_id'],
                              'roi': [x, y, x+w, y+h]})

    def test_http_ros_full_mock_workflow_and_graph(self):
        html_status, html = self.http('/')
        self.assertEqual(html_status, 200)
        self.assertIn(b'Dobot Eye-in-Hand Auto Center', html)
        self.assertEqual(self.http('/health')[0], 503)
        self.wait(lambda s: s['state'] == 'IDLE')
        code, health = self.http('/health')
        self.assertEqual(code, 200)
        self.assertEqual(health['mode'], 'simulation')
        self.assertEqual(health['camera_status'], 'MOCK CAMERA OFFLINE')
        self.assertFalse(health['real_motion_enabled'])
        self.assertIn(b'getRandomValues', self.http('/app.js')[1])
        self.assertIn(b'@media', self.http('/app.css')[1])
        self.assertFalse(self.node.motion.transport.commands)
        self.assertEqual(self.post('command', {'action': 'home'}, expected=403)['error'],
                         'Exclusive control lease required')
        self.prepare()
        names = dict(self.node.get_topic_names_and_types())
        image_prefix = '/dobot_auto_center/simulation/camera'
        self.assertEqual(names[image_prefix + '/color/image_raw'], ['sensor_msgs/msg/Image'])
        self.assertEqual(names[image_prefix + '/depth/image_raw'], ['sensor_msgs/msg/Image'])
        self.assertNotIn('/camera/color/image_raw', names)
        self.assertIn('/dobot_auto_center/guarded_move/_action/send_goal',
                      dict(self.node.get_service_names_and_types()))
        self.confirmed('center')
        result = self.wait(lambda s: s['state'] == 'CENTERED')
        self.assertLessEqual(max(map(abs, result['error'])), 12)
        self.assertEqual(result['stable_frames'], 5)
        self.assertEqual(result['motion'], 'HOLDING')
        self.assertGreater(len(self.node.motion.transport.commands), 2)

    def test_stop_works_during_native_action_from_peer_without_lease(self):
        self.prepare()
        self.confirmed('center')
        self.wait(lambda s: s['state'] == 'CENTERING' and s['motion'] == 'MOVING')
        self.post('control', expected=409)
        self.lease = ''
        self.post('stop')
        self.wait(lambda s: s['state'] == 'STOPPED')
        count = len(self.node.motion.transport.commands)
        for _ in range(16):
            rclpy.spin_once(self.node, timeout_sec=.025)
        self.assertEqual(count, len(self.node.motion.transport.commands))
        self.assertIsNone(self.node.motion.transport.travel)

    def test_private_action_rejects_unminted_permit(self):
        self.wait(lambda _: self.node.action.client.server_is_ready())
        goal = GuardedMove.Goal(permit='forged', operation='step',
                                tcp_mm_deg=[204., 0., 120., 0.], speed_mm_s=15.)
        future = self.node.action.client.send_goal_async(goal)
        self.wait(lambda _: future.done())
        self.assertFalse(future.result().accepted)
        self.assertFalse(self.node.motion.transport.commands)

    def test_lan_scope_and_same_origin(self):
        self.assertEqual(self.http('/', peer='172.30.11.4')[0], 403)
        self.assertEqual(self.http('/', peer='198.51.100.4')[0], 403)
        self.assertEqual(self.http('/', host='controller.example:8080')[0], 403)
        self.assertEqual(self.http('/api/stop', {}, origin='http://other.example')[0], 403)
        self.assertEqual(self.http('/api/stop', {}, peer='172.30.11.4')[0], 403)
        self.assertEqual(self.http('/api/control', {}, origin='http://other.example')[0], 403)
        self.assertEqual(self.http('/api/control', {}, origin=f'http://{HOST}')[0], 200)
        for bind in ('0.0.0.0', '198.51.100.4'):
            with self.assertRaises(ValueError):
                NetworkPolicy({'bind': bind, 'port': 8080, 'allowed_clients': ['172.30.10.0/24']})
        with self.assertRaises(ValueError):
            NetworkPolicy({'bind': '172.30.10.101', 'port': 8080,
                           'allowed_clients': ['0.0.0.0/0']})

    def test_callback_health_reports_live_subscriptions_without_mutating_state(self):
        self.acquire()
        self.post('command', {'action': 'camera'})
        frame = self.wait(lambda s: s['depth'])
        status, health = self.http('/api/camera-callback-health')
        self.assertEqual(status, 200)
        self.assertEqual(self.status()['frame_id'], frame['frame_id'])
        for topic in health['topics'].values():
            self.assertGreater(topic['raw'], 0)
            self.assertGreater(topic['validated'], 0)
            self.assertGreater(topic['enqueued'], 0)
            self.assertEqual(topic['exceptions'], 0)
            self.assertGreater(topic['rate_hz'], 0)
            self.assertGreater(topic['matched_publishers'], 0)
        self.assertTrue(health['rmw'])

    def test_camera_trace_endpoint(self):
        from collections import deque
        self.node.camera.trace = deque(maxlen=2048)
        self.node.camera.record('evaluate', rgb_ns=123, reason='missing_info')
        code, events = self.http('/api/camera-trace')
        self.assertEqual(code, 200)
        self.assertEqual(events[-1]['rgb_ns'], 123)
        self.assertEqual(events[-1]['reason'], 'missing_info')

    def test_camera_disconnect_keeps_web_healthy_and_retires_jpeg(self):
        self.acquire()
        self.post('command', {'action': 'camera'})
        frame = self.wait(lambda s: s['camera'])
        self.node.mock_publisher.enabled = False
        self.wait(lambda s: not s['camera'])
        self.assertEqual(self.http('/api/frame/' + str(frame['frame_id']) + '.jpg')[0], 404)
        self.assertEqual(self.http('/health')[0], 200)

    def test_optional_publisher_change_preserves_rgb_and_skips_expired_queue(self):
        from dobot_auto_center.ros_sensors import CameraReceiver
        camera = CameraReceiver(Mock(), load(CONFIG)['camera'], time.monotonic)
        camera.device_name = 'Verified test camera'
        camera.endpoints = dict(rgb=b'rgb', depth=b'depth', info=b'info')
        camera.device.service_is_ready.return_value = True
        rgb = np.zeros((4, 4, 3), np.uint8)
        camera.rgb.extend([(8000000000, 8., 8., rgb), (9900000000, 9.9, 9.9, rgb)])
        camera.depth.append((9900000000, 9.9, np.ones((4, 4)), 9.9))
        camera.info_stamps.append((9900000000, 9.9, 9.9))
        endpoints = dict(camera.endpoints, depth=b'')
        with patch.object(camera, 'publisher', side_effect=endpoints.get):
            frame = camera.take(10.)
        self.assertEqual(camera.device_name, 'Verified test camera')
        self.assertEqual(frame.source_stamp, 9.9)
        self.assertIsNone(frame.depth)
        self.assertFalse(camera.depth)
        camera.device.call_async.assert_not_called()

    def test_registered_camera_stream_and_servo_without_robot(self):
        config = load(CONFIG)
        self.assertFalse(config['hardware']['simulation_mode'])
        # Use fixture-only topics even if a developer has other nodes running.
        cam = config['camera']
        cam.update(driver_node='/test_orbbec/camera', device_info_service='/test_orbbec/device')
        for kind in ('rgb', 'depth', 'info'):
            cam[kind + '_topic'] = '/test_orbbec/' + kind
        config['web'].update(self.config['web'])
        passive = AutoCenterNode(config)
        self.addCleanup(passive.destroy_node)
        self.addCleanup(passive.close)
        driver = Node('camera', namespace='/test_orbbec')
        self.addCleanup(driver.destroy_node)
        handler = make_handler(passive, load_assets(WEB))
        publishers = {kind: driver.create_publisher(cls, cam[kind + '_topic'], qos_profile_sensor_data)
                      for kind, cls in [('rgb', Image), ('depth', Image), ('info', CameraInfo)]}

        def device_info(req, response):
            response.success = True
            response.info.name = 'Test fixture'
            response.info.serial_number = 'fixture'
            return response

        driver.create_service(GetDeviceInfo, cam['device_info_service'], device_info)
        bridge = CvBridge()
        bgr = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(bgr, (235, 125), 25, (0, 255, 255), -1)
        rgb = bridge.cv2_to_imgmsg(bgr, encoding='bgr8')
        depth = bridge.cv2_to_imgmsg(np.full((480, 640), 320, np.uint16), encoding='16UC1')
        info = CameraInfo(width=640, height=480, k=[520., 0., 320., 0., 520., 240., 0., 0., 1.])

        def pump(condition, *, publish_depth=True, publish_rgb=True):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                stamp = driver.get_clock().now().to_msg()
                for key, msg in [('info', info), ('depth', depth), ('rgb', rgb)]:
                    if (key == 'depth' and not publish_depth) or (key == 'rgb' and not publish_rgb):
                        continue
                    msg.header.stamp = stamp
                    msg.header.frame_id = cam['frame']
                    publishers[key].publish(msg)
                rclpy.spin_once(driver, timeout_sec=.005)
                for _ in range(8):
                    rclpy.spin_once(passive, timeout_sec=.005)
                status = passive.dashboard_status(passive.clock())
                if condition(status):
                    return status
            self.fail(passive.dashboard_status(passive.clock()))

        self.assertEqual(self.http('/api/stream.mjpg', handler=handler)[0], 503)
        frame = pump(lambda s: s['camera_fps'] is not None)
        self.assertEqual(frame['camera_status'], 'LIVE ORBBEC RGB-D')
        self.assertFalse(frame['connected'])
        self.assertIsNone(passive.motion.transport)
        detection, = frame['detections']
        self.assertAlmostEqual(detection['depth_m'], .32, places=4)
        self.assertEqual(frame['depth_skew_ms'], 0)
        self.lease = self.http('/api/control', {}, handler=handler)[1]['lease']
        x, y, w, h = detection['box']
        code, reply = self.http('/api/command', {'action': 'select', 'frame_id': frame['frame_id'],
                               'roi': [x, y, x+w, y+h]}, handler=handler)
        self.assertEqual(code, 200, reply)
        self.assertEqual(passive.workflow.servo.pixel_error, (-85., -115.))

        # A brief RGB gap must preserve the existing multipart connection.
        # A sustained outage ends it without emitting duplicate JPEGs.
        saved_frame = passive.workflow.frame
        clock = passive.clock()
        ticks = iter((clock + .5, clock + .6, clock + 3.0))

        def advance_stream(_):
            passive.clock.return_value = next(ticks)
            if passive.clock.return_value == clock + .6:
                fresh = replace(saved_frame, stamp=passive.clock(), received=passive.clock())
                passive.workflow.ingest(fresh, passive.clock())

        with patch.object(passive, 'clock', return_value=clock), patch(
                'dobot_auto_center.web.time.sleep', side_effect=advance_stream):
            code, data = self.http('/api/stream.mjpg', handler=handler)
        self.assertEqual(data.count(b'Content-Type: image/jpeg'), 2)
        self.assertEqual(code, 200)
        header, payload = data.split(b'\r\n\r\n', 1)
        self.assertIn(b'X-Frame-Metadata:', header)
        jpeg = payload.split(b'\r\n--frame')[0]
        self.assertEqual(cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR).shape, bgr.shape)

        # Reject competing publishers even when their topic type and stamps match.
        other = self.node.create_publisher(Image, cam['depth_topic'], qos_profile_sensor_data)
        pump(lambda s: s['camera_status'] == 'Camera Offline' and not passive.camera.device_name)
        self.assertIsNone(passive.workflow.servo.pixel_error)
        self.node.destroy_publisher(other)
        pump(lambda s: s['depth'])
        preview = pump(lambda s: s['camera'] and not s['depth'], publish_depth=False)
        self.assertEqual(preview['camera_status'], 'LIVE ORBBEC RGB · Depth unavailable')
        self.assertEqual(preview['detections'], [])
        self.assertIsNone(preview['target'])
        self.assertEqual(self.http(f"/api/frame/{preview['frame_id']}.jpg", handler=handler)[0], 200)
        self.assertIsNone(passive.dashboard_status(passive.clock())['depth_source'])
        pump(lambda s: s['depth'])
        info.k[0] = 0.
        pump(lambda s: s['camera'] and not s['depth'])
        info.k[0] = 520.
        depth.data = bytes(len(depth.data))
        pump(lambda s: s['camera'] and not s['depth'] and s['frame_id'] > preview['frame_id'] + 5)
        depth = bridge.cv2_to_imgmsg(np.full((480, 640), 320, np.uint16), encoding='16UC1')
        pump(lambda s: s['depth'])
        driver.destroy_publisher(publishers['depth'])
        pump(lambda s: s['camera'] and not s['depth'] and passive.camera.endpoints.get('depth') == b'',
             publish_depth=False)
        publishers['depth'] = driver.create_publisher(Image, cam['depth_topic'], qos_profile_sensor_data)
        pump(lambda s: s['depth'])
        pump(lambda s: not s['camera'], publish_rgb=False)
        self.assertEqual(self.http('/api/stream.mjpg', handler=handler)[0], 503)

    def test_read_only_status_and_no_motion_transport(self):
        config = load(CONFIG)
        config['hardware']['simulation_mode'] = False
        config['web'].update(self.config['web'])
        passive = AutoCenterNode(config)
        self.addCleanup(passive.destroy_node)
        self.addCleanup(passive.close)
        handler = make_handler(passive, load_assets(WEB))
        self.assertIsNone(passive.action)
        self.assertIsNone(passive.motion.transport)
        self.assertEqual(self.http('/api/status', handler=handler)[1]['camera_status'],
                         'Camera Offline')
        self.assertEqual(self.http('/api/status', handler=handler)[1]['robot_status'],
                         'ROBOT DISCONNECTED')

        topics = config['hardware']['topics']
        messages = {
            'device': DeviceStatus(connected=True, device_name='Fixture Magician', firmware_version=[1, 2, 3]),
            'alarms': AlarmState(valid=True, codes=[4]),
            'joints': JointState(name=JOINT_NAMES, position=[0., 0., 0., 0.]),
            'tcp': PoseStamped(),
            'suction': ToolState(valid=True, control_enabled=True, active=True),
            'gripper': ToolState(valid=False),
        }
        messages['tcp'].header.frame_id = 'magician_base_link'
        messages['tcp'].pose.orientation.w = 1.
        messages['tcp'].pose.position.x = 0.2
        publishers = {key: self.node.create_publisher(type(msg), topics[key], 10)
                      for key, msg in messages.items()}
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            for key, msg in messages.items():
                msg.header.stamp = self.node.get_clock().now().to_msg()
                publishers[key].publish(msg)
            for _ in range(10):
                rclpy.spin_once(passive, timeout_sec=.015)
            _, status = self.http('/api/status', handler=handler)
            if status['connected'] and status['suction'] is not None:
                break
        self.assertTrue(status['connected'], status)
        self.assertEqual(status['mode'], 'read-only')
        self.assertEqual(status['firmware_version'], [1, 2, 3])
        self.assertEqual(status['alarms'], [4])
        self.assertEqual(status['tcp'][0], 200.)
        self.assertEqual(status['suction'], {'control_enabled': True, 'active': True})
        self.assertIsNone(status['gripper'])
        stale = passive.dashboard_status(passive.clock() + config['hardware']['telemetry_timeout'] + .1)
        self.assertIn('TELEMETRY STALE', stale['robot_status'])
        self.assertFalse(stale['connected'] or stale['home_available'])
        disconnected = DeviceStatus(connected=False)
        disconnected.header.stamp = self.node.get_clock().now().to_msg()
        passive.robot.receive('device', disconnected)
        self.assertFalse(passive.dashboard_status(passive.clock())['connected'])
        passive.robot.receive('tcp', messages['tcp'])  # Late sample from the old session.
        reconnect = DeviceStatus(connected=True)
        reconnect.header.stamp = self.node.get_clock().now().to_msg()
        passive.robot.receive('device', reconnect)
        recovering = passive.dashboard_status(passive.clock())
        self.assertTrue(recovering['device_connected'])
        self.assertFalse(recovering['connected'])
        self.assertNotIn('tcp', passive.robot.samples)
        self.assertFalse(status['real_motion_enabled'])
        self.assertEqual(status['camera_status'], 'Camera Offline')
        self.lease = self.http('/api/control', {}, handler=handler)[1]['lease']
        issued = self.http('/api/confirm', {'action': 'home'}, handler=handler)[1]['confirmation']
        code, denied = self.http('/api/command', {'action': 'home', 'confirmation': issued},
                                 handler=handler)
        self.assertEqual(code, 409)
        self.assertEqual(denied['error'], 'Motion is disabled in read-only mode')

    def test_live_home_without_camera_requires_confirmation_and_replays_ack(self):
        config = load(CONFIG)
        config['web'].update(self.config['web'])
        driver = Mock(home_issue='')
        live = AutoCenterNode(config, home_driver=driver)
        self.addCleanup(live.destroy_node)
        self.addCleanup(live.close)
        handler = make_handler(live, load_assets(WEB))
        status = self.http('/api/status', handler=handler)[1]
        self.assertEqual(status['mode'], 'hardware-home')
        self.assertFalse(status['camera'])
        self.assertTrue(status['real_motion_enabled'])
        body = {'action': 'home'}
        self.assertEqual(self.http('/api/command', body, handler=handler)[0], 403)
        self.lease = self.http('/api/control', {}, handler=handler)[1]['lease']
        self.assertEqual(self.http('/api/command', body, handler=handler)[0], 409)
        body['confirmation'] = self.http('/api/confirm', body, handler=handler)[1]['confirmation']
        driver.start_homing.assert_not_called()
        key = str(uuid.uuid4())
        ack = self.http('/api/command', body, key, handler=handler)
        self.assertEqual(ack[0], 200)
        self.assertIn('acknowledged', ack[1]['message'])
        self.assertEqual(self.http('/api/command', body, key, handler=handler), ack)
        self.assertEqual(self.http('/api/command', body, handler=handler)[0], 409)
        driver.start_homing.assert_called_once()
        driver.start_homing.reset_mock()

        # Delay the hardware preflight while status, heartbeat and STOP arrive.
        reading, resume, sent = Event(), Event(), Event()
        def delayed_home(*, write_guard):
            reading.set()
            if not resume.wait(3):
                raise ValueError('Test timed out waiting for the HTTP requests')
            with write_guard():
                sent.set()

        driver.start_homing.side_effect = delayed_home
        body['confirmation'] = self.http('/api/confirm', body, handler=handler)[1]['confirmation']
        key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.http, '/api/command', body, key, handler=handler)
            try:
                self.assertTrue(reading.wait(2))
                self.assertEqual(self.http('/api/status', handler=handler)[1]['home_blocked_reason'],
                                 'Waiting for HOME command result')
                self.assertEqual(self.http('/api/heartbeat', {}, handler=handler)[0], 200)
                self.assertEqual(self.http('/api/command', body, key, handler=handler)[0], 409)
                self.assertEqual(self.http('/api/stop', {}, handler=handler)[0], 200)
            finally:
                resume.set()
            denied = pending.result(timeout=2)
        self.assertEqual(denied[0], 409)
        self.assertIn('interrupted', denied[1]['error'])
        self.assertEqual(self.http('/api/command', body, key, handler=handler), denied)
        self.assertFalse(sent.is_set())
        driver.start_homing.assert_called_once()


class LateAction(unittest.TestCase):
    def test_delayed_accepted_response_after_stop_is_canceled(self):
        class Handle:
            accepted = True
            canceled = 0

            def get_result_async(self):
                return Future()

            def cancel_goal_async(self):
                self.canceled += 1

        reply = Future()
        pending = PendingAction(reply, deadline=3)
        pending.cancel()
        self.assertIsNone(pending.poll(1))
        self.assertEqual(pending.poll(4).code, 'fault')
        handle = Handle()
        reply.set_result(handle)
        self.assertEqual(handle.canceled, 1)
