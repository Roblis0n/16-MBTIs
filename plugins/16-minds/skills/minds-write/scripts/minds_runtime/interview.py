"""Answer-driven, session-only questions and explicit interview state."""
from copy import deepcopy
from .contracts import validate_semantics
from .errors import fail

CAPS={'light':3,'middle':5,'heavy':7}


def create_interview(questions, *, run_id='interview', ask_mode='questions', include_why=False, max_interview_turns=5, known_answers=None):
    state={'run_id':run_id,'ask_mode':ask_mode,'include_why':include_why,'status':'ready','questions':deepcopy(questions),'active_question_id':None,'asked_turns':0,'max_interview_turns':max_interview_turns,'stop_reason':None,'persisted':False}
    known=known_answers or {}; seen=set()
    for q in state['questions']:
        uncertainty=q.get('target_uncertainty')
        if not uncertainty or uncertainty in seen: fail('E_SEMANTIC','Questions must target distinct identified uncertainties.')
        seen.add(uncertainty)
        if uncertainty in known:
            answer=known[uncertainty]
            if isinstance(answer,dict): q.update(answer_status=answer['status'],answer_summary=answer.get('summary'))
            else: q.update(answer_status='answered',answer_summary=str(answer))
    validate_semantics('interview_state',state)
    return state


def should_stop_interview(state, *, user_action=None, uncertainties_resolved=False):
    validate_semantics('interview_state',state)
    if state['status'] in ('completed','stopped'): return state.get('stop_reason') or 'already_stopped'
    if user_action in ('conclusion','exit','new_task'): return 'user_'+user_action
    if uncertainties_resolved: return 'key_uncertainties_resolved'
    if state['active_question_id'] is not None: return None
    if state['asked_turns']>=state['max_interview_turns']: return 'turn_budget'
    if not any(q['answer_status']=='unasked' for q in state['questions']): return 'no_remaining_questions'
    return None


def select_next_question(context, unknowns=None):
    """Advance one supplied, pre-reviewed question, never generate an answer."""
    state=deepcopy(context); validate_semantics('interview_state',state)
    if state['ask_mode']!='interview': fail('E_CONSTRAINT_CONFLICT','Sequential interview must be explicitly selected.')
    reason=should_stop_interview(state)
    if reason: state.update(status='completed',active_question_id=None,stop_reason=reason); return state
    if state['active_question_id'] is not None: return state  # idempotent wait
    candidates=[q for q in state['questions'] if q['answer_status']=='unasked' and (unknowns is None or q['target_uncertainty'] in unknowns)]
    if not candidates: state.update(status='completed',stop_reason='key_uncertainties_resolved'); return state
    state.update(status='waiting_user',active_question_id=candidates[0]['question_id'],asked_turns=state['asked_turns']+1)
    validate_semantics('interview_state',state)
    return state


def record_answer(state, question_id, answer_summary=None, *, answer_status='answered', new_constraints=None):
    out=deepcopy(state); validate_semantics('interview_state',out)
    if out['status']!='waiting_user' or out['active_question_id']!=question_id: fail('E_SEMANTIC','Only the single active question accepts an answer.')
    if answer_status not in ('answered','unknown','declined','skipped'): fail('E_SCHEMA','Answer status must distinguish answered, unknown, declined and skipped.')
    if answer_status=='answered' and (not isinstance(answer_summary,str) or not answer_summary.strip()): fail('E_SCHEMA','An answered question requires a summary.')
    q=next(q for q in out['questions'] if q['question_id']==question_id)
    q.update(answer_status=answer_status,answer_summary=answer_summary)
    out.update(status='ready',active_question_id=None)
    reason=should_stop_interview(out)
    if reason: out.update(status='completed',stop_reason=reason)
    validate_semantics('interview_state',out)
    # Frozen schema has no extra constraints field; callers carry explicit new
    # constraints in their next Request rather than silently mutate task scope.
    if new_constraints is not None: fail('E_CONSTRAINT_CONFLICT','New constraints require a new request/context; interview state is not an authorization channel.')
    return out


def stop_interview(state, reason='exit'):
    out=deepcopy(state)
    if reason not in ('exit','conclusion','new_task','key_uncertainties_resolved'): fail('E_SCHEMA','Unknown interview stop reason.')
    out.update(status='stopped',active_question_id=None,stop_reason=reason)
    validate_semantics('interview_state',out); return out


def render_questions(state, mode='light'):
    validate_semantics('interview_state',state)
    if mode not in CAPS: fail('E_SCHEMA','Unknown question mode.')
    if state['ask_mode']=='interview': questions=[q for q in state['questions'] if q['question_id']==state['active_question_id']]
    else: questions=[q for q in state['questions'] if q['answer_status']=='unasked'][:CAPS[mode]]
    return [{'question_id':q['question_id'],'text':q['text'],**({'why':q['why']} if state['include_why'] else {})} for q in questions]
