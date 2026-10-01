from pathlib import Path
import json
import unittest
from copy import deepcopy
from runtime.minds.contracts import validate_shape,validate_semantics,strict_loads,check_json,schema
from runtime.minds.errors import MindsError

FIX=Path(__file__).resolve().parents[1]/"fixtures/contracts"
def fixture(kind): return json.loads((FIX/"positive"/(kind+".valid.json")).read_text("utf-8"))
def context():
    e=fixture("evidence"); claim=fixture("claim")
    return {"evidence":{e["evidence_id"]:e},"support_reviews":{claim["claim_id"]:{"relevant":True,"scope_matches":True,"versions_match":True}}}

class ContractTests(unittest.TestCase):
    def test_all_authoritative_positive_shapes(self):
        for file in (FIX/"positive").glob("*.json"):
            kind=file.name.split(".")[0]
            with self.subTest(kind=kind): validate_shape(kind,json.loads(file.read_text("utf-8")))

    def test_all_authoritative_positive_semantics(self):
        for file in (FIX/"positive").glob("*.json"):
            kind=file.name.split(".")[0]
            with self.subTest(kind=kind): validate_semantics(kind,json.loads(file.read_text("utf-8")),context())

    def test_authoritative_negatives(self):
        cases=json.loads((FIX/"negative/index.json").read_text("utf-8"))
        for case in cases:
            d=json.loads((FIX/"negative"/Path(case["file"]).name).read_text("utf-8"))
            with self.subTest(file=case["file"]):
                with self.assertRaises(MindsError) as cm:
                    if case["expected_layer"]=="schema": validate_shape(case["schema"],d)
                    else: validate_semantics(case["schema"],d,context())
                self.assertEqual(cm.exception.code,case["expected_code"])

    def test_x_schema_01_strict_json(self):
        for raw in ('{"a":1,"a":2}','NaN','Infinity','-Infinity','1e999','['*60+'0'+']'*60,'"'+'a'*1048576+'"'):
            with self.subTest(raw=raw[:30]), self.assertRaises(MindsError): strict_loads(raw)
        loop=[]; loop.append(loop)
        with self.assertRaises(MindsError): check_json(loop)
        self.assertEqual(strict_loads('{"a":null}'),{"a":None})

    def test_x_schema_02_unknown_and_null(self):
        d=fixture("request"); validate_shape("request",d)
        d["unknown_secret_value"]=True
        with self.assertRaises(MindsError) as cm: validate_shape("request",d)
        self.assertNotIn("unknown_secret_value",cm.exception.message)
        d=fixture("request"); d["n"]=None
        with self.assertRaises(MindsError): validate_shape("request",d)

    def test_wp03_01_unknown_evidence(self):
        d=fixture("claim"); d["evidence_ids"]=["E99"]
        validate_shape("claim",d)
        with self.assertRaises(MindsError) as cm: validate_semantics("claim",d,context())
        self.assertEqual(cm.exception.code,"E_UNKNOWN_EVIDENCE")

    def test_wp03_03_legal_business_states(self):
        d=fixture("decision"); d.update(status="no_feasible_option",selected=None,violations=[{"candidate_id":x,"constraint":"合成约束未满足"} for x in d["candidate_ids"]])
        validate_semantics("decision",d,context())
        d.update(status="needs_information",violations=[],missing_information=["需补充合成候选成本"])
        validate_semantics("decision",d,context())
        b=fixture("ballot"); b["choice"]="abstain"; validate_semantics("ballot",b,context())

    def test_stale_ballot_and_actor(self):
        b=fixture("ballot")
        with self.assertRaises(MindsError) as cm: validate_semantics("ballot",b,{**context(),"proposal_version":"other"})
        self.assertEqual(cm.exception.code,"E_STALE_BALLOT")
        with self.assertRaises(MindsError): validate_semantics("ballot",b,{**context(),"eligible_ids":[]})

    def test_support_is_not_just_id_existence(self):
        d=fixture("claim"); d["status"]="supported"
        observed=context(); observed["evidence"]["E1"]["access_status"]="observed"
        with self.assertRaises(MindsError) as cm: validate_semantics("claim",d,{"evidence":observed["evidence"]})
        self.assertEqual(cm.exception.code,"E_CONTEXT_INCOMPLETE")
        c=observed; next(iter(c["evidence"].values()))["kind"]="participant_statement"
        with self.assertRaises(MindsError): validate_semantics("claim",d,c)

    def test_unsupported_schema_keyword_fails_closed(self):
        from runtime.minds.contracts import _check_schema
        with self.assertRaises(MindsError): _check_schema({"unevaluatedProperties":False})

    def test_control_intent_nullable_actor_and_spawn_refusal(self):
        d=fixture("action_intent")
        d.update(kind="verify",actor_id=None,round=1,budget_reservation={"agent_turns":0,"verification_actions":1})
        validate_semantics("action_intent",d,{"actor_ids":["intj"]})
        d.update(kind="spawn",budget_reservation={"agent_turns":1,"verification_actions":0})
        with self.assertRaises(MindsError): validate_semantics("action_intent",d,{"actor_ids":["intj"]})

    def test_invalid_context_and_vote_verdict(self):
        with self.assertRaises(MindsError) as cm: validate_semantics("claim",fixture("claim"),{"evidence":{"E1":5}})
        self.assertEqual(cm.exception.code,"E_SCHEMA")
        v=fixture("vote_summary"); v["verdict"]="pass"
        with self.assertRaises(MindsError): validate_semantics("vote_summary",v,context())

if __name__=="__main__": unittest.main()
