"""Versioned calibration provenance; activation requires an external trust boundary."""
import copy
import hashlib
import json
from .errors import fail

FIELDS = ('model_id','model_settings','host_schema_hash','persona_hash','workflow_hash','tool_scope',
          'task_set_version','scoring_version','judge_version','locale','seed')

def fingerprint_match(reference, current):
    known = lambda x: isinstance(x,str) and x.lower() not in {'','unknown','null'}
    pairs=[(reference.get(k),current.get(k)) for k in FIELDS]
    if any(known(a) and known(b) and a != b for a,b in pairs): return 'mismatch'
    matches=sum(known(a) and known(b) and a==b for a,b in pairs)
    if matches==len(FIELDS): return 'exact'
    return 'partial_match' if matches else 'unknown'

def generate_candidate(calibration_id, fingerprint, development_results, *, generation_command=None):
    if set(fingerprint) != set(FIELDS): fail('E_SCHEMA','Incomplete calibration fingerprint')
    hashes=[]
    for result in development_results:
        if result.get('split') != 'development': fail('E_PERMISSION','Holdout cannot tune candidates')
        h=result.get('answer_sha256')
        if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h): fail('E_SCHEMA','Missing original response hash')
        hashes.append(h)
    result={'schema_version':'1.0.0','calibration_id':calibration_id,'state':'candidate',
            'fingerprint':copy.deepcopy(fingerprint),'observed_date':None,'input_result_hashes':hashes,
            'errata_refs':[],'generation_command':list(generation_command or ['python','-m','minds.calibration']),
            'match_status':'unknown','reviewer_ref':None,'activation_approval_ref':None,
            'limitations':['Uncalibrated candidate; no inferred persona rankings; independent holdout and approval pending']}
    from .contracts import validate_shape
    validate_shape('calibration',result)
    return result

def apply_errata(observations, corrections, *, errata_ref):
    """Recompute exact numerator/denominator from corrected item records, preserving originals."""
    if not errata_ref: fail('E_SCHEMA','Errata reference required')
    original=copy.deepcopy(observations); revised=copy.deepcopy(observations)
    ids=[r.get('id') for r in original]
    if None in ids or len(set(ids))!=len(ids): fail('E_SCHEMA','Unique observation IDs required')
    def counts(rows):
        active=[r for r in rows if not r.get('excluded',False)]
        if any(type(r.get('verified')) is not bool for r in active): fail('E_SCHEMA','Verification must be explicit')
        return {'numerator':sum(r['verified'] for r in active),'denominator':len(active)}
    before=counts(original)
    for correction in corrections:
        if correction.get('id') not in ids or not correction.get('reason'): fail('E_SCHEMA','Invalid erratum')
        changes=correction.get('changes',{})
        if not changes or set(changes)-{'verified','excluded'} or any(type(v)is not bool for v in changes.values()): fail('E_SCHEMA','Unsupported correction')
        revised[ids.index(correction['id'])].update(changes)
    return {'errata_ref':errata_ref,'original_sha256':hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest(),
            'before':before,'after':counts(revised),'revised':revised,'corrections':copy.deepcopy(corrections)}

def activate_with_approval(candidate, approval, *, verifier=None, current_fingerprint=None):
    """Return a pointer only. Caller supplies trusted approval verification, never candidate fields.

    No CLI exposes activation; no default verifier exists. A callable must come from
    the trusted host, not an experiment JSON. Original candidate remains immutable.
    """
    if verifier is None or not callable(verifier): fail('E_PERMISSION','Independent trusted activation verifier required')
    candidate_hash=hashlib.sha256(json.dumps(candidate,sort_keys=True).encode()).hexdigest()
    if candidate.get('state')!='candidate' or not isinstance(approval,dict): fail('E_PERMISSION','Invalid activation request')
    required={'candidate_sha256','approval_ref','reviewer_ref','holdout_report_ref','holdout_passed','safety_passed','practical_gain_passed'}
    if not required <= approval.keys() or approval['candidate_sha256']!=candidate_hash: fail('E_PERMISSION','Approval does not bind candidate')
    if not all(approval[k] is True for k in ('holdout_passed','safety_passed','practical_gain_passed')): fail('E_PERMISSION','Release gates unmet')
    if not all(isinstance(approval[k],str) and approval[k] for k in ('approval_ref','reviewer_ref','holdout_report_ref')): fail('E_PERMISSION','Missing independent evidence')
    if current_fingerprint is None or fingerprint_match(candidate['fingerprint'],current_fingerprint)!='exact': fail('E_PERMISSION','No exact current calibration match')
    if verifier(copy.deepcopy(approval),candidate_hash) is not True: fail('E_PERMISSION','Untrusted approval')
    return {'state':'active','calibration_id':candidate['calibration_id'],'candidate_sha256':candidate_hash,
            'approval_ref':approval['approval_ref'],'reviewer_ref':approval['reviewer_ref']}

def revoke_pointer(pointer, *, reason):
    if not reason: fail('E_SCHEMA','Revocation reason required')
    return {'state':'uncalibrated','previous':copy.deepcopy(pointer),'reason':reason,'fallback':'heuristic'}

def main():
    """Read explicit development metadata on stdin; emit an immutable candidate only."""
    import sys
    from .contracts import strict_loads
    from .errors import MindsError
    try:
        request=strict_loads(sys.stdin.read())
        candidate=generate_candidate(request['calibration_id'],request['fingerprint'],request['development_results'],
                                     generation_command=['python','-B','-m','minds.calibration'])
        print(json.dumps(candidate,sort_keys=True)); return 0
    except (MindsError,KeyError,ValueError) as exc:
        print(json.dumps({'status':'error','message':str(exc)})); return 2

if __name__=='__main__':
    raise SystemExit(main())
