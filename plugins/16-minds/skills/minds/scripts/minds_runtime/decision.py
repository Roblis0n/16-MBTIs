"""Feasibility first. Semantic candidate assessments remain explicit inputs."""
from copy import deepcopy
from .errors import fail
from .contracts import validate_semantics


def filter_feasible(candidates, constraints):
    """Candidates: id/version/description plus assessments {constraint: {status,reason}}.

    status is pass/fail/unknown. Missing assessments are unknown, never pass.
    The caller supplies audited factual assessments; this function does not infer them.
    """
    if not isinstance(candidates,list) or not isinstance(constraints,list): fail('E_SCHEMA','Candidates and constraints must be arrays.')
    if any(not isinstance(c,dict) or set(c)-{'id','version','description','assessments'} for c in candidates): fail('E_SCHEMA','Unknown candidate fields.')
    ids=[c.get('id') for c in candidates]
    if len(ids)<2 or any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)): fail('E_CONSTRAINT_CONFLICT','At least two unique candidates are required.')
    if any(not isinstance(x,str) or not x for x in constraints) or len(constraints)!=len(set(constraints)): fail('E_SCHEMA','Hard constraints must be unique nonempty strings.')
    feasible=[]; unknown=[]; violations=[]; missing=[]
    for c in candidates:
        if not c.get('version') or not isinstance(c.get('description'),str): fail('E_SCHEMA','Candidates require version and description.')
        if not isinstance(c['version'],str): fail('E_SCHEMA','Candidate version must be a string.')
        assessments=c.get('assessments',{}); failures=[]; gaps=[]
        if not isinstance(assessments,dict): fail('E_SCHEMA','Candidate assessments must be an object.')
        if set(assessments)-set(constraints): fail('E_SEMANTIC','Assessment refers to an unknown hard constraint.')
        for constraint in constraints:
            a=assessments.get(constraint,{'status':'unknown','reason':'Assessment not provided'})
            if not isinstance(a,dict) or set(a)!={'status','reason'}: fail('E_SCHEMA','Assessment requires exactly status and reason.')
            if a.get('status') not in ('pass','fail','unknown') or not isinstance(a.get('reason'),str) or not a['reason'].strip(): fail('E_SEMANTIC','Constraint assessment requires pass/fail/unknown and a reason.')
            if a['status']=='fail': failures.append(constraint)
            if a['status']=='unknown': gaps.append(constraint)
        if failures: violations.extend({'candidate_id':c['id'],'constraint':x} for x in failures)
        elif gaps:
            unknown.append(c['id']); missing.extend(f"{c['id']}: {x}" for x in gaps)
        else: feasible.append(c['id'])
    return {'feasible_ids':feasible,'unknown_ids':unknown,'violations':violations,'missing_information':missing,'status':'needs_information' if unknown else ('feasible' if feasible else 'no_feasible_option')}


def validate_decision(decision, context):
    d=deepcopy(decision); candidates=context.get('candidates',[]); constraints=context.get('hard_constraints',[])
    f=filter_feasible(candidates,constraints)
    if d.get('candidate_ids')!=[c['id'] for c in candidates] or d.get('hard_constraints')!=constraints or d.get('user_goal')!=context.get('user_goal'):
        fail('E_SEMANTIC','Decision must preserve the user candidate set, goal and hard constraints.')
    validate_semantics('decision',d,{'evidence':context.get('evidence',{})})
    if d['status']=='decided':
        if d['selected'] not in f['feasible_ids'] or f['unknown_ids']: fail('E_SEMANTIC','Unknown material feasibility cannot be presented as decided.')
    elif d['status']=='no_feasible_option':
        if f['status']!='no_feasible_option': fail('E_SEMANTIC','No-feasible result requires each candidate to violate a hard constraint.')
    if d['violations']!=f['violations']: fail('E_SEMANTIC','Decision violations must match candidate assessments.')
    if d['status']=='needs_information' and not d['missing_information']: fail('E_SEMANTIC','Name the blocking information.')
    for trigger in d['revisit_when']:
        if not trigger['observable_signal'].strip() or not trigger['action_after_change'].strip(): fail('E_SEMANTIC','Revisit triggers require an observable signal and next action.')
    return d


def decide(context, proposed_decision=None):
    """Return blocker analysis or validate an explicit proposed recommendation."""
    if not isinstance(context,dict) or set(context)-{'candidates','hard_constraints','user_goal','evidence'} or not {'candidates','hard_constraints'}<=set(context): fail('E_SCHEMA','Unknown or missing decision context fields.')
    f=filter_feasible(context['candidates'],context['hard_constraints'])
    if proposed_decision is not None: return validate_decision(proposed_decision,context)
    return {**f,'selected':None,'recommendation_status':'requires_explicit_assessment' if f['status']=='feasible' else f['status'],'execution_authorized':False}
