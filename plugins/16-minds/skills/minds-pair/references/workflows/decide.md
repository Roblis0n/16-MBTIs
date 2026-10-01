# decide: feasibility before recommendation

Public operation: `decide` accepts `{context, proposed_decision?}`. Context has
candidates, hard_constraints, optional user_goal and evidence. Candidates require
id/version/description and may include assessments keyed by exact constraint.
Each assessment is exactly `{status: pass|fail|unknown, reason}`. Missing is unknown,
not pass; the helper does not infer feasibility from prose or a persona preference.

Require at least two unique frozen candidates. Preserve the user's goals and
hard constraints. No feasible candidate returns no_feasible_option with every
violation and selected=null. Material unknown feasibility returns needs_information
with named gaps, never a conditional recommendation disguised as decided. Without
an explicit proposed recommendation, the helper only filters candidates and
reports requires_explicit_assessment when comparison is still needed.

A proposed_decision uses the frozen decision schema. Validate selected membership,
actual feasibility, goal fidelity, exact violations and nonempty observable revisit
signals/action_after_change. Retain strongest_case, weakest_case, risk and
revisit_when. A reasoned condition is allowed; an unknown critical license is a
blocking gap. No invented probability, utility weighting or threshold. Ask only
for material missing information; cheaper evidence gathering beats more debate.

A decision is never execution authorization. Political choices get neutral
verifiable comparisons. High-stakes domains retain their own human/accountable
boundaries. The caller supplies and reviews semantic judgments; pure helper tests
are not evidence that a live model makes good recommendations.
