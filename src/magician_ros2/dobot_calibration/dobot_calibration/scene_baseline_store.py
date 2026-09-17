import os, yaml
from pathlib import Path
VALID={'PROVISIONAL','VALID','REJECTED','STALE','INCOMPATIBLE'}
def normalize(v):
 v=dict(v or {}); v.setdefault('quality_status','PROVISIONAL'); v.setdefault('eligible_for_preflight',False); v.setdefault('authoritative_generation',0); return v
def save(path, value):
 value=normalize(value)
 if value['quality_status']!='VALID' or not value['eligible_for_preflight']: raise ValueError('authoritative baseline must be VALID')
 old=load(path, evidence=True) if Path(path).exists() else {}
 value['authoritative_generation']=int(old.get('authoritative_generation',0))+1
 tmp=Path(str(path)+'.tmp')
 with open(tmp,'w',encoding='utf-8') as f: yaml.safe_dump(value,f); f.flush(); os.fsync(f.fileno())
 os.replace(tmp,path)
 return value
def load(path, *, evidence=False):
 try: value=normalize(yaml.safe_load(Path(path).read_text(encoding='utf-8')))
 except Exception: raise ValueError('SCENE_BASELINE_INCOMPATIBLE')
 if value['quality_status'] not in VALID: raise ValueError('SCENE_BASELINE_INCOMPATIBLE')
 if not evidence and (value['quality_status']!='VALID' or not value['eligible_for_preflight']): raise ValueError('SCENE_BASELINE_PROVISIONAL')
 return value
