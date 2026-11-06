"""Run the real operator script against only IDs present in its real HTML."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_read_only_calibration_dashboard_stop_and_ready_gate():
    if not shutil.which('node'):
        pytest.skip('Node.js required')
    static = Path(__file__).parents[1] / 'dobot_web_interface/static'
    result = subprocess.run(['node', '-e', r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const html = fs.readFileSync(process.argv[1] + '/operator.html', 'utf8');
class Element {
  constructor() { this.listeners = {}; this.children = []; this.value = ''; this.disabled = false;
    this.style = {setProperty() {}}; this.classList = {toggle() {}, add() {}, remove() {}, contains() {return false;}}; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this[name] = value; }
  get options() { return this.children; }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); }
  focus() {}
}
const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], new Element()]));
const get = id => elements.get(id) || null;
const removed = ['automaticCommission','automaticStart','automaticPause','automaticResume',
  'passiveCapture','passiveSolve','autoCalibrationStart','autoCalibrationPause','autoCalibrationResume',
  'autoCalibrationAbort','startupButton','automaticAuthorize'];
removed.forEach(id => assert.strictEqual(get(id), null, id + ' must only exist in Maintenance'));
const requests = [];
let fail = false;
let homeReply = {ok:true, json:async()=>({success:true})};
let resolveHome;
let holdHome = false;
let status = {ready: false, checks: [], operation: {active:false}, control:{state:'IDLE'},
  automatic_calibration:{state:'CAPTURING',current_pose:4,accepted_pose_count:3,total_poses:10}};
const context = vm.createContext({console, Date, URLSearchParams, document: {
  getElementById:get, createElement:()=>new Element(), body:new Element(), querySelectorAll:()=>[]},
  window:{setInterval(){},clearInterval(){},addEventListener(){}}, fetch:async(url, options)=>{
    if (options) requests.push({url,...options});
    if (fail) throw Error('offline');
    if (url === '/api/homing') {
      if (holdHome) await new Promise(resolve=>{resolveHome=resolve;});
      return homeReply;
    }
    return {ok:true,json:async()=> options ? {accepted:true} : status};
  }});
vm.runInContext(fs.readFileSync(process.argv[1] + '/operator.js','utf8'),context);
(async()=>{
  // Opening, polling, changing selection or reloading only reads status/images.
  await new Promise(resolve=>setImmediate(resolve));
  await vm.runInContext('refreshStatus()',context);
  await get('jobSelect').listeners.change();
  assert.strictEqual(requests.length,0);
  // A slow preview must finish before another image is requested.
  await get('annotatedCamera').listeners.load();
  vm.runInContext('refreshCamera()',context);
  assert(vm.runInContext('cameraPending',context));
  const firstFrame=get('annotatedCamera').src;
  vm.runInContext('refreshCamera()',context);
  assert.strictEqual(get('annotatedCamera').src,firstFrame);
  await get('annotatedCamera').listeners.load();
  assert(!vm.runInContext('cameraPending',context));
  vm.runInContext('document.hidden=true; refreshCamera()',context);
  assert(!vm.runInContext('cameraPending',context),'Hidden pages do not request images');
  vm.runInContext('document.hidden=false',context);
  assert.strictEqual(get('calibrationSummary').textContent,'กำลังคาลิเบรตอัตโนมัติ Pose 4/10 (40%)');
  assert.strictEqual(get('calibrationProgressBar').value,40);
  assert.strictEqual(get('calibrationAccepted').textContent,'3/10');
  vm.runInContext('renderAutomaticCalibration(' + JSON.stringify({
    state:'FAULT', reason:'START_POSE_OUTSIDE_WORKSPACE: clearance',
    start_pose_check:{current_xyz_mm:[57.7,0,-15.4],
      allowed_center_min_m:[.17025,-.0255,.1245],
      allowed_center_max_m:[.20425,.0255,.15],table_min_center_z_m:.1206}
  }) + ')', context);
  assert(get('calibrationError').textContent.includes('ข้อมูลติดตั้งเดิม'));
  assert(get('calibrationError').textContent.includes('170.3'));
  assert(get('calibrationError').textContent.includes('ระบบยังไม่ได้สั่งเคลื่อนแขน'));
  assert(get('startButton').disabled);
  assert(get('homeButton').disabled,'Home must not interrupt calibration');
  await get('homeButton').listeners.click();
  await get('startButton').listeners.click();
  assert.strictEqual(requests.length,0);
  assert(!get('stopButton').disabled,'STOP must be enabled during calibration without an operator job');
  await get('cameraFullscreen').listeners.click();
  assert(!get('stopButton').inert && !get('stopButton').disabled);
  await get('stopButton').listeners.click();
  assert.strictEqual(requests[0].url,'/api/operator/stop');
  await new Promise(resolve=>setImmediate(resolve));
  status = {...status, automatic_calibration:{state:'CANDIDATE_VERIFIED',production_ready:false},
    calibration:{state:'AWAITING_LIVE_VALIDATION',ready:false}};
  await vm.runInContext('refreshStatus()',context);
  assert(get('startButton').disabled,'candidate is not READY');
  status = {...status,ready:true,calibration:{state:'READY',ready:true}};
  await vm.runInContext('refreshStatus()',context);
  assert(!get('startButton').disabled);
  assert.strictEqual(get('calibrationSummary').textContent,'Calibration สำเร็จ ระบบพร้อมทำงาน');
  const start = get('startButton').listeners.click();
  await get('startButton').listeners.click();
  await start;
  assert.strictEqual(requests.filter(r=>r.url==='/api/operator/start').length,1);
  await new Promise(resolve=>setImmediate(resolve));
  // Home is available before full pick readiness and never runs from polling.
  status = {...status,ready:false};
  await vm.runInContext('refreshStatus()',context);
  assert(!get('homeButton').disabled);
  assert(!requests.some(r=>r.url==='/api/homing'));
  for (const busy of [
    {operation:{active:true}}, {control:{state:'STARTING'}},
    {control:{state:'STOPPING'}}, {control:{state:'IDLE',owner:'startup'}},
    {automatic_calibration:{state:'PAUSED'}}, {calibration:{state:'SOLVING'}},
  ]) {
    vm.runInContext('renderStatus(' + JSON.stringify({...status,...busy}) + ')',context);
    assert(get('homeButton').disabled,'Home must wait for active work');
    await get('homeButton').listeners.click();
  }
  assert(!requests.some(r=>r.url==='/api/homing'));
  status = {...status,ready:true};
  await vm.runInContext('refreshStatus()',context);
  holdHome=true;
  const home = get('homeButton').listeners.click();
  await get('homeButton').listeners.click();
  await vm.runInContext('refreshStatus()',context);
  assert(get('homeButton').disabled && get('startButton').disabled);
  assert(!get('stopButton').disabled,'STOP remains available while HOME is pending');
  assert.strictEqual(get('homeButton')['aria-busy'],'true');
  await get('startButton').listeners.click();
  assert.strictEqual(requests.filter(r=>r.url==='/api/operator/start').length,1);
  assert.strictEqual(requests.filter(r=>r.url==='/api/homing').length,1);
  assert.strictEqual(requests.find(r=>r.url==='/api/homing').method,'POST');
  resolveHome();
  await home;
  await new Promise(resolve=>setImmediate(resolve));
  assert(get('homeFeedback').textContent.includes('รับคำสั่ง Home แล้ว'));
  assert.strictEqual(get('homeButton')['aria-busy'],'false');
  holdHome=false;
  for (const reply of [
    {ok:false,status:401,json:async()=>{throw Error('plain-text authentication error');}},
    {ok:false,status:503,json:async()=>{throw Error('plain-text unavailable error');}},
    {ok:true,json:async()=>({success:false,message:'Home rejected'})},
  ]) {
    homeReply=reply;
    await get('homeButton').listeners.click();
    await new Promise(resolve=>setImmediate(resolve));
    const feedback=get('homeFeedback').textContent;
    assert(feedback.includes(reply.ok ? 'Home rejected' : 'Home'));
    await vm.runInContext('refreshStatus()',context);
    assert.strictEqual(get('homeFeedback').textContent,feedback,'Polling preserves Home errors');
  }
  fail=true;
  await vm.runInContext('refreshStatus()',context);
  assert(get('startButton').disabled);
  assert(get('homeButton').disabled);
  assert(!get('stopButton').disabled);
  assert(get('calibrationStateLabel').textContent.includes('ขาดการเชื่อมต่อ'));
})().catch(error=>{console.error(error);process.exitCode=1;});
''', str(static)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
