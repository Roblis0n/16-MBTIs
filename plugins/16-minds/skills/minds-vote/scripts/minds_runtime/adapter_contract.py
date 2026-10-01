"""Pure host boundary. No SDK, dispatch, network, persistence, or synthetic receipts."""
from .contracts import validate_semantics, validate_shape, canonical
from .errors import fail
import hashlib


def prepare_action(run, actor, round, *, kind="spawn", attempt=1, payload_ref=None, host_schema_hash=None, permission_ref=None):
    validate_semantics("run_state", run)
    if actor is not None and actor not in run["actor_ids"]: fail("E_SEMANTIC", "未知角色。")
    if type(attempt) is not int or attempt < 1: fail("E_SCHEMA", "attempt 必须为正整数。")
    identity=[run["run_id"],actor,round,kind,attempt,payload_ref]
    intent={"protocol_version":"1.0.0", "action_id":"act-"+hashlib.sha256(canonical(identity).encode()).hexdigest()[:32],
        "run_id":run["run_id"],"kind":kind,"actor_id":actor,"round":round,"input_hash":run["input_hash"],
        "payload_ref":payload_ref,"budget_reservation":{"agent_turns":int(kind in ("spawn","send")),"verification_actions":int(kind=="verify")},
        "host_schema_hash":host_schema_hash,"permission_ref":permission_ref,"dispatch_status":"proposed","host_receipt_ref":None}
    validate_semantics("action_intent",intent,{**({"actor_ids":run["actor_ids"]} if actor is not None else {}),"run_id":run["run_id"],"input_hash":run["input_hash"]})
    return intent


def record_receipt(intent, actual_host_result):
    """The caller must supply an externally retained receipt, never infer success."""
    validate_shape("action_intent",intent)
    r=actual_host_result
    if not isinstance(r,dict) or set(r)!={"action_id","host_thread_id","receipt_ref"} or r["action_id"]!=intent["action_id"]:
        fail("E_SCHEMA","宿主回执身份不匹配。")
    if not isinstance(r["receipt_ref"],str) or not r["receipt_ref"]: fail("E_CAPABILITY","缺少实际宿主回执。")
    if r["host_thread_id"] is not None and (not isinstance(r["host_thread_id"],str) or not r["host_thread_id"]): fail("E_SCHEMA","线程身份非法。")
    if intent["kind"]=="spawn" and r["host_thread_id"] is None: fail("E_CAPABILITY","创建线程缺少实际身份。")
    return {"kind":"receipt",**r}


def isolation_parameters(exposed_fields):
    """Map only fields explicitly exposed by the selected host schema."""
    if not isinstance(exposed_fields,list) or any(not isinstance(x,str) for x in exposed_fields): fail("E_SCHEMA","需要宿主字段列表。")
    if "fork_turns" in exposed_fields: return {"fork_turns":"none"}
    if "fork_context" in exposed_fields: return {"fork_context":False}
    return {}
