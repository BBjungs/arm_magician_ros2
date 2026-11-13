"""Real Chromium + repository assets; every request is intercepted, no robot API."""
import base64
import json
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright


static = Path(__file__).parents[1] / 'dobot_web_interface' / 'static'
canvas = np.full((480, 640, 3), 210, np.uint8)
cv2.rectangle(canvas, (170, 110), (450, 350), (60, 100, 150), -1)
cv2.rectangle(canvas, (250, 150), (390, 290), (30, 70, 110), -1)
cv2.putText(canvas, 'Reference object', (185, 390), cv2.FONT_HERSHEY_SIMPLEX, .9, (30, 30, 30), 2)
jpeg = cv2.imencode('.jpg', canvas)[1].tobytes()
reference = {'image_size': [640, 480], 'rgb_stamp': 42.,
             'preview_jpeg': base64.b64encode(jpeg).decode(), 'tracked': False, 'selection': None}
status = {'ready': False, 'overall_status': 'รอ Calibration', 'checks': [], 'jobs': [], 'places': [],
          'operation': {'active': False}, 'control': {'state': 'IDLE'},
          'automatic_calibration': {'state': 'IDLE'},
          'calibration': {'ready': False, 'state': 'UNCALIBRATED', 'age_sec': .1, 'object_calibration': reference}}
posts, errors = [], []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1280, 'height': 1000})
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(request_route):
        request = request_route.request
        path = request.url.split('object.test')[-1].split('?')[0]
        if request.method == 'POST':
            posts.append((path, request.post_data_json))
            request_route.fulfill(json={'accepted': True, 'success': True, 'motion_command_sent': False})
        elif path == '/api/operator/status':
            request_route.fulfill(json=status)
        elif path in ('/api/vision/annotated', '/api/snapshot'):
            request_route.fulfill(body=jpeg, content_type='image/jpeg')
        elif path == '/':
            request_route.fulfill(body=(static / 'operator.html').read_bytes(), content_type='text/html')
        elif path.startswith('/static/') and (static / Path(path).name).is_file():
            suffix = Path(path).suffix
            request_route.fulfill(body=(static / Path(path).name).read_bytes(),
                content_type={'.js': 'text/javascript', '.css': 'text/css'}.get(suffix, 'text/plain'))
        else:
            request_route.fulfill(json={})
    page.route('**/*', route)
    page.goto('http://object.test/')
    page.wait_for_selector('#objectReferenceImage:not([hidden])')
    assert posts == [], 'Loading the dashboard must never start or authorize calibration'
    box = page.locator('#objectReferenceImage').bounding_box()
    page.locator('#objectReferenceImage').click(position={'x': box['width'] / 2, 'y': box['height'] / 2})
    page.wait_for_timeout(100)
    path, payload = posts[-1]
    assert path == '/api/calibration/object/select'
    assert np.allclose(payload['pixel'], [320, 240], atol=2)
    assert payload['image_size'] == [640, 480] and payload['rgb_stamp'] == 42.
    page.locator('#objectCalibrationDryRun').click(); page.wait_for_timeout(100)
    assert posts[-1][0] == '/api/calibration/object/dry_run'
    page.locator('#objectCalibrationStart').click(); page.wait_for_timeout(100)
    assert posts[-1][0] == '/api/calibration/object/start'
    status['automatic_calibration'] = {'state': 'WAITING_FOR_OPERATOR_AUTHORIZATION',
        'total_poses': 10, 'plan_fingerprint': 'plan-A', 'motion_type': 'MOVL',
        'plan': [{'pose_index': i, 'xyz_mm': [150 + i, 0, 120], 'j4_deg': 0} for i in range(1, 11)]}
    page.evaluate('s => window.renderObjectCalibration(s)', status)
    page.locator('#objectMotionAuthorization summary').click()
    before = len(posts)
    page.locator('#objectMotionAuthorize').click(); page.wait_for_timeout(100)
    assert len(posts) == before, 'Unchecked safety confirmations must not authorize'
    for checkbox in page.locator('#objectMotionChecks input').all():
        checkbox.check()
    page.locator('#objectMotionAuthorize').click(); page.wait_for_timeout(100)
    assert posts[-1][0] == '/api/calibration/autonomous/authorize'
    assert posts[-1][1]['plan_fingerprint'] == 'plan-A'
    assert all(value is True for key, value in posts[-1][1].items() if key != 'plan_fingerprint')
    status['automatic_calibration']['plan_fingerprint'] = 'plan-B'
    page.evaluate('s => window.renderObjectCalibration(s)', status)
    assert page.locator('#objectMotionChecks input:checked').count() == 0
    status['automatic_calibration'] = {'state': 'FAULT', 'reason': 'OBJECT_SYMMETRIC_OR_AMBIGUOUS'}
    page.evaluate('s => renderStatus(s)', status)
    assert 'สมมาตร' in page.locator('#objectReferenceStatus').inner_text()
    page.evaluate('window.scrollTo(0, 0)')
    page.screenshot(path='/tmp/object-calibration-browser.png', full_page=True)
    assert errors == [], errors
    assert all(path.startswith('/api/calibration/') for path, _ in posts)
    print(json.dumps({'result': 'PASS', 'post_count': len(posts), 'page_errors': errors,
                      'motion_transport': 'mocked; no real API requests'}, ensure_ascii=False))
    browser.close()
