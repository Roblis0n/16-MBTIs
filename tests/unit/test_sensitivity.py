import unittest
from runtime.minds.sensitivity import linear_threshold,prioritize_verifications
from runtime.minds.errors import MindsError
class SensitivityTests(unittest.TestCase):
    def test_threshold_and_no_crossing(self):
        a={'intercept':0,'slope':2,'unit':'USD'}; b={'intercept':10,'slope':0,'unit':'USD'}
        self.assertEqual(linear_threshold(a,b,[0,10],'USD')['threshold'],5)
        self.assertIsNone(linear_threshold(a,b,[6,10],'USD')['threshold'])
        b['unit']='EUR'
        with self.assertRaises(MindsError): linear_threshold(a,b,[0,10],'USD')
    def test_bad_domain_and_booleans(self):
        a={'intercept':True,'slope':2,'unit':'USD'}
        with self.assertRaises(MindsError): linear_threshold(a,a,[0,10],'USD')
    def test_max_three_and_no_ev(self):
        actions=[dict(hypothesis=str(i),observation='sample',success_action='A',failure_action='B',cost_limit='one hour proposed',could_change_choice=True,impact='high',observable=True) for i in range(4)]
        self.assertEqual(len(prioritize_verifications(actions)),3)
    def test_original_wp23_formula_and_parallel(self):
        a={'intercept':100,'slope':2,'unit':'cost_units'};b={'intercept':40,'slope':5,'unit':'cost_units'}
        self.assertEqual(linear_threshold(a,b,[0,100],'cost_units')['threshold'],20)
        b['slope']=2;self.assertEqual(linear_threshold(a,b,[0,100],'cost_units')['relationship'],'parallel')
    def test_new_evidence_creates_new_version(self):
        from runtime.minds.sensitivity import revise_decision
        c=dict(goal='g',evidence=['e1'],assumptions=['a'],thresholds=[],constraints=[])
        r=revise_decision('d1',c,{**c,'evidence':['e2']})
        self.assertNotEqual(r['decision_version'],'d1');self.assertEqual(r['previous_conclusion_status'],'stale');self.assertTrue(r['requires_reassessment'])
        self.assertEqual(revise_decision('d1',c,c)['decision_version'],'d1')
