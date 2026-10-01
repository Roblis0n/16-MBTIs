"""Deterministic in-memory scheduler. Host assistant owns every actual tool call.

Persisting envelopes is separately opt-in. Synthetic drivers prove protocol behavior,
not host isolation, cancellation, tools, token cost, or physical thread cleanup.
"""
from copy import deepcopy
from .contracts import canonical, validate_semantics, check_json
from .errors import fail
from .state import new_reducer_state, reduce_state
from .adapter_contract import prepare_action
from .budget import preflight
from .context import build_round_snapshot, build_actor_context, _digest
from .personas import load_persona

TERMINAL={"completed","partial","failed","cancelled","blocked"}
ACTIVE={"queued","dispatched","running","dispatch_unknown"}


def _resolved_profile(profile_id, permissions, voice, supplied):
    if profile_id is None: return None
    from .profiles import compose_checks
    grants=[category for field,category in (("read_supplied","read_supplied"),("network","public_retrieval"),("run_untrusted_code","controlled_test")) if permissions.get(field) is True]
    resolved=compose_checks(profile_id,permissions=grants,voice=voice)
    if not isinstance(supplied,dict): fail("E_CONTEXT_INCOMPLETE","Profile requires explicitly supplied input fields.")
    missing=[key for key in resolved["main"]["required_inputs"] if key not in supplied or supplied[key] is None or supplied[key]==""]
    if missing: fail("E_CONTEXT_INCOMPLETE","Missing profile inputs: "+", ".join(missing))
    return resolved


def prepare_run(request, roster, capabilities, *, run_id, common_facts=None, persona_revision="1.0.0", evidence_version="1.0.0", permission_ref=None, parent_run_id=None):
    p=preflight(request,capabilities)
    validate_semantics("roster",roster,{"locked_personas":request["locked_personas"]})
    if roster["requested_n"]!=request["n"] or roster["run_id"]!=run_id: fail("E_SEMANTIC","名单和请求身份不一致。")
    if request["selection"]["preview_only"]: fail("E_PERMISSION","预览请求不能运行。")
    profile_contract=_resolved_profile(request["profile"],request["permissions"],request["voice"],common_facts)
    actors=[m["actor_id"] for m in roster["members"]]
    personas={a:load_persona(a) for a in actors}
    facts={"voice":request["voice"],"task_kind":request["task_kind"],"profile":request["profile"],"presentation":request["presentation"],"budget":deepcopy(request["budget"]),"question":request["question"],"source_text":request["source_text"],"workflow_options":request["workflow_options"],"permissions":request["permissions"],"input_refs":request["input_refs"],"supplied":common_facts}
    facts=deepcopy(facts)
    facts["profile_contract"]=profile_contract
    digest=_digest({"request":request,"roster":roster,"common_facts":facts,"persona_revision":persona_revision,"evidence_version":evidence_version,"personas":personas})
    run={"protocol_version":"1.0.0","run_id":run_id,"parent_run_id":parent_run_id,"status":"running","execution_mode":p["execution_mode"],"isolation_status":p["isolation_status"],"input_hash":digest,"round":1,"actor_ids":actors,"completed_actor_ids":[],"spent_agent_turns":0,"spent_verification_actions":0,"budget":deepcopy(request["budget"]),"pending_action_ids":[],"residual_thread_ids":[],"cleanup_status":"not_required","stop_reason":None,"observed_tokens":None,"observed_tool_calls":None,"events_ref":None}
    s={"scheduler_version":"1.0.0","reducer":new_reducer_state(run),"capabilities":deepcopy(capabilities),"concurrency":p["concurrency"],"permission_ref":permission_ref,"persona_revision":persona_revision,"evidence_version":evidence_version,"common_facts":facts,"personas":personas,"round_task":{"kind":"initial"},"snapshots":{},"elapsed_seconds":0,"control_intents":{},"verification_plans":{}}
    s["snapshots"]["1"]=build_round_snapshot(s)
    return s


def _validate(state):
    check_json(state)
    if not isinstance(state,dict) or state.get("scheduler_version")!="1.0.0": fail("E_SCHEMA","调度状态版本错误。")
    fields={"scheduler_version","reducer","capabilities","concurrency","permission_ref","persona_revision","evidence_version","common_facts","personas","round_task","snapshots","elapsed_seconds","control_intents","verification_plans"}
    if set(state)!=fields: fail("E_SCHEMA","调度状态字段缺失或未知。")
    for key in ("reducer","capabilities","common_facts","personas","round_task","snapshots","control_intents","verification_plans"):
        if not isinstance(state[key],dict): fail("E_SCHEMA","调度状态字段类型错误。")
    if set(state["reducer"])!={"reducer_version","run","tasks","results","events","quarantine"}: fail("E_SCHEMA","ReducerState 字段错误。")
    if not isinstance(state["reducer"]["tasks"],dict) or not isinstance(state["reducer"]["results"],dict): fail("E_SCHEMA","任务存储错误。")
    from .contracts import validate_shape
    validate_shape("capabilities",state["capabilities"])
    validate_semantics("run_state",state["reducer"]["run"])
    run=state["reducer"]["run"]
    if type(state["elapsed_seconds"]) not in (int,float) or state["elapsed_seconds"]<0: fail("E_SCHEMA","累计时间错误。")
    if set(state["personas"])!=set(run["actor_ids"]): fail("E_CONTEXT_INCOMPLETE","角色资料集合错误。")
    for actor,p in state["personas"].items():
        validate_shape("persona",p)
        if p["id"]!=actor: fail("E_CONTEXT_INCOMPLETE","角色资料身份错误。")
    snap=state["snapshots"].get(str(run["round"]))
    if not isinstance(snap,dict): fail("E_CONTEXT_INCOMPLETE","缺少当前冻结快照。")
    for k in ("run_id","input_hash","round"):
        if snap.get(k)!=run[k]: fail("E_CONTEXT_INCOMPLETE","快照与运行身份不一致。")
    build_actor_context(snap,run["actor_ids"][0])
    facts=state["common_facts"]
    if facts!=snap["common_facts"] or state["personas"]!=snap["personas"]: fail("E_CONTEXT_INCOMPLETE","Current inputs differ from the frozen round snapshot.")
    if not {"profile","profile_contract","permissions","voice","supplied"}<=facts.keys() or not isinstance(facts["permissions"],dict): fail("E_SCHEMA","Missing frozen profile and permission context.")
    expected_profile=_resolved_profile(facts["profile"],facts["permissions"],facts["voice"],facts["supplied"])
    if facts["profile_contract"]!=expected_profile: fail("E_CONTEXT_INCOMPLETE","Frozen profile differs from registered constraints; prepare a new run.")
    for aid,plan in state["verification_plans"].items():
        if not isinstance(plan,dict) or set(plan)!={"intent","attempt_id","task"} or plan["attempt_id"]!="verification-1": fail("E_SCHEMA","Malformed verification plan.")
        _check_verification_task(plan["task"],plan["intent"].get("permission_ref") if isinstance(plan["intent"],dict) else None,facts)
        expected_intent=prepare_action(run,None,plan["intent"].get("round"),kind="verify",payload_ref="sha256:"+_digest(plan["task"]),permission_ref=plan["intent"].get("permission_ref"),host_schema_hash=state["capabilities"]["tool_schema_hash"])
        if plan["intent"]!=expected_intent or aid!=expected_intent["action_id"]: fail("E_SEMANTIC","Verification intent differs from its frozen task.")
    unreserved=sum(aid not in state["reducer"]["tasks"] for aid in state["verification_plans"])
    if run["spent_verification_actions"]+unreserved>run["budget"]["max_verification_actions"]: fail("E_BUDGET_EXHAUSTED","Queued verification exceeds remaining budget.")
    for task in state["reducer"]["tasks"].values():
        if not isinstance(task,dict) or not {"intent","attempt_id","status","host_thread_id","receipt_ref"}<=task.keys(): fail("E_SCHEMA","任务记录错误。")
        validate_shape("action_intent",task["intent"])
        from .state import TASK_EDGES
        if not isinstance(task["status"],str) or task["status"] not in TASK_EDGES or not isinstance(task["attempt_id"],str): fail("E_SCHEMA","任务状态或身份错误。")
    if state["permission_ref"] is not None and not isinstance(state["permission_ref"],str): fail("E_SCHEMA","权限引用错误。")
    if type(state["concurrency"]) is not int or state["concurrency"]<1: fail("E_SCHEMA","并发上限非法。")


def _close_actions(state, ids):
    run=state["reducer"]["run"]
    if state["capabilities"]["close_supported"] is not True: return []
    return [{"intent":prepare_action(run,None,run["round"],kind="close",payload_ref=t),"host_thread_id":t} for t in ids if not any(i["payload_ref"]==t for i in state["control_intents"].values())]


def next_actions(state):
    """Return repeatable proposals. Register an intent with step before calling host."""
    _validate(state); r=state["reducer"]; run=r["run"]; tasks=r["tasks"]
    if run["status"] in TERMINAL: return _close_actions(state,run["residual_thread_ids"])
    if run["status"]!="running" or run["execution_mode"]=="single_context": return []
    if any(t["status"]=="dispatch_unknown" for t in tasks.values()): return []
    verification=[deepcopy(p) for aid,p in state["verification_plans"].items() if aid not in tasks]
    if verification: return verification[:1]
    active_threads={t["host_thread_id"] for t in tasks.values() if t["status"] in ACTIVE}
    idle=[t for t in run["residual_thread_ids"] if t not in active_threads]
    closes=_close_actions(state,idle)
    if closes: return closes
    open_count=len(run["residual_thread_ids"])+sum(t["status"]=="queued" for t in tasks.values())
    slots=max(0,state["concurrency"]-open_count)
    remaining=run["budget"]["max_agent_turns"]-run["spent_agent_turns"]
    snapshot=state["snapshots"][str(run["round"])]
    actions=[]
    for actor in run["actor_ids"]:
        current=[t for t in tasks.values() if t["intent"]["actor_id"]==actor and t["intent"]["round"]==run["round"]]
        if any(t["status"] in ACTIVE or t["status"]=="succeeded" for t in current): continue
        if current and (any(t["status"]!="invalid_output" for t in current) or len(current)>run["budget"]["max_repairs_per_result"]): continue
        if not slots or not remaining: break
        context=build_actor_context(snapshot,actor)
        if run["round"]>1 and not context["context_complete"]: fail("E_CONTEXT_INCOMPLETE","上轮公开历史不完整。")
        attempt=len(current)+1
        if current: context["repair_instruction"]="Repair syntax or structure only. Preserve stance, refusal, uncertainty and all substantive content."
        intent=prepare_action(run,actor,run["round"],attempt=attempt,payload_ref="sha256:"+_digest(context),host_schema_hash=state["capabilities"]["tool_schema_hash"],permission_ref=state["permission_ref"])
        actions.append({"intent":intent,"attempt_id":f"attempt-{attempt}","context":context})
        slots-=1; remaining-=1
    return actions


def step(state,event):
    _validate(state); check_json(event); s=deepcopy(state)
    if not isinstance(event,dict) or "kind" not in event: fail("E_SCHEMA","缺少事件类型。")
    if event["kind"]=="intent":
        proposed=next_actions(state)
        match=next((a for a in proposed if a["intent"]==event.get("intent")),None)
        aid=event.get("intent",{}).get("action_id")
        old=s["reducer"]["tasks"].get(aid)
        if old and old["intent"]==event["intent"] and old["attempt_id"]==event.get("attempt_id"):
            return {"state":s,"actions":next_actions(s)}
        if aid in s["control_intents"] and s["control_intents"][aid]==event["intent"]: return {"state":s,"actions":next_actions(s)}
        if match is None: fail("E_PERMISSION","动作不在当前调度计划中。")
        if event["intent"]["kind"]=="close": s["control_intents"][aid]=deepcopy(event["intent"])
        else:
            if event.get("attempt_id")!=match["attempt_id"]: fail("E_SEMANTIC","attempt 不匹配。")
            s["reducer"]=reduce_state(s["reducer"],event)
    elif event["kind"]=="elapsed":
        value=event.get("seconds")
        if set(event)!={"kind","seconds"} or type(value) not in (int,float) or value<s["elapsed_seconds"]: fail("E_SCHEMA","累计时间必须单调递增。")
        s["elapsed_seconds"]=value
        if value>=s["reducer"]["run"]["budget"]["soft_deadline_seconds"] and s["reducer"]["run"]["status"] not in TERMINAL:
            s["reducer"]=reduce_state(s["reducer"],{"kind":"transition","to":"partial","reason":"soft_deadline"})
    elif event["kind"]=="result":
        from .contracts import validate_shape
        validate_shape("agent_result",event.get("result"))
        event=deepcopy(event); event["context"]={**event.get("context",{}),"persona_revision":s["personas"].get(event["result"].get("actor_id"),{}).get("revision",s["persona_revision"])}
        s["reducer"]=reduce_state(s["reducer"],event)
    elif event["kind"]=="cleanup":
        # Cleanup requires a previously registered close intent for every ID.
        if not set(event.get("closed_thread_ids",[])) <= {i["payload_ref"] for i in s["control_intents"].values()}: fail("E_PERMISSION","清理没有已登记的 close intent。")
        s["reducer"]=reduce_state(s["reducer"],event)
    else:
        if event["kind"]=="transition" and (event.get("to")=="running" or "round" in event or "input_hash" in event):
            fail("E_PERMISSION","轮次与输入只能由调度器推进。")
        s["reducer"]=reduce_state(s["reducer"],event)
    return {"state":s,"actions":next_actions(s)}


def advance_round(state, task):
    _validate(state); run=state["reducer"]["run"]
    if not isinstance(task,dict) or not (task.get("target_claim_id") or task.get("new_evidence_task")): fail("E_SEMANTIC","后续轮需要目标主张或新证据任务。")
    if run["status"]!="running" or run["pending_action_ids"] or set(run["completed_actor_ids"])!=set(run["actor_ids"]): fail("E_CONTEXT_INCOMPLETE","上轮未完成。")
    if run["residual_thread_ids"]: fail("E_CAPABILITY","先确认关闭上一轮线程。")
    if run["budget"]["max_agent_turns"]-run["spent_agent_turns"]<len(run["actor_ids"]): fail("E_BUDGET_EXHAUSTED","预算不足完整下一轮。")
    s=deepcopy(state); s["reducer"]=reduce_state(s["reducer"],{"kind":"transition","to":"running","round":run["round"]+1})
    s["round_task"]=deepcopy(task); s["snapshots"][str(s["reducer"]["run"]["round"])]=build_round_snapshot(s)
    return s


def cancel_run(state):
    _validate(state); s=deepcopy(state)
    if s["reducer"]["run"]["status"] not in TERMINAL: s["reducer"]=reduce_state(s["reducer"],{"kind":"transition","to":"cancelled","reason":"user_cancelled"})
    if s["reducer"]["run"]["residual_thread_ids"]: s["reducer"]["run"]["cleanup_status"]="unknown"
    return {"state":s,"actions":next_actions(s)}


def resume_run(state, versions):
    _validate(state)
    run=state["reducer"]["run"]
    expected={"input_hash":run["input_hash"],"protocol_version":run["protocol_version"],"persona_revision":state["persona_revision"],"evidence_version":state["evidence_version"]}
    if versions!=expected: fail("E_CONTEXT_INCOMPLETE","关键版本变化；新建 run 并关联 parent_run_id。")
    if run["status"] in TERMINAL: fail("E_SEMANTIC","终态不能恢复；需要新 run。")
    if any(t["status"]=="dispatch_unknown" for t in state["reducer"]["tasks"].values()): fail("E_DISPATCH_UNKNOWN","先核实已有派发，禁止重发。")
    if run["spent_agent_turns"]>=run["budget"]["max_agent_turns"] and not run["pending_action_ids"]: fail("E_BUDGET_EXHAUSTED","无剩余预算。")
    for actor in run["actor_ids"]: build_actor_context(state["snapshots"][str(run["round"])],actor)
    return deepcopy(state)


def dispatch(data):
    """JSON facade: exact {op, ...operation-specific fields}; reject unknown keys."""
    if not isinstance(data,dict): fail("E_SCHEMA","执行请求必须是对象。")
    operations={
        "prepare":({"request","roster","capabilities","run_id"},{"common_facts","persona_revision","evidence_version","permission_ref","parent_run_id"},prepare_run),
        "step":({"state","event"},set(),step),"actions":({"state"},set(),next_actions),
        "advance":({"state","task"},set(),advance_round),"cancel":({"state"},set(),cancel_run),
        "resume":({"state","versions"},set(),resume_run),
        "context":({"snapshot","actor_id"},set(),build_actor_context),
        "preflight":({"request","capabilities"},set(),preflight),
        "verify":({"state","task","permission_ref"},set(),request_verification),
        "status":({"state"},set(),scheduler_status)}
    from .adapter_contract import record_receipt
    operations["receipt"]=({"intent","actual_host_result"},set(),record_receipt)
    op=data.get("op")
    if not isinstance(op,str) or op not in operations: fail("E_SCHEMA","未知调度操作。")
    required,optional,fn=operations[op]; args={k:v for k,v in data.items() if k!="op"}
    if not required<=args.keys() or args.keys()-(required|optional): fail("E_SCHEMA","调度字段缺失或未知。")
    return fn(**args)


def request_verification(state, task, permission_ref):
    """Register one explicit supplied-material or network verification proposal."""
    _validate(state); s=deepcopy(state); run=s['reducer']['run']
    if run['status']!='running': fail('E_PERMISSION','只有运行中的任务可请求核查。')
    _check_verification_task(task,permission_ref,s["common_facts"])
    queued=sum(aid not in s['reducer']['tasks'] for aid in s['verification_plans'])
    intent=prepare_action(run,None,run['round'],kind='verify',payload_ref='sha256:'+_digest(task),permission_ref=permission_ref,host_schema_hash=s['capabilities']['tool_schema_hash'])
    if intent['action_id'] in s['verification_plans']: return s
    if run['spent_verification_actions']+queued>=run['budget']['max_verification_actions']: fail('E_BUDGET_EXHAUSTED','核查预算用尽。')
    s['verification_plans'][intent['action_id']]={'intent':intent,'attempt_id':'verification-1','task':deepcopy(task)}
    return s


def scheduler_status(state):
    _validate(state); run=state['reducer']['run']; blocker=None
    if any(t['status']=='dispatch_unknown' for t in state['reducer']['tasks'].values()): blocker='dispatch_unknown: reconcile actual host receipt before new work'
    elif run['residual_thread_ids'] and state['capabilities']['close_supported'] is not True: blocker='cleanup_unavailable: physical threads remain open; capacity cannot be reclaimed'
    elif run['execution_mode']=='single_context': blocker='simulation_driver_required: no native actions emitted'
    elif not run['pending_action_ids'] and run['spent_agent_turns']>=run['budget']['max_agent_turns']: blocker='agent_turn_budget_exhausted'
    return {'status':run['status'],'blocker':blocker,'remaining_agent_turns':run['budget']['max_agent_turns']-run['spent_agent_turns'],'remaining_verification_actions':run['budget']['max_verification_actions']-run['spent_verification_actions'],'residual_thread_ids':deepcopy(run['residual_thread_ids']),'cleanup_status':run['cleanup_status'],'actions':next_actions(state)}


def _check_verification_task(task,permission_ref,facts):
    if not isinstance(task,dict) or set(task)!={'kind','question','source_ref'} or task['kind'] not in ('supplied_material','network') or any(not isinstance(task[k],str) or not task[k].strip() for k in ('question','source_ref')):
        fail('E_SCHEMA','核查需要类型、具体问题与来源引用。')
    if not isinstance(permission_ref,str) or not permission_ref: fail('E_PERMISSION','核查缺少授权引用。')
    permissions=facts['permissions']
    profile=facts['profile_contract']
    category='public_retrieval' if task['kind']=='network' else 'read_supplied'
    if profile is not None and category not in profile['main']['effective_tools']: fail('E_PERMISSION','Verification exceeds the frozen profile tool categories.')
    if not permissions.get('read_supplied') or (task['kind']=='network' and not permissions.get('network')): fail('E_PERMISSION','核查超出冻结权限。')
