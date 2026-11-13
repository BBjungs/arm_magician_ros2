'use strict';
const el = id => document.getElementById(id);
let latest = null;
let received = 0;
let pending = false;
let commandGeneration = 0;
const number = (value, digits = 2) => Number.isFinite(value) ? value.toFixed(digits) : '—';
const vector = value => Array.isArray(value) ? value.map(v => number(v)).join(' / ') : '—';

function buttons() {
  const fresh = Date.now() - received < 1000;
  const confirmed = ['workspace', 'estop', 'envelope'].every(id => el(id).checked);
  el('enable').disabled = !fresh || pending || !confirmed || !el('token').value || latest?.active || !!latest?.blocker;
  el('start').disabled = !fresh || pending || !confirmed || !el('token').value || !latest?.enabled || latest?.active || !!latest?.blocker;
}

function render(s) {
  el('state').textContent = s.servo_state;
  el('reason').textContent = [s.message, s.blocker].filter(Boolean).join(' · ') || 'พร้อมตรวจเงื่อนไขก่อนเคลื่อน';
  el('permit').textContent = s.enabled ? `ENABLE เหลือ ${number(s.enable_remaining_sec, 0)} วินาที` : 'ยังไม่ได้ ENABLE';
  el('stopDepth').textContent = `หยุดก่อนสัมผัส: Depth ${number(s.stop_depth_mm, 0)} mm`;
  el('pixelError').textContent = vector(s.pixel_error) + ' px';
  el('depth').textContent = number(s.depth_mm) + ' mm';
  el('tcp').textContent = vector(s.tcp_pose) + ' (mm / deg)';
  el('direction').textContent = vector(s.estimated_motion_direction);
  el('jacobian').textContent = `${s.jacobian_status} · condition ${number(s.jacobian_condition)} · updates ${s.model_updates}`;
  el('robot').textContent = s.robot_state;
  el('confidence').textContent = number(s.confidence, 3);
  el('timestamps').textContent = vector([s.rgb_stamp, s.depth_stamp]);
  if (s.image_size) el('overlay').setAttribute('viewBox', `0 0 ${s.image_size[0]} ${s.image_size[1]}`);
  if (s.reference) {
    const [x, y] = s.reference;
    el('reference').setAttribute('d', `M${x - 12} ${y}h24 M${x} ${y - 12}v24`);
  }
  el('box').toggleAttribute('hidden', !s.bbox);
  el('target').toggleAttribute('hidden', !s.target_center);
  if (s.bbox) {
    const [x, y, right, bottom] = s.bbox;
    Object.entries({x, y, width: right - x, height: bottom - y}).forEach(([k, v]) => el('box').setAttribute(k, v));
  }
  if (s.target_center) {
    el('target').setAttribute('cx', s.target_center[0]);
    el('target').setAttribute('cy', s.target_center[1]);
  }
  buttons();
}

async function poll() {
  try {
    const response = await fetch('/api/visual_servo/status', {cache: 'no-store', signal: AbortSignal.timeout(1000)});
    if (!response.ok) throw new Error(`Status HTTP ${response.status}`);
    latest = await response.json();
    received = Date.now();
    render(latest);
  } catch (error) {
    received = 0;
    el('state').textContent = 'DISCONNECTED';
    el('reason').textContent = 'ข้อมูลสถานะขาดหาย หากต้องหยุดฉุกเฉินให้ใช้ E-STOP';
    el('box').setAttribute('hidden', '');
    el('target').setAttribute('hidden', '');
    buttons();
  } finally { setTimeout(poll, 250); }
}

async function command(action) {
  // STOP/PAUSE remain usable while ENABLE/START is awaiting a response.
  const generation = ++commandGeneration;
  pending = true;
  buttons();
  const headers = {'Content-Type': 'application/json'};
  if (['enable', 'start'].includes(action)) headers.Authorization = `Bearer ${el('token').value}`;
  const payload = action === 'enable' ? {
    workspace_clear: el('workspace').checked, estop_tested: el('estop').checked,
    assembly_envelope_confirmed: el('envelope').checked
  } : {};
  try {
    const response = await fetch(`/api/visual_servo/${action}`, {
      method: 'POST', headers, body: JSON.stringify(payload), signal: AbortSignal.timeout(5000)
    });
    const text = await response.text();
    let result;
    try { result = JSON.parse(text); } catch (_) { result = {detail: text}; }
    if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
    if (generation === commandGeneration) el('command').textContent = result.message || `${action.toUpperCase()} รับคำสั่งแล้ว`;
  } catch (error) {
    if (generation === commandGeneration) el('command').textContent = error.message + ' · ตรวจสถานะก่อนสั่งใหม่; ใช้ E-STOP หากยืนยันการหยุดไม่ได้';
  } finally {
    if (generation === commandGeneration) { pending = false; received = 0; buttons(); }
  }
}
['enable', 'start', 'pause', 'stop'].forEach(id => el(id).addEventListener('click', () => command(id)));
['workspace', 'estop', 'envelope', 'token'].forEach(id => el(id).addEventListener('input', buttons));
function nextImage() { setTimeout(() => { el('camera').src = `/api/vision/annotated?t=${Date.now()}`; }, 150); }
el('camera').addEventListener('load', () => { el('cameraNotice').textContent = 'ภาพตัวอย่างสด · กรอบจากข้อมูลตรวจจับล่าสุด; เวลาอาจต่างจากภาพตัวอย่าง'; nextImage(); });
el('camera').addEventListener('error', () => { el('cameraNotice').textContent = 'ภาพตัวอย่างขาดหาย'; nextImage(); });
if (el('camera').complete) nextImage();
setInterval(buttons, 250);
poll();
