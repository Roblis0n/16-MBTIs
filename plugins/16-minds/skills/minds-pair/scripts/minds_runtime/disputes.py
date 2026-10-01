"""Structured dispute routing; no truth inference from wording or persona."""
from copy import deepcopy
from .errors import fail
from .contracts import validate_shape

KINDS={'factual','value','definition','scope','missing_information'}


def classify_dispute(claim_a, claim_b, assessment=None):
    if not claim_a.get('claim_id') or not claim_b.get('claim_id'): fail('E_SEMANTIC','Disputes require identified claims.')
    if assessment is None:
        return {'status':'needs_assessment','claim_ids':[claim_a['claim_id'],claim_b['claim_id']],'kind':None,'reason':'An explicit semantic assessment is required; wording alone does not determine disagreement.'}
    if assessment.get('kind') not in KINDS or not assessment.get('reason'): fail('E_SEMANTIC','Dispute assessment requires a supported kind and reason.')
    kind=assessment['kind']
    return {'status':'classified','claim_ids':[claim_a['claim_id'],claim_b['claim_id']],'kind':kind,'reason':assessment['reason'],'next_step':{'factual':'verify_original_evidence','value':'return_to_user_goal','definition':'agree_terms','scope':'restore_conditions_and_exceptions','missing_information':'obtain_missing_information'}[kind],'requires_another_debate':False}


def validate_target(challenge, claim_index):
    required={'target_claim_id','steelman','target_scope','preserved_conditions','attributed_evidence_ids','steelman_review'}
    if not isinstance(challenge,dict) or set(challenge)!=required: fail('E_SCHEMA','Challenge fields do not match the steelman contract.')
    target=claim_index.get(challenge.get('target_claim_id'))
    if target is None: fail('E_SEMANTIC','Challenge target does not exist.')
    if not challenge.get('steelman') or challenge.get('preserved_conditions')!=target.get('assumptions',[]): fail('E_SEMANTIC','Steelman must preserve the target conditions and exceptions.')
    if challenge.get('target_scope')!=target.get('scope'): fail('E_SEMANTIC','Challenge scope differs from the target claim.')
    if not set(challenge.get('attributed_evidence_ids',[]))<=set(target.get('evidence_ids',[])): fail('E_UNKNOWN_EVIDENCE','Do not invent evidence for the opposing claim.')
    review=challenge.get('steelman_review',{})
    if not isinstance(review,dict) or set(review)!={'faithful','reason'}: fail('E_SCHEMA','Steelman review requires exactly faithful and reason.')
    if review.get('faithful') is not True or not review.get('reason'): fail('E_CONTEXT_INCOMPLETE','Steelman fidelity requires an explicit semantic assessment.')
    return deepcopy(challenge)


def build_pair_round(snapshot):
    """Both participants receive the same previous-round snapshot, never live results."""
    allowed={'actor_ids','results','round','frozen','challenges','new_evidence_ids','dispute_kind','evidence'}
    if not isinstance(snapshot,dict) or set(snapshot)-allowed or not {'actor_ids','results','round','frozen'}<=set(snapshot): fail('E_SCHEMA','Unknown or missing pair snapshot fields.')
    if type(snapshot['round']) is not int or not 1<=snapshot['round']<=3: fail('E_SCHEMA','Invalid pair round.')
    actors=snapshot.get('actor_ids',[]); results=snapshot.get('results',[])
    if len(actors)!=2 or len(set(actors))!=2: fail('E_CONSTRAINT_CONFLICT','Pair requires exactly two unique actors.')
    if snapshot.get('frozen') is not True: fail('E_SEMANTIC','Pair continuation requires a frozen snapshot.')
    if any(r.get('actor_id') not in actors or r.get('round')!=snapshot.get('round') for r in results): fail('E_SEMANTIC','Pair snapshot contains another actor or round.')
    if len({r['actor_id'] for r in results})!=len(results): fail('E_SEMANTIC','Duplicate actor result in pair snapshot.')
    for r in results: validate_shape('agent_result',r)
    evidence=snapshot.get('evidence',{})
    for eid in snapshot.get('new_evidence_ids',[]):
        if eid not in evidence: fail('E_UNKNOWN_EVIDENCE','Pair follow-up cites unregistered new evidence.')
        validate_shape('evidence',evidence[eid])
        if evidence[eid]['access_status']!='observed': fail('E_CONTEXT_INCOMPLETE','New evidence has not been observed.')
    claims={c['claim_id']:c for r in results for c in r.get('claims',[])}
    challenges=[validate_target(c,claims) for c in snapshot.get('challenges',[])]
    if not challenges and not snapshot.get('new_evidence_ids'): return {'status':'stopped','stop_reason':'no_new_evidence_or_targeted_dispute','inputs':[]}
    if snapshot.get('dispute_kind')=='value': return {'status':'stopped','stop_reason':'value_tradeoff_requires_user_goal','inputs':[]}
    return {'status':'ready','inputs':[{'actor_id':actor,'previous_snapshot':deepcopy(snapshot),'targeted_challenges':deepcopy(challenges),'allowed_stance_changes':['maintained','partially_revised','retracted']} for actor in actors]}
