"""Anonymous first-pass packets and the public pure-JSON workflow dispatcher.

No function here starts a model, fabricates a response or treats a vote as truth.
"""
from copy import deepcopy
import hashlib
from .contracts import canonical, check_json, validate_semantics, validate_shape
from .errors import fail, MindsError
from .evidence import link_claim, evidence_roots, validate_summary_facts


def build_synthesis_packet(claims, evidence, *, hard_constraints=None, support_reviews=None, missing_actor_ids=None, context_complete=True):
    index={c['claim_id']:c for c in claims}
    if len(index)!=len(claims): fail('E_SEMANTIC','Duplicate claim IDs cannot be silently overwritten.')
    for eid,e in evidence.items():
        validate_shape('evidence',e)
        if eid!=e['evidence_id']: fail('E_SEMANTIC','Evidence registry key does not match its ID.')
    if type(context_complete) is not bool: fail('E_SCHEMA','context_complete must be boolean.')
    validated=[link_claim(c,evidence,index,support_review=(support_reviews or {}).get(c['claim_id'])) for c in claims]
    # IDs can encode a persona; replace all claim/evidence keys before judging.
    def content(c): return {k:v for k,v in c.items() if k not in ('actor_id','claim_id','counter_claim_ids','supersedes')}
    ordered=sorted(validated,key=lambda c:(canonical(content(c)),c['claim_id']))
    claim_ids={c['claim_id']:f'C{i+1}' for i,c in enumerate(ordered)}
    referenced=set(e for c in ordered for e in c['evidence_ids'])
    def include(eid,active):
        if eid in active: fail('E_SEMANTIC','Evidence derivation cycle.')
        if eid not in evidence: fail('E_UNKNOWN_EVIDENCE','Unknown evidence ID.')
        for ancestor in evidence[eid]['derived_from']:
            referenced.add(ancestor); include(ancestor,active|{eid})
    for eid in list(referenced): include(eid,set())
    evidence_ids={e:f'E{i+1}' for i,e in enumerate(sorted(referenced,key=lambda e:(canonical({k:v for k,v in evidence[e].items() if k not in ('evidence_id','derived_from')}),e)))}
    anon_claims=[]
    for c in ordered:
        a=content(c); a['claim_id']=claim_ids[c['claim_id']]; a['evidence_ids']=[evidence_ids[e] for e in c['evidence_ids']]
        a['counter_claim_ids']=[claim_ids[e] for e in c['counter_claim_ids']]
        a['supersedes']=claim_ids.get(c['supersedes'])
        a['evidence_root_ids']=[evidence_ids[e] for e in evidence_roots(c['evidence_ids'],evidence)]
        anon_claims.append(a)
    anon_evidence=[]
    for eid in evidence_ids:
        e=deepcopy(evidence[eid]); e['evidence_id']=evidence_ids[eid]; e['derived_from']=[evidence_ids[x] for x in e['derived_from']]
        anon_evidence.append(e)
    packet={'phase':'anonymous_review','claims':anon_claims,'evidence':anon_evidence,'hard_constraints':list(hard_constraints or []),'coverage':{'context_complete':context_complete,'missing_actor_count':len(missing_actor_ids or [])},'preserved_counterclaim_ids':[c['claim_id'] for c in anon_claims if c['counter_claim_ids']],'limitations':['All supplied claims and minority counterexamples are retained; no popularity weighting.','Identity labels are removed, but prose or source content may still reveal authorship.','Semantic support assessments are supplied explicitly; the helper does not independently establish their truth.']}
    packet['claim_binding']=hashlib.sha256(canonical(sorted(claims,key=lambda c:c['claim_id'])).encode()).hexdigest()
    packet['packet_hash']=hashlib.sha256(canonical(packet).encode()).hexdigest()
    return packet


def attach_attribution(packet, claims, *, reviewed_packet_hash):
    actual=hashlib.sha256(canonical({k:v for k,v in packet.items() if k!='packet_hash'}).encode()).hexdigest()
    if reviewed_packet_hash!=packet.get('packet_hash') or actual!=reviewed_packet_hash: fail('E_SEMANTIC','Attribution requires the unchanged reviewed anonymous packet hash.')
    binding=hashlib.sha256(canonical(sorted(claims,key=lambda c:c['claim_id'])).encode()).hexdigest()
    if binding!=packet.get('claim_binding'): fail('E_SEMANTIC','Attribution claims or authors differ from the reviewed source graph.')
    content=lambda c:{k:v for k,v in c.items() if k not in ('actor_id','claim_id','counter_claim_ids','supersedes')}
    ordered=sorted(claims,key=lambda c:(canonical(content(c)),c['claim_id']))
    if len(ordered)!=len(packet['claims']) or any(any(c.get(k)!=a.get(k) for k in ('text','scope','assumptions','status','revision','subject_id','kind','change_condition')) for c,a in zip(ordered,packet['claims'])): fail('E_SEMANTIC','Attribution set differs from anonymous packet.')
    return {'phase':'attributed','packet':deepcopy(packet),'attribution':[{'anonymous_claim_id':f'C{i+1}','claim_id':c['claim_id'],'actor_id':c['actor_id']} for i,c in enumerate(ordered)]}


def _payload(payload, required, optional=()):
    if not isinstance(payload,dict): fail('E_SCHEMA','Workflow payload must be an object.')
    if set(payload)-set(required)-set(optional): fail('E_UNKNOWN_ARGUMENT','Workflow payload contains unknown fields.')
    if set(required)-set(payload): fail('E_SCHEMA','Workflow payload is missing required fields.')


def dispatch_workflow(operation, payload):
    """Public API: raises MindsError; caller emits its redacted structured error.

    Exact per-operation payload grammar is in source/workflows/*.md.
    These operations prepare/validate supplied artifacts, never model generation.
    """
    check_json(payload)
    try:
        if operation=='cast':
            from .casting import preview_cast
            _payload(payload,('request',),('persona_registry','calibration'))
            validate_semantics('request',payload['request'])
            if 'persona_registry' in payload:
                from .resources import resource_json
                if payload['persona_registry']!=resource_json('casting/attention_registry.json'): fail('E_PERMISSION','Public casting cannot replace the frozen attention registry.')
            return preview_cast(**payload)
        if operation=='revise_proposal':
            from .vote import revise_proposal
            _payload(payload,('old','new','remaining_turns','eligible'),('conflicts',)); return revise_proposal(**payload)
        if operation=='attribution':
            _payload(payload,('packet','claims','reviewed_packet_hash')); return attach_attribution(**payload)
        if operation=='summary_facts':
            _payload(payload,('facts','claims','evidence'),('support_reviews',)); return validate_summary_facts(**payload)
        if operation=='register_evidence':
            from .evidence import register_evidence
            _payload(payload,('record',),('registry','content')); return register_evidence(**payload)
        if operation=='aggregate':
            from .aggregate import aggregate_scores
            _payload(payload,('records',),('object_key',)); return aggregate_scores(**payload)
        if operation=='vote':
            from .vote import tally_ballots
            _payload(payload,('ballots','eligible','run_id','proposal_id','proposal_version'),('policy','decisive_quorum','failed_ids','is_revision','evidence'))
            p=dict(payload); p['validated_ballots']=p.pop('ballots'); return tally_ballots(**p)
        if operation=='decide':
            from .decision import decide
            _payload(payload,('context',),('proposed_decision',)); return decide(**payload)
        if operation=='write':
            from .text_invariants import writing_result
            _payload(payload,('run_id','body'),('operation','source','source_version','variant_id','length_metric','semantic_review','authorized_changes','evidence_ids','evidence'))
            return writing_result(**payload)
        if operation=='pair':
            from .disputes import build_pair_round
            _payload(payload,('snapshot',)); return build_pair_round(**payload)
        if operation=='synthesis':
            _payload(payload,('claims','evidence'),('hard_constraints','support_reviews','missing_actor_ids','context_complete'))
            return build_synthesis_packet(**payload)
        if operation=='ask':
            from .interview import create_interview, select_next_question, record_answer, render_questions, stop_interview
            _payload(payload,('action',),('state','questions','run_id','ask_mode','include_why','max_interview_turns','known_answers','unknowns','question_id','answer_summary','answer_status','reason','mode'))
            action=payload['action']; p={k:v for k,v in payload.items() if k!='action'}
            if action=='create':
                _payload(p,('questions',),('run_id','ask_mode','include_why','max_interview_turns','known_answers')); return create_interview(**p)
            if action=='next':
                _payload(p,('state',),('unknowns',)); return select_next_question(p['state'],p.get('unknowns'))
            if action=='answer':
                _payload(p,('state','question_id'),('answer_summary','answer_status')); return record_answer(**p)
            if action=='stop':
                _payload(p,('state',),('reason',)); return stop_interview(**p)
            if action=='render':
                _payload(p,('state',),('mode',)); return render_questions(**p)
            fail('E_UNKNOWN_ARGUMENT','Unknown ask action.')
        fail('E_UNKNOWN_ARGUMENT','Unknown workflow operation.')
    except MindsError: raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError):
        fail('E_SCHEMA','Malformed workflow payload; consult the operation contract.')
