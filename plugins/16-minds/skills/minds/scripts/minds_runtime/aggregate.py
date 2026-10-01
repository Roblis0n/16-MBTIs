"""Deterministic ordinal statistics over a single frozen object."""
from collections import Counter
import math
from .errors import fail

OBJECT_FIELDS=('subject_id','subject_version','criterion_id','scale_id')


def aggregate_scores(records, object_key=None):
    rows=list(records)
    if object_key is not None:
        key=tuple(object_key[k] for k in OBJECT_FIELDS) if isinstance(object_key,dict) else tuple(object_key)
        if len(key)!=4: fail('E_SCORE_OBJECT_MISMATCH','A complete object key is required.')
    else: key=None
    actors=set(); values=[]
    for r in rows:
        if any(k not in r for k in (*OBJECT_FIELDS,'actor_id','value')): fail('E_SCORE_OBJECT_MISMATCH','Score object identity is incomplete.')
        if set(r)-set((*OBJECT_FIELDS,'actor_id','value')): fail('E_SCHEMA','Unknown score fields; revisions must be resolved before aggregation.')
        if any(not isinstance(r[k],str) or not r[k] for k in (*OBJECT_FIELDS,'actor_id')): fail('E_SCORE_OBJECT_MISMATCH','Score identity fields must be nonempty strings.')
        this=tuple(r[k] for k in OBJECT_FIELDS)
        if key is None: key=this
        if key!=this: fail('E_SCORE_OBJECT_MISMATCH','Scores refer to different objects, versions, criteria or scales.')
        if r['actor_id'] in actors: fail('E_SCORE_OBJECT_MISMATCH','A participant cannot appear in two score buckets.')
        v=r['value']
        if type(v) not in (int,float) or not math.isfinite(v): fail('E_SEMANTIC','A finite numeric ordinal score is required.')
        actors.add(r['actor_id']); values.append(v)
    values.sort(); c=Counter(values); n=len(values)
    return {'object_key':dict(zip(OBJECT_FIELDS,key)) if key else None,'count':n,'distribution':[{'value':v,'count':c[v],'actor_ids':sorted(r['actor_id'] for r in rows if r['value']==v)} for v in sorted(c)],'min':values[0] if n else None,'modes':[v for v in sorted(c) if c[v]==max(c.values())] if n else [],'max':values[-1] if n else None,'median':(values[(n-1)//2]+values[n//2])/2 if n else None,'median_definition':'Mean of two middle observations for even N; may not be a scale option.','interpretation':'Ordinal distribution, not a success probability.'}


def tally_ballots(validated_ballots,eligible,policy='distribution',**context):
    from .vote import tally_ballots as tally
    return tally(validated_ballots,eligible,policy,**context)
