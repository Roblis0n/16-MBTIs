import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'runtime'))
from minds.calibration import *
from minds.errors import MindsError

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.f={k:'known' for k in FIELDS}
        self.c=generate_candidate('candidate-1',self.f,[{'split':'development','answer_sha256':'a'*64}])
    def test_fingerprint_change(self):
        self.assertEqual(fingerprint_match(self.f,self.f),'exact')
        changed={**self.f,'persona_hash':'known!'}
        self.assertEqual(fingerprint_match(self.f,changed),'mismatch')
        self.assertEqual(fingerprint_match({k:None for k in FIELDS},{k:None for k in FIELDS}),'unknown')
        self.assertEqual(fingerprint_match({**self.f,'seed':None},self.f),'partial_match')
    def test_no_holdout_generation(self):
        with self.assertRaises(MindsError): generate_candidate('x',self.f,[{'split':'holdout','answer_sha256':'a'*64}])
    def test_errata_recomputes(self):
        rows=[{'id':'1','verified':True},{'id':'2','verified':True},{'id':'3','verified':False}]
        original=copy.deepcopy(rows)
        r=apply_errata(rows,[{'id':'1','reason':'false positive','changes':{'verified':False}}, {'id':'3','reason':'out of scope','changes':{'excluded':True}}],errata_ref='ERRATA-1')
        self.assertEqual(r['before'],{'numerator':2,'denominator':3})
        self.assertEqual(r['after'],{'numerator':1,'denominator':2}); self.assertEqual(rows,original)
    def approval(self):
        return {'candidate_sha256':hashlib.sha256(json.dumps(self.c,sort_keys=True).encode()).hexdigest(), 'approval_ref':'test-only-fixture','reviewer_ref':'independent-fixture','holdout_report_ref':'synthetic-fixture','holdout_passed':True,'safety_passed':True,'practical_gain_passed':True}
    def test_self_approval_refused(self):
        self.c['approved']=True
        with self.assertRaises(MindsError): activate_with_approval(self.c,self.approval())
    def test_trusted_activation_and_revoke(self):
        before=copy.deepcopy(self.c)
        p=activate_with_approval(self.c,self.approval(),verifier=lambda a,h:True,current_fingerprint=self.f)
        self.assertEqual(p['state'],'active'); self.assertEqual(self.c,before)
        self.assertEqual(revoke_pointer(p,reason='test')['state'],'uncalibrated')
    def test_negative_holdout_and_untrusted(self):
        a=self.approval(); a['practical_gain_passed']=False
        with self.assertRaises(MindsError): activate_with_approval(self.c,a,verifier=lambda a,h:True,current_fingerprint=self.f)
        with self.assertRaises(MindsError): activate_with_approval(self.c,self.approval(),verifier=lambda a,h:False,current_fingerprint=self.f)
    def test_bad_input(self):
        with self.assertRaises(MindsError): generate_candidate('x',{},[])
        with self.assertRaises(MindsError): apply_errata([{'id':'x','verified':True}], [{'id':'x','reason':'r','changes':{'verified':1}}],errata_ref='e')
