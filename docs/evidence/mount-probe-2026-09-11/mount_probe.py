import json,time,urllib.request,pathlib,sys
root=pathlib.Path('/tmp/mount-probe');root.mkdir(exist_ok=True)
def api(path,payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request('http://127.0.0.1:8080'+path,data=data,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=8) as r:return json.load(r)
def check(s):
 m=s['motion'];r=s['ros']
 assert r['alarm_state_fresh'] and r['no_critical_alarm'] and not r['alarm_codes'], 'Alarm gate'
 assert m['current_tcp_pose_age_sec']<0.5 and m['homing_confirmed'], 'Telemetry/homing gate'
 assert not m['vision_sequence_active'], 'Vision sequence running'
 assert s['camera_health']['ready'], 'Camera gate'
def snap(name):
 with urllib.request.urlopen('http://127.0.0.1:8080/api/snapshot',timeout=8) as r:(root/(name+'.jpg')).write_bytes(r.read())
s=api('/api/status');check(s);assert not s['motion']['active_goal']
name=sys.argv[1];offset=[float(v) for v in sys.argv[2:]]
assert len(offset)==4 and max(abs(v) for v in offset)<=5
p=s['motion']['current_tcp_pose'];target=[v+d for v,d in zip(p,offset)]
assert 149.5<=target[0]<=320 and -180<=target[1]<=180 and -45<=target[2]<=120
(root/(name+'-before.json')).write_text(json.dumps(s,indent=2));snap(name+'-before')
try:
 result=api('/api/move',{'target_pose':target,'motion_type':2,'velocity_ratio':0.05,'acceleration_ratio':0.05})
 print('request',result,flush=True);assert result.get('accepted'), 'Rejected'
 end=time.monotonic()+20
 while time.monotonic()<end:
  time.sleep(.15);s=api('/api/status');check(s)
  if not s['motion']['active_goal'] and s['motion']['last_result'] is not None:break
 else:raise RuntimeError('Motion timed out')
 assert s['motion']['last_result']['status']==4,s['motion']['last_result']
 assert max(abs(a-b) for a,b in zip(s['motion']['current_tcp_pose'],target))<0.8,'Pose disagreement'
 time.sleep(.5);snap(name+'-after');(root/(name+'-after.json')).write_text(json.dumps(s,indent=2))
 print('completed',s['motion']['current_tcp_pose'],s['motion']['last_result'],flush=True)
except BaseException:
 print('cancel',api('/api/cancel',{}),flush=True);raise
