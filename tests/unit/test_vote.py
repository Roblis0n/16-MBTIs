import itertools
import unittest
from minds.vote import tally_ballots, validate_ballots, revise_proposal
from minds.errors import MindsError

def ballot(voter,choice='yes',**extra):
    return {'run_id':'r','proposal_id':'p','proposal_version':'1','voter_id':voter,'ballot_revision':1,'choice':choice,'reason':'synthetic fixture','conditions':[],'supersedes':None,**extra}

def tally(choices,policy='absolute_majority',n=None,**kw):
    ids=[f'a{i}' for i in range(n or len(choices))]
    return tally_ballots([ballot(ids[i],c) for i,c in enumerate(choices)],ids,policy,run_id='r',proposal_id='p',proposal_version='1',**kw)

class VoteTests(unittest.TestCase):
    def test_c04_examples(self):
        r=tally(['yes']+['abstain']*15); self.assertEqual(r['verdict'],'no_quorum'); self.assertEqual(r['yes_over_eligible'],.0625)
        self.assertEqual(tally(['yes']*8+['no']*8)['verdict'],'tie')
        self.assertEqual(tally(['yes']*9+['abstain']*7)['verdict'],'pass')
        r=tally(['yes']*3,n=4); self.assertEqual((r['verdict'],r['provisional_verdict']),('partial','pass'))
    def test_all_4_voter_combinations(self):
        for choices in itertools.product(['yes','no','abstain'],repeat=4):
            y=choices.count('yes'); n=choices.count('no')
            for policy in ['distribution','absolute_majority','valid_majority','strict_unanimity']:
                kw={'decisive_quorum':2} if policy=='valid_majority' else {}
                r=tally(choices,policy,**kw)
                expected='not_requested' if policy=='distribution' else ('pass' if y==4 else 'fail') if policy=='strict_unanimity' else 'no_quorum' if y+n<2 else 'tie' if y==n else ('pass' if (y>2 if policy=='absolute_majority' else y>n) else 'fail')
                self.assertEqual(r['verdict'],expected)
                self.assertEqual(sum(r['counts'][k] for k in ['yes','no','abstain']),4)
    def test_strict_abstain_and_empty(self):
        self.assertEqual(tally(['yes','abstain'],'strict_unanimity')['verdict'],'fail')
        self.assertEqual(tally([],n=4)['verdict'],'partial')
    def test_required_valid_quorum(self):
        for q in (None,0,5,True):
            with self.assertRaises(MindsError): tally(['yes']*4,'valid_majority',decisive_quorum=q)
    def test_revote_stale_does_not_inherit(self):
        old=[ballot(f'a{i}') for i in range(4)]; new=ballot('a0',proposal_version='2')
        r=tally_ballots(old+[new],[f'a{i}' for i in range(4)],'absolute_majority',run_id='r',proposal_id='p',proposal_version='2',is_revision=True)
        self.assertEqual(r['verdict'],'pending_revote'); self.assertEqual(r['counts']['yes'],1)
    def test_duplicate_and_explicit_revision(self):
        a=ballot('a'); b=ballot('a','no',ballot_revision=2,supersedes='a:1')
        checked=validate_ballots([b,a],['a'],run_id='r',proposal_id='p',proposal_version='1')
        self.assertEqual(checked['ballots'][0]['choice'],'no')
        for rows in ([a,a],[b],[a,ballot('a','no')],[a,ballot('a',ballot_revision=3,supersedes='a:1')]):
            r=validate_ballots(rows,['a'],run_id='r',proposal_id='p',proposal_version='1')
            self.assertEqual(r['invalid_ids'],['a']); self.assertEqual(r['ballots'],[])
    def test_unknown_and_failed_separate(self):
        r=tally_ballots([ballot('outsider')],['a','b'],'absolute_majority',run_id='r',proposal_id='p',proposal_version='1',failed_ids=['a'])
        self.assertEqual(r['failed_ids'],['a']); self.assertEqual(r['missing_ids'],['b']); self.assertTrue(r['limitations'])
    def test_revision_budget_and_conflicts(self):
        old={'proposal_id':'p','proposal_version':'1'}; new={'proposal_id':'p','proposal_version':'2','diff':'Local-only changed to hosted.'}
        self.assertEqual(revise_proposal(old,new,remaining_turns=3,eligible=list('abcd'))['status'],'pending_revote')
        self.assertEqual(revise_proposal(old,new,remaining_turns=4,eligible=list('abcd'),conflicts=[{'constraint_ids':['local','hosted'],'reason':'mutually exclusive'}])['status'],'no_feasible_compromise')
