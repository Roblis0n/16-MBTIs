"""C04 text counts and bounded lexical risks with explicit semantic review.

Scanning is not a truth/fidelity model. Changed prose needs a complete assessment.
"""
from collections import Counter
import hashlib
import re
from .errors import fail
from .contracts import validate_semantics

CATEGORIES={'number','entity','date','unit','negation','condition','commitment','causality','stance'}
PATTERNS={
 'number':r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:%|％)?|\d+(?:[.,]\d+)*(?:%|％)?',
 'date':r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{4}年\d{1,2}月(?:\d{1,2}日)?',
 'unit':r'\b(?:kg|km|USD|EUR|hours?|days?|weeks?)\b|元|万元|公里|小时|天|日間',
 'negation':r'\b(?:not|never|no|cannot|without)\b|不保证|不一定|不得|不能|没有|ない|ません',
 'condition':r'\b(?:if|unless|provided|except)\b|如果|除非|仅当|但|ただし|場合',
 'commitment':r'\b(?:must|shall|will|may|might|guarantee)\b|必须|保证|可能|应当|必ず|かもしれない',
 'causality':r'\b(?:causes?|correlat\w*|leads? to)\b|导致|相关|造成|引き起こす|相関',
 'stance':r'\b(?:support|oppose|recommend)\b|支持|反对|建议|賛成|反対',
 'entity':r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',
}


def text_hash(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()


def count_text(text, metric='codepoints'):
    if not isinstance(text,str): fail('E_SCHEMA','Text must be a string.')
    if metric=='codepoints': return len(text)
    if metric=='words': return len(text.split())
    fail('E_SCHEMA','Length metric must be codepoints or words.')


def extract_invariants(source):
    if not isinstance(source,str): fail('E_MISSING_SOURCE','Source text is required.')
    result=[]
    for category,pattern in PATTERNS.items():
        for match in re.finditer(pattern,source,re.IGNORECASE if category!='entity' else 0):
            result.append({'category':category,'value':match.group(),'source_span':f'{match.start()}:{match.end()}','start':match.start(),'end':match.end()})
    return sorted(result,key=lambda x:(x['start'],x['category']))


def compare_draft(source, draft, *, semantic_review=None, authorized_changes=None):
    if not isinstance(source,str) or not isinstance(draft,str): fail('E_MISSING_SOURCE','Source and final draft are required.')
    before=extract_invariants(source); after=extract_invariants(draft); diff=[]
    for text,items in ((source,before),(draft,after)):
        structural={m.span(1) for m in re.finditer(r'^\s*(\d+)[.)、]\s+',text,re.MULTILINE)}
        for item in items:
            if item['category']=='number' and (item['start'],item['end']) in structural:
                item['category']='structural_number'
    for category in sorted(CATEGORIES|{'structural_number'}):
        old=Counter(x['value'] for x in before if x['category']==category); new=Counter(x['value'] for x in after if x['category']==category)
        for val,count in (old-new).items():
            for _ in range(count): diff.append({'category':category,'source_span':next(x['source_span'] for x in before if x['category']==category and x['value']==val),'before':val,'after':None,'status':'preserved' if category=='structural_number' else 'review_needed','reason':'Line-initial list-number whitelist.' if category=='structural_number' else 'Lexical candidate risk; meaning requires review.'})
        for val,count in (new-old).items():
            for _ in range(count): diff.append({'category':category,'source_span':None,'before':None,'after':val,'status':'preserved' if category=='structural_number' else 'review_needed','reason':'Line-initial list-number whitelist: digits followed by ., ) or 、 and whitespace.' if category=='structural_number' else 'New lexical candidate; not automatically a factual invention.'})
    status='preserved' if source==draft else 'review_needed'
    if semantic_review is not None:
        if semantic_review.get('source_hash')!=text_hash(source) or semantic_review.get('draft_hash')!=text_hash(draft): fail('E_SEMANTIC','Semantic review must bind the actual source and final draft hashes.')
        if set(semantic_review.get('reviewed_categories',[]))!=CATEGORIES or not semantic_review.get('reason'): fail('E_CONTEXT_INCOMPLETE','Semantic review must cover every invariant category with a reason.')
        verdict=semantic_review.get('status')
        if verdict not in ('preserved','authorized_change','review_needed','violation'): fail('E_SCHEMA','Invalid semantic review status.')
        assessments=semantic_review.get('diff',[])
        for item in assessments:
            if item.get('category') not in CATEGORIES or item.get('status') not in ('preserved','authorized_change','review_needed','violation') or not item.get('reason'): fail('E_SCHEMA','Malformed semantic invariant diff.')
            if item['status']=='authorized_change' and not any(all(item.get(k)==a.get(k) for k in ('category','before','after')) for a in (authorized_changes or [])): fail('E_PERMISSION','The exact invariant change needs explicit authorization.')
        if verdict=='authorized_change' and not any(x.get('status')=='authorized_change' for x in assessments): fail('E_PERMISSION','Authorized-change status needs an identified authorized change.')
        # Every scanner risk needs a corresponding reviewed category, not a global
        # "looks good" boolean. A scan cannot be silently dropped.
        for item in diff:
            if item['status']=='review_needed':
                matches=[a for a in assessments if a['category']==item['category'] and (a.get('before')==item['before'] if item['before'] is not None else a.get('after')==item['after'])]
                if matches: item.update(status=matches[0]['status'],reason=matches[0]['reason'])
        for item in assessments:
            diff.append({k:item.get(k) for k in ('category','source_span','before','after','status','reason')})
        statuses={x['status'] for x in diff}
        status='violation' if 'violation' in statuses or verdict=='violation' else 'review_needed' if 'review_needed' in statuses or verdict=='review_needed' else 'authorized_change' if 'authorized_change' in statuses else verdict
    return {'status':status,'invariant_diff':diff,'source_hash':text_hash(source),'draft_hash':text_hash(draft),'semantic_reviewed':semantic_review is not None,'limitations':['Lexical scans are candidate risks; entity, scope, obligation, causality and stance fidelity require explicit semantic assessment.']}


def writing_result(*, run_id, body, operation='write', source=None, source_version=None, variant_id='draft', length_metric='codepoints', semantic_review=None, authorized_changes=None, evidence_ids=None, evidence=None):
    if operation not in ('write','rewrite'): fail('E_SCHEMA','Unknown writing operation.')
    if operation=='rewrite':
        if source is None or not source_version: fail('E_MISSING_SOURCE','Rewrite requires source text and its version.')
        checked=compare_draft(source,body,semantic_review=semantic_review,authorized_changes=authorized_changes)
    else: checked={'status':'not_applicable','invariant_diff':[],'limitations':['New writing facts and personal experiences need supplied evidence or explicit hypothetical labeling.']}
    result={'run_id':run_id,'source_version':source_version,'variant_id':variant_id,'operation':operation,'body':body,'length_metric':length_metric,'actual_length':count_text(body,length_metric),'invariant_status':checked['status'],'invariant_diff':checked['invariant_diff'],'evidence_ids':list(evidence_ids or []),'limitations':checked['limitations']+(['Words use Unicode-whitespace splitting; codepoints are neither tokens nor visual graphemes.'])}
    validate_semantics('writing_result',result,{'evidence':evidence or {}})
    return result
