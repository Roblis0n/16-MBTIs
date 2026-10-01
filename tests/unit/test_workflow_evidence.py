import hashlib
import unittest
from copy import deepcopy
from minds.evidence import register_evidence, evidence_roots, link_claim, invalidate_stale_source, validate_summary_facts
from minds.synthesis import build_synthesis_packet, attach_attribution
from minds.disputes import classify_dispute, validate_target, build_pair_round
from minds.errors import MindsError

REVIEW={'relevant':True,'scope_matches':True,'versions_match':True,'reason':'The supplied synthetic test output directly reproduces the claimed condition.'}

def evidence(eid='e1',kind='provided_file',**extra):
    return {'evidence_id':eid,'kind':kind,'locator':'fixture.txt:1','content_hash':None,'observed_at':'2026-09-30T00:00:00Z','access_status':'observed','trust_class':'participant_statement' if kind=='participant_statement' else 'untrusted_content','source_version':'1','scope':'fixture-only','excerpt_or_summary':'synthetic material','derived_from':[],'observation':None,**extra}

def claim(cid='c1',actor='intj',**extra):
    return {'claim_id':cid,'revision':1,'actor_id':actor,'kind':'factual','text':'Synthetic test fails when input is empty.','subject_id':'fixture','scope':'fixture-only','assumptions':['empty input'],'evidence_ids':['e1'],'status':'supported','counter_claim_ids':[],'supersedes':None,'change_condition':'A corrected test output',**extra}

class EvidenceTests(unittest.TestCase):
    def setUp(self): self.e=register_evidence(evidence(),content='synthetic material')
    def test_observed_requires_content_and_hash(self):
        with self.assertRaises(MindsError): register_evidence(evidence())
        with self.assertRaises(MindsError): register_evidence(evidence(content_hash='0'*64),content='material')
        self.assertEqual(self.e['e1']['content_hash'],hashlib.sha256(b'synthetic material').hexdigest())
        self.assertEqual(register_evidence(self.e['e1'],self.e,content='synthetic material'),self.e)
    def test_unread_not_support(self):
        e=register_evidence(evidence(access_status='not_accessed',observed_at=None))
        with self.assertRaises(MindsError): link_claim(claim(),e,support_review=REVIEW)
    def test_semantic_review_required(self):
        with self.assertRaises(MindsError): link_claim(claim(),self.e)
        self.assertEqual(link_claim(claim(),self.e,support_review=REVIEW)['status'],'supported')
    def test_repeated_statement_not_independent(self):
        e=register_evidence(evidence('e2','participant_statement',derived_from=['e1']),self.e,content='another actor repeated e1')
        self.assertEqual(evidence_roots(['e1','e2'],e),['e1'])
        with self.assertRaises(MindsError): link_claim(claim(evidence_ids=['e2']),e,support_review=REVIEW)
    def test_stale_is_append_only(self):
        e=invalidate_stale_source(self.e,'e1','0'*64,new_id='e2')
        self.assertEqual(e['e1'],self.e['e1']); self.assertEqual(e['e2']['access_status'],'stale')
        with self.assertRaises(MindsError): link_claim(claim(evidence_ids=['e2']),e,support_review=REVIEW)
    def test_version_mismatch(self):
        with self.assertRaises(MindsError): link_claim(claim(),self.e,support_review=REVIEW,evidence_versions={'e1':'2'})
    def test_unknown_cyclic_reference(self):
        with self.assertRaises(MindsError): register_evidence(evidence('e2',derived_from=['missing']),self.e,content='x')
        e=deepcopy(self.e); e['e1']['derived_from']=['e1']
        with self.assertRaises(MindsError): evidence_roots(['e1'],e)
    def test_summary_new_fact_rejected(self):
        with self.assertRaises(MindsError): validate_summary_facts([{'text':'New unsupported fact','claim_ids':[]}],{'c1':claim()},self.e)
        with self.assertRaises(MindsError): validate_summary_facts([{'text':'Unsupported leap','claim_ids':['c1']}],{'c1':claim()},self.e,support_reviews={'c1':REVIEW})
        r=validate_summary_facts([{'text':claim()['text'],'claim_ids':['c1'],'semantic_review':{'entailed':True,'reason':'Exact claim'}}],{'c1':claim()},self.e,support_reviews={'c1':REVIEW})
        self.assertEqual(r['fact_count'],1)
    def test_minority_retained_and_labels_hidden(self):
        claims=[claim('minority','istp')]+[claim(f'majority{i}',f'actor{i}',text='No issue guessed.',status='unverified',evidence_ids=[]) for i in range(15)]
        packet=build_synthesis_packet(claims,self.e,support_reviews={'minority':REVIEW})
        self.assertEqual(len(packet['claims']),16)
        self.assertEqual(sum(c['status']=='supported' for c in packet['claims']),1)
        self.assertTrue(all('actor_id' not in c for c in packet['claims']))
        self.assertNotIn('minority',[c['claim_id'] for c in packet['claims']])
        a=attach_attribution(packet,claims,reviewed_packet_hash=packet['packet_hash']); self.assertEqual(len(a['attribution']),16)
        with self.assertRaises(MindsError): attach_attribution(packet,claims,reviewed_packet_hash='wrong')
        changed=deepcopy(packet); changed['claims'][0]['text']='tampered'
        with self.assertRaises(MindsError): attach_attribution(changed,claims,reviewed_packet_hash=packet['packet_hash'])
        swapped=deepcopy(claims); swapped[0]['actor_id']='intruder'
        with self.assertRaises(MindsError): attach_attribution(packet,swapped,reviewed_packet_hash=packet['packet_hash'])

class PairTests(unittest.TestCase):
    def challenge(self):
        return {'target_claim_id':'c1','steelman':'Fails only for empty input','target_scope':'fixture-only','preserved_conditions':['empty input'],'attributed_evidence_ids':['e1'],'steelman_review':{'faithful':True,'reason':'Preserves the stated exception'}}
    def test_exception_and_invented_evidence(self):
        index={'c1':claim()}; self.assertEqual(validate_target(self.challenge(),index)['target_claim_id'],'c1')
        for override in ({'target_claim_id':'absent'},{'target_scope':'all systems'},{'preserved_conditions':[]},{'attributed_evidence_ids':['fake']},{'steelman_review':{}}):
            with self.assertRaises(MindsError): validate_target({**self.challenge(),**override},index)
    def test_classifier_explicit_value_route(self):
        self.assertEqual(classify_dispute(claim(),claim('c2'))['status'],'needs_assessment')
        self.assertEqual(classify_dispute(claim(),claim('c2'),{'kind':'value','reason':'Different goals'})['next_step'],'return_to_user_goal')
    def test_no_new_information_stops(self):
        s={'actor_ids':['a','b'],'results':[],'round':1,'frozen':True}
        self.assertEqual(build_pair_round(s)['status'],'stopped')
        with self.assertRaises(MindsError): build_pair_round({**s,'frozen':False})
    def test_frozen_equal_inputs_and_retraction_allowed(self):
        s={'actor_ids':['a','b'],'results':[],'round':1,'frozen':True,'new_evidence_ids':['e1'],'evidence':register_evidence(evidence(),content='fixture')}
        r=build_pair_round(s)
        self.assertEqual(r['inputs'][0]['previous_snapshot'],r['inputs'][1]['previous_snapshot'])
        self.assertIn('retracted',r['inputs'][0]['allowed_stance_changes'])
