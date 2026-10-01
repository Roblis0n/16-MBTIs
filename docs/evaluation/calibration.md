# Calibration lifecycle

Current state: uncalibrated, heuristic selection. No synthetic result has been activated and no decimal persona ranking was fabricated. Human MBTI ability claims are outside scope.

Fingerprint fields are model ID/settings, host schema hash, persona/workflow hashes, tool scope, task-set/scoring/judge versions, locale and seed. Missing/unknown fields cannot exact-match; a changed known field produces mismatch. Partial match is descriptive only here, not permission to transfer scores. No arbitrary attenuation factor is used.

Generate candidates from development observations only; retain original response hashes and an exact generation command. A separate custodian owns holdout evaluation. Generating a candidate neither activates it nor produces rankings. No CLI command or JSON approved boolean can activate a candidate. The embedding host must supply a trusted verifier, a canonical candidate-bound independent approval, holdout/safety/practical-gain gates and exact current fingerprint. This repository supplies no trusted production verifier. The function returns an active pointer only; it never overwrites the candidate, legacy evidence or sealed records.

Errata supply item ID, reason, revised verified/excluded fields and a reference. apply_errata preserves input records, hashes the original, reports old/new numerator and denominator, and recomputes from records. No uniform multiplier or selective-improvement display. Callers must archive the returned erratum separately. Revocation returns an uncalibrated heuristic pointer retaining the previous pointer and reason. Storage integration and independent production approval remain not_run.
