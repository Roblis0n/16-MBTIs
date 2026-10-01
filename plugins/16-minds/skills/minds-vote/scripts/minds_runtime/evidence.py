"""Append-only evidence and explicit, inspectable semantic support reviews."""
from copy import deepcopy
import hashlib
from .contracts import validate_semantics
from .errors import fail


def register_evidence(record, registry=None, *, content=None):
    records=deepcopy(registry or {}); r=deepcopy(record)
    if r.get('access_status')=='observed':
        if content is None: fail('E_CONTEXT_INCOMPLETE','Observed evidence requires obtained content; a URL alone is insufficient.')
        if not isinstance(content,(str,bytes)): fail('E_SCHEMA','Evidence content must be text or bytes.')
        digest=hashlib.sha256(content.encode('utf-8') if isinstance(content,str) else content).hexdigest()
        if r.get('content_hash') not in (None,digest): fail('E_SEMANTIC','Evidence content hash does not match obtained content.')
        r['content_hash']=digest
        if not r.get('observed_at'): fail('E_SEMANTIC','Observed evidence needs an acquisition time.')
        if r.get('kind')=='tool_observation' and (not r.get('observation') or r['observation'].get('exit_code') is None): fail('E_CONTEXT_INCOMPLETE','Tool evidence needs an actual observation receipt.')
    validate_semantics('evidence',r,{'evidence':records})
    records[r['evidence_id']]=r
    return records


def evidence_roots(evidence_ids, registry):
    """Repeated participant statements do not create independent evidence roots."""
    roots=set(); active=set()
    def walk(eid):
        if eid not in registry: fail('E_UNKNOWN_EVIDENCE','Unknown evidence reference.')
        if eid in active: fail('E_SEMANTIC','Evidence derivation cycle.')
        active.add(eid); row=registry[eid]
        if row['derived_from']:
            for parent in row['derived_from']: walk(parent)
        elif row['kind']!='participant_statement': roots.add(eid)
        active.remove(eid)
    for eid in evidence_ids: walk(eid)
    return sorted(roots)


def link_claim(claim, evidence, claims=None, *, support_review=None, evidence_versions=None):
    c=deepcopy(claim); index=claims or {}; reviews={}
    if support_review is not None:
        if not isinstance(support_review.get('reason'),str) or not support_review['reason'].strip(): fail('E_CONTEXT_INCOMPLETE','Semantic support assessment requires a shareable reason.')
        reviews[c['claim_id']]={k:support_review.get(k) for k in ('relevant','scope_matches','versions_match')}
    validate_semantics('claim',c,{'evidence':evidence,'claims':index,'support_reviews':reviews,'evidence_versions':evidence_versions or {}})
    roots=evidence_roots(c['evidence_ids'],evidence)
    if c['status'] in ('supported','refuted') and c['kind']!='value_preference':
        if not roots or any(evidence[e]['access_status']!='observed' or evidence[e]['kind']=='participant_statement' for e in c['evidence_ids']) or any(evidence[e]['access_status']!='observed' for e in roots): fail('E_CONTEXT_INCOMPLETE','A factual disposition requires observed original evidence.')
        if not support_review or any(support_review.get(k) is not True for k in ('relevant','scope_matches','versions_match')): fail('E_CONTEXT_INCOMPLETE','Factual dispositions require explicit relevance, scope and version review.')
    return c


def invalidate_stale_source(registry, evidence_id, current_hash, *, new_id):
    if evidence_id not in registry: fail('E_UNKNOWN_EVIDENCE','Cannot invalidate unknown evidence.')
    original=registry[evidence_id]
    if original['content_hash']==current_hash: return deepcopy(registry)
    if new_id in registry or new_id==evidence_id: fail('E_SEMANTIC','Stale revision requires a new evidence ID.')
    stale=deepcopy(original); stale.update(evidence_id=new_id,access_status='stale',content_hash=None,derived_from=[evidence_id])
    # Preserve the immutable observation under the old ID; this new status record
    # cannot be used as current support. Consumers must freeze current IDs/versions.
    return register_evidence(stale,registry)


def validate_summary_facts(facts, claims, evidence, *, support_reviews=None):
    """Each supplied load-bearing factual sentence must identify a reviewed claim.

    Fact extraction itself is a caller/model review, not a regex truth detector.
    """
    for fact in facts:
        if not fact.get('text') or not fact.get('claim_ids'): fail('E_UNKNOWN_EVIDENCE','Summary fact has no claim provenance.')
        for cid in fact['claim_ids']:
            if cid not in claims: fail('E_UNKNOWN_EVIDENCE','Summary refers to unknown claim.')
            c=claims[cid]
            link_claim(c,evidence,claims,support_review=(support_reviews or {}).get(cid))
            if c['status']!='supported' or c['kind']=='value_preference' or not c['evidence_ids']: fail('E_CONTEXT_INCOMPLETE','Unverified or refuted claim cannot support a summary fact.')
        review=fact.get('semantic_review',{})
        if review.get('entailed') is not True or not review.get('reason'): fail('E_CONTEXT_INCOMPLETE','Summary-to-claim entailment requires explicit semantic review.')
    return {'status':'validated','fact_count':len(facts),'limitation':'Validation covers supplied factual spans; completeness needs an explicit editorial review.'}
