import unittest
from copy import deepcopy
from runtime.minds.scheduler import prepare_run,next_actions,step,advance_round,cancel_run,resume_run,dispatch
from runtime.minds.context import build_actor_context,restore_actor
from runtime.minds.adapter_contract import isolation_parameters,record_receipt
from runtime.minds.budget import preflight,reserve_budget,commit_observation
from runtime.minds.errors import MindsError
from tests.unit.test_contracts import fixture


def prepared(n=4,cap=2,rounds=2):
    from runtime.minds.resources import registry
    req=fixture('request'); req.update(workflow='many',workflow_options=None,n=n,mode='heavy' if rounds==3 else 'middle',locked_personas=[])
    req['budget'].update(max_rounds=rounds,max_agent_turns=n*rounds,concurrency_cap=cap)
    roster=fixture('roster'); roster.update(run_id='run-1',requested_n=n,members=[{'actor_id':a,'source':'heuristic','newly_covered_tags':[],'reason':'synthetic'} for a in registry()['personas'][:n]])
    capabilities=fixture('capabilities'); capabilities.update(native_delegation='observed',isolation_status='verified_clean',open_thread_cap=cap,close_supported=True)
    return prepare_run(req,roster,capabilities,run_id='run-1')


def complete_action(s,a):
    s=step(s,{'kind':'intent','intent':a['intent'],'attempt_id':a['attempt_id']})['state']
    receipt={'action_id':a['intent']['action_id'],'host_thread_id':'thread-'+a['intent']['action_id'],'receipt_ref':'synthetic-receipt'}
    s=step(s,record_receipt(a['intent'],receipt))['state']
    result=fixture('agent_result'); result.update(run_id='run-1',actor_id=a['intent']['actor_id'],action_id=a['intent']['action_id'],attempt_id=a['attempt_id'],round=a['intent']['round'],input_hash=a['intent']['input_hash'],persona_revision=a['context']['persona_revision'],claims=[],score_records=[],limitations=['Only valid offline; not 10 online users.'])
    return step(s,{'kind':'result','result':result})['state']


def close(s,a):
    s=step(s,{'kind':'intent','intent':a['intent']})['state']
    return step(s,{'kind':'cleanup','closed_thread_ids':[a['host_thread_id']],'receipt_ref':'synthetic-close'})['state']


def complete_round(s):
    while next_actions(s):
        actions=next_actions(s)
        # Always re-read after each checkpoint, as resource slots may change.
        a=actions[0]
        s=close(s,a) if a['intent']['kind']=='close' else complete_action(s,a)
    return s


class SchedulerTests(unittest.TestCase):
    def test_16_actor_two_round_rehydration(self):
        s=prepared(16,4); s=complete_round(s)
        self.assertEqual(s['reducer']['run']['spent_agent_turns'],16)
        s=advance_round(s,{'new_evidence_task':'Check synthetic offline scope'})
        snap=deepcopy(s['snapshots']['2']); a=next_actions(s)[0]; s=complete_action(s,a)
        for actor in s['reducer']['run']['actor_ids']:
            ctx=build_actor_context(snap,actor)
            self.assertEqual(len(ctx['own_history']),1)
            self.assertIn('Only valid offline',ctx['limitations'][0])
            self.assertTrue(all(r['round']==1 for r in ctx['peer_previous_results']))
            self.assertEqual(restore_actor(ctx),ctx)
        self.assertEqual(s['snapshots']['2'],snap)
        s=complete_round(s); self.assertEqual(s['reducer']['run']['spent_agent_turns'],32)

    def test_verification_and_malformed_envelopes(self):
        from runtime.minds.scheduler import request_verification,scheduler_status
        s=prepared()
        task={'kind':'supplied_material','question':'Is the fixture version exact?','source_ref':'synthetic-file'}
        s=request_verification(s,task,'user-synthetic-authorization')
        self.assertEqual(request_verification(s,task,'user-synthetic-authorization'),s)
        a=next_actions(s)[0]; self.assertEqual(a['intent']['kind'],'verify')
        s=step(s,{'kind':'intent','intent':a['intent'],'attempt_id':a['attempt_id']})['state']
        self.assertEqual(s['reducer']['run']['spent_verification_actions'],1)
        s=step(s,record_receipt(a['intent'],{'action_id':a['intent']['action_id'],'host_thread_id':None,'receipt_ref':'synthetic-verify'}))['state']
        s=step(s,{'kind':'task_status','action_id':a['intent']['action_id'],'status':'succeeded','receipt_ref':'synthetic-complete'})['state']
        with self.assertRaises(MindsError): request_verification(s,{**task,'kind':'network'},'not-enough-authority')
        self.assertIsNone(scheduler_status(s)['blocker'])
        with self.assertRaises(MindsError): next_actions({'scheduler_version':'1.0.0'})
        broken=deepcopy(s); broken['snapshots']['1']={}
        with self.assertRaises(MindsError): next_actions(broken)

    def test_round_three_preserves_original_exception(self):
        s=prepared(2,2,3)
        for _ in range(2):
            s=complete_round(s)
            s=advance_round(s,{'new_evidence_task':'Check original offline limitation'})
        for a in next_actions(s):
            self.assertEqual(len(a['context']['own_history']),2)
            self.assertTrue(all('Only valid offline' in x for x in a['context']['limitations']))
            self.assertEqual(a['context']['omitted_claims'],[])

    def test_four_open_slots_and_idle_threads_count(self):
        s=prepared(16,4)
        proposals=next_actions(s)
        self.assertEqual(len(proposals),4)
        for a in proposals:
            s=step(s,{'kind':'intent','intent':a['intent'],'attempt_id':a['attempt_id']})['state']
        self.assertEqual(next_actions(s),[])
        for a in proposals:
            s=step(s,record_receipt(a['intent'],{'action_id':a['intent']['action_id'],'host_thread_id':'slot-'+a['intent']['actor_id'],'receipt_ref':'synthetic-slot'}))['state']
        self.assertEqual(len(s['reducer']['run']['residual_thread_ids']),4)
        a=proposals[0]
        s=step(s,{'kind':'task_status','action_id':a['intent']['action_id'],'status':'failed','receipt_ref':'synthetic-failure'})['state']
        pending=next_actions(s)
        self.assertEqual([x['intent']['kind'] for x in pending],['close'])
        s=close(s,pending[0])
        self.assertEqual(len(next_actions(s)),1)
        self.assertEqual(next_actions(s)[0]['intent']['kind'],'spawn')

    def test_unknown_dispatch_no_retry_and_wait_not_failure(self):
        s=prepared(); a=next_actions(s)[0]; event={'kind':'intent','intent':a['intent'],'attempt_id':a['attempt_id']}
        s=step(s,event)['state']; self.assertEqual(step(s,event)['state']['reducer']['run']['spent_agent_turns'],1)
        s=step(s,{'kind':'task_status','action_id':a['intent']['action_id'],'status':'dispatch_unknown','receipt_ref':'synthetic-unknown'})['state']
        self.assertEqual(next_actions(s),[])
        s=step(s,{'kind':'wait_timeout','action_id':a['intent']['action_id']})['state']
        self.assertEqual(s['reducer']['tasks'][a['intent']['action_id']]['status'],'dispatch_unknown')

    def test_repair_spends_same_total_budget(self):
        s=prepared(); a=next_actions(s)[0]
        s=step(s,{'kind':'intent','intent':a['intent'],'attempt_id':a['attempt_id']})['state']
        s=step(s,record_receipt(a['intent'],{'action_id':a['intent']['action_id'],'host_thread_id':'bad-thread','receipt_ref':'synthetic'}))['state']
        s=step(s,{'kind':'task_status','action_id':a['intent']['action_id'],'status':'invalid_output','receipt_ref':'synthetic-invalid'})['state']
        s=close(s,next_actions(s)[0]); a=next_actions(s)[0]
        self.assertEqual(a['attempt_id'],'attempt-2'); self.assertIn('repair_instruction',a['context'])
        s=complete_action(s,a); s=complete_round(s)
        self.assertEqual(s['reducer']['run']['spent_agent_turns'],5)
        with self.assertRaises(MindsError): advance_round(s,{'target_claim_id':'c1'})

    def test_preflight_missing_and_unknown(self):
        req=fixture('request'); caps=fixture('capabilities'); caps['native_delegation']='unsupported'
        with self.assertRaises(MindsError): preflight(req,caps)
        req['permissions']['allow_simulation']=True
        self.assertEqual(preflight(req,caps)['execution_mode'],'single_context')
        caps.update(native_delegation='observed',isolation_status='unknown')
        with self.assertRaises(MindsError): preflight(req,caps)
        caps.update(isolation_status='verified_clean',open_thread_cap=None)
        self.assertEqual(preflight(req,caps)['concurrency'],1)
        req['budget']['max_agent_turns']=1; req['n']=4
        with self.assertRaises(MindsError): preflight(req,caps)

    def test_forgery_resume_and_deadline(self):
        s=prepared(); a=next_actions(s)[0]; a['intent']['actor_id']='esfp'
        with self.assertRaises(MindsError): step(s,{'kind':'intent','intent':a['intent'],'attempt_id':a['attempt_id']})
        with self.assertRaises(MindsError): step(s,{'kind':'transition','to':'running','round':2})
        with self.assertRaises(MindsError): resume_run(s,{})
        versions={k:s[k] for k in ('persona_revision','evidence_version')}; versions.update(input_hash=s['reducer']['run']['input_hash'],protocol_version='1.0.0')
        self.assertEqual(resume_run(s,versions),s)
        cancelled=cancel_run(s)['state']; self.assertEqual(next_actions(cancelled),[])
        self.assertEqual(cancel_run(cancelled)['state'],cancelled)
        elapsed=step(s,{'kind':'elapsed','seconds':10000})['state']; self.assertEqual(elapsed['reducer']['run']['status'],'partial')
        with self.assertRaises(MindsError): step(elapsed,{'kind':'elapsed','seconds':1})
        with self.assertRaises(MindsError): dispatch({'op':'actions','state':s,'extra':1})
        self.assertEqual(dispatch({'op':'actions','state':s}),next_actions(s))

    def test_adapter_budget_and_context_boundaries(self):
        self.assertEqual(isolation_parameters(['fork_turns']),{'fork_turns':'none'})
        self.assertEqual(isolation_parameters(['fork_context']),{'fork_context':False})
        self.assertEqual(isolation_parameters([]),{})
        with self.assertRaises(MindsError): isolation_parameters('fork_turns')
        s=prepared(); a=next_actions(s)[0]
        with self.assertRaises(MindsError): record_receipt(a['intent'],{})
        run=reserve_budget(a['intent'],s['reducer']['run']); self.assertEqual(run['spent_agent_turns'],1)
        self.assertIsNone(commit_observation({'receipt_ref':'synthetic'})['observed_tokens'])
        with self.assertRaises(MindsError): commit_observation({'receipt_ref':'r','observed_tokens':True})
        snapshot=deepcopy(s['snapshots']['1']); snapshot['round']=2
        with self.assertRaises(MindsError): build_actor_context(snapshot,'intj')
        with self.assertRaises(MindsError): restore_actor({'context_complete':False})

    def test_no_close_preserves_residual(self):
        s=prepared(4,1); s['capabilities']['close_supported']=False
        s=complete_action(s,next_actions(s)[0]); self.assertEqual(next_actions(s),[])
        s=cancel_run(s)['state']; self.assertEqual(s['reducer']['run']['cleanup_status'],'unknown')
        self.assertEqual(len(s['reducer']['run']['residual_thread_ids']),1)

if __name__=='__main__': unittest.main()
