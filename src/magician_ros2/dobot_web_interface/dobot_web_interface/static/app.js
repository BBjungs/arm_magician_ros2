let calibrationBackendReady = false;

const $ = (id) => document.getElementById(id);

const eventLog = $("eventLog");
const commandStatus = $("commandStatus");
const statusEls = {
  camera: $("cameraStatus"),
  action: $("actionStatus"),
  homing: $("homingStatus"),
  tool: $("toolStatus"),
};
const CONTROL_PAGE_STORAGE_KEY = "dobot.controlPage";
const visionPageTitles = {
  vision: "ตรวจจับและเลือกเป้าหมาย",
  run: "ตรวจสอบและสั่งหยิบ",
  calibration: "ตั้งค่าและคาลิเบรต",
};
const optionLabels = {
  all: "ทั้งหมด",
};
let lastSelectedTarget = null;
let allowRealMotion = false;
let currentEyeInHandStatus = null;
let currentFixedCalibrationStatus = null;
let cameraReconnectTimer = null;
let autoCalibrationInProgress = false;

function reconnectCameraStream(delayMs = 1000) {
  if (cameraReconnectTimer !== null) {
    window.clearTimeout(cameraReconnectTimer);
  }
  cameraReconnectTimer = window.setTimeout(() => {
    cameraReconnectTimer = null;
    $("cameraStream").src = `/stream?reconnect=${Date.now()}`;
  }, delayMs);
}

$("cameraStream").addEventListener("error", () => {
  setPill(statusEls.camera, "กำลังต่อกล้องใหม่", false, true);
  reconnectCameraStream(1500);
});

function datasetList(element, key) {
  return (element.dataset[key] || "").split(/\s+/).filter(Boolean);
}

function setControlPage(page) {
  const tabs = [...document.querySelectorAll("[data-page-target]")];
  const validPages = tabs.map((tab) => tab.dataset.pageTarget);
  const nextPage = validPages.includes(page) ? page : "robot";

  tabs.forEach((tab) => {
    const active = tab.dataset.pageTarget === nextPage;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });

  document.querySelectorAll("[data-control-page]").forEach((section) => {
    const active = datasetList(section, "controlPage").includes(nextPage);
    section.hidden = !active;
    section.classList.toggle("is-active", active);
  });

  document.querySelectorAll("[data-control-cluster]").forEach((cluster) => {
    cluster.hidden = !datasetList(cluster, "controlCluster").includes(nextPage);
  });

  if (visionPageTitles[nextPage]) {
    $("visionPickTitle").textContent = visionPageTitles[nextPage];
  }

  try {
    localStorage.setItem(CONTROL_PAGE_STORAGE_KEY, nextPage);
  } catch (_) {
    // Ignore storage failures; the tabs still work for the current session.
  }
}

function initControlPages() {
  const tabs = [...document.querySelectorAll("[data-page-target]")];
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => setControlPage(tab.dataset.pageTarget));
  });

  let savedPage = "robot";
  try {
    savedPage = localStorage.getItem(CONTROL_PAGE_STORAGE_KEY) || savedPage;
  } catch (_) {
    savedPage = "robot";
  }
  setControlPage(savedPage);
}

function displayOptionLabel(value) {
  return optionLabels[value] || value;
}

function log(message) {
  const time = new Date().toLocaleTimeString();
  eventLog.textContent = `[${time}] ${message}\n` + eventLog.textContent;
  commandStatus.textContent = message;
}

function setBusy(button, busy) {
  button.classList.toggle("busy", busy);
  button.disabled = busy;
}

function setPill(element, label, ready, warn = false) {
  element.textContent = label;
  element.classList.toggle("ready", ready);
  element.classList.toggle("warn", warn && !ready);
}

async function api(path, body = null) {
  const options = { method: "POST" };
  if (body !== null) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }

  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail || response.statusText;
    throw new Error(detail);
  }
  return data;
}

async function getJson(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail || response.statusText;
    throw new Error(detail);
  }
  return data;
}

async function refreshStatus() {
  try {
    const status = await fetch("/api/status").then((response) => response.json());
    const hasFrame = status.camera.has_frame;
    const frameAge = status.camera.frame_age_sec;
    const toolReady = status.ros.gripper_ready || status.ros.suction_ready;

    setPill(
      statusEls.camera,
      hasFrame ? `กล้อง ${frameAge}s` : "รอกล้อง",
      hasFrame,
      true
    );
    setPill(statusEls.action, "PTP", status.ros.ptp_action_ready, true);
    setPill(statusEls.homing, "กลับจุดเริ่ม", status.ros.homing_ready, true);
    setPill(statusEls.tool, "เครื่องมือ", toolReady, true);

    $("cameraTopic").textContent =
      status.camera.frame_source ||
      status.camera.device ||
      `${status.camera.raw_topic} or ${status.camera.compressed_topic}`;

    $("motionState").textContent = status.motion.active_goal
      ? "กำลังเคลื่อนที่ตามคำสั่ง"
      : "ไม่มีคำสั่งเคลื่อนที่";

    if (status.motion.last_feedback) {
      $("poseFeedback").textContent = `ตำแหน่ง ${status.motion.last_feedback.join(", ")}`;
    } else if (status.motion.last_result) {
      $("poseFeedback").textContent =
        `ผลลัพธ์ ${status.motion.last_result.achieved_pose.join(", ")}`;
    } else {
      $("poseFeedback").textContent = "ยังไม่มีข้อมูลตอบกลับ";
    }

    syncAxisControls(status.motion.joints_deg);
  } catch (error) {
    setPill(statusEls.camera, "ออฟไลน์", false, true);
    log(`อ่านสถานะไม่สำเร็จ: ${error.message}`);
  }
}

function setVisionError(message) {
  const errorEl = $("visionError");
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setCalibrationError(message) {
  const errorEl = $("calibrationError");
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setEyeInHandError(message) {
  const errorEl = $("eyeInHandError");
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setAutoCalibrationError(message) {
  const errorEl = $("autoCalibrationError");
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setSafetyError(message) {
  const errorEl = $("safetyError");
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setRealPickError(message) {
  const errorEl = $("realPickError");
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function setSelectOptions(select, values, fallback = []) {
  const current = select.value;
  const unique = [...new Set([...fallback, ...values].filter(Boolean))];
  select.textContent = "";
  unique.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = displayOptionLabel(value);
    select.appendChild(option);
  });
  if (unique.includes(current)) {
    select.value = current;
  }
}

function formatPoint(value) {
  return Array.isArray(value)
    ? value.map((item) => Number(item).toFixed(3)).join(", ")
    : "-";
}

function updateVisionStatus(status) {
  const pill = $("visionStatusPill");
  const ok = Boolean(status.ok);
  pill.textContent = ok ? "พร้อมตรวจจับ" : "ตรวจจับผิดพลาด";
  pill.classList.toggle("waiting", !ok);
  const engine = status.vision_engine || "rgbd_shape";
  $("visionEngine").value = engine;
  $("visionRgbStatus").textContent = status.rgb_ok ? "ONLINE" : "OFFLINE";
  $("visionDepthStreamStatus").textContent = status.depth_stream_ok ? "ONLINE" : "OFFLINE";
  $("visionDepthStatus").textContent = status.depth_data_valid
    ? `VALID (${(Number(status.depth_valid_ratio || 0) * 100).toFixed(1)}%)`
    : "INVALID";
  $("visionSyncStatus").textContent = status.sync_ok ? "PASS" : "FAIL";
  $("visionInfoStatus").textContent = status.camera_info_ok ? "PASS" : "FAIL";
  $("visionTableDepth").textContent = status.table_depth_mm === null || status.table_depth_mm === undefined
    ? "N/A" : `${Number(status.table_depth_mm).toFixed(1)} mm`;

  $("visionLoopFps").textContent = Number(status.loop_fps || 0).toFixed(2);
  $("visionInferenceFps").textContent = status.model_loaded && status.inference_fps !== null
    && status.inference_fps !== undefined
    ? Number(status.inference_fps).toFixed(2)
    : "N/A";
  $("visionInferenceMs").textContent = status.model_loaded && status.inference_time_ms !== null
    && status.inference_time_ms !== undefined
    ? `${Number(status.inference_time_ms).toFixed(2)} ms`
    : "N/A";
  $("visionInferenceCount").textContent = Number(status.inference_count || 0);
  $("visionDetectionCount").textContent = Number(status.detection_count || 0);
  const modelClasses = status.model_classes || {};
  $("visionModelClasses").textContent = Object.values(modelClasses).length
    ? Object.values(modelClasses).join(", ")
    : "N/A";
  $("visionCuda").textContent = status.model_loaded
    ? (status.cuda_available ? "ONLINE" : "OFFLINE")
    : "N/A";
  $("visionModel").textContent = engine === "rgbd_shape"
    ? "YOLO optional / unavailable"
    : (status.model_path || status.configured_model_path || status.fallback_model_path || "ไม่มีโมเดล");
  $("visionConfidence").textContent =
    status.confidence_threshold === null || status.confidence_threshold === undefined
      ? "n/a"
      : Number(status.confidence_threshold).toFixed(2);

  $("visionDryRun").checked = true;

  const details = [];
  if (!status.detector_running) {
    details.push("ตัวตรวจจับยังไม่ส่งสถานะ");
  }
  if (status.error) {
    details.push(status.error);
  }
  if (!status.source_ok && status.detector_running) {
    details.push(`แหล่งภาพใช้งานไม่ได้ (${status.source_type || "ไม่ทราบ"})`);
  }
  setVisionError(details.join(" "));
}

function renderVisionDetections(detections) {
  const body = $("visionDetectionsBody");
  body.textContent = "";

  if (!Array.isArray(detections) || detections.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "ไม่พบวัตถุ";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  detections.forEach((detection) => {
    const row = document.createElement("tr");
    [
      detection.id,
      detection.class_name,
      Number(detection.classification_score ?? detection.confidence ?? 0).toFixed(2),
      Array.isArray(detection.center_pixel)
        ? detection.center_pixel.join(", ")
        : "",
      Array.isArray(detection.bbox) ? detection.bbox.join(", ") : "",
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "");
      row.appendChild(cell);
    });
    body.appendChild(row);
  });
}

function renderSelectedTarget(result) {
  const panel = $("selectedTargetPanel");
  const status = $("selectedTargetStatus");
  panel.hidden = false;
  lastSelectedTarget = result || null;

  const selected = Boolean(result?.selected);
  status.textContent = selected ? "เลือกแล้ว" : "ถูกปฏิเสธ";
  status.classList.toggle("waiting", !selected);

  if (!selected) {
    $("selectedTargetId").textContent = "-";
    $("selectedTargetClass").textContent = "-";
    $("selectedTargetConfidence").textContent = "-";
    $("selectedTargetPixel").textContent = "-";
    $("selectedTargetRobot").textContent = "-";
    $("selectedTargetPick").textContent = "-";
    $("selectedTargetPlace").textContent = result?.reason || "-";
    return;
  }

  $("selectedTargetId").textContent = String(result.id ?? "-");
  $("selectedTargetClass").textContent = result.class_name || "-";
  $("selectedTargetConfidence").textContent =
    result.confidence === undefined ? "-" : Number(result.confidence).toFixed(3);
  $("selectedTargetPixel").textContent = formatPoint(result.center_pixel);
  $("selectedTargetRobot").textContent = formatPoint(result.robot_xy);
  $("selectedTargetPick").textContent = formatPoint(result.pick_pose);
  $("selectedTargetPlace").textContent =
    `${result.place_id || "-"}: ${formatPoint(result.place_pose)}`;
}

function renderSafety(report) {
  const allowed = Boolean(report?.allowed);
  const pill = $("safetyStatusPill");
  pill.textContent = allowed ? "ปลอดภัย" : "ถูกบล็อก";
  pill.classList.toggle("waiting", !allowed);
  allowRealMotion = Boolean(report?.config?.allow_real_motion);
  $("visionPickSelected").disabled = !allowRealMotion;
  $("realPickStatusPill").textContent = allowRealMotion ? "พร้อมสั่ง" : "ล็อกอยู่";
  $("realPickStatusPill").classList.toggle("waiting", !allowRealMotion);

  const checks = Array.isArray(report?.checks) ? report.checks : [];
  checks.forEach((check) => {
    const row = document.querySelector(
      `.safety-check[data-check="${check.name}"]`
    );
    if (!row) {
      return;
    }
    row.classList.toggle("ready", Boolean(check.ok));
    row.classList.toggle("warn", !check.ok && check.severity === "warning");
    row.classList.toggle("waiting", !check.ok && check.severity !== "warning");
    const strong = row.querySelector("strong");
    strong.textContent = check.ok ? "ผ่าน" : check.reason;
    strong.title = check.reason;
  });

  const messages = [];
  if (Array.isArray(report?.errors) && report.errors.length) {
    messages.push(report.errors.join("; "));
  }
  if (Array.isArray(report?.warnings) && report.warnings.length) {
    messages.push(report.warnings.join("; "));
  }
  setSafetyError(messages.join(" "));
}

function renderMotionPreview(result) {
  const body = $("motionPreviewBody");
  const pill = $("previewStatusPill");
  const sequence = Array.isArray(result?.motion_sequence)
    ? result.motion_sequence
    : [];

  body.textContent = "";
  pill.textContent = result?.accepted ? "ตัวอย่างพร้อม" : "ไม่มีตัวอย่าง";
  pill.classList.toggle("waiting", !result?.accepted);

  if (sequence.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = result?.reason || "ไม่มีตัวอย่าง";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  sequence.forEach((step) => {
    const row = document.createElement("tr");
    const safety = step.safety_result || {};
    [
      step.step,
      step.command,
      formatPoint(step.pose),
      step.simulated ? "ใช่" : "ไม่ใช่",
      safety.allowed ? "ผ่าน" : safety.reason || "ถูกบล็อก",
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value ?? "");
      row.appendChild(cell);
    });
    body.appendChild(row);
  });
}

function renderCalibration(calibration) {
  currentFixedCalibrationStatus = calibration || null;
  const pill = $("calibrationStatusPill");
  const complete = Boolean(calibration.is_complete);
  pill.textContent = complete ? "พร้อม" : `${calibration.point_count || 0}/4 จุด`;
  pill.classList.toggle("waiting", !complete);

  const body = $("calibrationPointsBody");
  body.textContent = "";
  const imagePoints = calibration.image_points || [];
  const robotPoints = calibration.robot_points || [];
  if (imagePoints.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "ยังไม่มีจุดคาลิเบรต";
    row.appendChild(cell);
    body.appendChild(row);
  } else {
    imagePoints.forEach((imagePoint, index) => {
      const row = document.createElement("tr");
      [
        index + 1,
        imagePoint.join(", "),
        Array.isArray(robotPoints[index]) ? robotPoints[index].join(", ") : "",
      ].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = String(value);
        row.appendChild(cell);
      });
      const actionCell = document.createElement("td");
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "inline-action";
      deleteButton.dataset.calibrationDeleteIndex = String(index);
      deleteButton.textContent = "ลบ";
      deleteButton.title = `ลบจุดคาลิเบรต #${index + 1}`;
      actionCell.appendChild(deleteButton);
      row.appendChild(actionCell);
      body.appendChild(row);
    });
  }

  const validation = calibration.validation || {};
  const meanError = validation.mean_error_mm;
  const maxError = validation.max_error_mm;
  const maxErrorText =
    maxError === null || maxError === undefined
      ? "n/a"
      : Number(maxError).toFixed(3);
  $("calMeanError").textContent =
    meanError === null || meanError === undefined
      ? "ค่า error เฉลี่ย n/a"
      : `เฉลี่ย ${Number(meanError).toFixed(3)} มม. / สูงสุด ${maxErrorText} มม.`;

  const messages = [];
  if (Array.isArray(calibration.validation_errors) && calibration.validation_errors.length) {
    messages.push(calibration.validation_errors.join("; "));
  }
  if (validation.warning) {
    messages.push(validation.warning);
  }
  setCalibrationError(messages.join(" "));
  renderAutoCalibration(calibration, "fixed_camera");
}

function formatCalibrationVector(value, digits = 2) {
  if (!Array.isArray(value)) {
    return "-";
  }
  return `[${value.map((item) => Number(item).toFixed(digits)).join(", ")}]`;
}

function calibrationFailureThai(warning) {
  const raw = String(warning || "").trim();
  if (!raw) {
    return "";
  }
  const messages = [];
  if (/missing|required marker|detected .* need/i.test(raw)) {
    messages.push("ตรวจพบ Marker ไม่ครบ จึงไม่นำเฟรมนี้ไปคำนวณ");
  }
  if (/corner geometry|board geometry|aspect|layout/i.test(raw)) {
    messages.push("Marker geometry หรือการจัดมุม ID ไม่ตรงกับบอร์ดที่กำหนด");
  }
  if (/cross-check/i.test(raw)) {
    messages.push("ผล cross-check ผิดปกติ: ตรวจ board model และทิศของ transform");
  }
  if (/mount translation|mount rotation|mount estimate/i.test(raw)) {
    messages.push("ค่า T_tcp_camera ไม่สอดคล้องกันหรืออาจกลับทิศ");
  }
  if (/stable marker samples|outlier|varies|moved/i.test(raw)) {
    messages.push("ข้อมูลหลายเฟรมไม่นิ่งหรือมี outlier มากเกินเกณฑ์");
  }
  if (/board pose.*not anchored|single robot pose/i.test(raw)) {
    messages.push("ยังไม่ได้ยืนยันตำแหน่งฟิกซ์เจอร์ของบอร์ดใน Dobot base");
  }
  if (/blur/i.test(raw)) {
    messages.push("ภาพเบลอเกินไป");
  }
  if (/look.*down|optical axis/i.test(raw)) {
    messages.push("แกน optical ของกล้องไม่หันลงตามค่าที่กำหนด");
  }
  const unique = [...new Set(messages)];
  return unique.length ? `${unique.join(" • ")} — ${raw}` : raw;
}

function renderCalibrationMarkerValidation(rows) {
  const body = $("autoCalibrationMarkerValidationBody");
  body.textContent = "";
  if (!Array.isArray(rows) || rows.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "ยังไม่มีผล cross-check";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }
  rows.forEach((marker) => {
    const delta = Array.isArray(marker.delta_xyz_mm)
      ? marker.delta_xyz_mm
      : [null, null, null];
    const values = [
      marker.id,
      formatCalibrationVector(marker.expected_xyz_mm, 2),
      marker.predicted_xyz_mm
        ? formatCalibrationVector(marker.predicted_xyz_mm, 2)
        : marker.warning || "-",
      delta[0] === null ? "-" : Number(delta[0]).toFixed(2),
      delta[1] === null ? "-" : Number(delta[1]).toFixed(2),
      delta[2] === null ? "-" : Number(delta[2]).toFixed(2),
      marker.error_norm_mm === null || marker.error_norm_mm === undefined
        ? "-"
        : Number(marker.error_norm_mm).toFixed(3),
    ];
    const row = document.createElement("tr");
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.appendChild(cell);
    });
    body.appendChild(row);
  });
}

function renderAutoCalibration(status, mode) {
  if ($("visionMode").value !== mode) {
    return;
  }
  const modeLabel = mode === "eye_in_hand" ? "กล้องติดปลายแขน" : "กล้องประจำที่";
  $("calibrationBoardLink").href =
    calibrationBackendReady
      ? `/api/vision/calibration/print?mode=${encodeURIComponent(mode)}`
      : "/static/calibration_board_a4.html";
  const attempt = status?.calibration_attempt || status?.last_auto_attempt || null;
  const validation = status?.validation || {};
  const quality = attempt?.quality || validation.quality || {};
  const board = attempt?.board
    || validation.board
    || status?.auto_calibration?.board
    || status?.aruco?.board
    || {};
  $("calibrationFixturePose").textContent = board.pose_base
    ? JSON.stringify(board.pose_base, null, 2)
    : "ยังไม่มี pose_base — ตรวจค่าปัจจุบันในหน้าพิมพ์";
  const complete = Boolean(status?.is_complete && status?.calibration_valid);
  const pill = $("autoCalibrationStatusPill");
  pill.textContent = complete ? "Calibration ผ่าน — ยังต้องตรวจจุดจริง" : attempt ? "ตรวจไม่ผ่าน" : "รอตรวจ";
  pill.classList.toggle("waiting", !complete);
  $("autoCalibrationMode").textContent = modeLabel;

  const frameCount = quality.frame_count ?? status?.captured_frame_count;
  const validFrames = quality.valid_frame_count ?? quality.valid_sample_count;
  $("autoCalibrationFrames").textContent = frameCount === undefined || frameCount === null
    ? "รอเก็บภาพ"
    : `${validFrames ?? "-"}/${frameCount} เฟรม`;

  const requiredIds = attempt?.required_ids || validation.required_ids || board.required_ids || [];
  const missingIds = attempt?.missing_ids || validation.missing_ids || quality.missing_ids || [];
  const detectedIds = attempt?.detected_ids || validation.detected_ids || [];
  $("autoCalibrationDictionary").textContent =
    attempt?.dictionary || validation.dictionary || board.dictionary || "-";
  $("autoCalibrationRequiredIds").textContent = requiredIds.length
    ? `[${requiredIds.join(", ")}]`
    : "-";
  $("autoCalibrationMarkers").textContent = missingIds.length
    ? `พบ [${detectedIds.join(", ") || "-"}] / ขาด [${missingIds.join(", ")}]`
    : detectedIds.length
      ? `ครบ [${detectedIds.join(", ")}]`
      : complete
        ? "ผ่าน"
        : "รอตรวจ";

  const geometry = board.geometry || board;
  $("autoCalibrationBoardGeometry").textContent =
    geometry.width_mm === undefined || geometry.height_mm === undefined
      ? "-"
      : `${Number(geometry.width_mm).toFixed(1)} × ${Number(geometry.height_mm).toFixed(1)} มม.`;
  const boardPose = board.pose_base || {};
  $("autoCalibrationBoardFrame").textContent = boardPose.anchored
    ? `board-local → base, XYZ ${formatCalibrationVector(boardPose.translation_mm, 1)}, RPY ${formatCalibrationVector(boardPose.rotation_rpy_deg, 1)}`
    : "board-local (ยังไม่ anchor กับ Dobot base)";
  const cameraMount = attempt?.measured_camera_mount
    || validation.measured_camera_mount
    || status?.camera_mount;
  $("autoCalibrationCameraMount").textContent = cameraMount
    ? `${formatCalibrationVector(cameraMount.translation_mm, 2)} / ${formatCalibrationVector(cameraMount.rotation_rpy_deg, 2)}`
    : mode === "eye_in_hand" ? "รอ solve" : "ไม่ใช้ในโหมดกล้องประจำที่";

  if (mode === "eye_in_hand") {
    const translation = quality.mount_translation_stability_mm;
    const rotation = quality.mount_rotation_stability_deg;
    $("autoCalibrationStability").textContent = translation === undefined || translation === null
      ? "รอตรวจ"
      : `${Number(translation).toFixed(2)} มม. / ${Number(rotation).toFixed(2)}°`;
    const reprojection = quality.reprojection_mean_px;
    $("autoCalibrationErrorValue").textContent = reprojection === undefined || reprojection === null
      ? "รอตรวจ"
      : `PnP ${Number(reprojection).toFixed(2)} / ${Number(quality.reprojection_max_px).toFixed(2)} px`;
  } else {
    const jitter = quality.corner_jitter_px;
    $("autoCalibrationStability").textContent = jitter === undefined || jitter === null
      ? "รอตรวจ"
      : `${Number(jitter).toFixed(2)} px`;
    const meanError = quality.verification_mean_error_mm ?? status?.validation?.mean_error_mm;
    const maxError = quality.verification_max_error_mm ?? status?.validation?.max_error_mm;
    $("autoCalibrationErrorValue").textContent = meanError === undefined || meanError === null
      ? "รอตรวจ"
      : `${Number(meanError).toFixed(2)} / ${Number(maxError).toFixed(2)} มม.`;
  }
  const inlierRatio = quality.inlier_ratio;
  $("autoCalibrationInliers").textContent =
    inlierRatio === undefined || inlierRatio === null
      ? "n/a"
      : `${(Number(inlierRatio) * 100).toFixed(1)}%`;
  const crossMean = quality.cross_validation_mean_error_mm
    ?? quality.marker_cross_check_mean_mm
    ?? attempt?.marker_cross_check_mean_mm;
  const crossMax = quality.cross_validation_max_error_mm
    ?? quality.marker_cross_check_max_mm
    ?? attempt?.marker_cross_check_max_mm;
  $("autoCalibrationCrossCheck").textContent =
    crossMean === undefined || crossMean === null
      ? "รอตรวจ"
      : `${Number(crossMean).toFixed(2)} / ${Number(crossMax).toFixed(2)} มม.`;
  renderCalibrationMarkerValidation(
    attempt?.marker_validation || validation.marker_validation || []
  );

  const attemptValid = Boolean(attempt?.calibration_valid);
  $("autoCalibrationSaved").textContent = attemptValid
    ? "บันทึกอัตโนมัติแล้ว"
    : attempt?.previous_calibration_preserved
      ? "ไม่ผ่าน — เก็บค่าเดิม"
      : complete
        ? "ใช้ค่าที่ผ่านล่าสุด"
        : "ยังไม่บันทึก";
  $("autoCalibrationProgress").textContent = attemptValid
    ? "ระบบตรวจด้วยภาพแยกชุดแล้วและบันทึกผลที่ผ่านเรียบร้อย"
    : attempt
      ? "ผลรอบนี้ไม่ผ่าน ระบบจึงไม่บันทึกทับค่าที่ใช้งานอยู่"
      : "ระบบจะไม่ขยับแขนกลระหว่างคาลิเบรต";
  setAutoCalibrationError(calibrationFailureThai(attempt?.warning || validation.warning));
}

function renderAutoCalibrationForSelectedMode() {
  if ($("visionMode").value === "eye_in_hand") {
    renderAutoCalibration(currentEyeInHandStatus || {}, "eye_in_hand");
  } else {
    renderAutoCalibration(currentFixedCalibrationStatus || {}, "fixed_camera");
  }
}

function formatMarkerPositions(status) {
  const validation = status?.validation || {};
  const calibration = status?.calibration || {};
  const markers = validation.markers_detected || calibration.markers_detected || [];
  if (!Array.isArray(markers) || markers.length === 0) {
    return "-";
  }
  return markers.slice(0, 6).map((marker) => {
    const center = Array.isArray(marker.center_pixel)
      ? `u=${Number(marker.center_pixel[0]).toFixed(0)},v=${Number(marker.center_pixel[1]).toFixed(0)}`
      : "u,v=?";
    const robot = Array.isArray(marker.robot_xy_estimate)
      ? ` -> X=${Number(marker.robot_xy_estimate[0]).toFixed(1)},Y=${Number(marker.robot_xy_estimate[1]).toFixed(1)}`
      : "";
    const configured = marker.configured ? "" : " ใหม่";
    return `id ${marker.id}${configured}: ${center}${robot}`;
  }).join(" | ");
}

function formatExpectedMarkers(status) {
  const aruco = status?.aruco || {};
  const board = aruco.board || status?.auto_calibration?.board || {};
  const markers = board.markers || {};
  const requiredIds = Array.isArray(board.required_ids)
    ? board.required_ids.map((id) => String(id))
    : Object.keys(markers).sort((left, right) => Number(left) - Number(right));
  if (!requiredIds.length) {
    return "-";
  }
  return requiredIds.map((id) => {
    const marker = markers[id];
    if (!marker || !Array.isArray(marker.center_mm)) {
      return `id ${id}: ยังไม่ได้ตั้งตำแหน่ง`;
    }
    const [x, y, z] = marker.center_mm;
    return `id ${id}: board [${Number(x).toFixed(1)}, ${Number(y).toFixed(1)}, ${Number(z).toFixed(1)}]`;
  }).join(" | ");
}

function renderEyeInHandStatus(status) {
  currentEyeInHandStatus = status || null;
  const complete = Boolean(status?.is_complete);
  const valid = Boolean(status?.calibration_valid);
  const positionAvailable = Boolean(
    status?.position_available || status?.can_estimate_position
  );
  const usingEstimate = positionAvailable && !valid;
  const pill = $("eyeInHandStatusPill");
  pill.textContent = complete && valid
    ? "พร้อม"
    : usingEstimate
      ? "ประมาณตำแหน่ง"
      : "ยังไม่พร้อม";
  pill.classList.toggle("waiting", !(complete && valid));

  const tcpPose = status?.current_tcp_pose || status?.tcp_pose;
  $("eyeTcpPose").textContent = formatPoint(tcpPose);

  const mount = status?.camera_mount || {};
  const translation = formatPoint(mount.translation_mm);
  const rotation = formatPoint(mount.rotation_rpy_deg);
  $("eyeCameraMount").textContent = `เลื่อน ${translation} / หมุน RPY ${rotation}`;

  const validation = status?.validation || {};
  const detected = Array.isArray(validation.detected_ids)
    ? validation.detected_ids.join(", ")
    : "";
  const missing = Array.isArray(validation.missing_ids)
    ? validation.missing_ids.join(", ")
    : "";
  const source = status?.position_source;
  const estimateText = usingEstimate || source === "configured_mount_estimate"
    ? " / ใช้ประมาณอัตโนมัติ"
    : "";
  $("eyeArucoStatus").textContent =
    `พบ [${detected || "-"}], ขาด [${missing || "-"}]${estimateText}`;
  $("eyeExpectedMarkers").textContent = formatExpectedMarkers(status);
  $("eyeMarkerPositions").textContent = formatMarkerPositions(status);

  const lookDown = status?.look_down || validation.look_down || {};
  $("eyeLookDownStatus").textContent = lookDown.tilt_deg === undefined ||
    lookDown.tilt_deg === null
    ? lookDown.warning || "-"
    : `${Number(lookDown.tilt_deg).toFixed(1)} องศา`;

  const messages = [];
  if (!status?.tcp_pose_available) {
    messages.push("ไม่มีตำแหน่ง TCP");
  }
  if (validation.warning) {
    messages.push(validation.warning);
  }
  if (usingEstimate && status?.auto_position?.warning) {
    messages.push(status.auto_position.warning);
  }
  if (lookDown.warning) {
    messages.push(lookDown.warning);
  }
  setEyeInHandError(messages.join(" "));
  renderAutoCalibration(status, "eye_in_hand");
}

function refreshVisionAnnotated() {
  const image = $("visionAnnotated");
  if (image) {
    image.src = `/api/vision/annotated?t=${Date.now()}`;
  }
}

function refreshEyeArucoAnnotated() {
  const image = $("eyeArucoAnnotated");
  if (image && !autoCalibrationInProgress) {
    image.src = `/api/vision/eye_in_hand/annotated?t=${Date.now()}`;
  }
}

async function refreshVisionStatus() {
  try {
    const status = await getJson("/api/vision/status");
    updateVisionStatus(status);
  } catch (error) {
    $("visionStatusPill").textContent = "ตรวจจับผิดพลาด";
    $("visionStatusPill").classList.add("waiting");
    setVisionError(`อ่านสถานะตรวจจับไม่สำเร็จ: ${error.message}`);
  }
}

async function refreshVisionDetections() {
  try {
    const result = await getJson("/api/vision/detections");
    renderVisionDetections(result.detections);
    if (result.error) {
      setVisionError(result.error);
    }
  } catch (error) {
    renderVisionDetections([]);
    setVisionError(`อ่านผลตรวจจับไม่สำเร็จ: ${error.message}`);
  }
}

async function refreshVisionOptions() {
  try {
    const [classes, places] = await Promise.all([
      getJson("/api/vision/classes"),
      getJson("/api/vision/places"),
    ]);
    setSelectOptions($("visionObjectClass"), classes.classes || [], ["all"]);
    setSelectOptions($("visionPlacePosition"), places.place_ids || []);
  } catch (error) {
    setVisionError(`อ่านตัวเลือกการตรวจจับไม่สำเร็จ: ${error.message}`);
  }
}

async function refreshCalibration() {
  try {
    const calibration = await getJson("/api/vision/calibration");
    renderCalibration(calibration);
  } catch (error) {
    setCalibrationError(`อ่านข้อมูลคาลิเบรตไม่สำเร็จ: ${error.message}`);
  }
}

async function refreshEyeInHandStatus() {
  try {
    const status = await getJson("/api/vision/eye_in_hand/status");
    renderEyeInHandStatus(status);
    refreshEyeArucoAnnotated();
  } catch (error) {
    renderEyeInHandStatus({ calibration_valid: false, is_complete: false });
    setEyeInHandError(`อ่านสถานะกล้องติดปลายแขนไม่สำเร็จ: ${error.message}`);
  }
}

async function refreshSafety() {
  try {
    const report = await api("/api/vision/validate_pick", {
      selected_target: lastSelectedTarget,
      dry_run: true,
      vision_mode: $("visionMode").value,
    });
    renderSafety(report);
  } catch (error) {
    setSafetyError(`ตรวจสอบความปลอดภัยไม่สำเร็จ: ${error.message}`);
  }
}

async function refreshVision() {
  await refreshVisionOptions();
  await refreshVisionStatus();
  await refreshVisionDetections();
  await refreshCalibration();
  await refreshEyeInHandStatus();
  await refreshSafety();
  refreshVisionAnnotated();
}

function targetPose() {
  return [
    Number($("poseX").value),
    Number($("poseY").value),
    Number($("poseZ").value),
    Number($("poseR").value),
  ];
}

const axisControls = {
  x: {
    label: "J1",
    index: 0,
    slider: "axisXSlider",
    value: "axisXValue",
    minus: "axisXMinus",
    plus: "axisXPlus",
  },
  y: {
    label: "J2",
    index: 1,
    slider: "axisYSlider",
    value: "axisYValue",
    minus: "axisYMinus",
    plus: "axisYPlus",
  },
  z: {
    label: "J3",
    index: 2,
    slider: "axisZSlider",
    value: "axisZValue",
    minus: "axisZMinus",
    plus: "axisZPlus",
  },
  r: {
    label: "J4",
    index: 3,
    slider: "axisRSlider",
    value: "axisRValue",
    minus: "axisRMinus",
    plus: "axisRPlus",
  },
};

const axisLiveStatus = $("axisLiveStatus");
let axisLiveTimer = null;
let axisMoveInFlight = false;
let axisMoveQueued = false;
let lastAxisPoseKey = "";
let axisInitialized = false;
let axisTargetPose = [0, 0, 0, 0];

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function writeAxis(axis, value) {
  const control = axisControls[axis];
  const slider = $(control.slider);
  const next = clamp(Number(value), Number(slider.min), Number(slider.max));

  slider.value = String(next);
  $(control.value).textContent = String(next);
  axisTargetPose[control.index] = next;
}

function syncAxisControls(jointsDeg) {
  if (!Array.isArray(jointsDeg) || jointsDeg.length < 4 || axisInitialized) {
    return;
  }

  Object.keys(axisControls).forEach((axis) => {
    const control = axisControls[axis];
    writeAxis(axis, jointsDeg[control.index]);
  });
  axisInitialized = true;
  lastAxisPoseKey = axisTargetPose.join(",");
  setAxisLiveStatus("พร้อม", false);
}

function setAxisLiveStatus(message, waiting = false) {
  axisLiveStatus.textContent = message;
  axisLiveStatus.classList.toggle("waiting", waiting);
  commandStatus.textContent = message;
}

function axisMovePayload() {
  return {
    motion_type: 4,
    target_pose: axisTargetPose,
    velocity_ratio: Number($("velocity").value),
    acceleration_ratio: Number($("acceleration").value),
  };
}

function scheduleAxisMove(delayMs = 300) {
  if (!axisInitialized) {
    setAxisLiveStatus("รอข้อมูล", true);
    log("กำลังรอสถานะข้อต่อปัจจุบัน...");
    return;
  }

  clearTimeout(axisLiveTimer);
  setAxisLiveStatus("รอส่ง", true);
  axisLiveTimer = setTimeout(sendAxisMove, delayMs);
}

async function sendAxisMove() {
  if (axisMoveInFlight) {
    axisMoveQueued = true;
    return;
  }

  axisMoveInFlight = true;
  const payload = axisMovePayload();
  const poseKey = payload.target_pose.join(",");

  try {
    if (poseKey === lastAxisPoseKey) {
      setAxisLiveStatus("พร้อม", false);
      return;
    }

    const status = await fetch("/api/status").then((response) => response.json());
    if (status.motion.active_goal) {
      axisMoveQueued = true;
      setAxisLiveStatus("กำลังเคลื่อนที่", true);
      return;
    }

    setAxisLiveStatus("กำลังส่ง", true);
    const result = await api("/api/move", payload);
    lastAxisPoseKey = poseKey;
    log(`ส่งแกนแบบ MOVJ ANGLE: J1=${payload.target_pose[0]}, J2=${payload.target_pose[1]}, J3=${payload.target_pose[2]}, J4=${payload.target_pose[3]}`);
    if (result.message) {
      commandStatus.textContent = result.message;
    }
  } catch (error) {
    axisMoveQueued = true;
    setAxisLiveStatus("ลองใหม่", true);
    commandStatus.textContent = `สั่งแกน: ${error.message}`;
  } finally {
    axisMoveInFlight = false;
    if (axisMoveQueued) {
      axisMoveQueued = false;
      clearTimeout(axisLiveTimer);
      axisLiveTimer = setTimeout(sendAxisMove, 550);
    }
  }
}

Object.entries(axisControls).forEach(([axis, control]) => {
  $(control.slider).addEventListener("input", () => {
    writeAxis(axis, $(control.slider).value);
    scheduleAxisMove();
  });

  $(control.minus).addEventListener("click", () => {
    writeAxis(axis, Number($(control.slider).value) - Number($("axisStep").value));
    scheduleAxisMove(120);
  });

  $(control.plus).addEventListener("click", () => {
    writeAxis(axis, Number($(control.slider).value) + Number($("axisStep").value));
    scheduleAxisMove(120);
  });
});

$("moveButton").addEventListener("click", async () => {
  const button = $("moveButton");
  try {
    setBusy(button, true);
    log("กำลังส่งคำสั่งเคลื่อนที่...");
    const result = await api("/api/move", {
      motion_type: Number($("motionType").value),
      target_pose: targetPose(),
      velocity_ratio: Number($("velocity").value),
      acceleration_ratio: Number($("acceleration").value),
    });
    log(result.message);
  } catch (error) {
    log(`สั่งเคลื่อนที่ไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
});

$("cancelButton").addEventListener("click", async () => {
  const button = $("cancelButton");
  try {
    setBusy(button, true);
    log("กำลังขอยกเลิกคำสั่ง...");
    const result = await api("/api/cancel");
    log(result.message || `ส่งคำขอยกเลิกแล้ว: ${result.goals_canceling}`);
  } catch (error) {
    log(`ยกเลิกไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
});

$("homeButton").addEventListener("click", async () => {
  const button = $("homeButton");
  try {
    setBusy(button, true);
    log("กำลังสั่งกลับจุดเริ่ม...");
    const result = await api("/api/homing");
    log(`กลับจุดเริ่ม: ${result.message}`);
  } catch (error) {
    log(`กลับจุดเริ่มไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
});

$("restartConnectionButton").addEventListener("click", async () => {
  const button = $("restartConnectionButton");
  try {
    setBusy(button, true);
    log("กำลังรีสตาร์ทการเชื่อมต่อ Dobot...");
    const result = await api("/api/restart_connection");
    log(result.message || "ส่งคำสั่งรีสตาร์ท Dobot แล้ว รอเชื่อมต่อใหม่อีกไม่กี่วินาที");
    reconnectCameraStream(2500);
  } catch (error) {
    log(`รีสตาร์ทไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
});

async function setGripper(state) {
  const button = state === "open" ? $("gripperOpen") : $("gripperClose");
  const label = state === "open" ? "เปิด" : "ปิด";
  try {
    setBusy(button, true);
    log(`กำลังสั่ง${label}กริปเปอร์...`);
    const result = await api("/api/gripper", {
      state,
      keep_compressor_running: $("keepCompressor").checked,
    });
    log(`กริปเปอร์${label}: ${result.message}`);
  } catch (error) {
    log(`สั่งกริปเปอร์ไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function setSuction(enable) {
  const button = enable ? $("suctionOn") : $("suctionOff");
  const label = enable ? "เปิด" : "ปิด";
  try {
    setBusy(button, true);
    log(`กำลังสั่ง${label}หัวดูด...`);
    const result = await api("/api/suction", { enable_suction: enable });
    log(`หัวดูด${label}: ${result.message}`);
  } catch (error) {
    log(`สั่งหัวดูดไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

function visionSelectionPayload() {
  const manualId = $("visionManualId").value;
  return {
    vision_mode: $("visionMode").value,
    object_class: $("visionObjectClass").value,
    place_id: $("visionPlacePosition").value,
    selection_mode: $("visionSelectionMode").value,
    manual_id: manualId === "" ? null : Number(manualId),
    dry_run: true,
  };
}

function visionRealPickPayload() {
  return {
    ...visionSelectionPayload(),
    dry_run: false,
    confirm_real_motion: $("visionConfirmRealMotion").checked,
    tool_type: $("visionToolType").value,
    velocity_ratio: Number($("visionVelocityRatio").value),
    acceleration_ratio: Number($("visionAccelerationRatio").value),
  };
}

async function visionDetectOnce() {
  const button = $("visionDetectOnce");
  $("visionDryRun").checked = true;

  try {
    setBusy(button, true);
    log("กำลังตรวจจับหนึ่งครั้งในโหมดทดลอง...");
    const result = await api("/api/vision/detect_once", {
      dry_run: true,
      object_class: $("visionObjectClass").value,
      place_id: $("visionPlacePosition").value,
      place_position: $("visionPlacePosition").value,
    });
    updateVisionStatus(result.status);
    renderVisionDetections(result.detections.detections);
    refreshVisionAnnotated();
    log(result.message);
  } catch (error) {
    setVisionError(`ตรวจจับครั้งเดียวไม่สำเร็จ: ${error.message}`);
    log(`ตรวจจับครั้งเดียวไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function selectVisionTarget() {
  const button = $("visionSelectTarget");
  $("visionDryRun").checked = true;
  const payload = visionSelectionPayload();

  try {
    setBusy(button, true);
    const result = await api("/api/vision/select_target", payload);
    renderSelectedTarget(result);
    await refreshSafety();
    if (result.selected) {
      setVisionError("");
      log(
        `เลือก ${result.class_name} id=${result.id} สำหรับ ${result.place_id}`
      );
    } else {
      setVisionError(result.reason || "เลือกเป้าหมายไม่ผ่าน");
      log(`เลือกเป้าหมายไม่ผ่าน: ${result.reason || "ไม่พบเป้าหมาย"}`);
    }
  } catch (error) {
    setVisionError(`เลือกเป้าหมายไม่สำเร็จ: ${error.message}`);
    log(`เลือกเป้าหมายไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function validateVisionPick() {
  const button = $("visionValidatePick");
  try {
    setBusy(button, true);
    const report = await api("/api/vision/validate_pick", {
      selected_target: lastSelectedTarget,
      dry_run: true,
      vision_mode: $("visionMode").value,
    });
    renderSafety(report);
    log(report.allowed ? "ตรวจสอบความปลอดภัยผ่าน" : `ความปลอดภัยบล็อกไว้: ${report.reason}`);
  } catch (error) {
    setSafetyError(`ตรวจสอบก่อนหยิบไม่สำเร็จ: ${error.message}`);
    log(`ตรวจสอบความปลอดภัยไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function previewVisionPick() {
  const button = $("visionPreviewPick");
  $("visionDryRun").checked = true;

  try {
    setBusy(button, true);
    const result = await api("/api/vision/preview_pick", visionSelectionPayload());
    if (result.selected_target) {
      renderSelectedTarget(result.selected_target);
    }
    if (result.safety) {
      renderSafety(result.safety);
    } else {
      await refreshSafety();
    }
    renderMotionPreview(result);
    log(
      result.accepted
        ? "สร้างตัวอย่างการเคลื่อนที่แบบทดลองแล้ว"
        : `ตัวอย่างถูกบล็อก: ${result.reason || "ไม่ผ่าน"}`
    );
  } catch (error) {
    renderMotionPreview({ accepted: false, reason: error.message });
    log(`สร้างตัวอย่างไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function pickSelectedVisionTarget() {
  const button = $("visionPickSelected");
  if (!allowRealMotion) {
    setRealPickError("allow_real_motion=false; ระบบล็อกการหยิบจริงไว้");
    return;
  }

  try {
    setBusy(button, true);
    setRealPickError("");
    const result = await api("/api/vision/pick_selected", visionRealPickPayload());
    if (result.selected_target) {
      renderSelectedTarget(result.selected_target);
    }
    if (result.safety) {
      renderSafety(result.safety);
    }
    if (result.motion_sequence) {
      renderMotionPreview({ accepted: Boolean(result.accepted), motion_sequence: result.motion_sequence });
    }
    if (!result.accepted) {
      setRealPickError(result.reason || "คำสั่งหยิบจริงถูกปฏิเสธ");
      log(`คำสั่งหยิบจริงถูกปฏิเสธ: ${result.reason || "ไม่ผ่าน"}`);
      return;
    }
    log(result.message || "สั่งหยิบจริงแล้ว");
  } catch (error) {
    setRealPickError(`หยิบเป้าหมายที่เลือกไม่สำเร็จ: ${error.message}`);
    log(`หยิบเป้าหมายที่เลือกไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function cancelVisionPick() {
  const button = $("visionCancelPick");
  try {
    setBusy(button, true);
    const result = await api("/api/vision/cancel", {});
    log(result.message || `ส่งคำขอยกเลิกแล้ว goals_canceling=${result.goals_canceling}`);
  } catch (error) {
    setRealPickError(`ยกเลิกไม่สำเร็จ: ${error.message}`);
    log(`ยกเลิกไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function addCalibrationPoint() {
  const button = $("calAddPoint");
  try {
    setBusy(button, true);
    const calibration = await api("/api/vision/calibration/add_point", {
      image_point: [Number($("calImageU").value), Number($("calImageV").value)],
      robot_point: [Number($("calRobotX").value), Number($("calRobotY").value)],
    });
    renderCalibration(calibration);
    log("เพิ่มจุดคาลิเบรตแล้ว");
  } catch (error) {
    setCalibrationError(`เพิ่มจุดไม่สำเร็จ: ${error.message}`);
    log(`เพิ่มจุดคาลิเบรตไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function computeCalibration() {
  const button = $("calCompute");
  try {
    setBusy(button, true);
    const calibration = await api("/api/vision/calibration/compute", {});
    renderCalibration(calibration);
    const meanError = calibration.validation?.mean_error_mm;
    log(`คำนวณ Homography แล้ว ค่า error เฉลี่ย ${meanError ?? "n/a"} มม.`);
  } catch (error) {
    setCalibrationError(`คำนวณไม่สำเร็จ: ${error.message}`);
    log(`คำนวณคาลิเบรตไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function deleteCalibrationPoint(index) {
  try {
    const calibration = await api("/api/vision/calibration/remove_point", {
      index,
    });
    renderCalibration(calibration);
    log(`ลบจุดคาลิเบรต #${index + 1} แล้ว`);
  } catch (error) {
    setCalibrationError(`ลบจุดไม่สำเร็จ: ${error.message}`);
    log(`ลบจุดคาลิเบรตไม่สำเร็จ: ${error.message}`);
  }
}

async function testCalibrationPoint() {
  const button = $("calTestPoint");
  try {
    setBusy(button, true);
    const result = await api("/api/vision/calibration/test_point", {
      u: Number($("calTestU").value),
      v: Number($("calTestV").value),
    });
    $("calTestResult").textContent =
      `หุ่นยนต์ X=${Number(result.robot_xy[0]).toFixed(3)}, ` +
      `Y=${Number(result.robot_xy[1]).toFixed(3)}`;
    const warning = result.validation?.warning || "";
    setCalibrationError(warning);
    log("แปลงพิกเซลทดสอบเป็นพิกัดหุ่นยนต์แล้ว");
  } catch (error) {
    setCalibrationError(`ทดสอบพิกเซลไม่สำเร็จ: ${error.message}`);
    log(`ทดสอบคาลิเบรตไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

async function runAutoCalibration(mode = $("visionMode").value, button = $("autoCalibrate")) {
  if (!calibrationBackendReady) {
    setAutoCalibrationError("Backend Calibration รุ่นใหม่ยังไม่พร้อม ต้องโหลด Web backend ใหม่ก่อน (หน้าพิมพ์ยังเปิดได้)");
    return;
  }
  if (mode === "eye_in_hand" && !$("calibrationFixtureMeasured").checked) {
    setAutoCalibrationError("ต้องวัดขนาดพิมพ์และตำแหน่งแผ่นจริงให้ตรง pose_base แล้วติ๊กยืนยันก่อนครับ");
    return;
  }
  autoCalibrationInProgress = true;
  try {
    setBusy(button, true);
    setAutoCalibrationError("");
    $("autoCalibrationProgress").textContent =
      "กำลังเก็บภาพใหม่หลายเฟรม กรุณาอย่าขยับกล้อง แผ่น ArUco หรือแขนกล…";
    const result = await api("/api/vision/calibration/auto", {
      dry_run: true,
      vision_mode: mode,
      fixture_measured: $("calibrationFixtureMeasured").checked,
    });
    if (mode === "eye_in_hand") {
      renderEyeInHandStatus(result);
    } else {
      renderCalibration(result);
    }
    const attempt = result.calibration_attempt || result.last_auto_attempt || {};
    log(attempt.calibration_valid
      ? "ระบบตรวจและคาลิเบรตอัตโนมัติผ่าน พร้อมบันทึกค่าแล้ว"
      : attempt.previous_calibration_preserved
        ? "ผลคาลิเบรตรอบใหม่ไม่ผ่าน ระบบเก็บค่าที่ผ่านล่าสุดไว้"
        : "ผลคาลิเบรตอัตโนมัติไม่ผ่าน กรุณาดูคำแนะนำบนหน้าจอ");
  } catch (error) {
    setAutoCalibrationError(`คาลิเบรตอัตโนมัติไม่สำเร็จ: ${error.message}`);
    $("autoCalibrationProgress").textContent =
      "ระบบไม่ได้บันทึกค่าใหม่ กรุณาแก้ตามข้อความแล้วลองอีกครั้ง";
    log(`คาลิเบรตอัตโนมัติไม่สำเร็จ: ${error.message}`);
  } finally {
    autoCalibrationInProgress = false;
    $("calibrationFixtureMeasured").checked = false;
    setBusy(button, false);
    if (mode === "eye_in_hand") {
      refreshEyeArucoAnnotated();
    }
  }
}

async function calibrateEyeInHand() {
  return runAutoCalibration("eye_in_hand", $("eyeCalibrate"));
}

async function testEyeInHandPixel() {
  const button = $("eyeTestPixel");
  try {
    setBusy(button, true);
    const result = await api("/api/vision/eye_in_hand/test_pixel", {
      dry_run: true,
      u: Number($("eyeTestU").value),
      v: Number($("eyeTestV").value),
    });
    $("eyeTestResult").textContent =
      `หุ่นยนต์ X=${Number(result.robot_xy[0]).toFixed(3)}, ` +
      `Y=${Number(result.robot_xy[1]).toFixed(3)}`;
    setEyeInHandError(
      result.warning || result.validation?.warning || result.look_down?.warning || ""
    );
    log("แปลงพิกเซลทดสอบของกล้องติดปลายแขนแล้ว");
  } catch (error) {
    $("eyeTestResult").textContent = "พิกัดหุ่นยนต์ X/Y ถูกปฏิเสธ";
    setEyeInHandError(`ทดสอบพิกเซลไม่สำเร็จ: ${error.message}`);
    log(`ทดสอบพิกเซลกล้องติดปลายแขนไม่สำเร็จ: ${error.message}`);
  } finally {
    setBusy(button, false);
  }
}

$("gripperOpen").addEventListener("click", () => setGripper("open"));
$("gripperClose").addEventListener("click", () => setGripper("close"));
$("suctionOn").addEventListener("click", () => setSuction(true));
$("suctionOff").addEventListener("click", () => setSuction(false));
$("visionDetectOnce").addEventListener("click", visionDetectOnce);
$("visionSelectTarget").addEventListener("click", selectVisionTarget);
$("visionValidatePick").addEventListener("click", validateVisionPick);
$("visionPreviewPick").addEventListener("click", previewVisionPick);
$("visionPickSelected").addEventListener("click", pickSelectedVisionTarget);
$("visionCancelPick").addEventListener("click", cancelVisionPick);
$("visionRefresh").addEventListener("click", refreshVision);
$("autoCalibrate").addEventListener("click", () => runAutoCalibration());
$("calAddPoint").addEventListener("click", addCalibrationPoint);
$("calCompute").addEventListener("click", computeCalibration);
$("calTestPoint").addEventListener("click", testCalibrationPoint);
$("calRefresh").addEventListener("click", refreshCalibration);
$("calibrationPointsBody").addEventListener("click", (event) => {
  const button = event.target.closest("[data-calibration-delete-index]");
  if (!button) {
    return;
  }
  deleteCalibrationPoint(Number(button.dataset.calibrationDeleteIndex));
});
$("eyeCalibrate").addEventListener("click", calibrateEyeInHand);
$("eyeTestPixel").addEventListener("click", testEyeInHandPixel);
$("visionDryRun").addEventListener("change", () => {
  if (!$("visionDryRun").checked) {
    $("visionDryRun").checked = true;
    setVisionError("ช่วงนี้ระบบตรวจจับและหยิบใช้ได้เฉพาะโหมดทดลองเท่านั้น");
    log("ระบบตรวจจับและหยิบยังอยู่ในโหมดทดลองเท่านั้น");
  }
});
$("visionMode").addEventListener("change", () => {
  $("calibrationFixtureMeasured").checked = false;
  lastSelectedTarget = null;
  renderSelectedTarget({ selected: false, reason: "เปลี่ยนโหมดกล้องแล้ว" });
  renderAutoCalibrationForSelectedMode();
  refreshSafety();
});

async function checkCalibrationBackend() {
  try {
    const response = await fetch("/api/vision/calibration/print?mode=eye_in_hand", {
      cache: "no-store",
    });
    calibrationBackendReady = response.ok;
  } catch (_) {
    calibrationBackendReady = false;
  }
  renderAutoCalibrationForSelectedMode();
}

initControlPages();
checkCalibrationBackend();
refreshStatus();
refreshVision();
setInterval(refreshStatus, 1000);
setInterval(refreshVision, 2500);
