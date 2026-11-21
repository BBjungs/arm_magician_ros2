"""Dashboard HTTP boundary for loopback and explicitly scoped private LANs."""

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import re
import secrets
import subprocess
from threading import Thread
import time
from urllib.parse import urlsplit

import cv2


CONFIRMED = {'home', 'observation', 'center', 'reset'}
OPERATIONS = CONFIRMED | {'camera', 'detect', 'select'}
REQUEST_KEY = re.compile(r'[A-Za-z0-9_-]{12,100}')


PRIVATE_RANGES = tuple(map(ipaddress.IPv4Network, ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')))


class NetworkPolicy:
    def __init__(self, config):
        self.bind = ipaddress.IPv4Address(config['bind'])
        self.port = config['port']
        self.clients = tuple(ipaddress.IPv4Network(cidr) for cidr in config.get('allowed_clients', []))
        if self.bind.is_loopback:
            if self.clients:
                raise ValueError('Loopback does not require a LAN allowlist')
        elif (not any(self.bind in network for network in PRIVATE_RANGES) or not self.clients
              or any(not any(client.subnet_of(network) for network in PRIVATE_RANGES)
                     for client in self.clients)):
            raise ValueError('LAN requires a specific private IPv4 bind and a private client CIDR allowlist')

    def allows_peer(self, address):
        try:
            peer = ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError:
            return False
        if self.bind.is_loopback:
            return peer.is_loopback
        return any(peer in network for network in self.clients)

    def allows_host(self, host):
        names = (str(self.bind), 'localhost') if self.bind.is_loopback else (str(self.bind),)
        return any(host == f'{name}:{self.port}' or (self.port == 80 and host == name)
                   for name in names)


@dataclass
class PendingHome:
    request_id: str
    encoded: str
    cancelled: bool = False


class Access:
    def __init__(self, config):
        self.config = config
        self.owner = None
        self.until = 0.
        self.confirmation = None
        self.requests = OrderedDict()
        self.pending_home = None

    def valid(self, owner, now):
        return bool(owner and owner == self.owner and now < self.until)

    def acquire(self, now):
        if self.pending_home is not None:
            raise ValueError('A HOME request is still in progress')
        if self.valid(self.owner, now):
            raise ValueError('Another browser holds control')
        self.owner = secrets.token_urlsafe(32)
        self.until = now + self.config['lease_seconds']
        self.confirmation = None
        self.requests.clear()
        return self.owner

    def renew(self, owner, now):
        if not self.valid(owner, now):
            raise ValueError('Control lease expired')
        self.until = now + self.config['lease_seconds']

    def release(self, owner, now):
        if not self.valid(owner, now):
            raise ValueError('Control lease expired')
        self.until = now
        self.confirmation = None

    def confirm(self, action, fingerprint, now):
        token = secrets.token_urlsafe(28)
        self.confirmation = token, action, fingerprint, now + self.config['confirmation_seconds']
        return token

    def execute(self, request_id, body, fingerprint, now, callback):
        encoded = json.dumps(body, sort_keys=True, allow_nan=False)
        previous = self.requests.get(request_id)
        if previous:
            if previous[0] != encoded:
                return 409, {'error': 'Request ID was already used for another command'}
            return previous[1:]
        if self.pending_home is not None and (body['action'] == 'home' or request_id == self.pending_home.request_id):
            return 409, {'error': 'A HOME request is still in progress'}
        if len(self.requests) + int(self.pending_home is not None) >= self.config['request_history_size']:
            return 409, {'error': 'Session command limit reached. Reacquire control'}
        try:
            action = body['action']
            if action in CONFIRMED:
                confirmation, self.confirmation = self.confirmation, None
                if (not confirmation or body.get('confirmation') != confirmation[0]
                        or (action, fingerprint) != confirmation[1:3] or now >= confirmation[3]):
                    raise ValueError('A current, single-use confirmation is required')
            if callback is None:
                self.pending_home = PendingHome(request_id, encoded)
                return self.pending_home
            message = callback()
            response = 200, {'accepted': True}
            if message:
                response[1]['message'] = message
        except ValueError as error:
            response = 409, {'error': str(error)}
        self.requests[request_id] = (encoded, *response)
        return response


def restart_live_service():
    try:
        subprocess.run(
            ['systemctl', '--user', '--no-block', 'restart', 'dobot-eye-center-live.service'],
            check=True, capture_output=True, text=True, timeout=2)
    except subprocess.CalledProcessError as error:
        raise ValueError(error.stderr.strip() or 'Service restart failed') from error
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(str(error)) from error
    return 'Reset requested. Reconnecting to dashboard…'


def fingerprint(workflow):
    return workflow.state, workflow.homed, workflow.at_observation, workflow.target_id


def dispatch(node, path, body, owner, request_id):
    access, workflow = node.access, node.workflow
    now = node.clock()
    if path == '/api/stop':
        access.confirmation = None
        if access.pending_home is not None:
            access.pending_home.cancelled = True
        workflow.stop(now)
        return 200, {'accepted': True}
    if path == '/api/control':
        return 200, {'lease': access.acquire(now), 'expires_in': access.config['lease_seconds']}
    if not access.valid(owner, now):
        return 403, {'error': 'Exclusive control lease required'}
    if path == '/api/heartbeat':
        access.renew(owner, now)
        return 200, {'accepted': True}
    if path == '/api/release':
        access.release(owner, now)
        if workflow.run_owner == owner and (workflow.pending or workflow.state == 'CENTERING'):
            workflow.stop(now, 'Browser released control')
        return 200, {'accepted': True}
    action = body.get('action')
    if not isinstance(action, str):
        return 400, {'error': 'Operation is required'}
    if action == 'reset':
        if node.home_driver is None:
            return 403, {'error': 'Reset requires the live hardware dashboard'}
        if access.pending_home or workflow.pending or workflow.state in ('CENTERING', 'HOMING', 'STOPPING'):
            return 409, {'error': 'Wait for the arm to stop before resetting'}
    live_home = action == 'home' and node.home_driver is not None
    context = ('hardware-home',) if live_home else fingerprint(workflow)
    if path == '/api/confirm' and action in CONFIRMED:
        if live_home and access.pending_home is not None:
            return 409, {'error': 'A HOME request is still in progress'}
        return 200, {'confirmation': access.confirm(action, context, now)}
    if path == '/api/command' and action in OPERATIONS:
        if not REQUEST_KEY.fullmatch(request_id):
            return 400, {'error': 'A valid Idempotency-Key is required'}
        if action == 'select':
            roi = body.get('roi')
            if (not isinstance(roi, list) or len(roi) != 4
                    or any(type(value) not in (int, float) or not math.isfinite(value)
                           for value in roi) or type(body.get('frame_id')) is not int):
                return 400, {'error': 'Invalid ROI or frame ID'}
        callback = None if live_home else lambda: workflow.command(action, body, owner, now)
        if action == 'reset':
            callback = restart_live_service
        return access.execute(request_id, body, context, now, callback)
    return 404, {'error': 'Unknown operation'}


def make_handler(node, assets, policy=None):
    policy = policy or NetworkPolicy(node.config['web'])

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(4)

        def log_message(self, *_):
            pass

        def send_data(self, status, payload, content_type):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy',
                             "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def send_json(self, status, value):
            self.send_data(status, json.dumps(value, allow_nan=False).encode(), 'application/json')

        def permitted_request(self):
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            if (len(self.headers.get_all('Host', [])) == 1 and policy.allows_host(host)
                    and policy.allows_peer(self.client_address[0])
                    and (origin is None or origin == f'http://{host}')):
                return True
            self.send_json(403, {'error': 'Request outside the configured network or origin'})
            return False

        def stream_frames(self):
            last_id = None
            last_sent = None
            try:
                while True:
                    with node.lock:
                        now = node.clock()
                        status = node.workflow.status(now)
                        frame = node.workflow.display_frame(now)
                        frame_id = status['frame_id']
                        metadata = {key: status[key] for key in ('frame_id', 'detections', 'target')}
                    if not status['camera']:
                        if last_sent is None:
                            self.send_json(503, {'error': 'Camera Offline'})
                            return
                        if now - last_sent >= 1.5:
                            self.wfile.write(b'--frame--\r\n')
                            return
                    elif frame_id != last_id:
                        ok, jpeg = cv2.imencode('.jpg', frame.rgb, [cv2.IMWRITE_JPEG_QUALITY, 83])
                        if not ok:
                            if last_id is None:
                                self.send_json(503, {'error': 'Image encoding failed'})
                            return
                        if last_id is None:
                            self.send_response(200)
                            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                            self.send_header('Cache-Control', 'no-store')
                            self.end_headers()
                        header = (f'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {jpeg.size}\r\n'
                                  f'X-Frame-Timestamp: {frame.source_stamp}\r\n'
                                  f'X-Frame-Metadata: {json.dumps(metadata, separators=(",", ":"))}\r\n\r\n')
                        self.wfile.write(header.encode('ascii'))
                        self.wfile.write(jpeg.tobytes())
                        self.wfile.write(b'\r\n')
                        last_id = frame_id
                        last_sent = node.clock()
                    time.sleep(1 / 30)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                return

        def do_GET(self):
            if not self.permitted_request():
                return
            path = urlsplit(self.path).path
            if path in assets:
                content, content_type = assets[path]
                self.send_data(200, content, content_type)
            elif path == '/api/stream.mjpg':
                self.stream_frames()
            elif path == '/api/camera-callback-health':
                # Keep a blocked workflow tick from blocking this diagnostic read.
                now = node.clock()
                last_tick = node.last_tick
                health = node.camera.callback_health(now)
                health['workflow_frame_id'] = node.workflow.frame_id
                health['executor'] = dict(last_tick_monotonic=last_tick,
                                          tick_age_s=max(0., now-last_tick) if last_tick is not None else None,
                                          tick_interval_ms=node.tick_interval_ms, tick_period_ms=25,
                                          executor_type=type(node.executor).__name__)
                self.send_json(200, health)
            elif path == '/api/camera-trace':
                with node.lock:
                    events = list(node.camera.trace or ())
                self.send_json(200, events)
            elif path in ('/api/status', '/health'):
                with node.lock:
                    now = node.clock()
                    status = node.dashboard_status(now)
                    running = (node.last_tick is not None and now - node.last_tick <= 1.0)
                if path == '/health':
                    value = {key: status[key] for key in
                             ('mode', 'camera_status', 'robot_status', 'real_motion_enabled', 'stream_url')}
                    self.send_json(200 if running else 503, {'ok': running, **value})
                else:
                    self.send_json(200, status)
            elif re.fullmatch(r'/api/frame/-?[0-9]{1,12}\.jpg', path):
                frame_id = int(path.rsplit('/', 1)[1][:-4])
                with node.lock:
                    status = node.workflow.status(node.clock())
                    image = next((img for seq, img, captured in node.workflow.images
                                  if seq == frame_id and status['camera']
                                  and node.clock() - captured <= node.config['camera']['freshness']), None)
                    preview = node.workflow.pending_preview
                    if (preview is not None and frame_id == node.workflow.preview_id
                            and preview.fresh(node.clock(), node.config['camera']['freshness'])):
                        image = preview.rgb
                if image is None:
                    self.send_json(404, {'error': 'Frame expired'})
                    return
                ok, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 83])
                if ok:
                    self.send_data(200, jpeg.tobytes(), 'image/jpeg')
                else:
                    self.send_json(503, {'error': 'Image encoding failed'})
            else:
                self.send_json(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.permitted_request():
                return
            if self.headers.get_content_type() != 'application/json':
                self.send_json(415, {'error': 'Use application/json for dashboard commands'})
                return
            path = urlsplit(self.path).path
            owner = self.headers.get('X-Control-Lease', '')
            key = self.headers.get('Idempotency-Key', '')
            if path == '/api/stop':
                with node.lock:
                    status, response = dispatch(node, path, {}, owner, key)
                self.send_json(status, response)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid JSON request')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Expected a JSON object')
                json.dumps(body, allow_nan=False)
            except (ValueError, TimeoutError, RecursionError):
                self.send_json(400, {'error': 'Invalid JSON request'})
                return
            trace_home = body.get('action') == 'home' and path in ('/api/confirm', '/api/command')
            if trace_home:
                node.get_logger().info(f"Received HOME POST {path}")
            status, response = self.dispatch_safe(path, body, owner, key)
            if trace_home:
                detail = response.get('error', '')
                node.get_logger().info(f"HOME POST {path} returned HTTP {status} {detail}".rstrip())
            self.send_json(status, response)

        def dispatch_safe(self, path, body, owner, key):
            try:
                with node.lock:
                    result = dispatch(node, path, body, owner, key)
                if isinstance(result, PendingHome):
                    return self.run_home(result, owner)
                return result
            except (ValueError, OverflowError) as error:
                return 409, {'error': str(error)}

        def run_home(self, pending, owner):
            @contextmanager
            def authorize_write():
                with node.lock:
                    if pending.cancelled or not node.access.valid(owner, node.clock()):
                        raise ValueError('HOME interrupted before serial write')
                    yield

            response = 409, {'error': 'HOME outcome unknown. Check the arm before sending HOME again.'}
            try:
                node.home_driver.start_homing(write_guard=authorize_write)
                response = 200, {'accepted': True, 'message':
                                 'HOME acknowledged. Wait until the arm stops and the indicator turns green.'}
            except (OSError, ValueError) as error:
                response = 409, {'error': str(error)}
            finally:
                with node.lock:
                    node.access.requests[pending.request_id] = (pending.encoded, *response)
                    node.access.pending_home = None
            return response

    return Handler


def load_assets(web_directory):
    files = {'/': ('index.html', 'text/html; charset=utf-8'),
             '/app.css': ('app.css', 'text/css; charset=utf-8'),
             '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
    return {url: ((web_directory / name).read_bytes(), content_type)
            for url, (name, content_type) in files.items()}


def serve(node, web_directory):
    config = node.config['web']
    bind = config['bind']
    policy = NetworkPolicy(config)
    assets = load_assets(web_directory)

    class DashboardServer(ThreadingHTTPServer):
        def verify_request(self, _socket, address):
            return policy.allows_peer(address[0])

    server = DashboardServer((bind, config['port']), make_handler(node, assets, policy))
    Thread(target=server.serve_forever, daemon=True).start()
    return server
