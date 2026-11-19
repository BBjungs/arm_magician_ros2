"""Native ROS sensor/action integration and HTTP requests using in-memory sockets."""

from concurrent.futures import Future
from http.client import HTTPResponse
from io import BytesIO
import json
from pathlib import Path
import time
import unittest
import uuid

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


TOKEN = 'test-operator-key-24-characters'
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
        self.config['web'].update(bind='172.30.10.101', allowed_clients=['172.30.10.0/24'])
        self.node = AutoCenterNode(self.config, TOKEN)
        self.addCleanup(self.node.destroy_node)
        self.addCleanup(self.node.close)
        self.handler = make_handler(self.node, load_assets(WEB))
        self.lease = ''
        self.next_heartbeat = 0.

    def http(self, path, body=None, token=TOKEN, request_id=None, *, host=HOST, peer=PEER,
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
                            'Authorization': 'Bearer ' + token, 'X-Control-Lease': self.lease,
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
        self.assertEqual(self.http('/api/stop', {}, token='wrong')[0], 401)
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

    def test_stop_works_during_native_action_from_authenticated_peer(self):
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
        self.assertEqual(self.http('/api/control', {}, origin='http://other.example')[0], 403)
        self.assertEqual(self.http('/api/control', {}, origin=f'http://{HOST}')[0], 200)
        for bind in ('0.0.0.0', '198.51.100.4'):
            with self.assertRaises(ValueError):
                NetworkPolicy({'bind': bind, 'port': 8080, 'allowed_clients': ['172.30.10.0/24']})
        with self.assertRaises(ValueError):
            NetworkPolicy({'bind': '172.30.10.101', 'port': 8080,
                           'allowed_clients': ['0.0.0.0/0']})

    def test_camera_disconnect_keeps_web_healthy_and_retires_jpeg(self):
        self.acquire()
        self.post('command', {'action': 'camera'})
        frame = self.wait(lambda s: s['camera'])
        self.node.mock_publisher.enabled = False
        self.wait(lambda s: not s['camera'])
        self.assertEqual(self.http('/api/frame/' + str(frame['frame_id']) + '.jpg')[0], 404)
        self.assertEqual(self.http('/health')[0], 200)

    def test_read_only_status_and_no_motion_transport(self):
        config = load(CONFIG)
        config['hardware']['simulation_mode'] = False
        config['web'].update(self.config['web'])
        passive = AutoCenterNode(config, TOKEN)
        self.addCleanup(passive.destroy_node)
        self.addCleanup(passive.close)
        handler = make_handler(passive, load_assets(WEB))
        self.assertIsNone(passive.action)
        self.assertIsNone(passive.motion.transport)
        self.assertEqual(self.http('/api/status', handler=handler)[1]['camera_status'],
                         'CAMERA DISCONNECTED')
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
        self.assertFalse(status['real_motion_enabled'])
        self.assertEqual(status['camera_status'], 'CAMERA DISCONNECTED')
        self.lease = self.http('/api/control', {}, handler=handler)[1]['lease']
        issued = self.http('/api/confirm', {'action': 'home'}, handler=handler)[1]['confirmation']
        code, denied = self.http('/api/command', {'action': 'home', 'confirmation': issued},
                                 handler=handler)
        self.assertEqual(code, 409)
        self.assertEqual(denied['error'], 'Motion is disabled in read-only mode')


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
