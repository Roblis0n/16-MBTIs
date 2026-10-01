import unittest
from minds.decision import filter_feasible, validate_decision, decide
from minds.errors import MindsError

def candidates(a='pass',b='pass'):
    return [{'id':i,'version':'1','description':i,'assessments':{'budget':{'status':s,'reason':'Synthetic budget comparison'}}} for i,s in [('A',a),('B',b)]]

class DecisionTests(unittest.TestCase):
    def test_no_feasible_and_missing_license(self):
        r=decide({'candidates':candidates('fail','fail'),'hard_constraints':['budget']})
        self.assertEqual(r['status'],'no_feasible_option'); self.assertIsNone(r['selected'])
        with self.assertRaises(MindsError): filter_feasible(candidates(),['license'])
        # Assessing unrelated constraints must be rejected, never silently reused.
    def test_unknown_not_pass(self):
        r=filter_feasible(candidates('unknown','fail'),['budget'])
        self.assertEqual(r['status'],'needs_information'); self.assertEqual(r['feasible_ids'],[])
    def test_missing_assessments(self):
        c=candidates(); [x.pop('assessments') for x in c]
        self.assertEqual(filter_feasible(c,['license'])['unknown_ids'],['A','B'])
    def test_explicit_decision_goal_and_feasibility(self):
        ctx={'candidates':candidates(),'hard_constraints':['budget'],'user_goal':'save time'}
        d={'run_id':'r','decision_id':'d','decision_version':'1','status':'decided','candidate_ids':['A','B'],'selected':'A','user_goal':'save time','hard_constraints':['budget'],'strongest_case':'faster','weakest_case':'less flexible','risk':['limited scope'],'revisit_when':[],'missing_information':[],'violations':[],'evidence_ids':[]}
        self.assertEqual(validate_decision(d,ctx)['selected'],'A')
        for extra in ({'selected':'C'},{'user_goal':'perfection'}):
            with self.assertRaises(MindsError): validate_decision({**d,**extra},ctx)
        with self.assertRaises(MindsError): validate_decision(d,{**ctx,'candidates':candidates('unknown','pass')})
    def test_duplicate_and_no_candidate(self):
        for c in ([],candidates()[:1],[candidates()[0]]*2):
            with self.assertRaises(MindsError): filter_feasible(c,['budget'])
