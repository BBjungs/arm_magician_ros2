"""Execute the operator JavaScript against a minimal DOM, with fake HTTP."""

from pathlib import Path
import shutil
import subprocess

import pytest


def test_autonomous_buttons_and_status_do_not_follow_passive_guidance():
    if not shutil.which('node'):
        pytest.skip('Node.js required for browser-script contract test')
    script = Path(__file__).parents[1] / 'dobot_web_interface/static/operator.js'
    result = subprocess.run(['node', '-e', r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
class Element {
  constructor() { this.listeners = {}; this.children = []; this.value = ''; this.checked = false;
    this.classList = { toggle() {}, add() {}, remove() {} }; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  get options() { return this.children; }
  append(...elements) { this.children.push(...elements); }
  appendChild(element) { this.children.push(element); }
}
const elements = new Map();
const get = (id) => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
const keys = ['operator_confirmed', 'estop_tested', 'workspace_clear', 'mount_secure',
              'workspace_measured', 'collision_reviewed', 'stop_tested'];
const boxes = keys.map((key) => Object.assign(new Element(), { dataset: { calibrationAck: key } }));
const requests = [];
const status = { automatic_calibration: { state: 'IDLE', authorization_protocol: 2 },
  calibration_guidance: { state: 'GUIDE_TO_TARGET' } };
const context = vm.createContext({ console, Date, URL, URLSearchParams, document: {
  getElementById: get, createElement: () => new Element(), querySelectorAll: () => boxes },
  window: { setInterval() {}, clearInterval() {}, addEventListener() {} },
  fetch: async (url, options) => { if (options) requests.push({ url, ...options });
    return { ok: true, json: async () => options ? { accepted: true, message: 'requested' } : status }; }
});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
(async () => {
  await vm.runInContext('refreshStatus()', context);
  assert(get('automaticResult').textContent.includes('พร้อมตรวจแผน'));
  assert(!get('automaticResult').textContent.includes('GUIDE_TO_TARGET'));
  vm.runInContext('renderAutomaticCalibration({ state: "IDLE" })', context);
  assert(get('automaticStart').disabled, 'old backend must not accept new start UI');
  const render = (plan, extra = {}) => vm.runInContext('renderAutomaticCalibration(' + JSON.stringify({
    state: 'WAITING_FOR_OPERATOR_AUTHORIZATION', authorization_protocol: 2,
    plan_fingerprint: plan, plan: [{ pose_index: 2, xyz_mm: [190, 10, 105], j4_deg: 5 }], ...extra
  }) + ')', context);
  render('plan-one');
  assert(get('automaticAuthorize').disabled);
  boxes.forEach((box) => box.checked = true);
  vm.runInContext('updateAuthorizationButton()', context);
  assert(!get('automaticAuthorize').disabled);
  assert(get('automaticPlan').children.some((row) => row.textContent.includes('190.0, 10.0, 105.0')));
  render('plan-two');
  assert(boxes.every((box) => !box.checked), 'new plan invalidates old confirmations');
  boxes.forEach((box) => box.checked = true);
  render('plan-two', { commissioning_required: true, commissioning_available: false });
  assert(get('automaticAuthorize').disabled, 'dry-run cannot authorize ten poses');
  render('plan-two', { commissioning_required: false });
  await get('automaticAuthorize').listeners.click();
  const authorized = requests.find((r) => r.url.endsWith('/autonomous/authorize'));
  assert(authorized && authorized.method === 'POST');
  const body = JSON.parse(authorized.body);
  assert(body.plan_fingerprint === 'plan-two' && keys.every((key) => body[key] === true));
  await get('automaticStart').listeners.click();
  assert(requests.some((r) => r.url === '/api/calibration/autonomous/start' && r.method === 'POST'));
})().catch((error) => { console.error(error); process.exitCode = 1; });
''', str(script)], text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
