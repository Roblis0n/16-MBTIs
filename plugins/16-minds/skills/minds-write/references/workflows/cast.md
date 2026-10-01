# cast: complete-pool roster then common workflow

`dispatch_workflow("cast", {"request": Request})` returns a preview containing a
schema-valid roster and `agent_turns: 0`. The public Request is fully validated.
Optional `persona_registry` must exactly equal the packaged frozen registry;
optional `calibration` cannot self-authenticate through JSON flags. Python's
select_roster supports a trusted `calibration_verifier` callback; absent verified
approval, coverage selection remains explicitly uncalibrated. No real calibrated
scores are shipped.

The pool is all sixteen legal IDs, never the old five-name display shortlist.
Preserve locked IDs in user order. Greedily maximize newly covered required tags,
then admitted same-task calibration, then stable ID lexicographic order. Unknown
new task tags do not acquire a made-up fitness. This is a reproducible heuristic,
not an optimality, psychological independence or accuracy claim.

An explicit challenger uses a slot within N; an explicit second locked persona
wins. N=1 plus required challenger conflicts. Already included personas never
create an N+1 slot. Return exact N unique IDs, per-member reasons, uncovered tags,
selection revision and calibration disclosures. Budget shortfall blocks before
dispatch, never silently shrinks N. A preview must never dispatch agents; when
execution is requested, pass this roster into the many scheduler and actual host
adapter, not another workflow implementation.

`source/casting/casting.legacy.json` is byte-preserved with separate metadata. Its
rankings are historical context only, not current fitness or success probability.
Historical detection corrections require audited original answers and independent
review; no correction or active ranking is invented.
