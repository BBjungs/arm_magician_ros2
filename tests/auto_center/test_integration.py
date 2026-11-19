"""Native ROS sensor/action integration and HTTP requests using in-memory sockets."""

from concurrent.futures import Future
from http.client import HTTPResponse
from io import BytesIO
import json
from pathlib import Path
import time
import unittest
import uuid

from action_msgs.msg import GoalStatus
import rclpy

from dobot_auto_center.action import GuardedMove
from dobot_auto_center.config import load
from dobot_auto_center.node import AutoCenterNode
from dobot_auto_center.ros_motion import PendingAction
from dobot_auto_center.web import make_handler

from test_core import CONFIG


TOKEN = 'test-operator-key-24-characters'
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
        self.node = AutoCenterNode(self.config, TOKEN)
        self.addCleanup(self.node.destroy_node)
        self.addCleanup(self.node.close)
        self.handler = make_handler(self.node, {
            '/': ((WEB / 'index.html').read_bytes(), 'text/html')})
        self.lease = ''
        self.next_heartbeat = 0.

    def http(self, path, body=None, token=TOKEN, request_id=None):
        headers = {'Host': '127.0.0.1:8080'}
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
        self.handler(connection, ('127.0.0.1', 0), None)
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
        self.wait(lambda s: s['state'] == 'IDLE')
        self.assertFalse(self.node.motion.transport.commands)
        self.assertEqual(self.http('/api/stop', {}, token='wrong')[0], 401)
        self.assertEqual(self.post('command', {'action': 'home'}, expected=403)['error'],
                         'Exclusive control lease required')
        self.prepare()
        names = dict(self.node.get_topic_names_and_types())
        self.assertEqual(names['/camera/color/image_raw'], ['sensor_msgs/msg/Image'])
        self.assertEqual(names['/camera/depth/image_raw'], ['sensor_msgs/msg/Image'])
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

    def test_read_only_mode_has_no_transport_or_action(self):
        config = load(CONFIG)
        config['hardware']['simulation_mode'] = False
        passive = AutoCenterNode(config, TOKEN)
        try:
            self.assertIsNone(passive.action)
            self.assertIsNone(passive.motion.transport)
            self.assertFalse(passive.workflow.status(passive.clock())['simulation'])
        finally:
            passive.close()
            passive.destroy_node()


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
