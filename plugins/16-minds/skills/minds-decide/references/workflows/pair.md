# pair: targeted, faithful response

Use C01's exact pair roster and C02's common scheduler. Both first responses are
independent; choosing a rival never dictates opposition. In each response, a
challenge names target_claim_id, steelman, target_scope, preserved_conditions,
attributed_evidence_ids, and steelman_review {faithful, reason}. The helper checks
IDs, exact scope/conditions and evidence membership; fidelity still requires an
explicit semantic assessment. It does not infer faithful steelmanning from a
nonempty sentence. Do not supply missing evidence for an opponent.

`classify_dispute(a,b,assessment)` routes factual/value/definition/scope/
missing_information with a reason. Omitted assessment returns needs_assessment,
not a regex guess. Values return to user goals, definitions to agreed terms,
facts to original-evidence verification. Scope mismatch is not a successful
refutation. Tone, identity and majority count are not external evidence.

Public operation: `pair` payload `{snapshot}`. Snapshot requires actor_ids,
results (schema-valid AgentResults), round and frozen; optional fields are
challenges, new_evidence_ids, evidence and dispute_kind. New evidence IDs must be
registered and observed. The helper creates equal previous-snapshot inputs for
both actors and allows maintained/partially_revised/retracted stances. The common
scheduler must still enforce actual rounds, budget and dispatch permissions.
No new evidence or targeted challenge stops. Pure value differences stop rather
than trigger fact voting. Record each participant's changes, gaps and stop reason;
never force a winner, concession or manufactured middle ground. Real political
choices receive neutral factual comparison, not persona candidate rankings.
