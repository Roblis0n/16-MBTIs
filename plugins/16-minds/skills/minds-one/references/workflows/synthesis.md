# Evidence-first anonymous synthesis

Public operation `synthesis` accepts `{claims, evidence, hard_constraints?,
support_reviews?, missing_actor_ids?, context_complete?}`. Claims and evidence
use C03 schemas and ID maps. A factual supported/refuted status requires observed
original evidence plus an explicit support review containing relevant,
scope_matches, versions_match and a concise reason. These are inspectable caller
assessments, not independently authenticated factual truth.

The anonymous packet retains every supplied claim and counterexample, scopes,
assumptions, evidence derivations and status. It strips actor labels and remaps
claim/evidence IDs before a judge sees the packet. A full-source claim binding
hash and packet hash prevent accidental attribution swaps or content tampering.
Prose and source content may still reveal authorship; label removal does not prove
absence of judge bias. Root evidence identity, not repeated actor statements,
determines distinct provenance. Never delete a reproducible minority finding
because fifteen other actors guessed otherwise.

Additional pure operations through `workflow`:
- `register_evidence`: `{record, registry?, content?}`. Actual obtained content is
  required for observed registration, and its hash is computed locally. URL-only
  evidence remains not_accessed; caller must obtain content with authorized tools
- `summary_facts`: `{facts, claims, evidence, support_reviews?}`. Each supplied fact
  has text, claim_ids and semantic_review {entailed, reason}. New uncited facts
  and unsupported claims fail. A human/model editorial pass must still identify
  all load-bearing factual spans; the helper cannot prove extraction completeness
- `attribution`: `{packet, claims, reviewed_packet_hash}`. Only after anonymous
  review, verify the unchanged packet hash and complete original claim binding,
  then append actor/source labels for presentation

Invalidate changed sources by appending a stale evidence record linked to the
immutable original. Freeze and check current source versions; do not reuse old
line-number evidence as current. Evidence hashes authenticate content equality,
not factual truth. Scope-incomplete material cannot support full-coverage claims.
Render conclusion/status, strongest grounded evidence, unresolved minority cases,
conditions/flip triggers, minimum next step and actual execution disclosure.
