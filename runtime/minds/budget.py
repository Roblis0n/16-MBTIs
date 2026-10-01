"""Auditable soft action limits; unseen tokens and nested calls stay unknown."""
from copy import deepcopy
from .contracts import validate_semantics
from .errors import fail


def preflight(request, capabilities):
    from .contracts import validate_shape
    validate_semantics("request",request); validate_shape("capabilities",capabilities)
    if capabilities["native_delegation"] not in ("observed","documented"):
        if not request["permissions"]["allow_simulation"]: fail("E_CAPABILITY","原生委派不可用；未授权模拟。")
        return {"execution_mode":"single_context","isolation_status":"not_applicable","concurrency":1}
    if capabilities["isolation_status"]!="verified_clean": fail("E_CAPABILITY","隔离尚未验证，不能派发独立首轮。")
    h=capabilities["open_thread_cap"]; u=request["budget"]["concurrency_cap"]
    if h==0: fail("E_CAPABILITY","宿主没有可用线程。")
    cap=min(h,u) if h is not None and u is not None else 1
    return {"execution_mode":"native_sequential" if cap==1 else ("native_parallel" if cap>=request["n"] else "native_batched"),"isolation_status":capabilities["isolation_status"],"concurrency":cap}


def reserve_budget(action, run):
    validate_semantics("run_state",run); validate_semantics("action_intent",action)
    if action["run_id"]!=run["run_id"]: fail("E_SEMANTIC","预算不属于该运行。")
    out=deepcopy(run)
    out["spent_agent_turns"]+=action["budget_reservation"]["agent_turns"]
    out["spent_verification_actions"]+=action["budget_reservation"]["verification_actions"]
    validate_semantics("run_state",out)
    return out


def commit_observation(receipt):
    if not isinstance(receipt,dict) or not isinstance(receipt.get("receipt_ref"),str) or not receipt["receipt_ref"]: fail("E_SCHEMA","观察必须关联回执。")
    out={"receipt_ref":receipt["receipt_ref"]}
    for k in ("observed_tokens","observed_tool_calls"):
        value=receipt.get(k)
        if value is not None and (type(value) is not int or value<0): fail("E_SCHEMA","观察计数必须非负。")
        out[k]=value
    out["nested_calls"]="unknown"
    return out
