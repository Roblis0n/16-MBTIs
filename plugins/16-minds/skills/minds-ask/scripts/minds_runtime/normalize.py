"""Deterministic request normalization. Never starts agents or infers permissions."""
import hashlib
import re
from copy import deepcopy
from .contracts import check_json, canonical, validate_semantics, schema, _validate
from .errors import MindsError, fail
from .resources import registry, resource_json

FLAG_FIELDS = {"n":"n", "types":"types", "mode":"mode", "workflow":"workflow",
    "task-kind":"task_kind", "locale":"locale", "voice":"voice", "presentation":"presentation",
    "profile":"profile", "source-text":"source_text", "operation":"operation",
    "length-metric":"length_metric", "length-target":"length_target", "variant-id":"variant_id",
    "ask-mode":"ask_mode", "max-interview-turns":"max_interview_turns",
    "proposal-id":"proposal_id", "proposal-version":"proposal_version", "proposal-text":"proposal_text",
    "policy":"policy", "decisive-quorum":"decisive_quorum", "run-id":"run_id"}
BOOL_FLAGS = {"all":"all", "rival":"rival", "require-challenger":"require_challenger",
    "legacy-preview":"legacy_preview", "preview-only":"preview_only", "include-why":"include_why", "is-revision":"is_revision"}
INTEGERS={"n","length_target","max_interview_turns","decisive_quorum"}
WORKFLOW_FIELDS={"write":{"operation","length_metric","length_target","variant_id"},
    "ask":{"ask_mode","include_why","max_interview_turns"},
    "vote":{"proposal_id","proposal_version","proposal_text","policy","decisive_quorum","is_revision"},
    "decide":{"candidates","user_goal","hard_constraints"}}

def _tokens(raw):
    """Token spans with plain quotes; backslashes are literal (Windows paths safe)."""
    i=0
    while i<len(raw):
        if raw[i].isspace(): i+=1; continue
        start=i; chars=[]; quote=None
        while i<len(raw) and (quote or not raw[i].isspace()):
            ch=raw[i]
            if quote:
                if ch==quote: quote=None
                else: chars.append(ch)
            elif ch in ('"', "'"): quote=ch
            else: chars.append(ch)
            i+=1
        if quote: fail("E_SCHEMA","参数引号未闭合。",layer="shape")
        yield ''.join(chars), start, i

def _parse(raw):
    options={}; spans=[]; body_start=None; positional=[]
    it=iter(_tokens(raw))
    for token,start,end in it:
        if token=="--" and raw[start:end]=="--":
            body_start=end
            # The one separator after -- is syntax; all following whitespace stays.
            if body_start<len(raw) and raw[body_start]==" ": body_start+=1
            break
        if token.startswith("--"):
            flag,sep,value=token[2:].partition("=")
            if flag in BOOL_FLAGS:
                if sep: fail("E_UNKNOWN_ARGUMENT","布尔开关不接受赋值。")
                key=BOOL_FLAGS[flag]; value=True
            elif flag in FLAG_FIELDS:
                key=FLAG_FIELDS[flag]
                if not sep:
                    try: value,_,end=next(it)
                    except StopIteration: fail("E_SCHEMA","参数缺少值。",layer="shape")
                    if value.startswith("--"): fail("E_SCHEMA","参数缺少值。",layer="shape")
                if key in INTEGERS:
                    if not re.fullmatch(r"-?\d+",value): fail("E_SCHEMA","人数或计数必须是整数。",layer="shape")
                    value=int(value)
            else: fail("E_UNKNOWN_ARGUMENT","未知参数；使用 -- 分隔原始正文。")
            if key in options and options[key]!=value: fail("E_CONSTRAINT_CONFLICT","同一参数重复且值冲突。")
            options[key]=value; spans.append((start,end))
        else: positional.append((token,start,end))
    return options,spans,positional,body_start

def normalize_request(raw_text, explicit_options=None):
    """Return a Request, a needs_information result, or a StructuredError."""
    try: return _normalize(raw_text,explicit_options)
    except MindsError as exc: return exc.as_dict()

def _normalize(raw_text, explicit_options):
    check_json([raw_text,explicit_options])
    if not isinstance(raw_text,str) or (explicit_options is not None and not isinstance(explicit_options,dict)):
        fail("E_SCHEMA","raw_text 必须为字符串，explicit_options 必须为对象。",layer="shape")
    supplied=deepcopy(explicit_options or {})
    allowed=set(FLAG_FIELDS.values())|set(BOOL_FLAGS.values())|{"budget","permissions","selection","workflow_options","question","input_refs","locked_personas","candidates","user_goal","hard_constraints"}
    if set(supplied)-allowed: fail("E_UNKNOWN_ARGUMENT","结构化参数包含未知字段。")
    parsed,spans,positional,body_start=_parse(raw_text)
    sources={k:"raw_input.flags" for k in parsed}
    for k,v in supplied.items():
        if k in parsed and parsed[k]!=v: fail("E_CONSTRAINT_CONFLICT","结构化参数与文本参数冲突；请明确采用哪一个值。")
        parsed[k]=v; sources[k]="explicit_options."+k
    o=parsed; reg=registry(); aliases={}
    if "workflow" in o and not isinstance(o["workflow"],str): fail("E_SCHEMA","workflow 必须为字符串。",layer="shape")
    for entry in reg["commands"]:
        for alias in [entry["workflow"],entry["skill"]]+entry["aliases"]: aliases[alias]=entry["workflow"]
    if positional and positional[0][0] in aliases:
        token,start,end=positional.pop(0); value=aliases[token]
        if "workflow" in o and aliases.get(o["workflow"])!=value: fail("E_CONSTRAINT_CONFLICT","入口名称冲突。")
        o["workflow"]=value; sources["workflow"]="raw_input.entry:"+token; spans.append((start,end))
    w=aliases.get(o.get("workflow","many"))
    if w is None: fail("E_UNKNOWN_ARGUMENT","未知工作流入口。")
    entry=next(x for x in reg["commands"] if x["workflow"]==w)
    notices=[]; provenance=[]
    def provenance_for(field, origin="default", ref=None):
        provenance.append({"field":field,"origin":origin,"source_ref":ref})
    def get(key,default):
        default_ref={"n":"contracts/defaults.json","budget":"contracts/defaults.json","permissions":"contracts/defaults.json","mode":"commands/registry.json"}.get(key,"normalize:"+key+"_default")
        provenance_for(key,"explicit" if key in o else "default",sources.get(key,default_ref))
        return deepcopy(o.get(key,default))
    types=o.get("types",o.get("locked_personas",[]))
    if "types" in o and "locked_personas" in o: fail("E_CONSTRAINT_CONFLICT","types 与 locked_personas 只能提供一项。")
    if isinstance(types,str): types=types.split(",")
    if not isinstance(types,list) or any(not isinstance(x,str) for x in types): fail("E_SCHEMA","types 必须为 ID 列表或逗号分隔文本。",layer="shape")
    if w in ("one","pair") and not types:
        while positional and len(types)<entry["fixed_n"] and positional[0][0].lower() in reg["personas"]:
            token,start,end=positional.pop(0); types.append(token); spans.append((start,end))
        if types: sources["types"]="raw_input.positional"
    locked=[]
    for persona in types:
        pid=persona.strip().lower()
        if pid not in reg["personas"]: fail("E_INVALID_PERSONA","人格 ID 必须是完整的十六人格 ID。")
        if pid in locked: notices.append("duplicate_persona:"+pid)
        else: locked.append(pid)
    provenance_for("locked_personas","explicit" if types else "default",sources.get("types",sources.get("locked_personas")))
    for flag in BOOL_FLAGS.values():
        if flag in o and type(o[flag]) is not bool: fail("E_SCHEMA","布尔参数必须是 true 或 false。",layer="shape")
    if "n" in o and (type(o["n"]) is not int or not 1<=o["n"]<=16): fail("E_SCHEMA","n 必须为 1—16 的整数。",layer="shape")
    fixed=entry["fixed_n"]
    if o.get("all"):
        if fixed is not None or ("n" in o and o["n"]!=16): fail("E_CONSTRAINT_CONFLICT","all 仅用于可变人数，且不能与不同的 n 并用。")
        n=16; provenance_for("n","explicit",sources["all"])
    else:
        n=get("n",fixed if fixed is not None else (len(locked) or 4))
        if "n" not in o and locked and fixed is None:
            provenance[-1].update(origin="explicit",source_ref=sources.get("types",sources.get("locked_personas")))
    if fixed is not None and n!=fixed: fail("E_CONSTRAINT_CONFLICT","该入口人数固定；如需多人请显式改用 many。")
    if len(locked)>n: fail("E_CONSTRAINT_CONFLICT","锁定角色超过请求人数。")
    selection=get("selection",{})
    if not isinstance(selection,dict) or set(selection)-{"require_challenger","legacy_preview","preview_only"}: fail("E_SCHEMA","selection 字段非法。",layer="shape")
    selection={"require_challenger":False,"legacy_preview":False,"preview_only":False,**selection}
    for k in selection:
        if k in o:
            if k in o.get("selection",{}) and o["selection"][k]!=o[k]: fail("E_CONSTRAINT_CONFLICT","selection 与参数冲突。")
            selection[k]=get(k,False)
    if o.get("rival"):
        if w=="pair" and len(locked)==2: notices.append("ignored_rival")
        else: selection["require_challenger"]=True
        provenance_for("selection.require_challenger","explicit",sources["rival"])
    if body_start is not None:
        if positional: fail("E_CONSTRAINT_CONFLICT","-- 前存在正文；请把完整正文放在分隔符之后。")
        body=raw_text[body_start:]
    else:
        cursor=0; parts=[]
        for start,end in sorted(spans): parts.append(raw_text[cursor:start]); cursor=end
        parts.append(raw_text[cursor:]); body=''.join(parts).strip()
    if "question" in o and body and body!=o["question"]: fail("E_CONSTRAINT_CONFLICT","显式 question 与正文冲突。")
    question=get("question",body)
    if "question" not in o: provenance[-1].update(origin="explicit",source_ref="raw_input.body")
    if not isinstance(question,str): fail("E_SCHEMA","question 必须为字符串。",layer="shape")
    if not question.strip(): return {"status":"needs_information","missing_fields":["question"],"question":"请提供本次要处理的问题或任务。"}
    # Only explicit, unambiguous requirements are detected; arbitrary prose is not NLP-parsed.
    if re.search(r"必须(?:双人|两人|2人)对抗",question): selection["require_challenger"]=True
    if selection["require_challenger"] and n<2: fail("E_CONSTRAINT_CONFLICT","当前 n=1 与必须双人挑战冲突；请明确人数或取消挑战要求。")
    mode=get("mode",entry["default_mode"])
    if mode not in ("light","middle","heavy"): fail("E_SCHEMA","mode 无效。",layer="shape")
    defaults=resource_json("contracts/defaults.json")
    budget={"max_rounds":defaults["max_rounds_by_mode"][mode],"max_agent_turns":n*defaults["agent_turns_multiplier"][mode],
        "max_verification_actions":defaults["verification_actions_by_mode"][mode],"max_repairs_per_result":defaults["max_repairs_per_result"],"concurrency_cap":None}
    for key in ("soft_deadline_seconds","agent_output_target_codepoints","final_summary_target_codepoints"): budget[key]=defaults[key][mode]
    explicit_budget=get("budget",{})
    permissions=get("permissions",{})
    if not isinstance(explicit_budget,dict) or not isinstance(permissions,dict): fail("E_SCHEMA","budget 与 permissions 必须为对象。",layer="shape")
    for key in budget: provenance_for("budget."+key,"explicit" if key in explicit_budget else "default","explicit_options.budget" if key in explicit_budget else "contracts/defaults.json")
    budget.update(explicit_budget)
    for key in ("max_verification_actions","soft_deadline_seconds"):
        default_value=defaults["verification_actions_by_mode"][mode] if key=="max_verification_actions" else defaults[key][mode]
        if type(budget[key]) is int and budget[key]>default_value:
            notices.append("explicit_budget_increase:"+key+":"+str(budget[key]))
    for key in defaults["permissions_default"]: provenance_for("permissions."+key,"explicit" if key in permissions else "default","explicit_options.permissions" if key in permissions else "contracts/defaults.json")
    permissions={**defaults["permissions_default"],**permissions}
    for key,value in (("budget",budget),("permissions",permissions),("selection",selection)):
        _validate(schema("request")["properties"][key],value,"$."+key)
    options=get("workflow_options",{})
    if options is None: options={}
    if not isinstance(options,dict): fail("E_SCHEMA","workflow_options 必须为对象或 null。",layer="shape")
    fieldset=set().union(*WORKFLOW_FIELDS.values())
    for key in fieldset & o.keys():
        if key not in WORKFLOW_FIELDS.get(w,set()): fail("E_UNKNOWN_ARGUMENT","参数不适用于当前工作流。")
        if key in options and options[key]!=o[key]: fail("E_CONSTRAINT_CONFLICT","工作流字段冲突。")
        options[key]=get(key,None)
    option_defaults={"write":{"operation":"write","length_metric":"codepoints","length_target":None,"variant_id":"variant-1"},
        "ask":{"ask_mode":"questions","include_why":False,"max_interview_turns":5},
        "vote":{"policy":"distribution","decisive_quorum":None,"is_revision":False},"decide":{}}
    for key,value in option_defaults.get(w,{}).items():
        if key not in options: options[key]=value; provenance_for("workflow_options."+key,"default","C01/C04")
    if set(options)-WORKFLOW_FIELDS.get(w,set()): fail("E_UNKNOWN_ARGUMENT","workflow_options 包含不适用于该入口的字段。")
    required={"vote":["proposal_id","proposal_version","proposal_text"],"decide":["candidates","user_goal","hard_constraints"]}.get(w,[])
    missing=[key for key in required if key not in options]
    if missing: return {"status":"needs_information","missing_fields":["workflow_options."+key for key in missing],"question":"请补充这些明确的业务字段："+"、".join(missing)+"。"}
    if w not in WORKFLOW_FIELDS:
        if options: fail("E_UNKNOWN_ARGUMENT","该工作流不接受专用选项。")
        options=None
    source=get("source_text",None)
    refs=get("input_refs",[])
    if isinstance(source,str) and source:
        if not isinstance(refs,list): fail("E_SCHEMA","input_refs 必须为列表。",layer="shape")
        refs=refs+["source:sha256:"+hashlib.sha256(source.encode("utf-8")).hexdigest()]
    task_default={"write":"creative","decide":"decision","vote":"decision","ask":"inquiry"}.get(w,"inquiry")
    # Registered profile determines only a missing routing kind, never permissions.
    if o.get("profile") is not None and "task_kind" not in o:
        profiles=resource_json("profiles/registry.json")["profiles"]
        selected=next((p for p in profiles if p["profile_id"]==o["profile"] and p["enabled"]),None)
        if selected is not None: task_default=selected["task_kind"]
    result={"protocol_version":"1.0.0","run_id":get("run_id","req-"+hashlib.sha256(canonical([raw_text,supplied]).encode("utf-8")).hexdigest()[:24]),
        "workflow":w,"task_kind":get("task_kind",task_default),"profile":get("profile",None),"voice":get("voice","persona"),
        "raw_input":raw_text,"question":question,"source_text":source,"locale":get("locale","zh-CN"),"locked_personas":locked,
        "n":n,"mode":mode,"presentation":get("presentation","summary"),"budget":budget,"permissions":permissions,
        "input_refs":refs,"provenance":provenance,"notices":notices,"selection":selection,"workflow_options":options}
    provenance_for("workflow","explicit" if "workflow" in sources else "default",sources.get("workflow","commands/registry.json"))
    validate_semantics("request",result)
    return result
