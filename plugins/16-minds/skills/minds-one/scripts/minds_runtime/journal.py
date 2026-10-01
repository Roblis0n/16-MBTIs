"""Immutable opt-in decision journal; no scheduler and no inferred user choices."""
import copy
from datetime import datetime, timezone
from .contracts import check_json, canonical
from .errors import fail
from .storage import create_run_dir, write_no_clobber, read_record, delete_selected_run, _run_path
from .render import public_payload
from .tool_policy import request_object

REQUIRED={'decision_version','goal','evidence','assumptions','triggers','recommendation','user_actual_choice','recorded_at'}

def _time(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None or d.utcoffset() is None: raise ValueError()
        return d.astimezone(timezone.utc).isoformat()
    except (ValueError,TypeError,AttributeError): fail('E_SCHEMA','Journal timestamps require a timezone-aware ISO date.')

def validate_entry(entry):
    check_json(entry)
    if not isinstance(entry,dict) or not REQUIRED<=entry.keys() or entry.keys()-(REQUIRED|{'outcome','outcome_source','outcome_at','retention_choice'}):
        fail('E_SCHEMA','Journal fields are missing or unknown.')
    if not isinstance(entry['decision_version'],str) or not entry['decision_version']: fail('E_SCHEMA','A decision version is required.')
    if not isinstance(entry['goal'],str) or not entry['goal']: fail('E_SCHEMA','Journal goal must be a nonempty string.')
    if any(entry[k] is not None and not isinstance(entry[k],str) for k in ('recommendation','user_actual_choice')): fail('E_SCHEMA','Recommendation and actual choice must be independent strings or null.')
    if not all(isinstance(entry[k],list) for k in ('evidence','assumptions','triggers')): fail('E_SCHEMA','Journal evidence, assumptions, and triggers must be arrays.')
    if entry.get('outcome') is not None and (not entry.get('outcome_source') or not entry.get('outcome_at')):
        fail('E_SCHEMA','An actual outcome requires its source and observation date.')
    result=copy.deepcopy(entry); result['recorded_at']=_time(entry['recorded_at'])
    if entry.get('outcome_at'): result['outcome_at']=_time(entry['outcome_at'])
    public_payload(result)
    return result

def save(entry,root=None,persist=False):
    if type(persist) is not bool: fail('E_SCHEMA','Persistence must be boolean.')
    value=validate_entry(entry)
    if persist is not True: return {'status':'summary_only','entry':value,'persisted':False}
    run_id=create_run_dir(root,True)
    receipt=write_no_clobber(root,_run_path(run_id)+'/journal.json',canonical(value)+'\n',True)
    return {'status':'saved','run_id':run_id,'receipt':receipt,'persisted':True,'background_reminder':False}

def read(root,run_id): return validate_entry(read_record(root,_run_path(run_id)+'/journal.json'))

def review(entry,outcome=None,outcome_source=None,outcome_at=None,available_evidence=None):
    value=validate_entry(entry)
    if outcome is not None:
        if not outcome_source or not outcome_at: fail('E_SCHEMA','Review outcome needs a source and date.')
        observed={'value':outcome,'source':outcome_source,'observed_at':_time(outcome_at)}
    else: observed=None
    if available_evidence is not None and (not isinstance(available_evidence,list) or any(not isinstance(x,str) for x in available_evidence)): fail('E_SCHEMA','Available evidence must be exact string references.')
    missing=[] if available_evidence is None else [e for e in value['evidence'] if e not in available_evidence]
    return {'status':'review','original_entry':value,'observed_outcome':observed,'missing_sources':missing,
            'process_assessment':'not_assessed','outcome_assessment':'not_assessed',
            'caution':'Outcome quality alone does not establish whether the original decision process was reasonable.'}

def delete(root,run_id,confirmed=False,preview_digest=None): return delete_selected_run(root,run_id,confirmed,preview_digest)

def dispatch(data):
    if not isinstance(data,dict): fail('E_SCHEMA','Expected journal request.')
    action=data.get('action','save')
    shapes={'save':({'entry'},{'action','root','persist'}),'read':({'action','root','run_id'},set()),'review':({'action'},{'entry','root','run_id','outcome','outcome_source','outcome_at','available_evidence'}),'delete':({'action','root','run_id'},{'confirmed','preview_digest'})}
    if not isinstance(action,str): fail('E_SCHEMA','Action must be a string.')
    if action not in shapes: fail('E_SCHEMA','Unknown journal action.')
    request_object(data,*shapes[action],booleans={'persist','confirmed'})
    if action=='review' and (('entry' in data)==('root' in data or 'run_id' in data)): fail('E_SCHEMA','Review needs either entry or exact root/run_id.')
    if action=='save': return save(data.get('entry'),data.get('root'),data.get('persist',False))
    if action=='read': return {'status':'ok','entry':read(data.get('root'),data.get('run_id'))}
    if action=='review':
        entry=data.get('entry') if 'entry' in data else read(data.get('root'),data.get('run_id'))
        return review(entry,data.get('outcome'),data.get('outcome_source'),data.get('outcome_at'),data.get('available_evidence'))
    if action=='delete': return delete(data.get('root'),data.get('run_id'),data.get('confirmed',False),data.get('preview_digest'))
    fail('E_SCHEMA','Unknown journal action.')
