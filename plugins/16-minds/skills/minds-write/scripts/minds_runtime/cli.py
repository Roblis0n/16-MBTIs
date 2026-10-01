"""JSON stdin/stdout command line. All commands are deterministic and local."""
import sys
import json
from .contracts import strict_loads, validate_shape, validate_semantics, check_json, MAX_BYTES
from .normalize import normalize_request
from .state import reduce_state, new_reducer_state
from .resources import registry, resource_json
from .errors import MindsError, fail

def _object(data,required,optional=()):
    if not isinstance(data,dict) or not set(required)<=data.keys() or data.keys()-(set(required)|set(optional)):
        fail("E_SCHEMA","命令 JSON 缺少字段或包含未知字段。",layer="shape")

def dispatch(command,data):
    if command=="normalize":
        _object(data,{"raw_text"},{"explicit_options"})
        value=normalize_request(data["raw_text"],data.get("explicit_options"))
        return value if "status" in value else {"status":"ok","request":value}
    if command=="validate":
        _object(data,{"kind","payload"},{"context","layer"})
        if data.get("layer","semantic") not in ("shape","semantic"): fail("E_SCHEMA","layer 仅接受 shape 或 semantic。",layer="shape")
        if not isinstance(data["kind"],str): fail("E_SCHEMA","kind 必须为字符串。",layer="shape")
        if data.get("layer")=="shape": validate_shape(data["kind"],data["payload"])
        else: validate_semantics(data["kind"],data["payload"],data.get("context"))
        return {"status":"ok","valid":True,"layer":data.get("layer","semantic"),"scope":"protocol validation; not factual truth or authenticated approval"}
    if command=="reduce":
        _object(data,{"state","event"})
        return {"status":"ok","state":reduce_state(data["state"],data["event"])}
    if command=="init-state":
        _object(data,{"run"})
        return {"status":"ok","state":new_reducer_state(data["run"])}
    if command in ("execute","step","record","scheduler"):
        from .scheduler import dispatch as schedule
        if command=="execute":
            if not isinstance(data,dict): fail("E_SCHEMA","execute 需要 JSON 对象。",layer="shape")
            if "capabilities" not in data: fail("E_CAPABILITY","需要本次宿主能力记录；未派发任何角色。")
            _object(data,{"request","capabilities","run_id"},{"roster","common_facts","persona_revision","evidence_version","permission_ref","parent_run_id"})
            validate_semantics("request",data["request"])
            validate_semantics("capabilities",data["capabilities"])
            from .casting import select_roster
            prepared={"op":"prepare",**data}
            if "roster" not in prepared:
                prepared["roster"]=select_roster(data["request"])
                prepared["roster"]["run_id"]=data["run_id"]
            return {"status":"ok","state":schedule(prepared),"execution_notice":"prepared only; host must dispatch intents and record actual receipts"}
        if command in ("step","record"):
            _object(data,{"state","event"})
            return {"status":"ok",**schedule({"op":"step",**data})}
        return {"status":"ok","result":schedule(data)}
    if command in ("cast","aggregate","pair","synthesis","decide","vote","write","ask","workflow"):
        from .synthesis import dispatch_workflow
        if command=="workflow":
            _object(data,{"operation","payload"})
            if not isinstance(data["operation"],str): fail("E_SCHEMA","operation 必须是字符串。",layer="shape")
            result=dispatch_workflow(data["operation"],data["payload"])
        else: result=dispatch_workflow(command,data)
        return {"status":"ok","result":result}
    if command in ("authorize","storage","render","sensitivity","journal","invalidate","profile"):
        from importlib import import_module
        module={"authorize":"tool_policy","storage":"storage","render":"render","sensitivity":"sensitivity","journal":"journal","invalidate":"invalidation","profile":"profiles"}[command]
        return {"status":"ok","result":import_module("."+module,__package__).dispatch(data)}
    fail("E_UNKNOWN_ARGUMENT","未知 helper 命令；运行 help 查看支持范围。")

DATA_COMMANDS=("normalize","validate","init-state","reduce","execute","step","record","scheduler","cast","aggregate","pair","synthesis","decide","vote","write","ask","workflow","authorize","storage","render","sensitivity","journal","invalidate","profile")

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    try:
        if not args or args in (["help"],["--help"],["-h"]):
            result={"status":"ok","commands":list(DATA_COMMANDS)+["version","help"],
                "stdin":"UTF-8 JSON; normalize={raw_text,explicit_options?}; validate={kind,payload,context?,layer?}",
                "exit_codes":{"success_or_business_status":0,"input":2,"capability_or_permission":3,"budget":4,"internal":5},
                "entries":registry()["commands"],"release_level":"static_candidate"}
        elif args in (["version"],["--version"]):
            identity=resource_json("plugin/identity.json")
            result={"status":"ok","name":identity["name"],"version":identity["version"],"protocol_version":"1.0.0","release_level":"static_candidate"}
        else:
            if len(args)!=1: fail("E_UNKNOWN_ARGUMENT","helper 接受一个命令；业务参数通过 JSON stdin 传入。")
            if args[0] not in DATA_COMMANDS:
                result=dispatch(args[0],None)
            else:
                raw=sys.stdin.buffer.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES: fail("E_SCHEMA","JSON 超过 1 MiB 限制。",layer="shape")
                try: data=strict_loads(raw.decode("utf-8-sig"))
                except UnicodeError: fail("E_SCHEMA","stdin 必须为 UTF-8 JSON。",layer="shape")
                if not isinstance(data,dict): fail("E_SCHEMA","命令 stdin 必须是 JSON 对象。",layer="shape")
                result=dispatch(args[0],data)
        check_json(result)
        code=0
        if result.get("status")=="error": code=MindsError(result["error"]["machine_code"],"").exit_code
    except MindsError as exc: result=exc.as_dict(); code=exc.exit_code
    except Exception:
        exc=MindsError("E_INTERNAL","helper 内部异常；检查相关操作的状态与去敏诊断。",layer="internal",side_effect_status="unknown",next_step="保留去敏复现输入并报告此错误。")
        result=exc.as_dict(); code=5
        print("16minds: internal error (payload redacted)",file=sys.stderr)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return code

if __name__=="__main__": raise SystemExit(main())
