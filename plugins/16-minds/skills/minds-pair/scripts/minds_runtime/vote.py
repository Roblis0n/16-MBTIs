"""C04 synthetic ballot validation, frozen policies, and deterministic counting."""
from collections import defaultdict
from copy import deepcopy
import math
import re
from .contracts import validate_shape, validate_semantics
from .errors import fail, MindsError

POLICIES={'distribution','absolute_majority','valid_majority','strict_unanimity'}


def ballot_key(ballot):
    """Public supersedes key; run/proposal/version are checked independently."""
    return f"{ballot['voter_id']}:{ballot['ballot_revision']}"


def validate_ballots(ballots, eligible, *, run_id, proposal_id, proposal_version, evidence=None):
    if not isinstance(eligible,list) or any(not isinstance(x,str) or not x for x in eligible) or not eligible or len(eligible)>16 or len(eligible)!=len(set(eligible)):
        fail('E_CONSTRAINT_CONFLICT','Eligible IDs must be a nonempty frozen unique set of at most sixteen.')
    groups=defaultdict(list); quarantine=[]; invalid=set(); hard_invalid=set()
    for original in ballots:
        b=deepcopy(original); voter=b.get('voter_id') if isinstance(b,dict) else None
        try:
            validate_shape('ballot',b)
            if voter not in eligible: fail('E_SEMANTIC','Unknown voter.')
            if any(b[k]!=v for k,v in [('run_id',run_id),('proposal_id',proposal_id),('proposal_version',proposal_version)]):
                fail('E_STALE_BALLOT','Ballot belongs to another run or proposal version.')
            for cond in b['conditions']:
                if not set(cond['evidence_ids'])<=set(evidence or {}): fail('E_UNKNOWN_EVIDENCE','Ballot condition references unknown evidence.')
            groups[voter].append(b)
        except MindsError as exc:
            quarantine.append({'voter_id':voter,'machine_code':exc.code})
            if voter in eligible:
                invalid.add(voter)
                if exc.code!='E_STALE_BALLOT': hard_invalid.add(voter)
    valid=[]
    for voter,rows in groups.items():
        rows.sort(key=lambda b:b['ballot_revision'])
        ok=rows[0]['ballot_revision']==1 and rows[0]['supersedes'] is None
        for previous,current in zip(rows,rows[1:]):
            ok=ok and current['ballot_revision']==previous['ballot_revision']+1 and current['supersedes']==ballot_key(previous)
        if not ok or voter in hard_invalid:
            invalid.add(voter); quarantine.append({'voter_id':voter,'machine_code':'E_SEMANTIC'})
        else:
            # A stale v1 alongside a valid v2 must not poison the valid new vote.
            invalid.discard(voter); valid.append(rows[-1])
    return {'ballots':sorted(valid,key=lambda b:eligible.index(b['voter_id'])),'invalid_ids':sorted(invalid),'quarantined':quarantine}


def tally_ballots(validated_ballots, eligible, policy='distribution', *, run_id=None, proposal_id=None, proposal_version=None, decisive_quorum=None, failed_ids=None, is_revision=False, evidence=None):
    if policy not in POLICIES: fail('E_CONSTRAINT_CONFLICT','Unknown frozen vote policy.')
    rows=list(validated_ballots); ids=list(eligible); first=rows[0] if rows and isinstance(rows[0],dict) else {}
    run_id=run_id or first.get('run_id'); proposal_id=proposal_id or first.get('proposal_id'); proposal_version=proposal_version or first.get('proposal_version')
    if not all(isinstance(x,str) and x for x in [run_id,proposal_id,proposal_version]): fail('E_SCHEMA','Run and proposal identity are required, including for an empty vote set.')
    checked=validate_ballots(rows,ids,run_id=run_id,proposal_id=proposal_id,proposal_version=proposal_version,evidence=evidence)
    valid=checked['ballots']; n=len(ids); failed=set(failed_ids or [])
    if not failed<=set(ids): fail('E_SEMANTIC','Failed IDs must belong to the frozen eligible set.')
    responded={b['voter_id'] for b in valid}
    if failed & responded: fail('E_SEMANTIC','A voter cannot be both failed and valid.')
    invalid=set(checked['invalid_ids'])-failed
    missing=set(ids)-responded-invalid-failed
    counts={c:sum(b['choice']==c for b in valid) for c in ('yes','no','abstain')}
    counts.update(eligible=n,responded=len(valid),valid_ballots=len(valid),decisive=counts['yes']+counts['no'])
    if policy=='valid_majority' and (type(decisive_quorum) is not int or not 1<=decisive_quorum<=n):
        fail('E_CONSTRAINT_CONFLICT','valid_majority requires a frozen decisive quorum in 1–eligible.')
    quorum=None if policy=='distribution' else n if policy=='strict_unanimity' else math.ceil(n/2) if policy=='absolute_majority' else decisive_quorum
    def calculate():
        if policy=='strict_unanimity': return 'pass' if counts['yes']==n else 'fail'
        if counts['decisive']<quorum: return 'no_quorum'
        if counts['yes']==counts['no']: return 'tie'
        return 'pass' if (counts['yes']>n/2 if policy=='absolute_majority' else counts['yes']>counts['no']) else 'fail'
    provisional=None
    if policy=='distribution': verdict='not_requested'
    elif len(valid)<n:
        verdict='pending_revote' if is_revision else 'partial'; provisional=calculate()
    else: verdict=calculate()
    out={'run_id':run_id,'proposal_id':proposal_id,'proposal_version':proposal_version,'synthetic':True,'policy':policy,'quorum':quorum,'eligible_ids':ids,'counts':counts,'missing_ids':sorted(missing),'invalid_ids':sorted(invalid),'failed_ids':sorted(failed),'yes_over_eligible':counts['yes']/n,'verdict':verdict,'provisional_verdict':provisional,'calculation_version':'1.0.0','limitations':['Synthetic distribution, not public opinion or a recommendation.']}
    if checked['quarantined']: out['limitations'].append(f"Quarantined {len(checked['quarantined'])} stale, invalid, duplicate or unknown records; inspect validate_ballots for details.")
    validate_semantics('vote_summary',out)
    return out


def revise_proposal(old, new, *, remaining_turns, eligible, conflicts=None):
    """Record a user/model-supplied revision; never invent a feasible compromise."""
    for proposal,is_new in ((old,False),(new,True)):
        allowed={'proposal_id','proposal_version','proposal_text'}|({'diff'} if is_new else set())
        if not isinstance(proposal,dict) or set(proposal)-allowed or not {'proposal_id','proposal_version'}<=set(proposal): fail('E_SCHEMA','Unknown or missing proposal fields.')
        if any(not isinstance(proposal[k],str) or not proposal[k].strip() for k in ('proposal_id','proposal_version')): fail('E_SCHEMA','Proposal identity and version must be nonempty strings.')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}',proposal['proposal_id']): fail('E_SCHEMA','Invalid proposal ID.')
        if 'proposal_text' in proposal and not isinstance(proposal['proposal_text'],str): fail('E_SCHEMA','Proposal text must be a string.')
    if type(remaining_turns) is not int or remaining_turns<0: fail('E_SCHEMA','Remaining turns must be a nonnegative integer.')
    if not isinstance(eligible,list) or not eligible or len(eligible)>16 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}',x) for x in eligible) or len(eligible)!=len(set(eligible)): fail('E_SCHEMA','Revision electorate must be nonempty unique legal IDs.')
    if old.get('proposal_id')!=new.get('proposal_id') or old.get('proposal_version')==new.get('proposal_version'):
        fail('E_STALE_BALLOT','Revision must retain proposal ID and use a new version.')
    if not isinstance(new.get('diff'),str) or not new['diff'].strip(): fail('E_SCHEMA','An explicit revision diff is required.')
    if conflicts:
        if not isinstance(conflicts,list): fail('E_SCHEMA','Conflicts must be a list.')
        for conflict in conflicts:
            if not isinstance(conflict,dict) or set(conflict)!={'constraint_ids','reason'}: fail('E_SCHEMA','Unknown or missing conflict fields.')
            if not isinstance(conflict['constraint_ids'],list) or len(conflict['constraint_ids'])<2 or any(not isinstance(x,str) or not x for x in conflict['constraint_ids']) or not isinstance(conflict['reason'],str) or not conflict['reason'].strip(): fail('E_SEMANTIC','Constraint conflict requires identified constraints and reason.')
        return {'status':'no_feasible_compromise','conflicts':deepcopy(conflicts),'selected':None}
    return {'status':'ready_for_revote' if remaining_turns>=len(eligible) else 'pending_revote','proposal':deepcopy(new),'eligible_ids':list(eligible),'inherited_ballots':[],'required_turns':len(eligible)}


def validate_ballot(ballot, context):
    """Validate one ballot with explicit frozen context and revision history."""
    history=context.get('history',[])
    checked=validate_ballots(history+[ballot],context['eligible'],run_id=context['run_id'],proposal_id=context['proposal_id'],proposal_version=context['proposal_version'],evidence=context.get('evidence'))
    matches=[b for b in checked['ballots'] if b['voter_id']==ballot['voter_id']]
    if not matches or matches[0]!=ballot: fail('E_SEMANTIC','Ballot is stale, duplicate or lacks a valid revision chain.')
    return deepcopy(matches[0])


def calculate_verdict(ballots, eligible, policy='distribution', **context):
    """Use the one canonical counting implementation, including all denominators."""
    return tally_ballots(ballots,eligible,policy,**context)


start_proposal_revision=revise_proposal
