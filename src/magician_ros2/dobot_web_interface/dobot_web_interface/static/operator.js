const $ = (id) => document.getElementById(id);

const jobSelect = $('jobSelect');
const placeSelect = $('placeSelect');
const startButton = $('startButton');
const stopButton = $('stopButton');
const homeButton = $('homeButton');
const homeFeedback = $('homeFeedback');
const notice = $('notice');
const annotatedCamera = $('annotatedCamera');
const cameraPanel = $('cameraPanel');
const cameraFullscreen = $('cameraFullscreen');
const checkViews = new Map();
let latestStatus = null;
let cameraTimer = null;
let cameraPending = !annotatedCamera.complete;
let cameraRetryAfter = 0;
let startPending = false;
let homePending = false;
let statusPending = false;
let stopFailure = '';

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
  if (response.status === 401 || response.status === 403) {
    if (path === '/api/homing') throw new Error('ไม่สามารถส่งคำสั่ง Home ได้ กรุณาเปิดแดชบอร์ดจากที่อยู่ของระบบโดยตรง');
    throw new Error('ต้องใช้สิทธิ์ Maintenance กรุณาเข้าสู่ระบบผ่านลิงก์ Maintenance แล้วลองอีกครั้ง');
  }
  const data = await response.json().catch(() => ({}));
  if (response.status === 503 && path === '/api/homing') {
    throw new Error(data.detail || 'Home ยังไม่พร้อมใช้งาน กรุณาตรวจการเชื่อมต่อหุ่นยนต์');
  }
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
  const currentKeys = new Set();
  checks.forEach((check) => {
    const key = check.key || check.label;
    currentKeys.add(key);
    let view = checkViews.get(key);
    if (!view) {
      const item = document.createElement('details');
      const summary = document.createElement('summary');
      const label = document.createElement('span');
      const value = document.createElement('strong');
      const reason = document.createElement('small');
      summary.append(label, value);
      item.append(summary, reason);
      container.appendChild(item);
      view = { item, label, value, reason };
      checkViews.set(key, view);
    }
    // Reuse each disclosure so polling preserves keyboard focus and open state.
    const { item, label, value, reason } = view;
    item.className = `check ${check.ok ? 'ready' : 'not-ready'}`;
    label.textContent = check.label;
    value.textContent = check.status;
    reason.textContent = `เหตุผล: ${check.reason || 'ไม่มีรายละเอียด'}`;
  });
  for (const [key, { item }] of checkViews) {
    if (!currentKeys.has(key)) {
      item.remove();
      checkViews.delete(key);
    }
  }
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
  renderAutomaticCalibration(status.automatic_calibration || {}, status.calibration || {});
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

  const canStart = status.ready === true && !operation.active && !startPending && !homePending;
  startButton.disabled = !canStart;
  const calibrationIdle = ['IDLE', 'FAULT', 'SAFE_STOP', 'COMMISSIONING_COMPLETE',
    'CANDIDATE_VERIFIED', 'AWAITING_LIVE_VALIDATION', 'READY']
    .includes(status.automatic_calibration?.state || 'IDLE');
  const calibrationBusy = ['AUTO_CALIBRATING', 'STARTING', 'CAPTURING', 'LOADING',
    'CALIBRATING', 'SOLVING', 'VERIFYING', 'SAVING'].includes(status.calibration?.state);
  homeButton.disabled = homePending || startPending || Boolean(operation.active)
    || Boolean(control.owner) || ['STARTING', 'RUNNING', 'STOPPING'].includes(control.state)
    || !calibrationIdle || calibrationBusy;
  $('homeHelp').textContent = homePending ? 'กำลังส่งคำสั่ง Home กรุณารอ'
    : startPending || operation.active || control.owner || ['STARTING', 'RUNNING', 'STOPPING'].includes(control.state)
      ? 'Home รอให้งานปัจจุบันหยุดก่อน · ใช้ STOP เพื่อหยุดงาน'
      : !calibrationIdle || calibrationBusy ? 'Home รอให้คาลิเบรตหยุดก่อน · ใช้ STOP เพื่อหยุดคาลิเบรต'
        : 'กด Home ได้ · แขนจะกลับจุดเริ่มต้นแล้วไปจุดสังเกต';
  jobSelect.disabled = Boolean(operation.active) || !(status.jobs || []).length;
  placeSelect.disabled = Boolean(operation.active) || !(status.places || []).length;
  stopButton.disabled = false;
  if (!operation.active && !status.ready) {
    setNotice(status.fault_message || 'ระบบไม่พร้อมใช้งาน กรุณาตรวจสอบสถานะระบบ', true);
  } else if (!operation.active && status.ready) {
    setNotice('พร้อมเลือกชิ้นงาน ตำแหน่งวาง และเริ่มทำงาน');
  }
  if (stopFailure) setNotice(stopFailure, true);
}

function renderAutomaticCalibration(auto, calibration = {}) {
  const state = auto.state || 'IDLE';
  const total = Math.max(1, Number(auto.total_poses) || 10);
  const accepted = Math.min(total, Math.max(0, Number(auto.accepted_pose_count) || 0));
  const pose = Math.min(total, Math.max(0, Number(auto.current_pose) || 0));
  // Pose progress and successfully accepted images are displayed separately.
  const percent = Math.round(Math.max(pose, accepted) / total * 100);
  const ready = calibration.ready === true && calibration.state === 'READY';
  const labels = {
    IDLE: 'รอตรวจสอบ', PREFLIGHT: 'ตรวจความพร้อม', LOADING: 'โหลดผลเดิม',
    WARMING_UP: 'รอภาพและแขนนิ่ง', PREPARING_BASELINE: 'กำลังเก็บภาพฉากอ้างอิง',
    WAITING_FOR_OPERATOR_AUTHORIZATION: 'รอผู้ได้รับอนุญาตใน Maintenance',
    MOVING: 'กำลังจัดท่า', SETTLING: 'รอแขนหยุดนิ่ง', CAPTURING: 'กำลังเก็บภาพ RGB-D',
    VALIDATING_CAPTURE: 'กำลังตรวจภาพ RGB-D', RETRYING_CAPTURE: 'กำลังถ่ายภาพซ้ำ',
    NEXT_POSE: 'เตรียม Pose ถัดไป', SOLVING: 'กำลังคำนวณ', VERIFYING: 'กำลังตรวจผล',
    SAVING: 'กำลังบันทึก', PAUSED: 'พักการทำงาน', FAULT: 'ทำงานไม่สำเร็จ',
    SAFE_STOP: 'หยุดแล้ว', COMMISSIONING_COMPLETE: 'ผ่าน Commissioning',
    CANDIDATE_VERIFIED: 'ตรวจผลผ่าน รอการตรวจรับระบบจริง',
    AWAITING_LIVE_VALIDATION: 'รอการตรวจรับระบบจริง', READY: 'ตรวจผลผ่าน',
  };
  const collecting = ['MOVING', 'SETTLING', 'CAPTURING', 'VALIDATING_CAPTURE', 'RETRYING_CAPTURE', 'NEXT_POSE'].includes(state);
  $('calibrationStateLabel').textContent = ready ? 'READY' : labels[state] || state;
  $('calibrationSummary').textContent = ready ? 'Calibration สำเร็จ ระบบพร้อมทำงาน'
    : collecting ? `กำลังคาลิเบรตอัตโนมัติ Pose ${pose}/${total} (${percent}%)`
    : labels[state] || 'กำลังรอสถานะ';
  $('calibrationPose').textContent = `${pose}/${total}`;
  $('calibrationAccepted').textContent = `${accepted}/${total}`;
  $('calibrationProgressBar').value = percent;
  $('calibrationProgressBar').textContent = `${percent}%`;
  $('calibrationProgressLabel').textContent = `${percent}%`;
  $('calibrationCapture').textContent = (auto.capture_status || labels[state] || 'รอข้อมูล')
    + (auto.capture_attempt ? ` · ครั้งที่ ${auto.capture_attempt}/${auto.max_capture_attempts || 3}` : '');
  $('calibrationResult').textContent = ready ? 'PASS'
    : auto.result?.independent_verification?.result === 'PASS' ? 'ตรวจคำนวณผ่าน · รอ READY'
    : ['FAULT', 'SAFE_STOP'].includes(state) ? 'ไม่สำเร็จ' : 'ยังไม่พร้อมใช้งาน';
  const completed = auto.last_completed_unix_s || calibration.last_completed_unix_s;
  $('calibrationCompleted').textContent = completed ? new Date(completed * 1000).toLocaleString('th-TH') : '—';
  const reason = (auto.blockers || []).join(' · ') || auto.reason || calibration.reason || '';
  const showReason = !ready && ['FAULT', 'SAFE_STOP', 'AWAITING_LIVE_VALIDATION', 'WAITING_FOR_OPERATOR_AUTHORIZATION'].includes(state);
  $('calibrationError').hidden = !showReason;
  const startPose = auto.start_pose_check;
  if (showReason && reason.includes('START_POSE_OUTSIDE_WORKSPACE') && startPose) {
    const xyz = startPose.current_xyz_mm.map(value => Number(value).toFixed(1)).join(', ');
    const ranges = ['X', 'Y', 'Z'].map((axis, i) => {
      const low = Math.max(startPose.allowed_center_min_m[i],
        i === 2 ? startPose.table_min_center_z_m : -Infinity) * 1000;
      const high = startPose.allowed_center_max_m[i] * 1000;
      return `${axis} ${low.toFixed(1)} ถึง ${high.toFixed(1)}`;
    }).join(' · ');
    $('calibrationError').textContent = `ตำแหน่งแขนปัจจุบัน (${xyz} มม.) อยู่นอกพื้นที่เริ่มคาลิเบรตตามข้อมูลติดตั้งเดิม `
      + `ช่วง TCP ที่ผ่านขอบเขตพื้นที่: ${ranges} มม. ต้องตรวจเส้นทางและจัดแขนเข้าพื้นที่ก่อนเริ่ม ระบบยังไม่ได้สั่งเคลื่อนแขน`;
  } else {
    $('calibrationError').textContent = showReason ? reason : '';
  }
}

async function refreshStatus() {
  if (statusPending) return;
  statusPending = true;
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
    homeButton.disabled = true;
    $('homeHelp').textContent = 'Home ใช้ไม่ได้ชั่วคราว: ขาดการเชื่อมต่อระบบ กำลังลองเชื่อมต่อใหม่';
    latestStatus = null;
    $('calibrationStateLabel').textContent = 'ขาดการเชื่อมต่อ';
    $('calibrationSummary').textContent = 'ไม่สามารถยืนยันสถานะ Calibration ได้';
    setNotice('ไม่สามารถอ่านสถานะระบบได้', true);
  } finally {
    statusPending = false;
  }
}

function refreshCamera() {
  // Keep at most one JPEG in flight so a slow connection cannot queue frames.
  if (document.hidden || cameraPending || Date.now() < cameraRetryAfter) return;
  cameraPending = true;
  annotatedCamera.src = `/api/vision/annotated?t=${Date.now()}`;
}

function updateCameraAspectRatio() {
  if (annotatedCamera.naturalWidth > 0 && annotatedCamera.naturalHeight > 0) {
    cameraPanel.style.setProperty(
      '--camera-ratio', annotatedCamera.naturalWidth / annotatedCamera.naturalHeight,
    );
  }
}

function cameraIsExpanded() {
  return document.fullscreenElement === cameraPanel || cameraPanel.classList.contains('camera-expanded');
}

function updateFullscreenButton() {
  const expanded = cameraIsExpanded();
  cameraFullscreen.setAttribute('aria-pressed', String(expanded));
  cameraFullscreen.setAttribute('aria-label', expanded ? 'ออกจากภาพกล้องเต็มจอ' : 'ขยายภาพกล้องเต็มจอ');
  $('fullscreenLabel').textContent = expanded ? 'ออกจากเต็มจอ' : 'เต็มจอ';
}

function setExpandedCameraFallback(expanded) {
  cameraPanel.classList.toggle('camera-expanded', expanded);
  document.body.classList.toggle('camera-expanded', expanded);
  // STOP remains keyboard-accessible while the camera is expanded.
  updateFullscreenButton();
  cameraFullscreen.focus();
}

cameraFullscreen.addEventListener('click', async () => {
  const displayNotice = $('cameraDisplayNotice');
  displayNotice.hidden = true;
  try {
    if (document.fullscreenElement === cameraPanel) {
      await document.exitFullscreen();
    } else if (cameraPanel.classList.contains('camera-expanded')) {
      setExpandedCameraFallback(false);

    } else {
      setExpandedCameraFallback(true);
    }
  } catch (error) {
    if (!document.fullscreenElement) {
      setExpandedCameraFallback(true);
      displayNotice.textContent = 'แสดงเต็มพื้นที่เบราว์เซอร์ · กด Esc หรือออกจากเต็มจอเพื่อกลับ';
    } else {
      displayNotice.textContent = 'กด Esc เพื่อออกจากภาพกล้องเต็มจอ';
    }
    displayNotice.hidden = false;
  }
  updateFullscreenButton();
});
window.addEventListener('fullscreenchange', updateFullscreenButton);
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && cameraPanel.classList.contains('camera-expanded')) {
    setExpandedCameraFallback(false);
    $('cameraDisplayNotice').hidden = true;
  }
});

annotatedCamera.addEventListener('load', () => {
  cameraPending = false;
  updateCameraAspectRatio();
  $('cameraLive').textContent = 'กำลังแสดงภาพสด';
  $('cameraLive').classList.add('live');
});
annotatedCamera.addEventListener('error', () => {
  cameraPending = false;
  cameraRetryAfter = Date.now() + 1000;
  $('cameraLive').textContent = 'กำลังรอภาพ';
  $('cameraLive').classList.remove('live');
});
updateCameraAspectRatio();

jobSelect.addEventListener('change', refreshStatus);
placeSelect.addEventListener('change', refreshStatus);

startButton.addEventListener('click', async () => {
  if (startButton.disabled || latestStatus?.ready !== true) return;
  startPending = true;
  startButton.disabled = true;
  homeButton.disabled = true;
  try {
    const result = await request('/api/operator/start', {
      job: jobSelect.value,
      place_id: placeSelect.value,
    });
    setNotice(result.message || 'เริ่มทำงานแล้ว');
  } catch (error) {
    setNotice(error.message, true);
  } finally {
    startPending = false;
  }
  refreshStatus();
});

homeButton.addEventListener('click', async () => {
  if (homeButton.disabled || homePending || !latestStatus) return;
  homePending = true;
  homeButton.textContent = 'กำลังส่งคำสั่ง Home…';
  homeButton.setAttribute('aria-busy', 'true');
  homeFeedback.hidden = false;
  homeFeedback.classList.remove('error');
  homeFeedback.textContent = 'กำลังส่งคำสั่งกลับ Home และจุดสังเกต';
  renderStatus(latestStatus);
  try {
    const result = await request('/api/homing');
    if (result.success !== true) throw new Error(result.message || 'ไม่สามารถกลับ Home ได้');
    homeFeedback.textContent = 'รับคำสั่ง Home แล้ว แขนจะกลับจุดเริ่มต้นและไปจุดสังเกต';
  } catch (error) {
    homeFeedback.textContent = error.message;
    homeFeedback.classList.add('error');
  } finally {
    homePending = false;
    homeButton.textContent = 'Home · กลับจุดเริ่มต้น';
    homeButton.setAttribute('aria-busy', 'false');
    refreshStatus();
  }
});

stopButton.addEventListener('click', async () => {
  try {
    const result = await request('/api/operator/stop');
    stopFailure = '';
    setNotice(result.message || 'ส่งคำสั่งหยุดแล้ว');
  } catch (error) {
    stopFailure = 'ไม่สามารถส่งคำสั่ง STOP ได้ ตรวจแขนและใช้ Emergency Stop ที่เครื่อง';
    setNotice(stopFailure, true);
  }
  refreshStatus();
});


refreshStatus();
refreshCamera();
cameraTimer = window.setInterval(refreshCamera, 100);
window.setInterval(refreshStatus, 1000);
window.addEventListener('beforeunload', () => window.clearInterval(cameraTimer));
