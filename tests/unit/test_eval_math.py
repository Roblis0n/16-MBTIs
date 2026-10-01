import copy
import json
import unittest
from pathlib import Path
from evaluation.protocol import *

class EvalMathTests(unittest.TestCase):
    def test_family_repetition(self):
        records=[{'status':'completed','project_group':'same-file','quality':i,'cost':1,'latency_seconds':2,'answer_sha256':'a'*64} for i in (1,2,3)]
        report=summarize(records)
        self.assertEqual(report['independent_families'],1)
        self.assertEqual(report['mean_family_quality'],2)
    def test_failure_cost_retained(self):
        rows=[{'status':s,'project_group':'g','quality':None,'cost':2,'latency_seconds':1,'answer_sha256':'b'*64} for s in ('failed','timeout','cancelled')]
        self.assertEqual(summarize(rows)['known_cost'],6)
        self.assertEqual(summarize(rows)['completion_rate'],0)
    def test_unobservable_tokens(self):
        self.assertEqual(budget_match([{'actions':3},{'actions':3}]),'action_matched')
        runs=[dict(input_tokens=1,output_tokens=2,reasoning_tokens=3,actions=3)]*2
        self.assertEqual(budget_match(runs),'token_matched')
        self.assertEqual(budget_match([]),'unmatched')
    def test_leakage(self):
        tasks=[dict(id='1',project_group='file',split='development'),dict(id='2',project_group='file',split='holdout')]
        with self.assertRaises(ValueError): validate_family_splits(tasks)
        with self.assertRaises(ValueError): validate_family_splits([dict(id='1',project_group='file',split='holdout',exposed=True)])
    def test_judge_length_and_swap(self):
        r=judge_pairs('short','very long answer'*10)
        self.assertTrue(r['length_confounded'])
        self.assertEqual(r['pairs'][0]['A'],r['pairs'][1]['B'])
    def test_no_marginal_gain(self):
        self.assertEqual(marginal_benefit(0,16)['outcome'],'negative')
        self.assertFalse(marginal_benefit(10,16)['change_default'])
    def test_dry_run(self):
        root=Path(__file__).resolve().parents[2]
        protocol=json.loads((root/'evaluation/protocol.json').read_text())
        tasks=json.loads((root/'evaluation/tasks/development.json').read_text())
        r=evaluate(protocol,0,tasks)
        self.assertEqual(r['external_calls'],0); self.assertEqual(r['status'],'not_run')
        self.assertEqual(evaluate(protocol,0,tasks),r)
    def test_invalid(self):
        for n in (-1,float('nan'),True):
            with self.assertRaises(ValueError): number(n)
        with self.assertRaises(ValueError): summarize([{'status':'completed','project_group':'g'}])
        with self.assertRaises(ValueError): evaluate({},0,[])

class ObservationTests(unittest.TestCase):
    def test_append_only_observation(self):
        import tempfile
        from evaluation.observations import record_response
        row={'observation_id':'synthetic-1','task_id':'engineering-2','project_group':'synthetic-boundary','split':'development','baseline':'B0','status':'failed','model_id':None,'model_settings':None,'tool_scope':[], 'input_tokens':None,'output_tokens':None,'reasoning_tokens':None,'actions':1,'agent_rounds':1,'latency_seconds':None,'cost':None,'quality':None,'observed_at':'synthetic-test','provenance':'Unit fixture, not real model response','generation_kind':'synthetic_fixture'}
        with tempfile.TemporaryDirectory() as d:
            r=record_response(d,row,'Synthetic failure observation')
            self.assertEqual(len(r['answer_sha256']),64)
            self.assertEqual(summarize([r])['completion_rate'],0)
            self.assertFalse(summarize([r])['cost_complete'])
            with self.assertRaises(FileExistsError): record_response(d,row,'new')
            with self.assertRaises(ValueError): record_response(d,{**row,'observation_id':'../bad'},'x')
    def test_executable_development_gold(self):
        from evaluation.check_development import check
        self.assertEqual(check()['status'],'pass')
        self.assertEqual(len(check()['checks']),8)
