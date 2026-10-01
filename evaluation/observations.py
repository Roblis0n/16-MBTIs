"""Append-only response records; metadata never grants execution authority."""
import hashlib
import json
import re
from pathlib import Path
from .protocol import BASELINES, STATUSES, number

def record_response(directory, observation, original_response):
    """Persist supplied observed output without invoking a model or reading gold.

    Use an exclusive observation ID. Caller must distinguish actual generation,
    synthetic fixture and replay; this records claims, not trusted host receipts.
    """
    if not isinstance(original_response,str): raise ValueError('Response must be exact text')
    required={'observation_id','task_id','project_group','split','baseline','status','model_id','model_settings',
              'tool_scope','input_tokens','output_tokens','reasoning_tokens','actions','agent_rounds',
              'latency_seconds','cost','quality','observed_at','provenance','generation_kind'}
    if not required <= observation.keys(): raise ValueError('Missing observation fields')
    oid=observation['observation_id']
    if not isinstance(oid,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}',oid): raise ValueError('Unsafe observation ID')
    if observation['baseline'] not in BASELINES and observation['baseline'] is not None: raise ValueError('Unknown baseline')
    if observation['status'] not in STATUSES or observation['split'] not in {'development','holdout'}: raise ValueError('Invalid status or split')
    if observation['generation_kind'] not in {'actual_model','synthetic_fixture','replay'}: raise ValueError('Invalid generation provenance')
    for key in ('input_tokens','output_tokens','reasoning_tokens','actions','agent_rounds','latency_seconds','cost','quality'):
        number(observation[key],nullable=True)
    for key in ('task_id','project_group','observed_at','provenance'):
        if not isinstance(observation[key],str) or not observation[key]: raise ValueError('Missing provenance')
    root=Path(directory).absolute()
    for p in (root,*root.parents):
        if p.is_symlink(): raise ValueError('Symlink output forbidden')
    root.mkdir(parents=True,exist_ok=True)
    record={**observation,'original_response':original_response,'answer_sha256':hashlib.sha256(original_response.encode()).hexdigest(),
            'authority_notice':'Supplied observation metadata is not an authenticated host receipt'}
    target=root/(oid+'.json')
    with target.open('x',encoding='utf-8') as out: json.dump(record,out,ensure_ascii=False,sort_keys=True,indent=2); out.write('\n')
    return record
