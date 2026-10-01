"""Strict project-schema subset, NOT a general JSON Schema implementation.

Supported keywords are exhaustively checked, including referenced schemas. An
unsupported keyword fails closed. No remote references, plugins or code execution.
"""
import json
import math
import re
from datetime import datetime
from functools import lru_cache
from .errors import MindsError, fail
from .resources import resource_json, registry

MAX_BYTES = 1_048_576
MAX_DEPTH = 48
KEYWORDS = {"$schema", "$id", "title", "description", "$ref", "type", "const", "enum",
    "properties", "required", "additionalProperties", "items", "uniqueItems",
    "minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "pattern",
    "format", "allOf", "anyOf", "oneOf", "if", "then", "else"}

def strict_loads(text):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result: fail("E_SCHEMA", "JSON 包含重复键。", layer="shape")
            result[k] = v
        return result
    def constant(_): fail("E_SCHEMA", "JSON 包含非法非有限数。", layer="shape")
    try:
        if len(text.encode("utf-8")) > MAX_BYTES: fail("E_SCHEMA", "JSON 超过 1 MiB 限制。", layer="shape")
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
        check_json(value)
        return value
    except (ValueError, RecursionError, UnicodeError):
        fail("E_SCHEMA", "输入不是受支持的 UTF-8 JSON。", layer="shape")

def check_json(value):
    active = set()
    def walk(v, depth):
        if depth > MAX_DEPTH: fail("E_SCHEMA", "JSON 嵌套超过 48 层。", layer="shape")
        if type(v) not in (dict, list, str, int, float, bool, type(None)):
            fail("E_SCHEMA", "输入含非 JSON 类型。", layer="shape")
        if type(v) is float and not math.isfinite(v): fail("E_SCHEMA", "数值必须有限。", layer="shape")
        if isinstance(v, (dict, list)):
            if id(v) in active: fail("E_SCHEMA", "输入包含循环引用。", layer="shape")
            active.add(id(v))
            if isinstance(v, dict) and any(type(k) is not str for k in v): fail("E_SCHEMA", "对象键必须为字符串。", layer="shape")
            for x in (v.values() if isinstance(v, dict) else v): walk(x, depth+1)
            active.remove(id(v))
    walk(value, 0)
    try:
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_BYTES:
            fail("E_SCHEMA", "JSON 超过 1 MiB 限制。", layer="shape")
    except (UnicodeError, ValueError): fail("E_SCHEMA", "非法 JSON 字符。", layer="shape")

def canonical(value):
    check_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def _equal(a, b):
    if isinstance(a, bool) != isinstance(b, bool): return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)): return a == b
    if type(a) != type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(_equal(a[k],b[k]) for k in a)
    if isinstance(a, list): return len(a)==len(b) and all(_equal(x,y) for x,y in zip(a,b))
    return a == b

@lru_cache(maxsize=64)
def schema(kind):
    if not isinstance(kind,str) or not re.fullmatch(r"[a-z_]+", kind): fail("E_SCHEMA", "未知契约类型。", layer="shape")
    try: s = resource_json(f"contracts/schemas/{kind}.schema.json")
    except FileNotFoundError: fail("E_SCHEMA", "未知契约类型。", layer="shape")
    _check_schema(s)
    return s

def _check_schema(s):
    if not isinstance(s, dict) or set(s)-KEYWORDS: fail("E_INTERNAL", "契约使用未支持的 schema 关键字。", layer="internal")
    if "format" in s and s["format"] != "date-time": fail("E_INTERNAL", "契约格式不受支持。", layer="internal")
    for child in s.get("properties", {}).values(): _check_schema(child)
    for k in ("items", "if", "then", "else"):
        if k in s: _check_schema(s[k])
    for k in ("allOf", "anyOf", "oneOf"):
        for child in s.get(k, []): _check_schema(child)
    if isinstance(s.get("additionalProperties"),dict): _check_schema(s["additionalProperties"])

def _matches(s, v):
    try: _validate(s,v,"$"); return True
    except MindsError as exc:
        if exc.code != "E_SCHEMA": raise
        return False

def _validate(s, v, path):
    def bad(rule): fail("E_SCHEMA", f"{path}: {rule}", layer="shape")
    if "$ref" in s:
        ref=s["$ref"]
        if not re.fullmatch(r"[a-z_]+\.schema\.json",ref): fail("E_INTERNAL", "仅支持包内 schema 引用。", layer="internal")
        _validate(schema(ref.split(".")[0]),v,path)
    types={"object":type(v) is dict,"array":type(v) is list,"string":type(v) is str,
        "integer":type(v) is int,"number":type(v) in (int,float),"boolean":type(v) is bool,"null":v is None}
    if "type" in s:
        expected=s["type"] if isinstance(s["type"],list) else [s["type"]]
        if not any(types.get(t,False) for t in expected): bad("类型错误")
    if "const" in s and not _equal(v,s["const"]): bad("常量不匹配")
    if "enum" in s and not any(_equal(v,e) for e in s["enum"]): bad("枚举不匹配")
    if isinstance(v,dict):
        if set(s.get("required",[]))-v.keys(): bad("缺少必需字段")
        props=s.get("properties",{})
        for k,x in v.items():
            if k in props: _validate(props[k],x,path+"."+k)
            elif s.get("additionalProperties") is False: bad("未知字段")
            elif isinstance(s.get("additionalProperties"),dict): _validate(s["additionalProperties"],x,path+".*")
    if isinstance(v,list):
        if len(v)<s.get("minItems",0) or len(v)>s.get("maxItems",MAX_BYTES): bad("数组长度越界")
        if s.get("uniqueItems") and any(_equal(x,y) for i,x in enumerate(v) for y in v[:i]): bad("数组元素重复")
        if "items" in s:
            for i,x in enumerate(v): _validate(s["items"],x,f"{path}[{i}]")
    if type(v) in (int,float):
        if v<s.get("minimum",-math.inf) or v>s.get("maximum",math.inf): bad("数值越界")
    if isinstance(v,str):
        if len(v)<s.get("minLength",0) or len(v)>s.get("maxLength",MAX_BYTES): bad("字符串长度越界")
        if "pattern" in s and not re.search(s["pattern"],v): bad("字符串格式不匹配")
        if s.get("format")=="date-time":
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",v): raise ValueError()
                if datetime.fromisoformat(v.replace("Z","+00:00")).tzinfo is None: raise ValueError()
            except ValueError: bad("需要带时区的 ISO8601 时间")
    for sub in s.get("allOf",[]): _validate(sub,v,path)
    for op in ("anyOf","oneOf"):
        if op in s:
            count=sum(_matches(sub,v) for sub in s[op])
            if (op=="oneOf" and count!=1) or count==0: bad(op+" 不匹配")
    if "if" in s:
        branch="then" if _matches(s["if"],v) else "else"
        if branch in s: _validate(s[branch],v,path)

def validate_shape(kind, payload):
    check_json(payload)
    _validate(schema(kind),payload,"$")
    return payload

def validate_semantics(kind, d, context=None):
    """Context uses evidence/claims registries and frozen run/object identities.

    This validates linkage, not natural-language entailment. A support review must
    be explicitly supplied for factual supported claims (otherwise review needed).
    """
    validate_shape(kind,d)
    c={} if context is None else context
    check_json(c)
    if not isinstance(c,dict): fail("E_SCHEMA", "context 必须为对象。", layer="shape")
    context_fields={"evidence","claims","support_reviews","evidence_versions","run_id","input_hash","persona_revision","actor_ids","score_objects","proposal_id","proposal_version","eligible_ids","ballots","source_version","locked_personas"}
    if c.keys()-context_fields: fail("E_SCHEMA","context 包含未知字段。",layer="shape")
    for field in ("evidence","claims","support_reviews","evidence_versions"):
        if field in c and not isinstance(c[field],dict): fail("E_SCHEMA","context 注册表必须为对象。",layer="shape")
    for field,contract in (("evidence","evidence"),("claims","claim")):
        for key,value in c.get(field,{}).items():
            validate_shape(contract,value)
            if key!=value[contract+"_id"]: fail("E_SEMANTIC","context 注册键与对象 ID 不一致。")
    for review in c.get("support_reviews",{}).values():
        if not isinstance(review,dict) or set(review)!={"relevant","scope_matches","versions_match"} or any(type(v) is not bool for v in review.values()): fail("E_SCHEMA","support review 必须包含三个布尔核查字段。",layer="shape")
    for field in ("run_id","input_hash","persona_revision","proposal_id","proposal_version","source_version"):
        if field in c and c[field] is not None and not isinstance(c[field],str): fail("E_SCHEMA","context 身份必须为字符串。",layer="shape")
    for field in ("actor_ids","eligible_ids","locked_personas"):
        if field in c and (not isinstance(c[field],list) or any(not isinstance(x,str) for x in c[field]) or len(c[field])!=len(set(c[field]))): fail("E_SCHEMA","context 身份集合必须为去重字符串列表。",layer="shape")
    if "score_objects" in c and (not isinstance(c["score_objects"],list) or any(not isinstance(x,list) or len(x)!=4 or any(not isinstance(v,str) for v in x) for x in c["score_objects"])): fail("E_SCHEMA","score_objects 必须包含四字段对象身份。",layer="shape")
    if "ballots" in c:
        if not isinstance(c["ballots"],(dict,list)): fail("E_SCHEMA","ballots 必须为票列表或历史票映射。",layer="shape")
        for b in c["ballots"].values() if isinstance(c["ballots"],dict) else c["ballots"]: validate_shape("ballot",b)
    def require(ok, code="E_SEMANTIC", message="跨字段关系不成立。"):
        if not ok: fail(code,message)
    evidence=c.get("evidence",{})
    if not isinstance(evidence,dict): fail("E_SCHEMA", "context.evidence 必须为 ID 映射。", layer="shape")
    def refs(ids):
        for eid in ids: require(eid in evidence,"E_UNKNOWN_EVIDENCE","引用了未登记的证据。")
    if "evidence_ids" in d: refs(d["evidence_ids"])
    for field in ("run_id","input_hash","persona_revision"):
        if field in c and field in d: require(d[field]==c[field],message="冻结运行身份或版本不匹配。")
    if "actor_id" in d and d["actor_id"] is not None and "actor_ids" in c: require(d["actor_id"] in c["actor_ids"],message="未知逻辑角色。")
    if kind=="request":
        entry=next(x for x in registry()["commands"] if x["workflow"]==d["workflow"])
        n=d["n"]; b=d["budget"]; depth={"light":1,"middle":2,"heavy":3}[d["mode"]]
        require(entry["fixed_n"] in (None,n),"E_CONSTRAINT_CONFLICT","该工作流要求固定人数。")
        require(len(d["locked_personas"])<=n,"E_CONSTRAINT_CONFLICT","锁定人数超过总人数。")
        require(not d["selection"]["require_challenger"] or n>=2,"E_CONSTRAINT_CONFLICT","挑战者需要总人数至少为 2。")
        require(not d["selection"]["preview_only"] or d["workflow"]=="cast","E_CONSTRAINT_CONFLICT","preview_only 仅用于 cast。")
        require(b["max_agent_turns"]>=n,"E_BUDGET_TOO_SMALL","预算不足以完成首轮。")
        require(b["max_rounds"]<=depth and b["max_agent_turns"]<=n*depth,"E_CONSTRAINT_CONFLICT","预算超过 mode 上限；请显式选择合适深度。")
        require(d["profile"] is None or d["profile"] in registry()["profiles"],"E_CAPABILITY","该 profile 尚未注册。")
        opts=d["workflow_options"]
        if d["workflow"]=="write" and opts["operation"]=="rewrite":
            require(bool(d["source_text"] and d["source_text"].strip()),"E_MISSING_SOURCE","rewrite 缺少原文。")
        if d["workflow"]=="vote":
            require(bool(opts["proposal_text"].strip() and opts["proposal_version"].strip()),message="提案内容与版本不能为空。")
            if opts["policy"]=="valid_majority": require(opts["decisive_quorum"] is not None and 1<=opts["decisive_quorum"]<=n,"E_CONSTRAINT_CONFLICT","valid_majority 需要 1—N 的明确 quorum。")
        if d["workflow"]=="decide":
            ids=[x["id"] for x in opts["candidates"]]
            require(len(ids)==len(set(ids)),message="候选 ID 必须唯一。")
            require(bool(opts["user_goal"].strip()) and all(x["version"].strip() and x["description"].strip() for x in opts["candidates"]),message="决策需要目标、候选版本及描述。")
    elif kind=="claim":
        claims=c.get("claims",{})
        for cid in d["counter_claim_ids"]: require(cid in claims,message="未知反主张引用。")
        if d["revision"]>1: require(d["supersedes"] is not None and d["supersedes"] in claims,message="修订须关联已登记旧主张。")
        elif d["supersedes"] is not None: require(False,message="初始主张不能 supersede。")
        old=claims.get(d["claim_id"])
        if old: require(old==d,message="claim_id 不可复用，修订使用新 ID 并保留 supersedes。")
        if d["status"] in ("supported","refuted") and d["kind"]!="value_preference":
            require(bool(d["evidence_ids"]) and all(evidence[e].get("access_status")=="observed" for e in d["evidence_ids"]),"E_UNOBSERVED_SUPPORT","支持状态需要实际观察的证据。")
            require(all(evidence[e].get("kind")!="participant_statement" for e in d["evidence_ids"]),"E_UNOBSERVED_SUPPORT","角色发言不能直接证明外部事实。")
            review=c.get("support_reviews",{}).get(d["claim_id"])
            require(review is not None and review.get("relevant") is True and review.get("scope_matches") is True and review.get("versions_match") is True,"E_CONTEXT_INCOMPLETE","事实支持尚缺相关性、范围与版本核查记录。")
        for eid in d["evidence_ids"]:
            if eid in c.get("evidence_versions",{}): require(evidence[eid].get("source_version")==c["evidence_versions"][eid],message="证据版本已过期。")
    elif kind=="evidence":
        refs(d["derived_from"])
        require(d["evidence_id"] not in d["derived_from"],message="证据不能派生自自身。")
        if d["access_status"]!="observed": require(d["content_hash"] is None,message="未观察材料不能声明内容哈希。")
        if d["kind"]=="participant_statement": require(d["trust_class"]=="participant_statement",message="角色发言信任类型错误。")
        old=evidence.get(d["evidence_id"])
        if old: require(old==d,message="证据 ID 不可覆盖；内容变化须新 ID 与新哈希。")
    elif kind=="agent_result":
        require(all(x["actor_id"]==d["actor_id"] for x in d["claims"]+d["score_records"]),message="结果不能冒充其他角色。")
        ids=[x["claim_id"] for x in d["claims"]]; require(len(ids)==len(set(ids)),message="重复主张 ID。")
        local=dict(c); local["claims"]={**c.get("claims",{}), **{x["claim_id"]:x for x in d["claims"]}}
        for claim in d["claims"]: validate_semantics("claim",claim,local)
        seen=set()
        for score in d["score_records"]:
            key=tuple(score[k] for k in ("subject_id","subject_version","criterion_id","scale_id"))
            require(key not in seen,"E_SCORE_OBJECT_MISMATCH","重复评分对象。")
            seen.add(key)
            if "score_objects" in c: require(list(key) in c["score_objects"],"E_SCORE_OBJECT_MISMATCH","评分对象、版本或量表不匹配。")
    elif kind=="ballot":
        for field in ("proposal_id","proposal_version"):
            if field in c: require(d[field]==c[field],"E_STALE_BALLOT","投票提案或版本不匹配。")
        if "eligible_ids" in c: require(d["voter_id"] in c["eligible_ids"],message="投票者不在冻结名单。")
        if d["ballot_revision"]>1: require(d["supersedes"] in c.get("ballots",{}),message="修订票缺少旧票引用。")
        for condition in d["conditions"]: refs(condition["evidence_ids"])
    elif kind=="decision":
        require((d["status"]=="decided" and d["selected"] in d["candidate_ids"]) or (d["status"]!="decided" and d["selected"] is None))
        violations={v["candidate_id"] for v in d["violations"]}
        require(violations<=set(d["candidate_ids"]))
        if d["status"]=="needs_information": require(bool(d["missing_information"]))
        if d["status"]=="no_feasible_option": require(violations==set(d["candidate_ids"]),message="不可行结论须逐个说明违反约束。")
        if d["status"]=="decided": require(d["selected"] not in violations and not d["missing_information"],message="不可选择违反约束或关键事实缺失的方案。")
        for trigger in d["revisit_when"]: refs(trigger["evidence_ids"])
    elif kind=="run_state":
        b=d["budget"]
        require(d["spent_agent_turns"]<=b["max_agent_turns"] and d["spent_verification_actions"]<=b["max_verification_actions"],"E_BUDGET_EXHAUSTED","已使用资源超过预算。")
        require(d["round"]<=b["max_rounds"],"E_BUDGET_EXHAUSTED","轮次超过预算。")
        require(set(d["completed_actor_ids"])<=set(d["actor_ids"]))
        if d["status"] in ("prepared","running","verifying","synthesizing","completed"): require(d["input_hash"] is not None,message="准备或执行状态必须冻结真实输入哈希。")
    elif kind=="roster":
        ids=[m["actor_id"] for m in d["members"]]
        require(len(ids)==len(set(ids))==d["requested_n"],"E_CONSTRAINT_CONFLICT","名单须符合精确人数且不重复。")
        if "locked_personas" in c: require(set(c["locked_personas"])<=set(ids),"E_CONSTRAINT_CONFLICT","锁定角色不能被替换。")
    elif kind=="vote_summary":
        counts=d["counts"]; n=len(d["eligible_ids"])
        require(counts["eligible"]==n and counts["responded"]==counts["valid_ballots"]==counts["yes"]+counts["no"]+counts["abstain"] and counts["decisive"]==counts["yes"]+counts["no"] and counts["responded"]<=n)
        require(d["yes_over_eligible"] is not None and math.isclose(d["yes_over_eligible"],counts["yes"]/n))
        unavailable=set()
        for field in ("missing_ids","invalid_ids","failed_ids"):
            ids=set(d[field]); require(ids<=set(d["eligible_ids"]) and not ids & unavailable); unavailable|=ids
        require(len(unavailable)+counts["responded"]==n)
        policy=d["policy"]; yes=counts["yes"]; no=counts["no"]
        if policy=="distribution": require(d["verdict"]=="not_requested",message="distribution 不产生算法决议。")
        else:
            quorum=math.ceil(n/2) if policy=="absolute_majority" else (n if policy=="strict_unanimity" else d["quorum"])
            require(type(quorum) is int and 1<=quorum<=n,"E_CONSTRAINT_CONFLICT","可决票制的 quorum 无效。")
            require(d["quorum"]==quorum,message="冻结 quorum 与票制不一致。")
            if counts["responded"]<n:
                require(d["verdict"] in ("partial","pending_revote"),message="未覆盖全体不能声明正式通过。")
            else:
                if policy=="strict_unanimity": expected="pass" if yes==n else "fail"
                elif yes+no<quorum: expected="no_quorum"
                elif yes==no: expected="tie"
                else: expected="pass" if (yes>n/2 if policy=="absolute_majority" else yes>no) else "fail"
                require(d["verdict"]==expected,message="完整票集的结论与冻结票制不一致。")
        if "ballots" in c:
            ballots=c["ballots"]; require(isinstance(ballots,list))
            require(len({b["voter_id"] for b in ballots})==len(ballots)==counts["responded"])
            for b in ballots: validate_semantics("ballot",b,{**c,"run_id":d["run_id"],"proposal_id":d["proposal_id"],"proposal_version":d["proposal_version"],"eligible_ids":d["eligible_ids"]})
            for choice in ("yes","no","abstain"): require(counts[choice]==sum(b["choice"]==choice for b in ballots))
    elif kind=="writing_result":
        actual=len(d["body"]) if d["length_metric"]=="codepoints" else len(d["body"].split())
        require(actual==d["actual_length"],message="实际正文计数不一致；words 使用 Unicode 空白分词。")
        if d["operation"]=="rewrite": require(bool(d["source_version"]),message="改写结果必须绑定源版本。")
        if "source_version" in c: require(d["source_version"]==c["source_version"],message="源版本不匹配。")
        if d["invariant_status"]=="preserved": require(all(x["status"]=="preserved" for x in d["invariant_diff"]))
    elif kind=="interview_state":
        ids=[q["question_id"] for q in d["questions"]]; require(len(ids)==len(set(ids)))
        active=d["active_question_id"]; require(active is None or active in ids)
        require(d["asked_turns"]<=d["max_interview_turns"],"E_BUDGET_EXHAUSTED","访谈轮次已用尽。")
        if active is not None: require(next(q for q in d["questions"] if q["question_id"]==active)["answer_status"]=="unasked")
        if d["status"] in ("completed","stopped"): require(active is None)
    elif kind=="action_intent":
        if d["dispatch_status"] in ("recorded","dispatched"): require(bool(d["host_receipt_ref"]),message="已派发或完成需要实际 receipt。")
        if d["kind"] in ("spawn","send"):
            require(d["actor_id"] is not None and d["round"]>=1 and d["budget_reservation"]=={"agent_turns":1,"verification_actions":0})
        if d["kind"]=="verify": require(d["budget_reservation"]=={"agent_turns":0,"verification_actions":1})
        if d["kind"] in ("wait","close"): require(d["budget_reservation"]=={"agent_turns":0,"verification_actions":0})
    elif kind=="calibration" and d["state"]=="active":
        require(bool(d["reviewer_ref"] and d["activation_approval_ref"]) and all(v is not None for v in d["fingerprint"].values()),"E_CALIBRATION_MISMATCH","激活校准缺少核查或签核。")
    elif kind=="change_request" and d["status"]=="approved":
        require(bool(d["approved_by"] and d["approved_at"] and d["evidence_refs"]),"E_PERMISSION","缺少批准记录。")
        require(d["approved_by"]!=d["requested_by"],"E_PERMISSION","实施者不能自批变更。")
    elif kind=="stage_report":
        if d["status"]=="pass": require(not d["is_template"] and all(w["status"] in ("pass","skipped") for w in d["work_packages"]))
        for test in d["test_results"]:
            if test["status"]=="not_run": require(bool(test["not_run_reason"]))
            if test["status"]=="pass": require(bool(test["evidence_ref"]))
    return d
