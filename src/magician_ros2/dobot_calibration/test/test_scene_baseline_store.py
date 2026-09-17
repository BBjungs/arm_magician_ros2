import pytest
from dobot_calibration.scene_baseline_store import save,load
def valid(): return {'quality_status':'VALID','eligible_for_preflight':True,'schema_version':1,'signature':{}}
def test_valid_generation(tmp_path):
 p=tmp_path/'b.yaml'; assert save(p,valid())['authoritative_generation']==1; assert load(p)['authoritative_generation']==1; assert save(p,valid())['authoritative_generation']==2
@pytest.mark.parametrize('q',['PROVISIONAL','REJECTED','STALE','INCOMPATIBLE'])
def test_nonvalid_evidence_only(tmp_path,q):
 p=tmp_path/'b.yaml'; p.write_text('quality_status: '+q+'\neligible_for_preflight: false\n'); assert load(p,evidence=True)['quality_status']==q
 with pytest.raises(ValueError):load(p)
def test_legacy_and_corrupt_fail_closed(tmp_path):
 p=tmp_path/'b.yaml'; p.write_text('signature: {}\n'); assert load(p,evidence=True)['quality_status']=='PROVISIONAL'
 with pytest.raises(ValueError):load(p)
 p.write_text('[')
 with pytest.raises(ValueError):load(p,evidence=True)
