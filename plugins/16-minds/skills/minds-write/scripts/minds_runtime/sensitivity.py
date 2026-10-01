"""Finite linear-model sensitivity; no fabricated probabilities or value of information."""
import math
from .errors import fail
from .contracts import check_json
from .tool_policy import request_object

def _num(x):
    if type(x) not in (int,float) or not math.isfinite(x): fail('E_SCHEMA','Sensitivity values must be finite numbers, not booleans.')
    return x

def linear_threshold(a,b,domain,unit):
    if not isinstance(unit,str) or not unit.strip(): fail('E_SCHEMA','An explicit shared unit is required.')
    if not isinstance(domain,list) or len(domain)!=2 or _num(domain[0])>=_num(domain[1]): fail('E_SCHEMA','A finite increasing domain is required.')
    for model in (a,b):
        if not isinstance(model,dict) or set(model)!={'intercept','slope','unit'} or model['unit']!=unit: fail('E_SCHEMA','Both linear utility models must use the same explicit unit.')
        _num(model['intercept']); _num(model['slope'])
    slope=a['slope']-b['slope']; intercept=a['intercept']-b['intercept']
    crossing=None if slope==0 else -intercept/slope
    if crossing is not None and not math.isfinite(crossing): fail('E_SCHEMA','Computed threshold is not finite.')
    return {'formula':'utility(x) = intercept + slope * x; choose the larger utility', 'unit':unit,'domain':domain,
            'threshold':crossing if crossing is not None and domain[0]<=crossing<=domain[1] else None,
            'relationship':'identical' if slope==0 and intercept==0 else 'parallel' if slope==0 else 'crossing' if domain[0]<=crossing<=domain[1] else 'no_crossing_in_domain',
            'probability':None,'expected_information_value':None}

def prioritize_verifications(actions):
    check_json(actions)
    if not isinstance(actions,list): fail('E_SCHEMA','Verification actions must be an array.')
    required={'hypothesis','observation','success_action','failure_action','cost_limit','could_change_choice','impact','observable'}
    for a in actions:
        if not isinstance(a,dict) or set(a)!=required or type(a['could_change_choice']) is not bool or type(a['observable']) is not bool or a['impact'] not in ('high','medium','low'):
            fail('E_SCHEMA','Verification action fields are missing or invalid.')
        if any(not isinstance(a[k],str) or not a[k].strip() for k in ('hypothesis','observation','success_action','failure_action','cost_limit')): fail('E_SCHEMA','Verification actions need concrete observations, branches, and proposed cost bounds.')
    ranks={'high':0,'medium':1,'low':2}
    return sorted(actions,key=lambda a:(not a['could_change_choice'],not a['observable'],ranks[a['impact']]))[:3]

def dispatch(data):
    if not isinstance(data,dict): fail('E_SCHEMA','Expected sensitivity request.')
    if data.get('action')=='revise':
        request_object(data, {'action','previous_version','previous_context','new_context'})
        return {'status':'ok',**revise_decision(data['previous_version'],data['previous_context'],data['new_context'])}
    if data.get('action')=='threshold':
        request_object(data, {'action','a','b','domain','unit'})
        return {'status':'ok',**linear_threshold(data.get('a'),data.get('b'),data.get('domain'),data.get('unit'))}
    request_object(data, {'actions'}, {'action'})
    if data.get('action','prioritize')!='prioritize': fail('E_SCHEMA','Unknown sensitivity action.')
    return {'status':'ok','verification_actions':prioritize_verifications(data.get('actions',[])),'expected_information_value':None}

def revise_decision(previous_version,previous_context,new_context):
    """Derive a new immutable version whenever a decision-relevant input changes."""
    import hashlib
    from .contracts import canonical
    if not isinstance(previous_version,str) or not previous_version: fail('E_SCHEMA','Previous decision version is required.')
    for context in (previous_context,new_context):
        request_object(context, {'goal','evidence','assumptions','thresholds','constraints'})
    changed=canonical(previous_context)!=canonical(new_context)
    version=previous_version+'-'+hashlib.sha256(canonical(new_context).encode()).hexdigest()[:12] if changed else previous_version
    return {'decision_version':version,'previous_decision_version':previous_version,'previous_conclusion_status':'stale' if changed else 'reuse','requires_reassessment':changed,'recommendation':None}
