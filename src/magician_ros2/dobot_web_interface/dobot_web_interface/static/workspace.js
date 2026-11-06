(() => {
  const get = id => document.getElementById(id);
  const button = get('workspacePropose');
  if (!button) return;
  const status = get('workspaceStatus');
  const result = get('workspaceResult');
  const canvas = get('workspacePreview');
  const download = get('workspaceDownload');
  let latest = null;
  let pending = false;
  let polling = false;
  let displayedStamp = null;
  const labels = {
    CAMERA_TO_BASE_UNVERIFIED: 'ยังแปลงพื้นที่นี้เป็นพิกัดฐานแขนไม่ได้ ต้องมีผลคาลิเบรตหรือข้อมูลอ้างอิงที่ตรวจสอบแล้ว',
    WHOLE_ROBOT_ENVIRONMENT_NOT_OBSERVED: 'ภาพนี้ไม่ครอบคลุมรอบแขนทั้งหมด ส่วนที่กล้องมองไม่เห็นยังไม่ทราบว่ามีสิ่งกีดขวางหรือไม่',
    OPERATOR_REVIEW_REQUIRED: 'ต้องตรวจพื้นที่จริงก่อนนำข้อเสนอไปกำหนดพื้นที่คาลิเบรต',
    ATTACHMENT_ENVELOPE_DOES_NOT_FIT: 'พื้นที่ที่เห็นยังเล็กกว่าขนาดเผื่อกล้องและหัวดูด จึงยังใช้วางแผนเคลื่อนที่ไม่ได้',
    ATTACHMENT_ENVELOPE_UNVERIFIED: 'ยังไม่มีขนาดชุดกล้องและหัวดูดที่ยืนยันแล้วสำหรับตรวจว่าพอดีกับพื้นที่หรือไม่',
    NO_CONTIGUOUS_VALID_DEPTH: 'ยังไม่พบพื้นที่ต่อเนื่องที่มีข้อมูลความลึกครบทุกเฟรม',
    OBSERVED_REGION_TOO_SMALL_FOR_CLEARANCE: 'พื้นที่ที่วัดได้ยังเล็กเกินไปหลังหักระยะเผื่อ',
    DEPTH_CLEARANCE_TOO_SMALL: 'พื้นผิวอยู่ใกล้กล้องเกินไปสำหรับพื้นที่ว่างที่เผื่อระยะในมุมนี้',
  };
  const mm = values => values.map(value => (Number(value) * 1000).toFixed(1)).join(', ');
  function render(data) {
    latest = data;
    const observing = data.state === 'OBSERVING';
    button.disabled = pending || observing || data.state === 'UNAVAILABLE';
    download.disabled = !data.observed_unix_s;
    result.textContent = '';
    const add = text => {
      const item = document.createElement('p');
      item.textContent = text;
      result.appendChild(item);
    };
    if (observing) {
      status.textContent = `กำลังอ่านภาพขณะแขนหยุดนิ่ง · ${data.frame_count || 0}/3 เฟรม`;
    } else if (data.state === 'PROPOSED' || data.state === 'INSUFFICIENT_OBSERVATION') {
      status.textContent = data.state === 'PROPOSED' ? 'ได้ข้อเสนอแล้ว · ยังไม่ใช่พื้นที่ที่อนุญาตให้เคลื่อนแขน'
        : 'ได้ภาพแล้ว แต่ยังเสนอพื้นที่ที่มีระยะเผื่อเพียงพอไม่ได้';
      add(`ภาพที่ใช้: ${new Date(data.observed_unix_s * 1000).toLocaleString('th-TH')}`);
      add(`ข้อมูลความลึกคงที่ ${(data.stable_valid_ratio * 100).toFixed(1)}% · ไม่ทราบหรือไม่นิ่ง ${(data.unknown_or_unstable_ratio * 100).toFixed(1)}%`);
      if (data.observed_surface) {
        const surface = data.observed_surface;
        add(`พื้นผิวที่วัดพบในพิกัดกล้อง: X/Y/Z ต่ำสุด [${mm(surface.min_m)}] mm ถึงสูงสุด [${mm(surface.max_m)}] mm`);
        add(`ขนาดขอบเขตพื้นผิว ${surface.size_mm.map(value => Number(value).toFixed(1)).join(' × ')} mm · ช่วงความลึก ${mm(surface.depth_range_m)} mm`);
      }
      for (const [key, title] of [['camera_volume', 'พื้นที่เสนอในพิกัดกล้อง'], ['base_volume', 'พื้นที่เสนอในพิกัดฐานแขน']]) {
        const volume = data[key];
        if (!volume) continue;
        add(`${title}: X/Y/Z ต่ำสุด [${mm(volume.min_m)}] mm ถึงสูงสุด [${mm(volume.max_m)}] mm`);
        add(`ขนาด ${volume.size_mm.map(value => Number(value).toFixed(1)).join(' × ')} mm`);
      }
      if (data.dominant_surface) add('ตรวจพบพื้นผิวหลักในภาพ แต่ยังไม่ได้ยืนยันว่าเป็นผิวโต๊ะ');
      (data.blockers || []).forEach(code => add(labels[code] || code));
    } else {
      const states = {IDLE: 'กดปุ่มเพื่ออ่านเซนเซอร์และเสนอพื้นที่', CANCELLED: 'ยกเลิกการอ่านเซนเซอร์แล้ว',
        FAILED: 'ยังเสนอพื้นที่ไม่ได้', UNAVAILABLE: 'การเชื่อมต่อข้อมูลเซนเซอร์ไม่พร้อม'};
      status.textContent = states[data.state] || 'รอข้อมูลเซนเซอร์';
      if (data.reason) add(data.reason);
    }
    canvas.hidden = !data.preview_jpeg;
    if (data.preview_jpeg && data.observed_unix_s !== displayedStamp) {
      displayedStamp = data.observed_unix_s;
      const stamp = displayedStamp;
      const image = new Image();
      image.onload = () => {
        if (latest?.observed_unix_s !== stamp) return;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        if (data.observed_roi_px) {
          const [x0, y0, x1, y1] = data.observed_roi_px;
          const sx = canvas.width / data.image_size[0], sy = canvas.height / data.image_size[1];
          ctx.strokeStyle = '#36f098'; ctx.lineWidth = 3;
          ctx.strokeRect(x0 * sx, y0 * sy, (x1 - x0) * sx, (y1 - y0) * sy);
        }
      };
      image.src = 'data:image/jpeg;base64,' + data.preview_jpeg;
    }
  }
  async function refresh() {
    if (polling) return;
    polling = true;
    try {
      const response = await fetch('/api/workspace/proposal');
      if (!response.ok) throw Error('อ่านสถานะไม่ได้');
      render(await response.json());
    } catch (_) {
      render({state: 'UNAVAILABLE', reason: 'รอการเชื่อมต่อแล้วลองใหม่'});
    } finally { polling = false; }
  }
  button.addEventListener('click', async () => {
    if (pending || button.disabled) return;
    pending = true; button.disabled = true;
    status.textContent = 'กำลังเริ่มอ่านข้อมูลเซนเซอร์';
    try {
      const response = await fetch('/api/workspace/proposal', {method: 'POST'});
      const data = await response.json();
      if (!response.ok || !data.accepted) throw Error(data.detail || data.message || 'เริ่มอ่านข้อมูลไม่ได้');
      displayedStamp = null;
      render({state: 'OBSERVING', frame_count: 0});
    } catch (error) { status.textContent = error.message; }
    finally { pending = false; button.disabled = latest?.state === 'OBSERVING'; }
  });
  download.addEventListener('click', () => {
    if (!latest?.observed_unix_s) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(latest, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a');
    link.href = url; link.download = 'workspace-sensor-proposal.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  refresh();
  window.setInterval(refresh, 2000);
})();
