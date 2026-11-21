const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('pointer selection uses the displayed frame and image pixels', () => {
  const controls = new Map();
  const document = {getElementById(id) {
    if (!controls.has(id)) controls.set(id, {});
    return controls.get(id);
  }};
  const canvas = document.getElementById('camera');
  let width = 320;
  Object.assign(canvas, {
    width: 640, height: 480, setPointerCapture() {},
    getContext: () => ({clearRect() {}}),
    getBoundingClientRect: () => ({left: 12, top: 40, width, height: width * .75}),
  });
  const calls = [];
  const context = vm.createContext({document, calls, setInterval() {}, setTimeout() {},
    AbortSignal, fetch: () => new Promise(() => {})});
  vm.runInContext(readFileSync(path.join(__dirname, '../../src/dobot_auto_center/web/app.js'), 'utf8'), context);
  vm.runInContext(`
    command = (_, body) => calls.push(body);
    status = {detecting: true, depth: true};
    displayed = {frame_id: 17, detections: [{box: [160, 120, 40, 40]}]};
  `, context);
  const point = (x, y) => ({pointerId: 1, clientX: 12 + x * width / 640,
    clientY: 40 + y * width / 640});
  for (width of [320, 960]) {
    canvas.onpointerdown(point(180, 139));
    canvas.onpointerup(point(181, 140));
    assert.deepEqual(JSON.parse(JSON.stringify(calls.pop())), {frame_id: 17, roi: [160, 120, 200, 160]});
    canvas.onpointerdown(point(240, 190));
    canvas.onpointerup(point(155, 110));
    assert.deepEqual(Array.from(calls.pop().roi), [155, 110, 240, 190]);
    canvas.onpointerdown(point(10, 10));
    canvas.onpointerup(point(10, 10));
    assert.equal(calls.length, 0);
  }
});

test('status timeout keeps the video connection and labels the retained frame', async () => {
  const controls = new Map();
  const draws = [];
  const document = {getElementById(id) {
    if (!controls.has(id)) controls.set(id, {});
    return controls.get(id);
  }, createElement() { return {append() {}}; }};
  document.getElementById('camera').getContext = () => ({
    clearRect() {}, drawImage(bitmap) { draws.push(bitmap); },
  });
  for (const id of ['tcp', 'joints']) document.getElementById(id).replaceChildren = () => {};
  const context = vm.createContext({document, AbortController, AbortSignal,
    setInterval() {}, setTimeout() {}, fetch: () => new Promise(() => {})});
  vm.runInContext(readFileSync(path.join(__dirname, '../../src/dobot_auto_center/web/app.js'), 'utf8'), context);
  await vm.runInContext(`
    streamController = new AbortController();
    image = {width: 640, height: 480};
    drag = choiceFrame = displayed = {detections: []};
    fetch = async () => { throw new Error('status timeout'); };
    update();
  `, context);
  assert.equal(vm.runInContext('streamController.signal.aborted', context), false);
  assert.equal(vm.runInContext('displayed || drag || choiceFrame', context), undefined);
  assert.equal(draws.at(-1), vm.runInContext('image', context));
  assert.equal(document.getElementById('state').textContent, 'STATUS UNAVAILABLE');
  assert.match(document.getElementById('empty').textContent, /Last received frame/);
  assert.equal(document.getElementById('empty').hidden, false);
  for (const id of ['detect', 'center', 'lock', 'choices', 'home'])
    assert.equal(document.getElementById(id).disabled, true);
});
