import pytest
from dobot_calibration.baseline_preflight import validate_authoritative_scene_baseline_for_preflight as v
def b(**x):
 d={'schema_version':1,'quality_status':'VALID','eligible_for_preflight':True,'session_id':'s','mount_fingerprint':'m','camera_serial':'c','intrinsics_fingerprint':'i'};d.update(x);return d
@pytest.mark.parametrize('value,expected',[(None,'SCENE_BASELINE_MISSING'),(b(quality_status='PROVISIONAL'),'SCENE_BASELINE_PROVISIONAL'),(b(eligible_for_preflight=False),'SCENE_BASELINE_NOT_ELIGIBLE'),(b(session_id='x'),'SCENE_BASELINE_SESSION_MISMATCH'),(b(mount_fingerprint='x'),'SCENE_BASELINE_MOUNT_MISMATCH'),(b(camera_serial='x'),'SCENE_BASELINE_CAMERA_MISMATCH'),(b(intrinsics_fingerprint='x'),'SCENE_BASELINE_INTRINSICS_MISMATCH'),(b(schema_version=2),'SCENE_BASELINE_SCHEMA_MISMATCH')])
def test_reject(value,expected):assert v(value,session_id='s',mount='m',camera='c',intrinsics='i',live_verified=True)==expected
def test_pass():assert v(b(),session_id='s',mount='m',camera='c',intrinsics='i',live_verified=True)==''
