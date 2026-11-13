"""Browser integration against intercepted, simulated HTTP responses only.

Run with a Python environment containing Playwright and Chromium. No ROS nodes
or requests to the live robot service are used.
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


STATIC = Path(__file__).resolve().parents[1] / 'dobot_web_interface' / 'static'
EVIDENCE = Path(__file__).resolve().parents[4] / 'docs' / 'evidence' / 'visual-servo'


def main():
    state = dict(servo_state='IDLE', message='', blocker='', enabled=False, active=False,
        enable_remaining_sec=60, stop_depth_mm=200, pixel_error=[20, -10], depth_mm=245,
        tcp_pose=[220, 0, 160, 0], estimated_motion_direction=[.6, -.8, 0],
        jacobian_status='UNLEARNED', jacobian_condition=None, model_updates=0,
        robot_state='IDLE', confidence=.95, rgb_stamp=10, depth_stamp=10,
        image_size=[640, 480], reference=[320, 240], target_center=[340, 230],
        bbox=[320, 210, 360, 250], calibration_required=False, grasp_enabled=False)
    calls, errors, held = [], [], []
    offline = False
    hold_enable = False

    def route(request_route):
        nonlocal hold_enable
        request = request_route.request
        path = request.url.split('ibvs.test', 1)[1].split('?', 1)[0]
        if path == '/visual-servo':
            return request_route.fulfill(path=str(STATIC / 'visual_servo.html'), content_type='text/html')
        if path.startswith('/static/'):
            mime = 'text/javascript' if path.endswith('.js') else 'text/css'
            return request_route.fulfill(path=str(STATIC / path.rsplit('/', 1)[1]), content_type=mime)
        if path == '/api/vision/annotated':
            return request_route.fulfill(content_type='image/svg+xml', body='''
                <svg xmlns="http://www.w3.org/2000/svg" width="640" height="480">
                <rect width="640" height="480" fill="#52616c"/>
                <circle cx="340" cy="230" r="20" fill="#101010"/>
                <text x="20" y="36" fill="white">SIMULATION · NO HARDWARE</text></svg>''')
        if path == '/api/visual_servo/status':
            if offline:
                return request_route.abort()
            return request_route.fulfill(json=state)
        if request.method == 'POST':
            action = path.rsplit('/', 1)[1]
            calls.append((action, request.post_data_json, request.headers))
            if action == 'enable' and hold_enable:
                held.append(request_route)
                return
            if action == 'enable': state.update(enabled=True, servo_state='ENABLED')
            elif action == 'start': state.update(active=True, servo_state='LEARN')
            elif action in ('stop', 'pause'):
                state.update(enabled=False, active=False, servo_state='STOP' if action == 'stop' else 'PAUSED')
            return request_route.fulfill(json={'accepted': True, 'message': action.upper()})
        raise AssertionError(f'Unexpected browser request: {request.url}')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1360, 'height': 980})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/*', route)
        page.goto('http://ibvs.test/visual-servo')
        expect(page.locator('#state')).to_have_text('IDLE')
        expect(page.locator('#enable')).to_be_disabled()
        page.locator('#token').fill('test-operator-secret')
        for name in ('workspace', 'estop', 'envelope'):
            page.locator('#' + name).check()
        expect(page.locator('#enable')).to_be_enabled()
        page.locator('#enable').click()
        expect(page.locator('#start')).to_be_enabled()
        assert calls[-1][1] == dict(workspace_clear=True, estop_tested=True, assembly_envelope_confirmed=True)
        assert calls[-1][2]['authorization'] == 'Bearer test-operator-secret'
        expect(page.locator('#box')).to_have_attribute('width', '40')
        expect(page.locator('#reference')).to_have_attribute('d', 'M308 240h24 M320 228v24')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / 'desktop-simulation.png'), full_page=True)
        page.locator('#start').click()
        expect(page.locator('#state')).to_have_text('LEARN')
        expect(page.locator('#start')).to_be_disabled()
        page.locator('#pause').click()
        expect(page.locator('#state')).to_have_text('PAUSED')
        expect(page.locator('#start')).to_be_disabled()
        hold_enable = True
        page.locator('#enable').click()
        expect(page.locator('#stop')).to_be_enabled()
        page.locator('#stop').click()
        expect(page.locator('#state')).to_have_text('STOP')
        assert held
        held.pop().fulfill(json={'accepted': False, 'message': 'OLD ENABLE RESPONSE'})
        expect(page.locator('#command')).to_have_text('STOP')
        assert page.evaluate('localStorage.length + sessionStorage.length') == 0
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(EVIDENCE / 'mobile-simulation.png'), full_page=True)
        offline = True
        expect(page.locator('#state')).to_have_text('DISCONNECTED')
        expect(page.locator('#start')).to_be_disabled()
        expect(page.locator('#enable')).to_be_disabled()
        expect(page.locator('#box')).to_be_hidden()
        expect(page.locator('#stop')).to_be_enabled()
        assert not errors, errors
        browser.close()
    report = {'result': 'PASS', 'hardware_access': False,
        'checks': ['explicit confirmation and credentials', 'start/pause/stop',
                   'stop during pending enable', 'late response ignored',
                   'bbox/reference overlay', 'telemetry loss disables admission',
                   'no credentials in browser storage', 'desktop/mobile layout', 'no JavaScript errors']}
    (EVIDENCE / 'browser-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
