"""Loopback-only dashboard and operator authorization boundary."""

from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import math
import re
import secrets
from threading import Thread
from urllib.parse import urlsplit

import cv2


CONFIRMED = {'home', 'observation', 'center'}
OPERATIONS = CONFIRMED | {'camera', 'detect', 'select'}
REQUEST_KEY = re.compile(r'[A-Za-z0-9_-]{12,100}')


class Access:
    def __init__(self, config, secret):
        if secret and len(secret) < 24:
            raise ValueError('DOBOT_OPERATOR_TOKEN must have at least 24 characters')
        self.secret = secret.encode()
        self.config = config
        self.owner = None
        self.until = 0.
        self.confirmation = None
        self.requests = OrderedDict()

    def authenticated(self, authorization):
        return bool(self.secret and authorization.startswith('Bearer ')
                    and secrets.compare_digest(self.secret, authorization[7:].encode()))

    def valid(self, owner, now):
        return bool(owner and owner == self.owner and now < self.until)

    def acquire(self, now):
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
        if len(self.requests) >= self.config['request_history_size']:
            return 409, {'error': 'Session command limit reached. Reacquire control'}
        try:
            action = body['action']
            if action in CONFIRMED:
                confirmation, self.confirmation = self.confirmation, None
                if (not confirmation or body.get('confirmation') != confirmation[0]
                        or (action, fingerprint) != confirmation[1:3] or now >= confirmation[3]):
                    raise ValueError('A current, single-use confirmation is required')
            callback()
            response = 200, {'accepted': True}
        except ValueError as error:
            response = 409, {'error': str(error)}
        self.requests[request_id] = (encoded, *response)
        return response


def fingerprint(workflow):
    return workflow.state, workflow.homed, workflow.at_observation, workflow.target_id


def dispatch(node, path, body, owner, request_id):
    access, workflow = node.access, node.workflow
    now = node.clock()
    if path == '/api/stop':
        access.confirmation = None
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
    if path == '/api/confirm' and action in CONFIRMED:
        return 200, {'confirmation': access.confirm(action, fingerprint(workflow), now)}
    if path == '/api/command' and action in OPERATIONS:
        if not REQUEST_KEY.fullmatch(request_id):
            return 400, {'error': 'A valid Idempotency-Key is required'}
        if action == 'select':
            roi = body.get('roi')
            if (not isinstance(roi, list) or len(roi) != 4
                    or any(type(value) not in (int, float) or not math.isfinite(value)
                           for value in roi) or type(body.get('frame_id')) is not int):
                return 400, {'error': 'Invalid ROI or frame ID'}
        return access.execute(request_id, body, fingerprint(workflow), now,
                              lambda: workflow.command(action, body, owner, now))
    return 404, {'error': 'Unknown operation'}


def make_handler(node, assets):
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

        def valid_host(self):
            try:
                host = urlsplit('//' + self.headers.get('Host', '')).hostname
                return host == 'localhost' or ipaddress.ip_address(host or '').is_loopback
            except ValueError:
                return False

        def do_GET(self):
            if not self.valid_host():
                self.send_json(403, {'error': 'Loopback host required'})
                return
            path = urlsplit(self.path).path
            if path in assets:
                content, content_type = assets[path]
                self.send_data(200, content, content_type)
            elif path == '/api/status':
                with node.lock:
                    status = node.workflow.status(node.clock())
                    status['operator_configured'] = bool(node.access.secret)
                self.send_json(200, status)
            elif re.fullmatch(r'/api/frame/[0-9]{1,12}\.jpg', path):
                frame_id = int(path.rsplit('/', 1)[1][:-4])
                with node.lock:
                    image = next((img for seq, img in node.workflow.images if seq == frame_id), None)
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
            if not self.valid_host() or not node.access.authenticated(self.headers.get('Authorization', '')):
                self.send_json(401, {'error': 'Operator authorization required'})
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
                if not 0 < length <= 4096 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Invalid JSON request')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Expected a JSON object')
                json.dumps(body, allow_nan=False)
            except (ValueError, TimeoutError, RecursionError):
                self.send_json(400, {'error': 'Invalid JSON request'})
                return
            with node.lock:
                status, response = self.dispatch_safe(path, body, owner, key)
            self.send_json(status, response)

        def dispatch_safe(self, path, body, owner, key):
            try:
                return dispatch(node, path, body, owner, key)
            except (ValueError, OverflowError) as error:
                return 409, {'error': str(error)}

    return Handler


def serve(node, web_directory):
    config = node.config['web']
    bind = config['bind']
    if bind != '127.0.0.1':
        raise ValueError('Dashboard binds to 127.0.0.1. Use an authenticated tunnel for remote access')
    files = {'/': ('index.html', 'text/html; charset=utf-8'),
             '/app.css': ('app.css', 'text/css; charset=utf-8'),
             '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
    assets = {url: ((web_directory / name).read_bytes(), content_type)
              for url, (name, content_type) in files.items()}
    server = ThreadingHTTPServer((bind, config['port']), make_handler(node, assets))
    Thread(target=server.serve_forever, daemon=True).start()
    return server
