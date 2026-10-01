# write/rewrite: supplied draft, honest invariants, final-body counts

Public payload: `{run_id, body, operation?, source?, source_version?, variant_id?,
length_metric?, semantic_review?, authorized_changes?, evidence_ids?, evidence?}`.
The body is a supplied draft; this helper validates/counts it and does not generate
model prose. Rewrite requires source and source_version. Pure rewriting does not
trigger network access. User genre, audience, voice and factual stance override
persona style. Variants are separately authorized bounded runs under C01.

Codepoints count Python Unicode code points; words split on Unicode whitespace.
Counts use only the final body, not commentary, bytes, tokens or visual graphemes.
The extract_invariants lexical scanner identifies candidate numbers, dates, units,
entities, negations, conditions, commitments, causality and stance; it is not a
semantic judge. Any changed prose defaults to review_needed. Unsupported ratios,
strengthened guarantees, omitted exceptions and changed causality require review.
A list marker is whitelisted only at line start, digits followed by ., ) or 、 plus
whitespace; other added numbers remain risks.

A semantic_review binds source_hash and draft_hash, includes reviewed_categories
(all nine categories), reason, status and diff. Diff entries use the frozen
writing_result fields. Every lexical risk needs a corresponding reviewed change;
an empty “preserved” assertion does not clear changed numbers. Authorized changes
must match exact category/before/after entries in authorized_changes. This caller
input is an explicit assessment and permission record, not a discovered fact.
No assessment means no claim of factual preservation. Unknown evidence IDs fail.

Keep source and versions intact. Do not silently repair source claims, invent
personal experience, or promise AI-detector outcomes. New writing uses evidence,
clearly hypothetical framing or explicit missing-fact placeholders. A generated
factual draft and its check share the same C01 budget; at most one scoped repair,
not an unbounded rewrite loop. Publishing remains a separate user decision.
