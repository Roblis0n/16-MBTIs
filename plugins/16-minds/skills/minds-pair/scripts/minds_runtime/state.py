"""Pure event reducer; records supplied intents/receipts, never dispatches tools.

ReducerState wraps unchanged C02 RunState with in-memory event/task/result stores.
No wall clock reads: deadline/timeout facts must arrive as explicit host events.
"""
from copy import deepcopy
import hashlib
from .contracts import canonical, check_json, validate_semantics, validate_shape
from .errors import fail
from .resources import resource_json

TASK_EDGES={
    "queued":{"dispatched","dispatch_unknown","cancelled","failed"},
    "dispatched":{"running","succeeded","invalid_output","timed_out","failed","cancelled","cleanup_unknown"},
    "running":{"succeeded","invalid_output","timed_out","failed","cancelled","cleanup_unknown"},
    "dispatch_unknown":{"dispatched","failed","cancelled","cleanup_unknown"},
    "succeeded":set(),"invalid_output":set(),"timed_out":set(),"failed":set(),"cancelled":set(),"cleanup_unknown":set()}
EVENT_FIELDS={
    "transition":({"kind","to"},{"reason","input_hash","round"}),
    "intent":({"kind","intent","attempt_id"},set()),
    "receipt":({"kind","action_id","host_thread_id","receipt_ref"},set()),
    "task_status":({"kind","action_id","status","receipt_ref"},set()),
    "result":({"kind","result"},{"context"}),
    "wait_timeout":({"kind","action_id"},set()),
    "cleanup":({"kind","closed_thread_ids","receipt_ref"},set())}

def new_reducer_state(run):
    validate_semantics("run_state",run)
    return {"reducer_version":"1.0.0","run":deepcopy(run),"tasks":{},"results":{},"events":[],"quarantine":[]}

def _event_shape(event):
    check_json(event)
    if not isinstance(event,dict) or not isinstance(event.get("kind"),str) or event["kind"] not in EVENT_FIELDS: fail("E_SCHEMA","未知状态事件。",layer="shape")
    required,optional=EVENT_FIELDS[event["kind"]]
    if not required<=event.keys() or event.keys()-(required|optional): fail("E_SCHEMA","状态事件缺少字段或含未知字段。",layer="shape")
    for key in ("action_id","attempt_id","receipt_ref","to","status","reason","input_hash"):
        if key in event and (not isinstance(event[key],str) or not event[key]): fail("E_SCHEMA","状态事件身份字段必须为非空字符串。",layer="shape")
    if "host_thread_id" in event and event["host_thread_id"] is not None and (not isinstance(event["host_thread_id"],str) or not event["host_thread_id"]): fail("E_SCHEMA","物理线程身份非法。",layer="shape")
    if "round" in event and type(event["round"]) is not int: fail("E_SCHEMA","轮次必须为整数。",layer="shape")
    if "context" in event and not isinstance(event["context"],dict): fail("E_SCHEMA","context 必须为对象。",layer="shape")
    if "closed_thread_ids" in event and (not isinstance(event["closed_thread_ids"],list) or any(not isinstance(x,str) for x in event["closed_thread_ids"])): fail("E_SCHEMA","关闭线程列表非法。",layer="shape")

def reduce_state(state,event):
    check_json(state); _event_shape(event)
    if not isinstance(state,dict) or set(state)!={"reducer_version","run","tasks","results","events","quarantine"} or state["reducer_version"]!="1.0.0": fail("E_SCHEMA","ReducerState 格式或版本错误。",layer="shape")
    if not all(isinstance(state[k],dict) for k in ("tasks","results")) or not all(isinstance(state[k],list) for k in ("events","quarantine")): fail("E_SCHEMA","ReducerState 存储类型错误。",layer="shape")
    validate_semantics("run_state",state["run"])
    for aid,task in state["tasks"].items():
        fields={"intent","attempt_id","status","host_thread_id","receipt_ref"}
        if not isinstance(task,dict) or not fields<=task.keys() or task.keys()-(fields|{"status_receipt_ref"}): fail("E_SCHEMA","任务记录结构非法。",layer="shape")
        if not isinstance(task["status"],str) or task["status"] not in TASK_EDGES or not isinstance(task["attempt_id"],str) or not task["attempt_id"]: fail("E_SCHEMA","任务状态或 attempt 身份非法。",layer="shape")
        validate_shape("action_intent",task["intent"])
        if aid!=task["intent"]["action_id"] or task["intent"]["run_id"]!=state["run"]["run_id"]: fail("E_SEMANTIC","任务索引与冻结身份不匹配。")
    for key,record in state["results"].items():
        if not isinstance(record,dict) or set(record)!={"hash","disposition","result"}: fail("E_SCHEMA","结果存储结构非法。",layer="shape")
        validate_shape("agent_result",record["result"])
        if record["hash"]!=hashlib.sha256(canonical(record["result"]).encode("utf-8")).hexdigest(): fail("E_SEMANTIC","存储结果哈希不一致。")
        expected_key=canonical([record["result"][k] for k in ("run_id","actor_id","round","attempt_id","action_id","result_revision")])
        if key!=expected_key: fail("E_SEMANTIC","存储结果身份不一致。")
    if not set(state["run"]["pending_action_ids"])<=state["tasks"].keys(): fail("E_SEMANTIC","pending action 没有对应任务记录。")
    s=deepcopy(state); run=s["run"]; kind=event["kind"]
    transitions=resource_json("contracts/state_transitions.json")
    terminal=not transitions[run["status"]]
    def log(disposition, **fields): s["events"].append({"kind":disposition,**fields})
    def conflict(message): fail("E_SEMANTIC",message)
    def task_for(aid):
        if aid not in s["tasks"]: conflict("事件关联了未知 action。")
        return s["tasks"][aid]
    if kind=="result":
        result=event["result"]; validate_shape("agent_result",result)
        if result["run_id"]!=run["run_id"]: conflict("结果属于其他运行。")
        digest=hashlib.sha256(canonical(result).encode("utf-8")).hexdigest()
        key=canonical([result[k] for k in ("run_id","actor_id","round","attempt_id","action_id","result_revision")])
        old=s["results"].get(key)
        if old:
            if old["hash"]==digest: log("duplicate_ignore",result_key=key)
            else:
                s["quarantine"].append({"kind":"conflicting_duplicate","result_key":key,"hash":digest,"result":result})
                log("conflicting_duplicate",result_key=key)
            return s
        if terminal:
            s["results"][key]={"hash":digest,"disposition":"late_result","result":result}
            log("late_result",result_key=key)
            return s
        task=task_for(result["action_id"]); intent=task["intent"]
        if (result["actor_id"],result["round"],result["attempt_id"],result["input_hash"])!=(intent["actor_id"],intent["round"],task["attempt_id"],intent["input_hash"]): conflict("结果与 action 冻结身份不一致。")
        if task["status"] not in ("dispatched","running"):
            s["quarantine"].append({"kind":"late_task_result","result":result}); log("late_task_result",action_id=intent["action_id"]); return s
        context={**event.get("context",{}),"run_id":run["run_id"],"actor_ids":run["actor_ids"],"input_hash":run["input_hash"]}
        validate_semantics("agent_result",result,context)
        s["results"][key]={"hash":digest,"disposition":"accepted","result":result}
        task["status"]="succeeded"
        if result["action_id"] in run["pending_action_ids"]: run["pending_action_ids"].remove(result["action_id"])
        if result["actor_id"] not in run["completed_actor_ids"]: run["completed_actor_ids"].append(result["actor_id"])
        log("result_accepted",result_key=key)
    elif terminal:
        # Only confirmed cleanup may change lifecycle bookkeeping, never published data.
        if kind=="receipt":
            task=task_for(event["action_id"])
            if task["receipt_ref"] and (task["receipt_ref"]!=event["receipt_ref"] or task["host_thread_id"]!=event["host_thread_id"]):
                s["quarantine"].append({"kind":"conflicting_receipt","event":event}); log("conflicting_duplicate",action_id=event["action_id"])
                return s
            task.update(receipt_ref=event["receipt_ref"],host_thread_id=event["host_thread_id"])
            tid=event["host_thread_id"]
            if tid is not None and tid not in run["residual_thread_ids"]:
                run["residual_thread_ids"].append(tid); run["cleanup_status"]="unknown"
            log("late_receipt",action_id=event["action_id"])
        elif kind=="cleanup":
            ids=set(event["closed_thread_ids"])
            if not ids<=set(run["residual_thread_ids"]): conflict("不能关闭未登记的物理线程。")
            run["residual_thread_ids"]=[x for x in run["residual_thread_ids"] if x not in ids]
            run["cleanup_status"]="partial" if run["residual_thread_ids"] else "confirmed"
            log("cleanup",closed_thread_ids=event["closed_thread_ids"],receipt_ref=event["receipt_ref"])
        else: log("late_event",event=event)
    elif kind=="transition":
        target=event["to"]
        if target not in transitions[run["status"]]: conflict("非法运行状态迁移。")
        if "input_hash" in event:
            if run["input_hash"] is not None and event["input_hash"]!=run["input_hash"]: conflict("冻结输入变化必须新建 run。")
            run["input_hash"]=event["input_hash"]
        if "round" in event:
            if event["round"]<run["round"] or event["round"]>run["round"]+1: conflict("轮次必须按顺序推进。")
            if event["round"]>run["round"]:
                if run["pending_action_ids"]: conflict("上轮仍有未完成 action，不能推进轮次。")
                run["completed_actor_ids"]=[]
            run["round"]=event["round"]
        if target=="running" and run["round"]<1: conflict("运行需指定首轮。")
        if target=="completed" and (run["pending_action_ids"] or set(run["completed_actor_ids"])!=set(run["actor_ids"])): conflict("覆盖不完整只能发布 partial。")
        if target in ("blocked","failed","cancelled","partial"):
            if not event.get("reason"): conflict("终止状态必须说明原因。")
            run["stop_reason"]=event["reason"]
        run["status"]=target; log("transition",to=target)
    elif kind=="intent":
        intent=event["intent"]; validate_semantics("action_intent",intent,{"run_id":run["run_id"],"actor_ids":run["actor_ids"],"input_hash":run["input_hash"]})
        aid=intent["action_id"]
        if aid in s["tasks"]:
            if s["tasks"][aid]["intent"]==intent and s["tasks"][aid]["attempt_id"]==event["attempt_id"]: log("duplicate_ignore",action_id=aid); return s
            s["quarantine"].append({"kind":"conflicting_intent","event":event}); log("conflicting_duplicate",action_id=aid); return s
        if run["status"] not in ("running","verifying"): conflict("仅运行或核查阶段可登记 intent。")
        if intent["dispatch_status"] not in ("proposed","authorized"): conflict("先登记 pending intent，再回填宿主 receipt。")
        if intent["round"]!=run["round"]: conflict("action 不属于当前轮次。")
        if intent["kind"] in ("spawn","send") and any(t["intent"]["actor_id"]==intent["actor_id"] and t["status"] in ("queued","dispatched","running","dispatch_unknown") for t in s["tasks"].values()): conflict("该角色有未完成或派发状态未知的 action，不能重派。")
        reservation=intent["budget_reservation"]
        run["spent_agent_turns"]+=reservation["agent_turns"]
        run["spent_verification_actions"]+=reservation["verification_actions"]
        s["tasks"][aid]={"intent":deepcopy(intent),"attempt_id":event["attempt_id"],"status":"queued","host_thread_id":None,"receipt_ref":None}
        run["pending_action_ids"].append(aid); log("intent_pending",action_id=aid)
    elif kind=="receipt":
        task=task_for(event["action_id"])
        if task["receipt_ref"]:
            if task["receipt_ref"]==event["receipt_ref"] and task["host_thread_id"]==event["host_thread_id"]: log("duplicate_ignore",action_id=event["action_id"]); return s
            s["quarantine"].append({"kind":"conflicting_receipt","event":event}); log("conflicting_duplicate",action_id=event["action_id"]); return s
        if task["status"] not in ("queued","dispatch_unknown"): conflict("当前任务不能接收派发 receipt。")
        task.update(status="dispatched",receipt_ref=event["receipt_ref"],host_thread_id=event["host_thread_id"])
        tid=event["host_thread_id"]
        if tid is not None and tid not in run["residual_thread_ids"]: run["residual_thread_ids"].append(tid); run["cleanup_status"]="pending"
        log("receipt_recorded",action_id=event["action_id"])
    elif kind=="task_status":
        task=task_for(event["action_id"]); target=event["status"]
        if target not in TASK_EDGES.get(task["status"],set()): conflict("非法任务状态迁移。")
        if target=="succeeded" and task["intent"]["kind"] in ("spawn","send"): conflict("角色成功必须经结果校验。")
        task["status"]=target; task["status_receipt_ref"]=event["receipt_ref"]
        if not TASK_EDGES[target] and event["action_id"] in run["pending_action_ids"]: run["pending_action_ids"].remove(event["action_id"])
        log("task_status",action_id=event["action_id"],status=target)
    elif kind=="wait_timeout":
        task_for(event["action_id"]); log("wait_timeout",action_id=event["action_id"])
    elif kind=="cleanup":
        ids=set(event["closed_thread_ids"])
        if not ids<=set(run["residual_thread_ids"]): conflict("不能关闭未登记的物理线程。")
        run["residual_thread_ids"]=[x for x in run["residual_thread_ids"] if x not in ids]
        run["cleanup_status"]="partial" if run["residual_thread_ids"] else "confirmed"
        log("cleanup",closed_thread_ids=event["closed_thread_ids"],receipt_ref=event["receipt_ref"])
    validate_semantics("run_state",run)
    return s
