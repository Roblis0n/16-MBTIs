import unittest
from copy import deepcopy
from runtime.minds.state import new_reducer_state,reduce_state
from runtime.minds.errors import MindsError
from tests.unit.test_contracts import fixture

def running():
    run=fixture("run_state"); run.update(actor_ids=["intj"],status="running",round=1,input_hash="a"*64)
    return new_reducer_state(run)

def intent():
    i=fixture("action_intent"); i.update(action_id="action-1",actor_id="intj",round=1,input_hash="a"*64,kind="spawn",dispatch_status="proposed",host_receipt_ref=None,budget_reservation={"agent_turns":1,"verification_actions":0})
    return {"kind":"intent","intent":i,"attempt_id":"attempt-1"}

def dispatched():
    s=reduce_state(running(),intent())
    return reduce_state(s,{"kind":"receipt","action_id":"action-1","host_thread_id":"physical-A","receipt_ref":"receipt-1"})

def result_event():
    d=fixture("agent_result"); d.update(actor_id="intj",action_id="action-1",attempt_id="attempt-1",input_hash="a"*64,claims=[],score_records=[])
    return {"kind":"result","result":d}

class StateTests(unittest.TestCase):
    def test_x_state_01_all_terminal_late_results(self):
        for status in ("completed","partial","failed","cancelled","blocked"):
            s=running(); s["run"]["status"]=status
            before=deepcopy(s)
            out=reduce_state(s,result_event())
            self.assertEqual(out["run"],s["run"]); self.assertEqual(s,before)
            self.assertEqual(out["events"][-1]["kind"],"late_result")
            out=reduce_state(out,{"kind":"transition","to":"running"})
            self.assertEqual(out["run"]["status"],status)

    def test_x_state_02_duplicates(self):
        s=reduce_state(dispatched(),result_event()); original=deepcopy(s["results"])
        same=reduce_state(s,result_event())
        self.assertEqual(same["results"],original); self.assertEqual(same["events"][-1]["kind"],"duplicate_ignore")
        event=result_event(); event["result"]["summary"]="contradiction"
        conflict=reduce_state(same,event)
        self.assertEqual(conflict["results"],original); self.assertEqual(len(conflict["quarantine"]),1)

    def test_transitions_and_immutability(self):
        s=new_reducer_state(fixture("run_state")); before=deepcopy(s)
        with self.assertRaises(MindsError): reduce_state(s,{"kind":"transition","to":"completed"})
        self.assertEqual(s,before)
        s=reduce_state(s,{"kind":"transition","to":"validated"})
        with self.assertRaises(MindsError): reduce_state(s,{"kind":"transition","to":"prepared"})
        s=reduce_state(s,{"kind":"transition","to":"prepared","input_hash":"a"*64})
        s=reduce_state(s,{"kind":"transition","to":"running","round":1})
        self.assertEqual(s["run"]["status"],"running")

    def test_wait_timeout_does_not_timeout_task(self):
        s=dispatched(); out=reduce_state(s,{"kind":"wait_timeout","action_id":"action-1"})
        self.assertEqual(out["tasks"],s["tasks"])

    def test_budget_and_intent_idempotency(self):
        s=reduce_state(running(),intent()); out=reduce_state(s,intent())
        self.assertEqual(out["run"]["spent_agent_turns"],1)
        s=running(); s["run"]["spent_agent_turns"]=s["run"]["budget"]["max_agent_turns"]
        with self.assertRaises(MindsError) as cm: reduce_state(s,intent())
        self.assertEqual(cm.exception.code,"E_BUDGET_EXHAUSTED")

    def test_thread_identity_and_completion(self):
        s=dispatched(); self.assertEqual(s["tasks"]["action-1"]["host_thread_id"],"physical-A")
        self.assertEqual(s["run"]["actor_ids"],["intj"])
        s=reduce_state(s,result_event())
        s=reduce_state(s,{"kind":"transition","to":"synthesizing"})
        s=reduce_state(s,{"kind":"transition","to":"completed"})
        self.assertEqual(s["run"]["cleanup_status"],"pending")
        s=reduce_state(s,{"kind":"cleanup","closed_thread_ids":["physical-A"],"receipt_ref":"close-1"})
        self.assertEqual(s["run"]["cleanup_status"],"confirmed")

    def test_result_identity_and_unknown_dispatch(self):
        s=dispatched(); e=result_event(); e["result"]["actor_id"]="entp"
        with self.assertRaises(MindsError): reduce_state(s,e)
        s=reduce_state(running(),intent())
        s=reduce_state(s,{"kind":"task_status","action_id":"action-1","status":"dispatch_unknown","receipt_ref":"uncertain-1"})
        e=intent(); e["intent"]["action_id"]="new-action"
        with self.assertRaises(MindsError): reduce_state(s,e)

    def test_cancel_then_late_receipt_keeps_cleanup_visible(self):
        s=reduce_state(running(),intent())
        s=reduce_state(s,{"kind":"transition","to":"cancelled","reason":"用户取消"})
        s=reduce_state(s,{"kind":"receipt","action_id":"action-1","host_thread_id":"late-physical","receipt_ref":"late-receipt"})
        self.assertEqual(s["run"]["status"],"cancelled")
        self.assertEqual(s["run"]["residual_thread_ids"],["late-physical"])
        self.assertEqual(s["run"]["cleanup_status"],"unknown")

    def test_every_transition_edge(self):
        from runtime.minds.resources import resource_json
        table=resource_json("contracts/state_transitions.json")
        for status,targets in table.items():
            if not targets: continue
            for target in table:
                s=running(); s["run"].update(status=status,completed_actor_ids=["intj"])
                event={"kind":"transition","to":target,"reason":"synthetic transition"}
                with self.subTest(start=status,to=target):
                    if target in targets: self.assertEqual(reduce_state(s,event)["run"]["status"],target)
                    else:
                        with self.assertRaises(MindsError): reduce_state(s,event)

if __name__=="__main__": unittest.main()
