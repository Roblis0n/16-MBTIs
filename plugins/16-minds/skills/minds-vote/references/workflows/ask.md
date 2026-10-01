# ask: questions or explicit answer-driven interview

Public `ask` payload starts with action:
- create: questions; optional run_id, ask_mode, include_why,
  max_interview_turns, known_answers
- next: state; optional unknowns (unresolved uncertainty IDs)
- answer: state, question_id; optional answer_summary and answer_status
- stop: state; optional reason (exit/conclusion/new_task/key_uncertainties_resolved)
- render: state; optional mode

Question objects use C04 interview_state fields. The model/user supplies reviewed,
non-leading questions in priority order. The helper does not invent questions or
infer motives. Every question targets one identified uncertainty; duplicate targets
are rejected. known_answers maps those targets to a supplied answer or
{status,summary}; answered, unknown, declined and skipped remain distinct.

Questions mode renders at most C04's light/middle/heavy cap, never pads to it.
include_why defaults false and heavy does not override it. Questions-only output
contains question text, not recommendations, summaries or unsolicited why.
Interview requires explicit ask_mode=interview. next exposes exactly one active
question and is idempotent while waiting; answer must match that question.
Already resolved/declined/unknown questions are not repeatedly forced on the user.
New uncertainty can be explored with a different supplied question, such as a
small reachable validation step rather than blaming the user for not knowing.

Stop on the user's conclusion/exit/new-task request, resolved key uncertainty,
no remaining question or explicit turn budget. A final active question may still
receive its answer at the budget boundary. New constraints belong in an explicit
new request/context, not silent permission changes. Persona changes carry shared
facts and existing answers only, not unverified opinions. State is session-only;
no automatic persistence, background interviewing or follow-up promise.
