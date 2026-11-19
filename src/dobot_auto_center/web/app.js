'use strict';

const byId = (name) => document.getElementById(name);
const canvas = byId('camera');
const ctx = canvas.getContext('2d');
let sessionRequest;
let stopGeneration = 0;
let lease = '';
let status;
let displayed;
let image;
let drag;
let confirmation;
let running = false;
let heartbeatBusy = false;
let choiceFrame;

function chip(id, value, style = '') {
  const node = byId(id);
  node.textContent = value;
  node.className = 'chip ' + style;
}

function feedback(message = '') {
  byId('feedback').textContent = message;
}

async function post(path, body = {}, requestId = '') {
  const reply = await fetch('/api/' + path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Control-Lease': lease, 'Idempotency-Key': requestId,
    },
    body: JSON.stringify(body), signal: AbortSignal.timeout(1800),
  });
  const result = await reply.json();
  if (!reply.ok) throw new Error(result.error);
  return result;
}

function newRequestId() {
  const random = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(random, (value) => value.toString(16).padStart(2, '0')).join('');
}

async function withSession(path, body, requestId) {
  const generation = stopGeneration;
  if (!lease) {
    sessionRequest ??= post('control').then(result => {
      lease = result.lease;
    }).finally(() => { sessionRequest = undefined; });
    await sessionRequest;
  }
  if (generation !== stopGeneration) throw new Error('Command interrupted by STOP');
  return post(path, body, requestId);
}

async function command(action, data = {}) {
  feedback();
  try {
    await withSession('command', {action, ...data}, newRequestId());
  } catch (error) {
    feedback(error.message);
  }
}

function clearLease() {
  lease = '';
  hideConfirmation();
  if (status) renderStatus(status);
}

byId('release').onclick = async () => {
  try {
    await post('release');
    feedback();
  } catch (error) {
    feedback(error.message);
  } finally {
    clearLease();
  }
};

setInterval(async () => {
  if (!lease || heartbeatBusy) return;
  const current = lease;
  heartbeatBusy = true;
  try {
    await post('heartbeat');
  } catch (error) {
    if (lease === current) {
      clearLease();
      feedback(error.message);
    }
  } finally {
    heartbeatBusy = false;
  }
}, 500);

byId('stop').onclick = async () => {
  stopGeneration++;
  hideConfirmation();
  try {
    await post('stop');
    feedback('STOP requested');
  } catch (error) {
    feedback(error.message);
  }
};

byId('camera-start').onclick = () => command('camera');
byId('detect').onclick = () => command('detect');

const motionLabels = {
  home: 'Run mock HOME and verify the reference position?',
  observation: 'Move the mock arm from HOME to the observation pose?',
  center: 'Start mock Auto Center for the locked target?',
};

async function askConfirmation(action) {
  try {
    const generation = stopGeneration;
    const result = await withSession('confirm', {action});
    if (generation !== stopGeneration) return;
    confirmation = {action, token: result.confirmation};
    byId('confirm-text').textContent = motionLabels[action];
    byId('confirmation').hidden = false;
    byId('confirm-run').focus();
  } catch (error) {
    feedback(error.message);
  }
}

function hideConfirmation() {
  confirmation = undefined;
  byId('confirmation').hidden = true;
}

for (const action of Object.keys(motionLabels)) byId(action).onclick = () => askConfirmation(action);
byId('confirm-cancel').onclick = hideConfirmation;
byId('confirm-run').onclick = () => {
  if (!confirmation) return;
  const current = confirmation;
  hideConfirmation();
  command(current.action, {confirmation: current.token});
};

function axes(id, labels, values) {
  byId(id).replaceChildren(...labels.map((label, index) => {
    const item = document.createElement('div');
    const name = document.createElement('dt');
    const value = document.createElement('dd');
    name.textContent = label;
    value.textContent = values ? values[index].toFixed(1) : '—';
    item.append(name, value);
    return item;
  }));
}

function renderStatus(s) {
  const busy = ['CENTERING', 'HOMING', 'STOPPING'].includes(s.state) || ['MOVING', 'VERIFYING'].includes(s.motion);
  running = busy;
  chip('mode', s.simulation ? 'Simulation' : 'Read only', 'warn');
  chip('camera-status', s.camera_status, s.camera ? (s.simulation ? 'warn' : 'good') : '');
  chip('state', s.state.replaceAll('_', ' '), s.state === 'CENTERED' ? 'good' : busy ? 'warn' : '');
  chip('robot', s.robot_status, s.connected ? (s.simulation ? 'warn' : 'good') : '');
  byId('release').hidden = !lease;
  byId('camera-start').hidden = !s.simulation;
  byId('camera-start').disabled = s.camera;
  byId('home').disabled = busy || !s.simulation || !s.connected || !s.depth || s.state === 'FAULT';
  byId('observation').disabled = busy || !s.simulation || !s.homed || s.observation_pose || s.state !== 'READY';
  byId('detect').disabled = busy || !s.depth || s.state === 'FAULT' ||
    (s.simulation && !s.observation_pose);
  byId('center').disabled = busy || !s.simulation || s.state !== 'TARGET_LOCKED' || !s.depth;
  byId('diagnostic').textContent = s.diagnostic;
  byId('safety').textContent = s.safety;
  byId('motion').textContent = s.motion;
  byId('depth').textContent = !s.depth ? 'Unavailable' :
    s.target_depth_m == null ? 'Registered' : s.target_depth_m.toFixed(3) + ' m';
  byId('stable').textContent = s.stable_frames + ' / ' + s.stable_frames_required;
  byId('error-x').textContent = s.error ? s.error[0].toFixed(1) + ' px' : '—';
  byId('error-y').textContent = s.error ? s.error[1].toFixed(1) + ' px' : '—';
  byId('resolution').textContent = s.width + ' × ' + s.height;
  byId('empty').hidden = s.camera && Boolean(image);
  byId('empty').textContent = s.simulation && !s.frame_id ? 'Start the mock camera' : s.camera_status;
  byId('frame-age').textContent = s.camera_age_ms == null ? 'No fresh frame' : s.camera_age_ms + ' ms old';
  byId('frame-age').title = s.camera_timestamp == null ? '' : new Date(s.camera_timestamp * 1000).toISOString();
  for (const group of ['hardware-details', 'suction-details', 'gripper-details']) byId(group).hidden = s.simulation;
  byId('firmware').textContent = s.firmware_version.length ? s.firmware_version.join('.') : 'Unavailable';
  for (const tool of ['suction', 'gripper']) {
    const sample = s[tool];
    byId(tool).textContent = sample == null ? 'Unavailable' :
      (sample.active ? 'Active' : 'Inactive') + (sample.control_enabled ? '' : ' · control disabled');
  }
  byId('alarms').textContent = !s.alarm_valid ? 'Unknown' : s.alarms.length ? s.alarms.join(', ') : 'No active alarms';
  axes('tcp', ['X', 'Y', 'Z', 'R'], s.connected ? s.tcp : null);
  axes('joints', ['J1', 'J2', 'J3', 'J4'], s.connected ? s.joints : null);
  updateChoices();
}

function updateChoices() {
  const choices = byId('choices');
  // Freeze the candidate list while the operator interacts with it.
  if (document.activeElement !== choices && !choices.value && !drag) {
    const labels = (displayed?.detections ?? []).map((d, index) =>
      'Object ' + (index + 1) + ' · ' + Math.round(d.center[0]) + ', ' + Math.round(d.center[1]));
    if (choices.dataset.labels !== labels.join('|')) {
      choices.replaceChildren(new Option('Select a detected object', ''),
        ...labels.map((label, index) => new Option(label, String(index))));
      choices.dataset.labels = labels.join('|');
    }
    choiceFrame = displayed;
  }
  choices.disabled = running || !status?.detecting || !status?.camera || status?.state === 'FAULT';
  byId('lock').disabled = choices.disabled || !choices.value;
}

function cross(x, y, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x - 10, y); ctx.lineTo(x + 10, y);
  ctx.moveTo(x, y - 10); ctx.lineTo(x, y + 10);
  ctx.stroke();
}

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!image || !displayed || !status?.camera) return;
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
  cross(canvas.width / 2, canvas.height / 2, '#e3ebed');
  for (const object of displayed.detections) {
    ctx.strokeStyle = '#97e2bd';
    ctx.lineWidth = 2;
    ctx.strokeRect(...object.box);
    ctx.fillStyle = '#97e2bd';
    ctx.beginPath();
    ctx.arc(...object.center, 3, 0, Math.PI * 2);
    ctx.fill();
  }
  if (displayed.target) cross(...displayed.target, '#ffd078');
  if (drag) {
    const [x, y, x2, y2] = bounds(drag.start, drag.end);
    ctx.strokeStyle = '#ffd078';
    ctx.setLineDash([6, 5]);
    ctx.strokeRect(x, y, x2 - x, y2 - y);
    ctx.setLineDash([]);
  }
}

async function update() {
  try {
    const response = await fetch('/api/status', {signal: AbortSignal.timeout(1500)});
    if (!response.ok) throw new Error('Dashboard unavailable');
    status = await response.json();
    if (status.camera && !drag && displayed?.frame_id !== status.frame_id) {
      const frame = await fetch('/api/frame/' + status.frame_id + '.jpg', {signal: AbortSignal.timeout(1500)});
      if (frame.ok && !drag) {
        const nextImage = await createImageBitmap(await frame.blob());
        if (!drag) {
          image?.close();
          image = nextImage;
          displayed = status;
          canvas.width = status.width;
          canvas.height = status.height;
        } else {
          nextImage.close();
        }
      }
    }
    renderStatus(status);
    draw();
  } catch {
    chip('camera-status', 'CAMERA DISCONNECTED');
    chip('robot', 'Disconnected');
    byId('empty').textContent = 'Dashboard connection lost';
    byId('empty').hidden = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const action of ['camera-start', 'home', 'observation', 'detect', 'center', 'lock', 'choices']) byId(action).disabled = true;
  } finally {
    setTimeout(update, 175);
  }
}

function point(event) {
  const r = canvas.getBoundingClientRect();
  const clip = (n, max) => Math.min(max, Math.max(0, n));
  return [clip((event.clientX - r.left) * canvas.width / r.width, canvas.width),
    clip((event.clientY - r.top) * canvas.height / r.height, canvas.height)];
}

function bounds(a, b) {
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]),
    Math.max(a[0], b[0]), Math.max(a[1], b[1])];
}

byId('choices').onchange = updateChoices;
byId('lock').onclick = () => {
  const choices = byId('choices');
  const frame = choiceFrame;
  const object = frame?.detections[Number(choices.value)];
  if (!choices.value || !object) return;
  const [x, y, w, h] = object.box;
  command('select', {frame_id: frame.frame_id, roi: [x, y, x + w, y + h]});
  choices.value = '';
  updateChoices();
};

canvas.onpointerdown = (event) => {
  if (running || !status?.detecting || !status.camera ||
      status.state === 'FAULT' || !displayed || drag) return;
  canvas.setPointerCapture(event.pointerId);
  const start = point(event);
  drag = {start, end: start, frame: displayed.frame_id, pointer: event.pointerId};
};
canvas.onpointermove = (event) => {
  if (!drag || drag.pointer !== event.pointerId) return;
  drag.end = point(event);
  draw();
};
canvas.onpointerup = (event) => {
  if (!drag || drag.pointer !== event.pointerId) return;
  const roi = bounds(drag.start, point(event));
  const frameId = drag.frame;
  drag = undefined;
  draw();
  command('select', {frame_id: frameId, roi});
};
canvas.onpointercancel = () => { drag = undefined; draw(); };
update();
