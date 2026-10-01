# vote: synthetic distribution with explicit frozen policy

Public payload: `{ballots, eligible, run_id, proposal_id, proposal_version,
policy?, decisive_quorum?, failed_ids?, is_revision?, evidence?}`. Every ballot uses
the C04 ballot schema. Eligible IDs are frozen unique IDs, not whoever replied.
Default distribution gives verdict=not_requested. Only an explicit prior request
permits an algorithm verdict; it is not a real organization's decision, public
opinion, market support or a recommendation.

Quarantine stale versions, unknown voters, malformed records and duplicates.
Never last-write-wins: revision chains start at 1 and every next revision must
supersede `voter_id:previous_revision`, within the same run/proposal/version.
Arrival order is irrelevant. A stale old vote never inherits into a new proposal.
Returned integer counts retain eligible/responded/valid_ballots/yes/no/abstain/
decisive; missing/invalid/failed IDs are separate, and yes_over_eligible is a ratio.
Original input ballots retain reasons and conditions; `validate_ballots` exposes
the quarantined details for a complete audit/presentation.

Follow C04 ordering: incomplete modified proposal -> pending_revote; incomplete
initial collection -> partial plus provisional_verdict; then quorum, tie and
policy threshold. strict_unanimity has its own complete-coverage path: any no or
abstain fails, never disguised as no_quorum. valid_majority requires its decisive
quorum in advance. Freeze policy before seeing votes; never change it to get pass.

`workflow` operation `revise_proposal` accepts `{old,new,remaining_turns,eligible,
conflicts?}`. New keeps proposal ID, changes version and includes a nonempty diff.
Explicit hard-constraint conflicts return no_feasible_compromise. Otherwise the
helper reports ready_for_revote only if the remaining turn budget covers the
frozen electorate; insufficient turns returns pending_revote. No ballots inherit
and no agents start. The common scheduler separately enforces budgets/receipts.
Real political/ electoral choices must not be transformed into persona preference
rankings or vote predictions; provide neutral factual information instead.
