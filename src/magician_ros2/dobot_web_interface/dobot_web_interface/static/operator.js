const $ = (id) => document.getElementById(id);

const jobSelect = $('jobSelect');
const placeSelect = $('placeSelect');
const startButton = $('startButton');
const stopButton = $('stopButton');
const homeButton = $('homeButton');
const startupButton = $('startupButton');
const autoCalibrationStart = $('autoCalibrationStart');
const autoCalibrationPause = $('autoCalibrationPause');
const autoCalibrationResume = $('autoCalibrationResume');
const autoCalibrationAbort = $('autoCalibrationAbort');
const notice = $('notice');
const annotatedCamera = $('annotatedCamera');
let latestStatus = null;
let cameraTimer = null;

function setNotice(message, error = false) {
  notice.textContent = message;
  notice.classList.toggle('error', error);
}

async function request(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'ไม่สามารถส่งคำสั่งได้');
  return data;
}

function replaceOptions(select, values) {
  const current = select.value;
  select.textContent = '';
  values.forEach(({ id, label }) => {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = label;
    select.appendChild(option);
  });
  if ([...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
  select.disabled = values.length === 0;
}

function renderChecks(checks) {
  const container = $('checks');
  container.textContent = '';
  checks.forEach((check) => {
    const item = document.createElement('div');
    item.className = `check ${check.ok ? 'ready' : 'not-ready'}`;
    const label = document.createElement('span');
    label.textContent = check.label;
    const value = document.createElement('strong');
    value.textContent = check.status;
    const reason = document.createElement('small');
    reason.textContent = `เหตุผล: ${check.reason || 'ไม่มีรายละเอียด'}`;
    item.append(label, value, reason);
    container.appendChild(item);
  });
}

function renderStatus(status) {
  latestStatus = status;
  const overall = $('overallStatus');
  overall.textContent = status.overall_status;
  overall.classList.toggle('ready', status.ready);
  overall.classList.toggle('not-ready', !status.ready);
  $('motionMode').textContent = status.motion_mode === 'REAL'
    ? 'โหมดเคลื่อนไหวจริง'
    : 'โหมดทดสอบ — ยังไม่อนุญาตการเคลื่อนไหวจริง';

  replaceOptions(jobSelect, status.jobs || []);
  replaceOptions(placeSelect, status.places || []);
  renderChecks(status.checks || []);
  renderCalibrationGuidance(status.calibration_guidance || {}, status.supervised_auto || {});

  const counts = status.counts || {};
  $('blackCount').textContent = counts.black || 0;
  $('whiteCount').textContent = counts.white || 0;
  $('yellowCount').textContent = counts.yellow || 0;

  const operation = status.operation || {};
  const control = status.control || { state: 'IDLE' };
  $('operationState').textContent = operation.message || 'รอคำสั่ง';
  const progress = $('pickAllProgress');
  const pickAll = status.pick_all || {};
  const showProgress = jobSelect.value === 'pick_all' || operation.job === 'หยิบทั้งหมด';
  progress.hidden = !showProgress;
  progress.textContent = `หยิบทั้งหมด: ${pickAll.completed || 0} / ${pickAll.total || 0}`;

  const canStart = Boolean(status.ready) && !operation.active;
  startButton.disabled = !canStart;
  jobSelect.disabled = Boolean(operation.active) || !(status.jobs || []).length;
  placeSelect.disabled = Boolean(operation.active) || !(status.places || []).length;
  stopButton.disabled = !operation.active && control.state === 'IDLE';
  startupButton.disabled = Boolean(operation.active) || control.state === 'STOPPING';
  homeButton.disabled = Boolean(operation.active) || ['STARTING', 'RUNNING', 'STOPPING'].includes(control.state);
  if (!operation.active && !status.ready) {
    setNotice(status.fault_message || 'ระบบไม่พร้อมใช้งาน กรุณาตรวจสอบสถานะระบบ', true);
  } else if (!operation.active && status.ready) {
    setNotice('พร้อมเลือกชิ้นงาน ตำแหน่งวาง และเริ่มทำงาน');
  }
}

function formatPose(value) {
  const xyz = value?.xyz_mm || [];
  return `X ${Number(xyz[0] || 0).toFixed(1)} | Y ${Number(xyz[1] || 0).toFixed(1)} | Z ${Number(xyz[2] || 0).toFixed(1)} mm | J4 ${Number(value?.j4_deg || 0).toFixed(1)}°`;
}

function renderCalibrationGuidance(guidance, supervisedAuto) {
  const autoState = supervisedAuto.state && supervisedAuto.state !== 'IDLE'
    ? ` · AUTO ${supervisedAuto.state}` : '';
  $('guidanceState').textContent = `${guidance.state || 'PLAN_UNAVAILABLE'}${autoState}`;
  const coordinates = $('guidanceCoordinates');
  coordinates.textContent = '';
  if (guidance.current && guidance.target && guidance.delta) {
    ['Current', 'Target', 'Delta'].forEach((label) => {
      const row = document.createElement('div');
      const value = label === 'Current' ? guidance.current : label === 'Target' ? guidance.target : guidance.delta;
      row.textContent = `${label}: ${formatPose(value)}`;
      coordinates.appendChild(row);
    });
  }
  const directions = guidance.directions || {};
  $('guidanceDirections').textContent = [directions.X, directions.Y, directions.Z, directions.J4]
    .filter(Boolean).join(' · ') + (guidance.distance_to_target_mm === undefined
      ? '' : ` · ระยะ ${Number(guidance.distance_to_target_mm).toFixed(1)} mm`);
  const progress = $('calibrationProgress');
  progress.textContent = '';
  (guidance.progress || []).forEach((pose) => {
    const item = document.createElement('div');
    const icon = pose.state === 'ACCEPTED' ? '✓' : pose.state === 'GUIDE_TO_TARGET' ? '●' : '○';
    item.textContent = `Pose ${pose.pose_index} ${icon} ${pose.state}`;
    progress.appendChild(item);
  });
}

async function refreshStatus() {
  try {
    const query = new URLSearchParams({
      job: jobSelect.value || 'black',
      place_id: placeSelect.value || 'Zone A',
    });
    const response = await fetch(`/api/operator/status?${query.toString()}`);
    const status = await response.json();
    if (!response.ok) throw new Error(status.detail || 'อ่านสถานะไม่สำเร็จ');
    renderStatus(status);
  } catch (error) {
    $('overallStatus').textContent = 'ไม่พร้อมใช้งาน';
    $('overallStatus').classList.remove('ready');
    $('overallStatus').classList.add('not-ready');
    startButton.disabled = true;
    setNotice('ไม่สามารถอ่านสถานะระบบได้', true);
  }
}

function refreshCamera() {
  annotatedCamera.src = `/api/vision/annotated?t=${Date.now()}`;
}

annotatedCamera.addEventListener('load', () => {
  $('cameraLive').textContent = 'กำลังแสดงภาพสด';
});
annotatedCamera.addEventListener('error', () => {
  $('cameraLive').textContent = 'กำลังรอภาพ';
});

jobSelect.addEventListener('change', refreshStatus);
placeSelect.addEventListener('change', refreshStatus);

startButton.addEventListener('click', async () => {
  startButton.disabled = true;
  try {
    const result = await request('/api/operator/start', {
      job: jobSelect.value,
      place_id: placeSelect.value,
    });
    setNotice(result.message || 'เริ่มทำงานแล้ว');
  } catch (error) {
    setNotice(error.message, true);
  }
  refreshStatus();
});

stopButton.addEventListener('click', async () => {
  try {
    const result = await request('/api/operator/stop');
    setNotice(result.message || 'ส่งคำสั่งหยุดแล้ว');
  } catch (error) {
    setNotice('ไม่สามารถส่งคำสั่งหยุดได้', true);
  }
  refreshStatus();
});

startupButton.addEventListener('click', async () => {
  startupButton.disabled = true;
  try {
    const result = await request('/api/system/startup');
    setNotice(result.startup?.reason || 'เริ่มตรวจสอบระบบแล้ว');
  } catch (error) {
    setNotice('ไม่สามารถเริ่มตรวจสอบระบบได้', true);
  }
  startupButton.disabled = false;
  refreshStatus();
});

homeButton.addEventListener('click', async () => {
  homeButton.disabled = true;
  try {
    const result = await request('/api/homing');
    setNotice(result.success ? 'กำลังกลับ HOME และจุดสังเกต' : 'ไม่สามารถกลับจุดเริ่มต้นได้', !result.success);
  } catch (error) {
    setNotice('ไม่สามารถกลับจุดเริ่มต้นได้', true);
  }
  homeButton.disabled = false;
  refreshStatus();
});

async function autoCalibrationAction(action) {
  try {
    const result = await request(`/api/calibration/auto/${action}`);
    setNotice(`Supervised calibration: ${action} (dry-run)`);
    return result;
  } catch (error) {
    setNotice(error.message, true);
    return null;
  }
}

autoCalibrationStart.addEventListener('click', () => autoCalibrationAction('start'));
autoCalibrationPause.addEventListener('click', () => autoCalibrationAction('pause'));
autoCalibrationResume.addEventListener('click', () => autoCalibrationAction('resume'));
autoCalibrationAbort.addEventListener('click', () => autoCalibrationAction('abort'));

refreshStatus();
refreshCamera();
cameraTimer = window.setInterval(refreshCamera, 500);
window.setInterval(refreshStatus, 1000);
window.addEventListener('beforeunload', () => window.clearInterval(cameraTimer));
