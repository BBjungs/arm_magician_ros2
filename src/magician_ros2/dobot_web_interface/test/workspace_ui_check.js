// Runs in Node or another JavaScript runtime; no browser or robot is required.
async function checkWorkspaceUI(source) {
  const assert = (value, message) => { if (!value) throw Error(message); };
  class Element {
    constructor() { this.disabled = false; this.hidden = false; this.children = []; this.listeners = {}; this._text = ''; }
    set textContent(value) { this._text = value; this.children = []; }
    get textContent() { return this._text; }
    addEventListener(event, callback) { this.listeners[event] = callback; }
    appendChild(value) { this.children.push(value); }
    getContext() { return {drawImage() {}, strokeRect() {}}; }
    click() {}
  }
  const elements = Object.fromEntries(['workspacePropose', 'workspaceStatus', 'workspaceResult',
    'workspacePreview', 'workspaceDownload'].map(id => [id, new Element()]));
  const requests = [], intervals = [];
  let data = {state: 'IDLE'};
  let offline = false;
  const fetch = async (url, options) => {
    requests.push({url, method: options?.method || 'GET'});
    if (offline) throw Error('offline');
    return {ok: true, json: async () => options ? {accepted: true} : data};
  };
  const window = {setInterval: fn => intervals.push(fn)};
  const document = {getElementById: id => elements[id], createElement: () => new Element()};
  const execute = new Function('document', 'window', 'fetch', 'Image', 'URL', 'Blob', 'setTimeout', source);
  execute(document, window, fetch, class {}, {}, class {}, () => {});
  const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  await flush();
  assert(requests.every(r => r.method === 'GET'), 'Page load must not scan or move');
  assert(!elements.workspacePropose.disabled, 'Idle backend should allow a scan');
  await elements.workspacePropose.listeners.click();
  assert(requests.filter(r => r.method === 'POST').length === 1, 'Exactly one explicit scan');
  assert(requests.every(r => r.url === '/api/workspace/proposal'), 'No motion/config endpoints');
  assert(elements.workspacePropose.disabled, 'Repeated clicks must not overlap scans');
  await elements.workspacePropose.listeners.click();
  assert(requests.filter(r => r.method === 'POST').length === 1, 'Duplicate click rejected');
  data = {state: 'PROPOSED', observed_unix_s: 123456, stable_valid_ratio: .75,
    unknown_or_unstable_ratio: .25, camera_volume: {min_m: [-.1, -.1, .2], max_m: [.1, .1, .4],
      size_mm: [200, 200, 200]}, base_volume: null, blockers: ['CAMERA_TO_BASE_UNVERIFIED']};
  await intervals[0]();
  assert(!elements.workspaceDownload.disabled, 'Proposal can be exported');
  assert(elements.workspaceStatus.textContent.includes('ยังไม่ใช่'), 'Proposal is not motion approval');
  assert(elements.workspaceResult.children.some(e => e.textContent.includes('พิกัดกล้อง')), 'Camera coordinates identified');
  assert(elements.workspaceResult.children.some(e => e.textContent.includes('25.0%')), 'Unknown depth shown');
  assert(elements.workspaceResult.children.some(e => e.textContent.includes('ยังแปลง')), 'Missing base transform explained');
  offline = true;
  await intervals[0]();
  assert(elements.workspacePropose.disabled && elements.workspaceDownload.disabled, 'Stale backend cannot appear current');
  assert(elements.workspacePreview.hidden, 'Old preview is hidden when disconnected');
  return {result: 'PASS', checks: 'read-only polling, one explicit scan, no motion/config calls, frame labels, unknown depth, stale data'};
}
if (typeof module !== 'undefined') module.exports = checkWorkspaceUI;
