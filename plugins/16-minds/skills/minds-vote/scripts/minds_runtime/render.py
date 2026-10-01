"""Public-output rendering, with conservative secret refusal before storage."""
import hashlib
import html
import json
import re
from .contracts import check_json
from .errors import fail
from .tool_policy import request_object

SECRET = re.compile(r'(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{12,}|AKIA[A-Z0-9]{16})\b|(?:password|api[_ -]?key|access[_ -]?token|secret)\s*[:=]\s*\S+)', re.I)
HIDDEN = {'chain_of_thought', 'hidden_reasoning', 'private_reasoning', 'scratchpad', 'credentials', 'password', 'api_key', 'access_token'}

def public_payload(value):
    check_json(value)
    def walk(v):
        if isinstance(v, dict):
            if any(k.lower() in HIDDEN or re.search(r'(?:password|secret|credential|(?:api|access)[_-]?key|access[_-]?token|private[_-]?key)',k,re.I) for k in v): fail('E_PERMISSION', 'Private reasoning or credential fields cannot be exported.')
            return {k: walk(x) for k,x in v.items()}
        if isinstance(v,list): return [walk(x) for x in v]
        if isinstance(v,str):
            if SECRET.search(v): fail('E_PERMISSION', 'Possible sensitive content prevents saving; supply a reviewed public summary.')
            # Data remains data even in a spreadsheet-like consumer.
            return "'"+v if v.lstrip().startswith(('=', '+', '-', '@')) else v
        return v
    return walk(value)

def render(value, format='json'):
    clean=public_payload(value)
    if format=='json': return json.dumps(clean, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    if format!='markdown': fail('E_SCHEMA', 'Only JSON and Markdown exports are supported.')
    def escape(v):
        s=re.sub(r'([\\`*{}_\[\]()#!|>])', r'\\\1', str(v))
        return html.escape(s, quote=True).replace('\n','  \n')
    return '# Public run summary\n\n'+ '\n'.join('- '+escape(k)+': '+escape(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in (clean.items() if isinstance(clean,dict) else [('result',clean)]))+'\n'

def dispatch(data):
    if not isinstance(data,dict) or 'payload' not in data: fail('E_SCHEMA','Rendering requires payload.')
    request_object(data, {'payload'}, {'format'})
    text=render(data['payload'],data.get('format','json'))
    return {'status':'ok', 'format':data.get('format','json'),'text':text, 'source_sha256':hashlib.sha256(json.dumps(data['payload'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(), 'rendered_sha256':hashlib.sha256(text.encode()).hexdigest(), 'display_escaped':public_payload(data['payload'])!=data['payload'], 'canonical_body':False}
