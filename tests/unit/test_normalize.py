import unittest
from runtime.minds.normalize import normalize_request
from runtime.minds.contracts import validate_semantics

class NormalizeTests(unittest.TestCase):
    def error(self,raw,opts,code):
        result=normalize_request(raw,opts)
        self.assertEqual(result.get("error",{}).get("machine_code"),code,result)

    def test_wp02_01_challenger_conflict(self):
        self.error("必须双人对抗",{"n":1},"E_CONSTRAINT_CONFLICT")

    def test_wp02_02_deduplicate(self):
        r=normalize_request("深入思考",{"types":" INTJ,intj,ENFP "})
        self.assertEqual(r["locked_personas"],["intj","enfp"]); self.assertEqual(r["n"],2)
        self.assertIn("duplicate_persona:intj",r["notices"])
        self.assertFalse(any(v for k,v in r["permissions"].items() if k!="read_supplied"))

    def test_wp02_03_pair(self):
        r=normalize_request("pair intj enfp --rival -- 讨论")
        self.assertEqual(r["n"],2); self.assertEqual(r["locked_personas"],["intj","enfp"])
        self.assertIn("ignored_rival",r["notices"])
        r=normalize_request("pair intj --rival -- 讨论")
        self.assertEqual(r["n"],2); self.assertEqual(len(r["locked_personas"]),1)
        self.assertTrue(r["selection"]["require_challenger"])

    def test_x_req_01_body_separator(self):
        self.error("--unknown -- 正文",{},"E_UNKNOWN_ARGUMENT")
        r=normalize_request('many --n 2 -- --n 99\n保留  双空格 "未闭合')
        self.assertEqual(r["question"],'--n 99\n保留  双空格 "未闭合')
        self.assertEqual(r["n"],2)

    def test_x_req_02_boundaries(self):
        for n in (0,17,-1,1.2,"4",True,None):
            with self.subTest(n=n): self.error("问题",{"n":n},"E_SCHEMA")
        for n in (1,16): self.assertEqual(normalize_request("问题",{"n":n})["n"],n)
        for text in ("--n a 问题","--n 1.2 问题","--n -- 问题"):
            self.error(text,{},"E_SCHEMA")

    def test_x_req_03_fixed(self):
        for w in ("one","write","ask","decide"):
            self.error("问题",{"workflow":w,"n":2},"E_CONSTRAINT_CONFLICT")

    def test_x_req_04_all(self):
        self.error("问题",{"n":1,"rival":True},"E_CONSTRAINT_CONFLICT")
        self.error("问题",{"n":4,"all":True},"E_CONSTRAINT_CONFLICT")
        self.error("问题",{"workflow":"pair","all":True},"E_CONSTRAINT_CONFLICT")
        self.assertEqual(normalize_request("问题",{"n":16,"all":True})["n"],16)

    def test_missing_source_and_options(self):
        self.error("改写",{"workflow":"write","operation":"rewrite"},"E_MISSING_SOURCE")
        r=normalize_request("改写",{"workflow":"write","operation":"rewrite","source_text":"不能发布，12 个。"})
        self.assertTrue(r["input_refs"][0].startswith("source:sha256:"))
        for workflow in ("decide","vote"):
            r=normalize_request("问题",{"workflow":workflow})
            self.assertEqual(r["status"],"needs_information"); self.assertTrue(r["missing_fields"])

    def test_budget_and_conflicts(self):
        self.error("问题",{"n":4,"budget":{"max_agent_turns":3}},"E_BUDGET_TOO_SMALL")
        self.error("问题",{"n":4,"budget":{"max_agent_turns":13}},"E_CONSTRAINT_CONFLICT")
        self.error("--n 2 -- 问题",{"n":3},"E_CONSTRAINT_CONFLICT")
        self.error("问题",{"types":"intj,enfp","n":1},"E_CONSTRAINT_CONFLICT")
        self.error("问题",{"types":"INT"},"E_INVALID_PERSONA")
        self.error("问题",{"permission_override":True},"E_UNKNOWN_ARGUMENT")
        self.error("问题",{"permissions":{"network":"true"}},"E_SCHEMA")
        self.error("问题",{"workflow":[]},"E_SCHEMA")
        self.error("问题",{"workflow":"vote","workflow_options":{"unknown":True}},"E_UNKNOWN_ARGUMENT")
        self.error("问题",{"workflow":"vote","budget":{"unknown":1}},"E_SCHEMA")

    def test_all_entries_and_aliases(self):
        from runtime.minds.resources import registry
        for entry in registry()["commands"]:
            for alias in [entry["workflow"],entry["skill"]]+entry["aliases"]:
                opts={"workflow":alias}
                if entry["workflow"]=="vote": opts["workflow_options"]={"proposal_id":"p1","proposal_version":"v1","proposal_text":"合成提案"}
                if entry["workflow"]=="decide": opts["workflow_options"]={"candidates":[{"id":"a","version":"v1","description":"A"},{"id":"b","version":"v1","description":"B"}],"user_goal":"合成目标","hard_constraints":[]}
                with self.subTest(alias=alias):
                    r=normalize_request("问题",opts); self.assertEqual(r.get("workflow"),entry["workflow"],r)
                    validate_semantics("request",r)
                    self.assertEqual(r,normalize_request("问题",opts))

    def test_provenance_and_purity(self):
        opts={"permissions":{"network":True},"budget":{"max_agent_turns":4}}
        r=normalize_request("深入",opts)
        self.assertEqual(opts,{"permissions":{"network":True},"budget":{"max_agent_turns":4}})
        p={x["field"]:x for x in r["provenance"]}
        self.assertEqual(p["permissions.network"]["origin"],"explicit")
        self.assertEqual(p["permissions.publish"]["origin"],"default")

if __name__=="__main__": unittest.main()
