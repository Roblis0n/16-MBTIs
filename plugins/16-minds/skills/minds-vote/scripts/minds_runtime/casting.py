"""C01/WP09 deterministic coverage selector. No model or legacy-score transfer."""
from .resources import resource_json, registry
from .contracts import validate_semantics
from .errors import fail
import math


def select_roster(request, persona_registry=None, calibration=None, *, calibration_verifier=None):
    table=persona_registry or resource_json('casting/attention_registry.json')
    tags=table.get('persona_tags',{})
    legal=set(registry()['personas'])
    if set(tags)!=legal: fail('E_INVALID_PERSONA','Casting requires the complete sixteen-persona registry.')
    n=request.get('n'); locked=request.get('locked_personas',[])
    if type(n) is not int or not 1<=n<=16: fail('E_CONSTRAINT_CONFLICT','Roster size must be 1–16.')
    if len(set(locked))!=len(locked) or not set(locked)<=legal or len(locked)>n:
        fail('E_CONSTRAINT_CONFLICT','Locked personas must be unique, legal and fit N.')
    selection=request.get('selection',{})
    challenger=selection.get('require_challenger',False)
    if challenger and n==1: fail('E_CONSTRAINT_CONFLICT','An explicit challenger needs at least two slots.')
    kind=request.get('task_kind','factual'); kind=table.get('legacy_task_aliases',{}).get(kind,kind)
    required=set(request.get('required_tags',table.get('task_required_tags',{}).get(kind,[])))
    scores={}; state='uncalibrated'; ref=None; notices=[]
    if calibration:
        # Only a separately verified exact/approved partial match is admissible.
        match=calibration.get('match_state')
        admitted=callable(calibration_verifier) and calibration_verifier(calibration,request) is True and calibration.get('state')=='active' and (match=='exact' or (match=='partial_match' and calibration.get('partial_match_approved') is True))
        if admitted and calibration.get('task_kind')==kind and calibration.get('fingerprint_verified') is True:
            scores=calibration.get('scores',{})
            if set(scores)!=legal or any(type(x) not in (int,float) or not math.isfinite(x) for x in scores.values()):
                fail('E_CALIBRATION_MISMATCH','Calibration requires finite scores for all sixteen IDs.')
            state=match; ref=calibration.get('calibration_ref')
            if not ref: fail('E_CALIBRATION_MISMATCH','Calibration provenance is required.')
        else: notices.append('Calibration unavailable or mismatched; explicit uncalibrated coverage fallback.')
    if selection.get('legacy_preview'): notices.append('Legacy data are available as a separate historical preview, never current performance evidence.')
    selected=[]; covered=set(); members=[]
    def add(pid,source):
        new=sorted((set(tags[pid]) & required)-covered)
        selected.append(pid); covered.update(tags[pid])
        members.append({'actor_id':pid,'source':source,'newly_covered_tags':new,'reason':'User locked persona' if source=='locked' else 'Lexicographic uncovered coverage, admitted calibration, stable ID'})
    for pid in locked: add(pid,'locked')
    if challenger and len(locked)>=2: notices.append('Explicit second persona retained; automatic challenger ignored.')
    while len(selected)<n:
        pid=min(legal-set(selected),key=lambda p:(-len((set(tags[p])&required)-covered),-scores.get(p,0),p))
        source='calibrated' if scores else 'heuristic'
        if challenger and len(selected)==1 and len(locked)<2: source='heuristic_challenger'
        add(pid,source)
    result={'run_id':request.get('run_id','cast'),'requested_n':n,'members':members,'required_tags':sorted(required),'uncovered_tags':sorted(required-covered),'calibration_state':state,'calibration_ref':ref,'selection_revision':'1.0.0','notices':notices}
    validate_semantics('roster',result,{'locked_personas':locked})
    return result


def preview_cast(request, persona_registry=None, calibration=None):
    return {'status':'preview','roster':select_roster(request,persona_registry,calibration),'agent_turns':0}
