(() => {
  const get = id => document.getElementById(id);
  const image = get('objectReferenceImage');
  const feedback = get('objectReferenceStatus');
  let displayed = null, latest = null, pending = false, fingerprint = '';
  const acknowledgements = {
    operator_confirmed: 'ฉันเป็นผู้ปฏิบัติงานที่ได้รับอนุญาตและอยู่หน้าเครื่อง',
    estop_tested: 'ทดสอบ E-stop แล้ว', workspace_clear: 'พื้นที่เคลื่อนที่ว่างและไม่มีคน',
    mount_secure: 'กล้องและเครื่องมือยึดแน่น', workspace_measured: 'Workspace วัดและตรวจสอบแล้ว',
    collision_reviewed: 'ตรวจเส้นทางและ Collision ของแผนนี้แล้ว', stop_tested: 'ทดสอบการหยุดแขนแล้ว',
  };
  const messages = [
    ['OBJECT_SYMMETRIC', 'วัตถุสมมาตรเกินไป กรุณาเลือกชิ้นที่มีรูปทรงต่างกันตามแต่ละด้าน'],
    ['OBJECT_TEXTURE_INSUFFICIENT', 'รายละเอียดบนวัตถุน้อยเกินไป กรุณาเลือกวัตถุที่มีลวดลายชัดเจน'],
    ['Insufficient scene geometry', 'วัตถุแบนหรือเล็กเกินไป กรุณาเลือกชิ้นที่มีความลึกและขนาดมากขึ้น'],
    ['REFERENCE_OBJECT_MOVED', 'วัตถุอ้างอิงขยับหรือการติดตามไม่สอดคล้อง กรุณาวางให้นิ่งแล้วเริ่มใหม่'],
    ['OBJECT_SELECTION_AMBIGUOUS', 'มีวัตถุที่เหมาะสมหลายชิ้น กรุณาคลิกเลือกเพียงหนึ่งชิ้น'],
    ['OBJECT_REFERENCE_UNSUITABLE_OR_LOST', 'ติดตามวัตถุไม่ได้ กรุณาเลือกวัตถุที่เห็นรายละเอียดและความลึกชัดเจน'],
    ['OBJECT_DEPTH', 'ข้อมูลความลึกของวัตถุไม่เพียงพอหรือมี Noise มาก กรุณาปรับวัตถุหรือแสง'],
    ['OBJECT_DETECTION', 'ข้อมูลตรวจจับยังไม่ตรงกับภาพ RGB-D ปัจจุบัน กรุณารอภาพใหม่'],
    ['OBJECT_SELECTION_IMAGE_CHANGED', 'ภาพเปลี่ยนแล้ว กรุณาคลิกเลือกจากภาพล่าสุดอีกครั้ง'],
    ['CAMERA_ATTACHMENT', 'ยังยืนยันลิงก์ที่ยึดกล้องไม่ได้ ต้องตรวจการติดตั้งก่อน'],
    ['OBJECT_AUTOMATIC_CAMERA_PARENT', 'ลิงก์ติดตั้งกล้องนี้ยังไม่ได้ตรวจรับสำหรับแผนอัตโนมัติ'],
    ['observable', 'การเคลื่อนที่ยังให้ข้อมูลไม่พอสำหรับคำนวณ Transform ระบบจะไม่เดาค่า'],
    ['excitation', 'มุมมองยังให้ข้อมูลอิสระไม่เพียงพอสำหรับคำนวณ Transform'],
    ['TWO_POSE_COMMISSIONING_REQUIRED', 'ต้องผ่านการตรวจรับการเคลื่อนที่สองท่าใน Maintenance ก่อน'],
    ['LIVE_VALIDATION', 'คำนวณเสร็จแล้ว แต่ต้องตรวจรับฮาร์ดแวร์และความแม่นยำจริงก่อนเปิดการหยิบ'],
  ];
  const explain = text => (messages.find(([code]) => String(text).includes(code)) || [null, text])[1];
  const checks = {};
  Object.entries(acknowledgements).forEach(([key, label]) => {
    const row = document.createElement('label'), box = document.createElement('input');
    box.type = 'checkbox'; box.checked = false; checks[key] = box;
    row.append(box, document.createTextNode(label));
    get('objectMotionChecks').append(row, document.createElement('br'));
  });
  async function post(action, body = {}) {
    const response = await fetch(`/api/calibration/${action}`, {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    if (response.status === 401 || response.status === 403) {
      throw Error('ต้องเข้าสู่ระบบ Maintenance ด้วยสิทธิ์เดิมก่อนเริ่มหรืออนุญาต Calibration');
    }
    const result = await response.json();
    if (!response.ok || result.accepted === false) throw Error(result.detail || result.report?.reason || result.message || 'ไม่สามารถเริ่มได้');
    return result;
  }
  async function command(action, body) {
    if (pending) return;
    pending = true;
    try { await post(action, body); feedback.textContent = 'รับคำขอแล้ว กำลังตรวจข้อมูล'; }
    catch (error) { feedback.textContent = explain(error.message); }
    finally { pending = false; }
  }
  image.addEventListener('click', event => {
    if (!displayed) return;
    const box = image.getBoundingClientRect();
    const pixel = [(event.clientX - box.left) * displayed.image_size[0] / box.width,
      (event.clientY - box.top) * displayed.image_size[1] / box.height];
    command('object/select', {pixel, image_size: displayed.image_size, rgb_stamp: displayed.rgb_stamp});
  });
  get('objectCalibrationStart').addEventListener('click', () => command('object/start'));
  get('objectCalibrationDryRun').addEventListener('click', () => command('object/dry_run'));
  get('objectMotionAuthorize').addEventListener('click', () => {
    if (!latest || latest.state !== 'WAITING_FOR_OPERATOR_AUTHORIZATION' || !fingerprint) return;
    if (!Object.values(checks).every(box => box.checked)) {
      feedback.textContent = 'ต้องตรวจและยืนยันทุกเงื่อนไขความปลอดภัยก่อนอนุญาต'; return;
    }
    command('autonomous/authorize', {plan_fingerprint: fingerprint,
      ...Object.fromEntries(Object.entries(checks).map(([key, box]) => [key, box.checked]))});
  });
  window.renderObjectCalibration = status => {
    const calibration = status.calibration || {};
    const live = Number.isFinite(calibration.age_sec) && calibration.age_sec <= 2;
    latest = status.automatic_calibration || calibration.automatic_calibration || {};
    const reference = calibration.object_calibration || {};
    if (reference.preview_jpeg && reference.rgb_stamp !== displayed?.rgb_stamp && !pending) {
      const packet = {rgb_stamp: reference.rgb_stamp, image_size: reference.image_size};
      image.onload = () => { displayed = packet; image.hidden = false; };
      image.src = `data:image/jpeg;base64,${reference.preview_jpeg}`;
    }
    const idle = ['IDLE', 'FAULT', 'SAFE_STOP', 'DRY_RUN_COMPLETE', 'READY',
      'CANDIDATE_VERIFIED', 'AWAITING_LIVE_VALIDATION', 'COMMISSIONING_COMPLETE'].includes(latest.state || 'IDLE');
    const busy = pending || !live || !idle || status.operation?.active;
    get('objectCalibrationStart').disabled = busy;
    get('objectCalibrationDryRun').disabled = busy;
    const nextFingerprint = latest.plan_fingerprint || '';
    if (nextFingerprint !== fingerprint) {
      Object.values(checks).forEach(box => { box.checked = false; }); fingerprint = nextFingerprint;
    }
    get('objectMotionAuthorization').hidden = !live || latest.state !== 'WAITING_FOR_OPERATOR_AUTHORIZATION';
    const plan = latest.plan || [];
    get('objectMotionAuthorize').disabled = !live || plan.length === 0 || !fingerprint;
    get('objectMotionPlan').style.whiteSpace = 'pre-line';
    get('objectMotionPlan').textContent = `แผน ${latest.total_poses || 10} ท่า · ${latest.motion_type || 'MOVL'}\n`
      + plan.map(p => `ท่า ${p.pose_index}: XYZ ${(p.xyz_mm || []).map(x => Number(x).toFixed(1)).join(', ')} มม. · หมุน ${Number(p.j4_deg).toFixed(1)}°`).join('\n');
    if (!live) { feedback.textContent = 'รอสถานะ Calibration ปัจจุบัน'; return; }
    if (latest.reason && ['FAULT', 'AWAITING_LIVE_VALIDATION', 'SAFE_STOP'].includes(latest.state)) {
      feedback.textContent = explain(latest.reason);
    } else if (reference.tracked) {
      feedback.textContent = 'ติดตามวัตถุอ้างอิงแล้ว กรุณาอย่าขยับวัตถุ';
    } else if (reference.selection) {
      feedback.textContent = 'เลือกตำแหน่งแล้ว ระบบจะตรวจความเหมาะสมก่อนเริ่ม';
    }
  };
})();
