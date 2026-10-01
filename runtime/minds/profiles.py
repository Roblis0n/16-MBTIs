"""Declarative, bounded profiles and evidence-aware workflow validators."""
import copy
import math
import hashlib
from .contracts import validate_shape, check_json, canonical
from .resources import resource_json
from .errors import fail
from .sensitivity import prioritize_verifications
from .tool_policy import request_object

TOOLS={'read_supplied','public_retrieval','controlled_test'}

def validate_profile(profile):
    validate_shape('profile',profile)
    if len(profile['references'])>8 or len(profile['references'])!=len(set(profile['references'])): fail('E_PROFILE_CYCLE','Duplicate or excessive profile references.')
    if not set(profile['allowed_tool_categories'])<=TOOLS: fail('E_PERMISSION','Profile requests an unsupported tool.')
    return copy.deepcopy(profile)

def _registry():
    return {p['profile_id']:validate_profile(p) for p in resource_json('profiles/registry.json')['profiles']}

def preview_profile(profile):
    p=validate_profile(profile); p['source_trust']='user_untrusted'; p['enabled']=False; p['review_ref']=None
    return {'profile':p,'preview_digest':hashlib.sha256(canonical(p).encode()).hexdigest(),'executes_code':False,'grants_permissions':False}

def resolve_profile(profile_id,profiles=None,voice=None,enabled_custom=None):
    reg=_registry(); custom={} if profiles is None else profiles
    if not isinstance(custom,dict): fail('E_SCHEMA','Custom profiles must be an ID-indexed object.')
    for key,p in custom.items():
        if key in reg: fail('E_PERMISSION','Custom profiles cannot replace built-in profiles.')
        p=validate_profile(p)
        if p['profile_id']!=key: fail('E_SCHEMA','Profile registry key does not match ID.')
        reg[key]=p
    if not isinstance(profile_id,str): fail('E_SCHEMA','Profile ID must be a string.')
    if profile_id not in reg: fail('E_SCHEMA','Unknown profile.')
    active=set(); seen=set()
    def walk(pid,depth):
        if pid in active or depth>8: fail('E_PROFILE_CYCLE','Profile reference cycle or depth limit.')
        if pid in seen: return
        if pid not in reg: fail('E_SCHEMA','Profile reference is missing.')
        p=reg[pid]; active.add(pid)
        for other in p['references']: walk(other,depth+1)
        active.remove(pid); seen.add(pid)
    walk(profile_id,0)
    for pid in seen:
        p=reg[pid]
        if pid in custom:
            digest=preview_profile(p)['preview_digest']
            if not isinstance(enabled_custom,dict) or enabled_custom.get(pid)!=digest:
                fail('E_PERMISSION','Custom profile needs explicit approval of its exact normalized preview.')
        elif not p['enabled']: fail('E_PERMISSION','Profile is disabled.')
    p=copy.deepcopy(reg[profile_id])
    if profile_id in custom: p['source_trust']='user_untrusted'; p['enabled']=True
    if voice is not None:
        if voice not in ('persona','neutral'): fail('E_SCHEMA','Voice must be persona or neutral.')
        p['voice']=voice
    return p

def compose_checks(main,checks=None,permissions=None,profiles=None,voice=None,enabled_custom=None):
    if not isinstance(main,str): fail('E_SCHEMA','Exactly one main profile ID is required.')
    checks=[] if checks is None else checks
    if not isinstance(checks,list) or len(checks)>8 or any(not isinstance(x,str) for x in checks) or len(set(checks))!=len(checks) or main in checks:
        fail('E_PROFILE_CYCLE','Checks must be bounded, unique, and different from the main profile.')
    resolved=[resolve_profile(x,profiles,voice,enabled_custom) for x in [main]+checks]
    if permissions is not None and (not isinstance(permissions,list) or any(not isinstance(x,str) or x not in TOOLS for x in permissions)): fail('E_SCHEMA','Permissions must be supported tool category names.')
    allowed=set(permissions or [])
    # Profiles narrow the current grant. They never add a capability or duplicate budget.
    for p in resolved: p['effective_tools']=sorted(set(p['allowed_tool_categories'])&allowed)
    return {'main':resolved[0],'checks':resolved[1:],'budget_policy':'one_shared_frozen_budget','permission_expansion':False,'voice':voice or resolved[0]['voice']}

def _records(value,fields,label):
    check_json(value)
    if not isinstance(value,list) or len(value)>1000: fail('E_SCHEMA',label+' requires a bounded array.')
    for r in value:
        if not isinstance(r,dict) or not fields<=r.keys(): fail('E_SCHEMA',label+' is missing required fields.')
    return [copy.deepcopy(row) for row in value]

def review_findings(findings,checked_scope):
    if not isinstance(checked_scope,dict) or not all(checked_scope.get(k) for k in ('paths','snapshot_hash')):
        fail('E_SCHEMA','Review requires exact checked paths and a snapshot hash.')
    request_object(checked_scope, {'paths','snapshot_hash'}, {'blind_spots','base','head'})
    if not isinstance(checked_scope['paths'],list) or any(not isinstance(x,str) for x in checked_scope['paths']) or not isinstance(checked_scope['snapshot_hash'],str): fail('E_SCHEMA','Review scope must have string paths and a snapshot hash.')
    fields={'location','trigger','root_cause','reproduction_status','impact','remedy','test','evidence'}
    values=_records(findings,fields,'Finding'); unique={}
    for f in values:
        request_object(f, fields, {'execution_receipt','severity','source_refs'})
        loc=f['location']
        if not isinstance(loc,dict) or set(loc)!={'file','start_line','end_line'} or loc['file'] not in checked_scope['paths'] or type(loc['start_line']) is not int or type(loc['end_line']) is not int or not 1<=loc['start_line']<=loc['end_line']:
            fail('E_SCHEMA','Finding location must lie in the checked scope.')
        if f['reproduction_status'] not in ('unverified','not_run','reproduced','not_reproduced'): fail('E_SCHEMA','Invalid reproduction status.')
        if f['reproduction_status']=='reproduced':
            r=f.get('execution_receipt')
            if not isinstance(r,dict) or not r.get('receipt_ref') or any(type(r.get(k)) is not int for k in ('collected','executed','failed')) or r.get('collected',0)<=0 or r.get('executed',0)<=0 or r.get('failed',0)<=0:
                f['reproduction_status']='not_run'; f['verification']='inconclusive'
        if any(not f[k] for k in ('trigger','root_cause','impact','remedy','test','evidence')): fail('E_SCHEMA','A finding needs concrete evidence and an actionable regression test.')
        key=(loc['file'],canonical(f['root_cause']),canonical(f['trigger']))
        refs=f.get('source_refs',f['evidence'])
        if not isinstance(refs,list) or any(not isinstance(x,str) for x in refs): fail('E_SCHEMA','Finding sources must be a string array.')
        if key in unique:
            merged=sorted(set(unique[key].get('source_refs',[])+refs))
            if f['reproduction_status']=='reproduced': unique[key]=f
            unique[key]['source_refs']=merged
        else: f['source_refs']=sorted(set(refs)); unique[key]=f
    ordered=sorted(unique.values(),key=lambda f:f['reproduction_status']!='reproduced')
    return {'findings':ordered,'checked_scope':checked_scope,'confirmed_count':sum(f['reproduction_status']=='reproduced' for f in ordered),
            'summary':'In the stated scope, no issue was confirmed.' if not any(f['reproduction_status']=='reproduced' for f in ordered) else 'Evidence-backed findings in the stated scope.',
            'blind_spots':checked_scope.get('blind_spots',['Unexecuted paths and host behavior remain unverified.']),'source_modified':False}

def premortem(paths,plan):
    if not isinstance(plan,dict) or not all(plan.get(k) for k in ('plan','horizon','success','failure','hard_constraints')): fail('E_SCHEMA','Premortem requires a fixed plan, horizon, success/failure definition, and constraints.')
    request_object(plan, {'plan','horizon','success','failure','hard_constraints'}, {'budget'})
    fields={'assumption','event','mechanism','early_signal','consequence','prevention','response','stop_condition'}
    records=_records(paths,fields,'Failure path'); result=[]; seen=set()
    for p in records:
        if any(not p[k] for k in fields): fail('E_SCHEMA','Failure path lacks an actionable mechanism or signal.')
        for key in ('prevention','response'):
            action=p[key]
            request_object(action, {'owner_role','resources','earliest_time','verification'})
            if not isinstance(action,dict) or not all(action.get(k) for k in ('owner_role','resources','earliest_time','verification')):
                fail('E_SCHEMA','Preventive and response actions need responsibility, resources, timing, and verification.')
        request_object(p, fields, {'probability','probability_source','new_costs_and_risks','source_refs','prevention_cost','cost_unit','constraint_fit','within_budget_alternative'})
        if p.get('probability') is not None and (type(p['probability']) not in (int,float) or not math.isfinite(p['probability']) or not 0<=p['probability']<=1): fail('E_SCHEMA','Probability must be in [0,1].')
        if p.get('probability') is not None and not p.get('probability_source'): fail('E_SCHEMA','Measured probabilities require an explicit source.')
        p.setdefault('probability',None); p['status']='hypothesis'; p.setdefault('new_costs_and_risks','not_assessed')
        if 'prevention_cost' in p:
            if type(p['prevention_cost']) not in (int,float) or not math.isfinite(p['prevention_cost']) or p['prevention_cost']<0: fail('E_SCHEMA','Prevention cost must be finite and nonnegative.')
            if not isinstance(plan.get('budget'),dict) or p.get('cost_unit')!=plan['budget'].get('unit') or type(plan['budget'].get('limit')) not in (int,float): fail('E_SCHEMA','Cost comparison requires a same-unit user budget.')
            p['constraint_fit']='infeasible' if p['prevention_cost']>plan['budget']['limit'] else 'within_stated_budget'
            if p['constraint_fit']=='infeasible' and not p.get('within_budget_alternative'): p['within_budget_alternative']='needs_user_revised_scope'
        refs=p.get('source_refs',[])
        if not isinstance(refs,list) or any(not isinstance(x,str) for x in refs): fail('E_SCHEMA','Failure path sources must be string references.')
        p['source_refs']=sorted(set(refs))
        key=canonical([p['event'],p['mechanism']])
        if key not in seen: seen.add(key); result.append(p)
        else:
            original=next(x for x in result if canonical([x['event'],x['mechanism']])==key)
            original['source_refs']=sorted(set(original['source_refs']+p['source_refs']))
    return {'plan':plan,'failure_paths':result,'guaranteed_success':False}

def research_feasibility(requirements,question,minimum_deliverable,identification):
    if not isinstance(question,str) or not question.strip(): fail('E_SCHEMA','A research question is required.')
    fields={'variable','grain','source','acquisition','permission','cost','source_access','alternative'}
    rows=_records(requirements,fields,'Data requirement'); blockers=[]
    for i,r in enumerate(rows):
        request_object(r,fields,{'sample_origin','sample_count'})
        if r.get('sample_origin') not in (None,'observed','synthetic'): fail('E_SCHEMA','Sample origin is invalid.')
        if 'sample_count' in r and (type(r['sample_count']) is not int or r['sample_count']<0): fail('E_SCHEMA','Sample count must be nonnegative integer.')
        if r.get('sample_origin')=='synthetic': r['real_sample_count']=0
        if r['permission'] not in ('granted','denied','unknown') or r['source_access'] not in ('available','unavailable','unknown'):
            fail('E_SCHEMA','Access and permission must be reported separately.')
        if r['permission']!='granted' or r['source_access']!='available': blockers.append(i)
    if not isinstance(identification,dict) or identification.get('claim_type') not in ('descriptive','associational','causal'): fail('E_SCHEMA','Identification assessment is required.')
    request_object(identification, {'claim_type'}, {'identification_evidence','risks'})
    if identification['claim_type']=='causal' and not identification.get('identification_evidence'): fail('E_SCHEMA','Causal claims require stated identification evidence.')
    if not isinstance(minimum_deliverable,dict) or not all(minimum_deliverable.get(k) for k in ('scope','requirements_preserved','fallback','first_verification')):
        fail('E_SCHEMA','Minimum deliverable requires scope, preserved requirements, fallback, and first verification.')
    request_object(minimum_deliverable, {'scope','requirements_preserved','fallback','first_verification'}, {'available_duration','required_duration','time_unit'})
    feasibility='not_assessed'
    if 'available_duration' in minimum_deliverable or 'required_duration' in minimum_deliverable:
        if any(type(minimum_deliverable.get(k)) not in (int,float) or not math.isfinite(minimum_deliverable[k]) or minimum_deliverable[k]<=0 for k in ('available_duration','required_duration')) or not minimum_deliverable.get('time_unit'): fail('E_SCHEMA','Delivery comparison requires positive durations in an explicit shared unit.')
        feasibility='infeasible' if minimum_deliverable['required_duration']>minimum_deliverable['available_duration'] else 'within_stated_duration'
    return {'delivery_feasibility':feasibility,'question':question,'data_requirements':rows,'blocking_data_rows':blockers,'identification':identification,'minimum_deliverable':minimum_deliverable,'status':'needs_information' if blockers or feasibility=='infeasible' else 'ready_for_review','data_collected':False}

def dispatch(data):
    if not isinstance(data,dict): fail('E_SCHEMA','Expected profile request.')
    action=data.get('action','list')
    shapes={'list':(set(),{'action'}),'preview':({'action','profile'},set()),'resolve':({'action','profile_id'},{'profiles','voice','enabled_custom'}),'compose':({'action','main'},{'checks','permissions','profiles','voice','enabled_custom'}),'review':({'action','findings','checked_scope'},set()),'premortem':({'action','paths','plan'},set()),'decision-check':({'action','decision_version','actions'},set()),'research':({'action','requirements','question','minimum_deliverable','identification'},set())}
    if not isinstance(action,str): fail('E_SCHEMA','Action must be a string.')
    if action not in shapes: fail('E_SCHEMA','Unknown profile action.')
    request_object(data,*shapes[action])
    if action=='decision-check' and (not isinstance(data['decision_version'],str) or not data['decision_version']): fail('E_SCHEMA','Decision check requires a decision version.')
    if action=='list': return {'status':'ok','profiles':list(_registry().values())}
    if action=='preview': return {'status':'ok',**preview_profile(data.get('profile'))}
    if action=='resolve': return {'status':'ok','profile':resolve_profile(data.get('profile_id'),data.get('profiles'),data.get('voice'),data.get('enabled_custom'))}
    if action=='compose': return {'status':'ok',**compose_checks(data.get('main'),data.get('checks'),data.get('permissions'),data.get('profiles'),data.get('voice'),data.get('enabled_custom'))}
    if action=='review': return {'status':'ok',**review_findings(data.get('findings'),data.get('checked_scope'))}
    if action=='premortem': return {'status':'ok',**premortem(data.get('paths'),data.get('plan'))}
    if action=='decision-check': return {'status':'ok','decision_version':data.get('decision_version'),'verification_actions':prioritize_verifications(data.get('actions',[])),'expected_information_value':None}
    if action=='research': return research_feasibility(data.get('requirements'),data.get('question'),data.get('minimum_deliverable'),data.get('identification'))
    fail('E_SCHEMA','Unknown profile action.')
