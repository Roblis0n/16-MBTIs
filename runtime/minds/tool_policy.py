"""Data-only authorization gate. This does not replace the host sandbox."""
import copy
import hashlib
import re
from urllib.parse import urlsplit
from pathlib import Path
from .contracts import check_json, canonical
from .errors import fail

ACTIONS = {'read_supplied', 'public_retrieval', 'controlled_test', 'save', 'write_source', 'send', 'install', 'delete', 'publish'}
FORBIDDEN = {'.ssh', '.aws', '.gnupg', '.env', 'credentials', 'cookies', 'login data'}

def security_event(action, allowed, reason):
    return {'action': action if isinstance(action,str) and action in ACTIONS else 'unknown', 'allowed': bool(allowed), 'reason': reason, 'payload_recorded': False}

def authorize_action(intent, permissions, capabilities):
    check_json([intent, permissions, capabilities])
    if not all(isinstance(x, dict) for x in (intent, permissions, capabilities)):
        fail('E_SCHEMA', 'Authorization inputs must be objects.')
    request_object(intent, {'action','authority','target'}, {'network'}, {'network'})
    request_object(permissions, {'actions'}, {'paths','urls','targets','scripts_reviewed','isolation_verified','execution_approved','network_approved'}, {'scripts_reviewed','isolation_verified','execution_approved','network_approved'})
    if any(k not in ACTIONS or type(v) is not bool for k,v in capabilities.items()): fail('E_SCHEMA','Capabilities must map supported actions to booleans.')
    for k in ('actions','paths','urls','targets'):
        if k in permissions and (not isinstance(permissions[k],list) or any(not isinstance(x,str) for x in permissions[k])): fail('E_SCHEMA','Permission scopes must be string arrays.')
    action = intent.get('action')
    if not isinstance(action,str) or action not in ACTIONS or intent.get('authority') not in ('user', 'host'):
        fail('E_PERMISSION', 'Action lacks current user or host authority.')
    if capabilities.get(action) is not True or action not in permissions.get('actions', []):
        fail('E_PERMISSION', 'Action is outside the granted capability and scope.')
    target = intent.get('target')
    if not isinstance(target, str) or not target:
        fail('E_SCHEMA', 'Action requires a bounded target.')
    if any(x.lower() in FORBIDDEN or re.search(r'(?:credential|password|secret|token|private[_-]?key|application_default_credentials)',x,re.I) for x in re.split(r'[/\\]', target)):
        fail('E_PERMISSION', 'Credential and authentication material is outside plugin scope.')
    if action == 'public_retrieval':
        u=urlsplit(target)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or target not in permissions.get('urls', []):
            fail('E_PERMISSION', 'URL is not explicitly allowed; redirects require a new check.')
    elif action in {'read_supplied', 'save', 'write_source', 'delete', 'controlled_test'}:
        # Exact supplied targets avoid implicit recursive grants or prefix confusion.
        if target not in permissions.get('paths', []):
            fail('E_PERMISSION', 'Target is not in the exact supplied-material allowlist.')
        if '..' in Path(target).parts or target.startswith('~'):
            fail('E_PERMISSION', 'Ambiguous paths are not authorized.')
    elif target not in permissions.get('targets', []):
        fail('E_PERMISSION', 'Destination is not explicitly authorized.')
    if action == 'controlled_test':
        if any(permissions.get(k) is not True for k in ('scripts_reviewed', 'isolation_verified', 'execution_approved')):
            fail('E_PERMISSION', 'Tests require reviewed scripts, verified isolation, and execution approval.')
        if intent.get('network', False) and permissions.get('network_approved') is not True:
            fail('E_PERMISSION', 'Test network side effects are not authorized.')
    return security_event(action, True, 'current_scope_match')

def sanitize_untrusted_payload(payload, source='external'):
    check_json(payload)
    if not isinstance(source,str): fail('E_SCHEMA','Untrusted source label must be a string.')
    # Quoting is not a security boundary; no text is promoted into permissions.
    return {'trust': 'untrusted_data', 'source': str(source)[:120], 'sha256': hashlib.sha256(canonical(payload).encode()).hexdigest(),
            'payload': copy.deepcopy(payload), 'authority': None, 'instructions_executable': False}

def dispatch(data):
    if not isinstance(data, dict): fail('E_SCHEMA', 'Expected an authorization object.')
    if data.get('action') == 'sanitize':
        request_object(data, {'action','payload'}, {'source'})
        if 'source' in data and not isinstance(data['source'],str): fail('E_SCHEMA','Source must be a string.')
        return {'status': 'ok', 'data': sanitize_untrusted_payload(data.get('payload'), data.get('source', 'external'))}
    request_object(data, {'intent','permissions','capabilities'})
    return {'status': 'ok', 'authorization': authorize_action(data.get('intent'), data.get('permissions'), data.get('capabilities'))}

def request_object(data, required=(), optional=(), booleans=()):
    """Strict helper command envelope shared by the safety modules."""
    check_json(data)
    if not isinstance(data,dict) or not set(required)<=data.keys() or data.keys()-(set(required)|set(optional)):
        fail('E_SCHEMA','Request contains missing or unknown fields.')
    for k in booleans:
        if k in data and type(data[k]) is not bool: fail('E_SCHEMA','Boolean options must be true or false.')
    return data
