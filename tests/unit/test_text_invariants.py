import unittest
from minds.text_invariants import count_text, extract_invariants, compare_draft, writing_result, text_hash, CATEGORIES
from minds.errors import MindsError

def review(source,draft,status='preserved',diff=None):
    return {'source_hash':text_hash(source),'draft_hash':text_hash(draft),'reviewed_categories':sorted(CATEGORIES),'reason':'Explicit synthetic semantic assessment','status':status,'diff':diff or []}

class WritingTests(unittest.TestCase):
    def test_counts_unicode_final_body(self):
        self.assertEqual(count_text('中e\u0301👩\u200d💻'),6)
        self.assertEqual(count_text('one\t two\nthree','words'),3)
        r=writing_result(run_id='r',body='中e\u0301👩\u200d💻')
        self.assertEqual(r['actual_length'],6)
    def test_source_version_required(self):
        with self.assertRaises(MindsError): writing_result(run_id='r',body='x',operation='rewrite',source='a')
    def test_changed_prose_never_regex_certified(self):
        for src,dst in [('很多人反馈方便','半数用户好评'),('不保证按期上线','保证按期上线'),('may correlate','causes'),('必ず成功するとは限らない','必ず成功する')]:
            r=compare_draft(src,dst); self.assertEqual(r['status'],'review_needed'); self.assertFalse(r['semantic_reviewed'])
    def test_explicit_semantic_violation(self):
        src='很多人反馈方便'; dst='半数用户好评'
        r=compare_draft(src,dst,semantic_review=review(src,dst,'violation',[{'category':'number','source_span':'0:3','before':'很多人','after':'半数','status':'violation','reason':'Unsupported quantified proportion'}]))
        self.assertEqual(r['status'],'violation')
    def test_structural_number_whitelist(self):
        src='Keep this'; dst='1. Keep this'
        r=compare_draft(src,dst,semantic_review=review(src,dst))
        self.assertEqual(r['status'],'preserved'); self.assertEqual(r['invariant_diff'][0]['category'],'structural_number')
    def test_changed_numbers_need_exact_review(self):
        src='10 users'; dst='20 users'; r=compare_draft(src,dst,semantic_review=review(src,dst))
        self.assertEqual(r['status'],'review_needed')
    def test_review_bound_to_draft(self):
        with self.assertRaises(MindsError): compare_draft('a','b',semantic_review=review('a','c'))
    def test_authorized_change_requires_exact_scope(self):
        src='10 users'; dst='20 users'; d={'category':'number','source_span':'0:2','before':'10','after':'20','status':'authorized_change','reason':'User explicitly updated count'}
        with self.assertRaises(MindsError): compare_draft(src,dst,semantic_review=review(src,dst,'authorized_change',[d]))
        self.assertEqual(compare_draft(src,dst,semantic_review=review(src,dst,'authorized_change',[d]),authorized_changes=[d])['status'],'authorized_change')
    def test_same_source_two_variants(self):
        src='Release date remains unknown.'
        for variant in ['entj','infp']:
            r=writing_result(run_id='r',body=src,operation='rewrite',source=src,source_version='v1',variant_id=variant)
            self.assertEqual(r['invariant_status'],'preserved'); self.assertEqual(r['source_version'],'v1')
    def test_unknown_evidence_rejected(self):
        with self.assertRaises(MindsError): writing_result(run_id='r',body='x',evidence_ids=['fake'])

    def test_unchanged_numbered_source_is_preserved(self):
        r=writing_result(run_id='r',body='1. Keep this\n2. Keep that',operation='rewrite',source='1. Keep this\n2. Keep that',source_version='v1')
        self.assertEqual(r['invariant_status'],'preserved')
