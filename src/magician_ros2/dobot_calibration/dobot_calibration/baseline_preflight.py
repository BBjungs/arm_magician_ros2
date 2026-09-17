def validate_authoritative_scene_baseline_for_preflight(baseline, *, session_id, mount, camera, intrinsics, live_verified):
 if baseline is None:return 'SCENE_BASELINE_MISSING'
 q=baseline.get('quality_status','PROVISIONAL')
 if q!='VALID': return {'PROVISIONAL':'SCENE_BASELINE_PROVISIONAL','REJECTED':'SCENE_BASELINE_REJECTED','STALE':'SCENE_BASELINE_STALE','INCOMPATIBLE':'SCENE_BASELINE_INCOMPATIBLE'}.get(q,'SCENE_BASELINE_INCOMPATIBLE')
 if not baseline.get('eligible_for_preflight'): return 'SCENE_BASELINE_NOT_ELIGIBLE'
 if baseline.get('schema_version')!=1:return 'SCENE_BASELINE_SCHEMA_MISMATCH'
 for key,value,enum in [('session_id',session_id,'SCENE_BASELINE_SESSION_MISMATCH'),('mount_fingerprint',mount,'SCENE_BASELINE_MOUNT_MISMATCH'),('camera_serial',camera,'SCENE_BASELINE_CAMERA_MISMATCH'),('intrinsics_fingerprint',intrinsics,'SCENE_BASELINE_INTRINSICS_MISMATCH')]:
  if baseline.get(key)!=value:return enum
 return '' if live_verified else 'SCENE_BASELINE_NOT_VERIFIED'
