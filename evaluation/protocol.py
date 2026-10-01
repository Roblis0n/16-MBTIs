"""C06 evaluation: no model/network execution, no sealed-answer access."""
import hashlib
import json
import math
from collections import defaultdict

BASELINES = {
    'B0': 'single agent with equal-resource self-review',
    'B1': 'independent agents without personas',
    'B2': 'domain-specialist agents',
    'B3': 'persona independent first round',
    'B4': 'personas with discussion',
    'B5': 'personas with evidence verification',
    'B6': 'all sixteen personas',
}
TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'reasoning_tokens')
STATUSES = {'completed', 'failed', 'timeout', 'cancelled', 'rate_limited', 'partial'}

def number(value, *, nullable=False):
    if value is None and nullable: return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Expected finite nonnegative number')
    return value

def validate_family_splits(tasks):
    families = {}
    ids = set()
    for task in tasks:
        if not task.get('id') or task['id'] in ids: raise ValueError('Task IDs must be unique')
        ids.add(task['id'])
        family, split = task.get('project_group'), task.get('split')
        if not family or split not in {'development', 'holdout'}: raise ValueError('Missing family or split')
        if family in families and families[family] != split: raise ValueError('Project-family leakage invalidates holdout')
        if task.get('exposed', False) and split == 'holdout': raise ValueError('Exposed task cannot be sealed holdout')
        families[family] = split
    return families

def budget_match(runs):
    if len(runs) < 2: return 'unmatched'
    for run in runs:
        for field in (*TOKEN_FIELDS, 'actions'): number(run.get(field), nullable=True)
    if all(all(r.get(f) is not None for f in TOKEN_FIELDS) for r in runs):
        if len({sum(r[f] for f in TOKEN_FIELDS) for r in runs}) == 1: return 'token_matched'
    if all(r.get('actions') is not None for r in runs) and len({r['actions'] for r in runs}) == 1:
        return 'action_matched'
    return 'unmatched'

def summarize(runs):
    groups = defaultdict(list)
    costs, delays = [], []
    for run in runs:
        if run.get('status') not in STATUSES or not run.get('project_group'): raise ValueError('Invalid observation')
        if not run.get('answer_sha256') or len(run['answer_sha256']) != 64 or any(c not in '0123456789abcdef' for c in run['answer_sha256']):
            raise ValueError('Original response hash required, including failures')
        number(run.get('quality'), nullable=True)
        costs.append(number(run.get('cost'), nullable=True)); delays.append(number(run.get('latency_seconds'), nullable=True))
        groups[run['project_group']].append(run)
    means = {g: sum(r['quality'] for r in rs if r.get('quality') is not None)/sum(r.get('quality') is not None for r in rs)
             for g,rs in groups.items() if any(r.get('quality') is not None for r in rs)}
    return {'run_count': len(runs), 'independent_families': len(groups), 'family_means': means,
            'mean_family_quality': sum(means.values())/len(means) if means else None,
            'completion_rate': sum(r['status']=='completed' for r in runs)/len(runs) if runs else None,
            'known_cost': sum(c for c in costs if c is not None), 'cost_complete': all(c is not None for c in costs),
            'known_latency_seconds': sum(d for d in delays if d is not None),
            'inference': 'inconclusive', 'interval': None,
            'limitations': ['Descriptive family means only; no inferred accuracy or unearned confidence interval']}

def judge_pairs(left, right):
    """Anonymous order swaps; length imbalance is a diagnostic, never trimmed facts."""
    a, b = str(left), str(right)
    ratio = max(len(a),len(b))/max(1,min(len(a),len(b)))
    return {'pairs': [{'A': a, 'B': b}, {'A': b, 'B': a}], 'length_ratio': ratio,
            'length_confounded': ratio > 1.2, 'requires_independent_review': True}

def marginal_benefit(quality_delta, extra_cost, *, minimum_gain=None):
    if not isinstance(quality_delta,(int,float)) or isinstance(quality_delta,bool) or not math.isfinite(quality_delta): raise ValueError('Invalid delta')
    number(extra_cost)
    if minimum_gain is not None: number(minimum_gain)
    return {'outcome': 'negative' if quality_delta <= 0 and extra_cost > 0 else 'inconclusive',
            'quality_delta': quality_delta, 'extra_cost': extra_cost, 'change_default': False,
            'reason': 'Independent holdout, safety gates and preregistered practical thresholds required'}

def evaluate(protocol, authorized_budget, dataset_refs):
    """Validate a preregistered plan; dry run never produces model results."""
    number(authorized_budget)
    if set(protocol.get('baselines', [])) != set(BASELINES): raise ValueError('Freeze B0–B6')
    for key in ('model_config', 'tool_scope', 'scoring_version', 'verification_opportunities', 'budget_allocation'):
        if not protocol.get(key): raise ValueError('Missing fairness field: '+key)
    families = validate_family_splits(dataset_refs)
    return {'status': 'not_run', 'mode': 'dry_run', 'authorized_budget': authorized_budget,
            'spent': 0, 'external_calls': 0, 'task_count': len(dataset_refs), 'family_count': len(families),
            'plan_sha256': hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest(),
            'results': [], 'limitations': ['No model execution adapter or budget approval',
              'No sealed holdout answers read', 'Synthetic development fixtures are not performance evidence']}
