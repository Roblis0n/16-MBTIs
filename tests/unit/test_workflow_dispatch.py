import unittest
from copy import deepcopy
from minds.synthesis import dispatch_workflow
from minds.normalize import normalize_request
from minds.errors import MindsError
from tests.unit.test_interview import questions
from tests.unit.test_vote import ballot
from tests.unit.test_workflow_evidence import evidence

class WorkflowDispatchTests(unittest.TestCase):
    def test_public_cast_uses_frozen_request(self):
        request=normalize_request('minds-cast --n 6 -- inspect this project')
        result=dispatch_workflow('cast',{'request':request})
        self.assertEqual(result['agent_turns'],0); self.assertEqual(result['roster']['requested_n'],6)
        with self.assertRaises(MindsError): dispatch_workflow('cast',{'request':{'n':6}})
        request['extra']='unsupported'
        with self.assertRaises(MindsError): dispatch_workflow('cast',{'request':request})
    def test_all_public_operations(self):
        examples={
            'aggregate':{'records':[]},
            'pair':{'snapshot':{'actor_ids':['a','b'],'round':1,'results':[],'frozen':True}},
            'synthesis':{'claims':[],'evidence':{}},
            'decide':{'context':{'candidates':[{'id':'A','version':'1','description':'a'},{'id':'B','version':'1','description':'b'}],'hard_constraints':['license']}},
            'vote':{'ballots':[ballot('a')],'eligible':['a'],'run_id':'r','proposal_id':'p','proposal_version':'1'},
            'write':{'run_id':'r','body':'Draft supplied explicitly'},
            'ask':{'action':'create','questions':questions(2),'ask_mode':'interview'},
            'summary_facts':{'facts':[],'claims':{},'evidence':{}},
            'register_evidence':{'record':evidence(),'content':'fixture'},
            'revise_proposal':{'old':{'proposal_id':'p','proposal_version':'1'},'new':{'proposal_id':'p','proposal_version':'2','diff':'Changed condition'},'remaining_turns':0,'eligible':['a']},
        }
        for op,payload in examples.items():
            self.assertIsNotNone(dispatch_workflow(op,payload))
            with self.assertRaises(MindsError): dispatch_workflow(op,{**payload,'unrecognized':True})
    def test_ask_end_to_end_dispatch(self):
        state=dispatch_workflow('ask',{'action':'create','questions':questions(1),'ask_mode':'interview'})
        state=dispatch_workflow('ask',{'action':'next','state':state})
        self.assertEqual(len(dispatch_workflow('ask',{'action':'render','state':state})),1)
        state=dispatch_workflow('ask',{'action':'answer','state':state,'question_id':'q0','answer_summary':'500'})
        self.assertEqual(state['status'],'completed')
    def test_malformed_inputs_redacted(self):
        for op,payload in [('missing',{}),('cast',[]),('decide',{'context':None}),('vote',{'ballots':[None],'eligible':['a'],'run_id':'r','proposal_id':'p','proposal_version':'1'}),('write',{'run_id':'r','body':None}),('ask',{'action':'next','state':{}})]:
            if op=='vote':
                # Malformed ballots are quarantined and coverage remains missing.
                r=dispatch_workflow(op,payload); self.assertEqual(r['counts']['responded'],0)
            else:
                with self.assertRaises(MindsError): dispatch_workflow(op,payload)
    def test_nested_unknown_fields_rejected(self):
        for op,payload in [('aggregate',{'records':[{'actor_id':'a','subject_id':'s','subject_version':'1','criterion_id':'c','scale_id':'five','value':5,'revision':2}]}),('pair',{'snapshot':{'actor_ids':['a','b'],'round':1,'results':[],'frozen':True,'secret_override':True}}),('decide',{'context':{'candidates':[],'hard_constraints':[],'execute':True}})]:
            with self.assertRaises(MindsError): dispatch_workflow(op,payload)

    def test_peer_review_stale_refutation_and_value_laundering(self):
        from tests.unit.test_workflow_evidence import claim, REVIEW
        from minds.evidence import register_evidence, invalidate_stale_source
        e=register_evidence(evidence(),content='fixture')
        e=invalidate_stale_source(e,'e1','0'*64,new_id='e2')
        with self.assertRaises(MindsError): dispatch_workflow('synthesis',{'claims':[claim(status='refuted',evidence_ids=['e2'])],'evidence':e,'support_reviews':{'c1':REVIEW}})
        preference=claim(kind='value_preference',evidence_ids=[])
        with self.assertRaises(MindsError): dispatch_workflow('summary_facts',{'facts':[{'text':'An external factual statement','claim_ids':['c1'],'semantic_review':{'entailed':True,'reason':'assertion'}}],'claims':{'c1':preference},'evidence':{}})
    def test_peer_review_revision_shape(self):
        good={'old':{'proposal_id':'p','proposal_version':'1'},'new':{'proposal_id':'p','proposal_version':'2','diff':'Updated scope'},'remaining_turns':2,'eligible':['a','b']}
        for patch in ({'new':{**good['new'],'proposal_version':None}},{'eligible':[]},{'remaining_turns':True},{'new':{**good['new'],'execute_shell':'do not run'}}):
            with self.assertRaises(MindsError): dispatch_workflow('revise_proposal',{**good,**patch})
