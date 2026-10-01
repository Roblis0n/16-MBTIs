# Fair evaluation (C06, protocol 1.0.0)

Current status: protocol implementation tested on synthetic fixtures; model pilot, human review, sealed holdout and statistical superiority **not_run**. Authorized spending is zero. No hidden answers were read. Public development tasks now have explicit developer-authored gold and bounded checks; they are not independently reviewed benchmarks and provide no quality-superiority evidence.

## Frozen comparisons

B0 single-agent equal-resource review; B1 independent agents without personas; B2 domain specialization; B3 independent persona first round; B4 persona discussion; B5 persona evidence verification; B6 all 16 personas. Keep exact model/configuration, material and permission scope constant. Record allocation and verification opportunities. Extra tools in B5 are a disclosed intervention, not evidence for personality alone. B0 may spend the same resource envelope on deeper/repeated self-review.

Planned pilot: 12 tasks (4 engineering, 4 decision, 4 writing), 8 development and 4 sealed holdout, with at least one held-out family per domain. The 12 public tasks are all development and have exposed versioned gold; an independent custodian must separately author the sealed pilot families before a controlled evaluation. Never re-label public fixtures as sealed. Split by project/topic family, not retries or questions from the same file. Any exposure invalidates that holdout; use a new independently held-out family.

## Observations

Keep every completed, partial, failed, rate-limited, timed-out and cancelled run. Record original response SHA-256 (an empty response has its own SHA), exact model ID/settings/date, material hash, tool permissions, actions, agent rounds, observable input/output/reasoning tokens, monetary cost, delay and reading burden. Unknown cost stays null and known subtotal is not total. Retry costs remain included. Only fully observed equal token totals support token_matched; equal calls alone support action_matched. No word-count estimate of subscription tokens.

Engineering: verified unique findings, false positives, checked scope and reproduction status. Pre-register duplicate finding identity (same root cause/location), keep unknown verification distinct. Decision: hard-constraint violations, traceable factual claims, material gaps and conditional actionability. Writing: numeric, entity, negation, causal, commitment and stance drift. Serious factual/safety failures block defaults regardless of style preference. Without verifiable truth never compute accuracy.

Model judging is anonymous and order-swapped; unequal irrelevant length is flagged rather than silently truncating facts. Audit pivotal results through executable truth or independent human review. Judge preference is not user satisfaction. Summaries cluster by project_group; repeated answers do not increase independent sample size. The implementation emits descriptive family means and inconclusive without unsupported intervals. Pilot variance and a user-selected practical effect determine later sample planning, not an invented fixed sample count.

## Release decision

Before viewing holdout, user sets useful improvement, acceptable added cost, latency and reading burden. Require deterministic P0 regressions clear, no unresolved safety/serious drift, real eight-entry host smoke, independent holdout and independent activation review. Otherwise do not change defaults. A costly 16-person result with no gain is negative; more data without enough evidence is inconclusive. No default winner is assumed.

Run the offline plan check from repository root: python -B tools/evaluate.py. This command has no model execution adapter and always reports not_run. It validates metadata and cannot turn budget numbers into authorization.

Actual response recording: evaluation.observations.record_response persists exact supplied output, provenance, SHA-256 and nullable observed resources using exclusive creation. It never overwrites an observation or invokes models. Failed responses remain cost-bearing records. Baseline can be null for an uncontrolled observation; do not assign B0–B6 after seeing a result. The current native one-response sample is recorded as actual_model with baseline null, unknown tokens/cost/latency and no quality score.
