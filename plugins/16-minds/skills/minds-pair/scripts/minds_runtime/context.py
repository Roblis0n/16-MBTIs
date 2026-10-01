"""Immutable-by-copy round barriers and lossless public-history restoration."""
from copy import deepcopy
import hashlib
from .contracts import canonical,check_json
from .errors import fail


def _digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()


def build_round_snapshot(state):
    """Read only prior rounds, even when current-round results already exist."""
    check_json(state)
    reducer=state["reducer"]; run=reducer["run"]
    previous=[deepcopy(r["result"]) for r in reducer["results"].values() if r["disposition"]=="accepted" and r["result"]["round"]<run["round"]]
    previous.sort(key=lambda x:(x["round"],x["actor_id"],x["result_revision"]))
    prior=run["round"]-1
    seen={r["actor_id"] for r in previous if r["round"]==prior}
    out={"protocol_version":run["protocol_version"],"run_id":run["run_id"],"input_hash":run["input_hash"],"round":run["round"],
         "actor_ids":deepcopy(run["actor_ids"]),"persona_revision":state["persona_revision"],"evidence_version":state["evidence_version"],
         "common_facts":deepcopy(state["common_facts"]),"personas":deepcopy(state["personas"]),"previous_results":previous,
         "missing_actor_ids":[a for a in run["actor_ids"] if prior and a not in seen],"task":deepcopy(state["round_task"])}
    out["snapshot_hash"]=_digest(out)
    return out


def build_actor_context(snapshot,actor_id):
    check_json(snapshot)
    fields={"protocol_version","run_id","input_hash","round","actor_ids","persona_revision","evidence_version","common_facts","personas","previous_results","missing_actor_ids","task","snapshot_hash"}
    if not isinstance(snapshot,dict) or set(snapshot)!=fields: fail("E_SCHEMA","快照字段错误。")
    if not isinstance(snapshot["actor_ids"],list) or not isinstance(snapshot["personas"],dict) or not isinstance(snapshot["previous_results"],list) or not isinstance(snapshot["common_facts"],dict): fail("E_SCHEMA","快照类型错误。")
    if any(not isinstance(a,str) for a in snapshot["actor_ids"]) or type(snapshot["round"]) is not int: fail("E_SCHEMA","快照身份或轮次错误。")
    if set(snapshot["actor_ids"])!=set(snapshot["personas"]): fail("E_CONTEXT_INCOMPLETE","快照缺少角色。")
    from .contracts import validate_shape
    for result in snapshot["previous_results"]:
        validate_shape("agent_result",result)
        if result["round"]>=snapshot["round"]: fail("E_CONTEXT_INCOMPLETE","快照包含同轮或未来结果。")
    copy=deepcopy(snapshot); digest=copy.pop("snapshot_hash",None)
    if digest!=_digest(copy): fail("E_CONTEXT_INCOMPLETE","冻结快照被修改。")
    if actor_id not in copy["actor_ids"]: fail("E_SEMANTIC","未知角色。")
    history=[r for r in copy["previous_results"] if r["actor_id"]==actor_id]
    claims=[c for r in history for c in r["claims"]]
    return {"run_id":copy["run_id"],"actor_id":actor_id,"round":copy["round"],"input_hash":copy["input_hash"],
        "protocol_version":copy["protocol_version"],"persona_revision":copy["personas"][actor_id]["revision"],"evidence_version":copy["evidence_version"],
        "snapshot_hash":digest,"common_facts":copy["common_facts"],"persona":None if copy["common_facts"].get("voice")=="neutral" else copy["personas"][actor_id],"task":copy["task"],
        "own_history":history,"peer_previous_results":[r for r in copy["previous_results"] if r["actor_id"]!=actor_id],
        "original_claims":claims,"limitations":[x for r in history for x in r["limitations"]],
        "seen_evidence_ids":sorted({e for c in claims for e in c["evidence_ids"]}),
        "included_claims":[c["claim_id"] for c in claims],"omitted_claims":[],"source_refs":[r["action_id"] for r in history],
        "context_complete":not copy["missing_actor_ids"],"missing_actor_ids":copy["missing_actor_ids"],
        "instructions":"Do not delegate or spawn nested agents. Do not run tools or access outside supplied material. Preserve negations, numbers, exceptions and uncertainty. Only return the public result contract."}


def restore_actor(public_state):
    check_json(public_state)
    if not isinstance(public_state,dict) or not public_state.get("context_complete") or public_state.get("omitted_claims"):
        fail("E_CONTEXT_INCOMPLETE","公开历史不完整，不能恢复。")
    for key in ("input_hash","protocol_version","persona_revision","evidence_version","own_history","original_claims","limitations"):
        if key not in public_state: fail("E_CONTEXT_INCOMPLETE","恢复缺少冻结版本或历史。")
    return deepcopy(public_state)
