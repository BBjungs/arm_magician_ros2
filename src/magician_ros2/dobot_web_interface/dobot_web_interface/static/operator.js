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
const cameraPanel = $('cameraPanel');
const cameraFullscreen = $('cameraFullscreen');
const checkViews = new Map();
let latestStatus = null;
let automaticPlanFingerprint = null;
let latestAutomatic = {};
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
  renderCalibrationGuidance(status.calibration_guidance || {}, status.supervised_auto || {});
  renderAutomaticCalibration(status.automatic_calibration || {});
  const solve = status.passive_solve || {};
  if (solve.state && solve.state !== 'IDLE') {
    $('passiveResult').textContent = `${solve.state}: ${solve.reason || 'กำลังคำนวณจากข้อมูลจริง'}`;
  }

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

function renderAutomaticCalibration(auto) {
  const labels = {
    WAITING_FOR_OPERATOR_AUTHORIZATION: 'รอผู้ควบคุมอนุญาตเฉพาะรอบ',
    COMMISSIONING_COMPLETE: 'ทดสอบสองท่าจริงเสร็จแล้ว',
    IDLE: 'พร้อมตรวจแผน', PREFLIGHT: 'กำลังตรวจความพร้อม', MOVING: 'กำลังจัดท่า',
    SETTLING: 'รอแขนหยุดนิ่ง', CAPTURING: 'กำลังเก็บภาพ',
    VALIDATING_CAPTURE: 'กำลังตรวจภาพ', NEXT_POSE: 'เตรียมท่าถัดไป',
    SOLVING: 'กำลังคำนวณและตรวจผล', PAUSED: 'พักการทำงาน',
    CANDIDATE_VERIFIED: 'คำนวณและตรวจผลผ่าน', FAULT: 'ยังดำเนินการไม่ได้', SAFE_STOP: 'หยุดแล้ว',
  };
  const active = !['IDLE', 'FAULT', 'SAFE_STOP', 'COMMISSIONING_COMPLETE', 'CANDIDATE_VERIFIED'].includes(auto.state || 'IDLE');
  latestAutomatic = auto;
  const compatible = auto.authorization_protocol === 2;
  $('automaticStart').disabled = active || !compatible;
  $('automaticCommission').disabled = active || !compatible;
  const planChanged = automaticPlanFingerprint !== auto.plan_fingerprint;
  if (planChanged) {
    document.querySelectorAll('[data-calibration-ack]').forEach((box) => { box.checked = false; });
    automaticPlanFingerprint = auto.plan_fingerprint;
  }
  $('automaticAuthorization').hidden = auto.state !== 'WAITING_FOR_OPERATOR_AUTHORIZATION';
  updateAuthorizationButton();
  const planView = $('automaticPlan');
  planView.textContent = '';
  (auto.plan || []).forEach((pose) => {
    const row = document.createElement('div');
    row.textContent = `Pose ${pose.pose_index}: XYZ ${(pose.xyz_mm || []).map((n) => Number(n).toFixed(1)).join(', ')} mm · J4 ${Number(pose.j4_deg).toFixed(1)}°`;
    planView.appendChild(row);
  });
  $('automaticPause').disabled = !active || auto.state === 'PAUSED';
  $('automaticResume').disabled = auto.state !== 'PAUSED';
  $('automaticAbort').disabled = !active;
  let reason = (auto.blockers || []).join(' · ') || auto.reason || '';
  if (!compatible) reason = 'โปรเซสคาลิเบรตยังเป็นรุ่นเดิม ต้องโหลดรุ่นที่รองรับการอนุญาตเฉพาะรอบก่อน';
  if (auto.commissioning_required && !auto.commissioning_available) {
    reason += ' · ต้องผ่าน Commissioning สองท่าจริงก่อนรอบสิบท่า';
  }
  const progress = `${auto.accepted_pose_count || 0}/${auto.total_poses || 10} ท่า`;
  $('automaticResult').textContent = `${labels[auto.state] || 'รอสถานะจากระบบ'} · ${progress}`;
  $('calibrationTechnicalReason').textContent = reason || 'ยังไม่มีรายละเอียดเพิ่มเติมจากระบบ';
  renderCalibrationWizard(auto, planChanged);
}

function calibrationInstructions(reasons) {
  const messages = [
    ['WORKSPACE_NOT_CONFIGURED', 'กำหนดพื้นที่ทำงานก่อน', 'ให้ผู้ติดตั้งวัดระดับโต๊ะและขอบเขตพื้นที่ว่างในพิกัดฐานหุ่นยนต์ แล้วบันทึกค่าพื้นที่คาลิเบรต'],
    ['SCENE_BASELINE_MISSING', 'ยังไม่มีข้อมูลฉากอ้างอิง', 'ให้ผู้ติดตั้งเก็บและตรวจสอบฉากอ้างอิงของพื้นที่ทำงานก่อนตรวจแผนอีกครั้ง'],
    ['MOUNT_ROTATION_UNVERIFIED', 'ยังไม่ยืนยันมุมติดตั้งกล้อง', 'ให้ผู้ติดตั้งทำขั้นตอนคาลิเบรตแบบมีผู้ดูแล เพื่อยืนยันมุมกล้องกับแขนกล'],
    ['DEPTH_INSUFFICIENT_VALID_PIXELS', 'กล้องเห็นความลึกไม่เพียงพอ', 'ตรวจว่ากล้องเห็นพื้นผิวพื้นที่ทำงานชัดเจนและอยู่ในระยะวัด แล้วกดตรวจระบบอีกครั้ง'],
    ['DEPTH_ALL_ZERO', 'กล้องยังไม่มีข้อมูลความลึก', 'ตรวจสาย USB 3 และภาพความลึกในสถานะระบบก่อนทำต่อ'],
    ['TWO_POSE_COMMISSIONING_REQUIRED', 'ต้องทดสอบ 2 ท่าก่อน', 'ตรวจแผนทดสอบ 2 ท่า ยืนยันรอบนั้น และรอผลผ่านก่อนตรวจแผนคาลิเบรต 10 ท่า'],
    ['OPERATOR_AUTHORIZATION_EXPIRED', 'หมดเวลายืนยันแผน', 'ตรวจแผนใหม่และยืนยันเงื่อนไขหน้าเครื่องอีกครั้งสำหรับรอบใหม่'],
    ['ROBOT_MOVED_SINCE_PLAN_VALIDATION', 'ตำแหน่งแขนเปลี่ยนหลังตรวจแผน', 'รอให้แขนหยุดนิ่ง แล้วตรวจแผนใหม่ก่อนยืนยัน'],
  ];
  const raw = reasons.filter(Boolean).join('; ');
  const known = messages.filter(([code]) => raw.includes(code));
  if (raw && !known.length) {
    return [['OTHER', 'ยังมีเงื่อนไขที่ต้องตรวจสอบ', 'ดูสถานะระบบและเปิดรายละเอียดสำหรับผู้ติดตั้งด้านล่าง แก้สาเหตุแล้วจึงตรวจแผนอีกครั้ง']];
  }
  return known;
}

function renderCalibrationWizard(auto, planChanged) {
  const state = auto.state || 'IDLE';
  const waiting = state === 'WAITING_FOR_OPERATOR_AUTHORIZATION';
  const fault = state === 'FAULT';
  const capturing = ['MOVING', 'SETTLING', 'CAPTURING', 'VALIDATING_CAPTURE', 'NEXT_POSE', 'PAUSED'].includes(state);
  const complete = ['COMMISSIONING_COMPLETE', 'CANDIDATE_VERIFIED'].includes(state);
  const step = waiting ? 2 : capturing ? 3 : state === 'SOLVING' || complete ? 4 : 1;
  for (let i = 1; i <= 4; i += 1) {
    const element = $(`calibrationStep${i}`);
    element.classList.toggle('completed', i < step && !fault);
    if (i === step) element.setAttribute('aria-current', 'step');
    else element.removeAttribute('aria-current');
  }

  let title = 'เริ่มจากตรวจแผนทดสอบ 2 ท่า';
  let help = 'ครั้งแรกให้ทดสอบ 2 ท่าก่อน แล้วจึงคาลิเบรตครบ 10 ท่า การตรวจแผนยังไม่สั่งแขนเคลื่อนที่';
  let badge = 'เตรียมคาลิเบรต';
  const total = Math.max(1, Number(auto.total_poses) || 10);
  const accepted = Math.max(0, Math.min(total, Number(auto.accepted_pose_count) || 0));
  if (state === 'PREFLIGHT') {
    title = 'กำลังตรวจอุปกรณ์และแผนการเคลื่อนที่';
    help = 'รอผลตรวจ หากผ่าน ระบบจะแสดงแผนและรายการให้คุณยืนยันก่อนเคลื่อนที่';
    badge = 'กำลังตรวจแผน';
  } else if (waiting) {
    title = 'ตรวจแผน แล้วติ๊กยืนยันทีละข้อ';
    help = 'อ่านแผนด้านล่างและตรวจพื้นที่จริงให้ครบ เมื่อกดอนุญาต แขนจะเริ่มเคลื่อนตามแผนรอบนี้';
    badge = 'รอคุณยืนยัน';
  } else if (capturing) {
    title = state === 'PAUSED' ? 'พักการคาลิเบรตแล้ว' : `กำลังเก็บภาพ · ผ่านแล้ว ${accepted} / ${total} ท่า`;
    help = state === 'PAUSED'
      ? 'กดทำต่อเมื่อพร้อม ระบบจะตรวจการอนุญาตและเงื่อนไขอีกครั้ง หรือกดหยุดคาลิเบรตเพื่อยุติรอบนี้'
      : 'ติดตามภาพกล้องและความคืบหน้า ปุ่มพักจะพักเมื่อแขนหยุดนิ่ง ส่วนปุ่มหยุดใช้ขอยุติรอบนี้';
    badge = state === 'PAUSED' ? 'พักอยู่' : 'กำลังทำงาน';
  } else if (state === 'SOLVING') {
    title = 'เก็บภาพแล้ว กำลังคำนวณและตรวจผล';
    help = 'รอผลตรวจจากระบบก่อนเริ่มงาน ขั้นตอนนี้ยังไม่ใช่การยืนยันว่าพร้อมหยิบชิ้นงาน';
    badge = 'กำลังตรวจผล';
  } else if (state === 'COMMISSIONING_COMPLETE') {
    title = 'ทดสอบ 2 ท่าผ่านแล้ว';
    help = 'ต่อไปกดตรวจแผนคาลิเบรต 10 ท่า แล้วตรวจและยืนยันแผนรอบใหม่ให้ครบ';
    badge = 'ทดสอบผ่าน';
  } else if (state === 'CANDIDATE_VERIFIED') {
    title = 'ผลคำนวณผ่านแล้ว';
    help = 'กดตรวจระบบเพื่อยืนยันผลคาลิเบรตกับอุปกรณ์ปัจจุบัน จากนั้นทำตามสถานะ HOME และจุดสังเกตก่อนเริ่มงาน';
    badge = 'รอตรวจระบบ';
  } else if (state === 'SAFE_STOP') {
    title = 'ยุติรอบคาลิเบรตแล้ว';
    help = 'ตรวจว่าแขนหยุดจริงและพื้นที่พร้อม ก่อนตรวจแผนใหม่ ข้อมูลที่เก็บบางส่วนยังไม่ถือเป็นผลคาลิเบรตที่ผ่าน';
    badge = 'หยุดแล้ว';
  } else if (fault) {
    title = 'แก้เงื่อนไขด้านล่าง แล้วตรวจแผนอีกครั้ง';
    help = 'ระบบยังไม่ผ่านการคาลิเบรต รายการด้านล่างบอกสิ่งที่ต้องเตรียมก่อนทำต่อ';
    badge = 'ต้องตรวจสอบ';
  } else if (state !== 'IDLE') {
    title = 'รอสถานะล่าสุดจากระบบคาลิเบรต';
    help = 'ดูรายละเอียดจากระบบด้านล่างก่อนดำเนินการต่อ';
    badge = 'รอสถานะ';
  }
  if (auto.authorization_protocol !== 2) {
    title = 'ยังเชื่อมต่อระบบคาลิเบรตรุ่นที่รองรับไม่ได้';
    help = 'ให้ผู้ดูแลตรวจบริการคาลิเบรต ปุ่มตรวจแผนจะใช้งานได้เมื่อระบบรองรับการยืนยันก่อนเคลื่อนที่';
    badge = 'รอระบบ';
  }

  const reasons = [...(auto.blockers || [])];
  if (fault && auto.reason) reasons.push(auto.reason);
  if (auto.commissioning_required && !auto.commissioning_available) reasons.push('TWO_POSE_COMMISSIONING_REQUIRED');
  const guidance = calibrationInstructions(reasons);
  const blockers = $('calibrationBlockers');
  blockers.textContent = '';
  blockers.hidden = !guidance.length;
  guidance.forEach(([, heading, instruction]) => {
    const item = document.createElement('li');
    const label = document.createElement('strong');
    const detail = document.createElement('p');
    label.textContent = heading;
    detail.textContent = instruction;
    item.append(label, detail);
    blockers.appendChild(item);
  });
  if (waiting && auto.commissioning_required && !auto.commissioning_available) {
    title = 'รอบ 10 ท่ายังขาดผลทดสอบ 2 ท่า';
    help = 'หยุดคาลิเบรตรอบที่รออยู่นี้ก่อน แล้วตรวจแผนทดสอบ 2 ท่าและทำให้ผ่าน จึงกลับมาตรวจแผน 10 ท่า';
  }
  $('calibrationNextTitle').textContent = title;
  $('calibrationNextHelp').textContent = help;
  $('calibrationStateLabel').textContent = badge;
  $('calibrationStateLabel').classList.toggle('error', fault);
  $('calibrationStateLabel').classList.toggle('success', state === 'COMMISSIONING_COMPLETE');
  $('calibrationRunProgress').hidden = !capturing && state !== 'SOLVING' && !complete;
  $('calibrationProgressBar').max = total;
  $('calibrationProgressBar').value = accepted;
  $('calibrationProgressLabel').textContent = `เก็บภาพที่ผ่านตรวจแล้ว ${accepted} / ${total} ท่า`;

  const details = $('calibrationPlanDetails');
  details.hidden = !(auto.plan || []).length;
  if (waiting && planChanged) details.open = true;
  $('calibrationPlanHelp').textContent = auto.purpose === 'COMMISSIONING_TWO_POSES'
    ? 'รอบทดสอบนี้ใช้ 2 ท่าแรกจากแผน ด้านล่างแสดงแผนเต็มที่ระบบตรวจสอบ'
    : 'ตรวจพิกัดและพื้นที่เคลื่อนที่ของแผนนี้ก่อนยืนยันเงื่อนไขหน้าเครื่อง';
}

function setCalibrationFeedback(message, error = false) {
  const feedback = $('calibrationFeedback');
  feedback.hidden = !message;
  feedback.textContent = message;
  feedback.classList.toggle('error', error);
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
  // Keep keyboard navigation within the expanded camera panel.
  document.querySelectorAll('.topbar, .count-card, .control-panel').forEach((element) => {
    element.inert = expanded;
  });
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
    } else if (document.fullscreenEnabled && cameraPanel.requestFullscreen) {
      await cameraPanel.requestFullscreen();
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
  updateCameraAspectRatio();
  $('cameraLive').textContent = 'กำลังแสดงภาพสด';
  $('cameraLive').classList.add('live');
});
annotatedCamera.addEventListener('error', () => {
  $('cameraLive').textContent = 'กำลังรอภาพ';
  $('cameraLive').classList.remove('live');
});
updateCameraAspectRatio();

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

function updateAuthorizationButton() {
  const boxes = [...document.querySelectorAll('[data-calibration-ack]')];
  $('calibrationAckProgress').textContent = `ยืนยันแล้ว ${boxes.filter((box) => box.checked).length} / ${boxes.length} ข้อ`;
  $('automaticAuthorize').disabled = latestAutomatic.state !== 'WAITING_FOR_OPERATOR_AUTHORIZATION'
    || latestAutomatic.authorization_protocol !== 2
    || !automaticPlanFingerprint || !boxes.every((box) => box.checked)
    || (latestAutomatic.commissioning_required && !latestAutomatic.commissioning_available);
}
document.querySelectorAll('[data-calibration-ack]').forEach((box) => {
  box.addEventListener('change', updateAuthorizationButton);
});
$('automaticAuthorize').addEventListener('click', async () => {
  const body = { plan_fingerprint: automaticPlanFingerprint };
  document.querySelectorAll('[data-calibration-ack]').forEach((box) => {
    body[box.dataset.calibrationAck] = box.checked;
  });
  $('automaticAuthorize').disabled = true;
  setCalibrationFeedback('กำลังส่งการยืนยันสำหรับแผนรอบนี้…');
  try {
    const result = await request('/api/calibration/autonomous/authorize', body);
    setNotice(result.message, !result.accepted);
    setCalibrationFeedback(result.accepted
      ? 'ส่งการยืนยันแล้ว ติดตามสถานะการเคลื่อนที่และการเก็บภาพด้านบน'
      : result.message || 'ระบบไม่รับการยืนยัน กรุณาตรวจสถานะและแผนรอบนี้', !result.accepted);
  } catch (error) {
    setNotice(error.message, true);
    setCalibrationFeedback(`ส่งการยืนยันไม่สำเร็จ: ${error.message}`, true);
  } finally {
    await refreshStatus();
  }
});

for (const [id, action] of [['automaticStart', 'start'], ['automaticCommission', 'commission'], ['automaticPause', 'pause'],
                            ['automaticResume', 'resume'], ['automaticAbort', 'abort']]) {
  $(id).addEventListener('click', async () => {
    $(id).disabled = true;
    setCalibrationFeedback('กำลังส่งคำขอ…');
    try {
      const result = await request(`/api/calibration/autonomous/${action}`);
      setNotice(result.message, !result.accepted);
      const messages = {
        start: 'ส่งคำขอตรวจแผน 10 ท่าแล้ว รอผลและตรวจแผนก่อนยืนยันการเคลื่อนที่',
        commission: 'ส่งคำขอตรวจแผนทดสอบ 2 ท่าแล้ว รอผลและตรวจแผนก่อนยืนยันการเคลื่อนที่',
        pause: 'ส่งคำขอพักแล้ว รอให้สถานะแสดงว่าพักการทำงาน',
        resume: 'ส่งคำขอทำต่อแล้ว ติดตามสถานะด้านบน',
        abort: 'ส่งคำขอหยุดแล้ว ตรวจว่าแขนหยุดจริงจากสถานะและหน้าเครื่อง',
      };
      setCalibrationFeedback(result.accepted ? messages[action] : result.message || 'ระบบไม่รับคำขอ กรุณาตรวจสถานะ', !result.accepted);
    } catch (error) {
      setNotice(error.message, true);
      setCalibrationFeedback(`ส่งคำขอไม่สำเร็จ: ${error.message}`, true);
    } finally {
      refreshStatus();
    }
  });
}

for (const [id, action] of [['passiveCapture', 'capture'], ['passiveSolve', 'solve']]) {
  $(id).addEventListener('click', async () => {
    $(id).disabled = true;
    try {
      const result = await request(`/api/calibration/passive/${action}`);
      const message = result.reason || (result.rejection_reasons || []).join('; ')
        || (action === 'capture' ? `เก็บท่าจริง ${result.pose_index}/10 แล้ว`
          : 'กำลังคำนวณข้อมูลจริง ผลจะอยู่ที่ /api/vision/calibration → passive_solve');
      $('passiveResult').textContent = message;
      setNotice(message, !result.success);
    } catch (error) {
      setNotice(error.message, true);
    } finally {
      $(id).disabled = false;
      refreshStatus();
    }
  });
}

refreshStatus();
refreshCamera();
cameraTimer = window.setInterval(refreshCamera, 500);
window.setInterval(refreshStatus, 1000);
window.addEventListener('beforeunload', () => window.clearInterval(cameraTimer));
