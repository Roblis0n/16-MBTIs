import unittest
from minds.casting import select_roster, preview_cast
from minds.resources import resource_json, registry
from minds.errors import MindsError

class CastingTests(unittest.TestCase):
    def test_128_all_sizes_and_locks(self):
        table=resource_json('casting/attention_registry.json')
        for task in table['legacy_task_aliases']:
            for n in range(1,17):
                for locks in ([],['intj'],list(registry()['personas'])[:n]):
                    request={'n':n,'task_kind':task,'locked_personas':locks}
                    r=select_roster(request); ids=[m['actor_id'] for m in r['members']]
                    self.assertEqual(n,len(set(ids))); self.assertEqual(ids[:len(locks)],locks)
                    self.assertEqual(r,select_roster(request))
    def test_challenger_inside_n(self):
        for n in range(2,17):
            r=select_roster({'n':n,'locked_personas':['intj'],'selection':{'require_challenger':True}})
            self.assertEqual(n,len(r['members'])); self.assertEqual('heuristic_challenger',r['members'][1]['source'])
    def test_explicit_second_wins(self):
        r=select_roster({'n':2,'locked_personas':['intj','intp'],'selection':{'require_challenger':True}})
        self.assertEqual([x['actor_id'] for x in r['members']],['intj','intp'])
    def test_invalid_n_lock_or_registry(self):
        for req in [{'n':0},{'n':True},{'n':17},{'n':1,'locked_personas':['intj','intp']},{'n':2,'locked_personas':['intj','intj']},{'n':1,'selection':{'require_challenger':True}}]:
            with self.assertRaises(MindsError): select_roster(req)
        with self.assertRaises(MindsError): select_roster({'n':4},{'persona_tags':{'intj':[]}})
    def test_unknown_task_and_preview(self):
        r=preview_cast({'n':8,'task_kind':'research_feasibility'})
        self.assertEqual(r['agent_turns'],0); self.assertEqual(r['roster']['calibration_state'],'uncalibrated')
    def test_json_cannot_activate_calibration(self):
        c={'state':'active','match_state':'exact','fingerprint_verified':True,'task_kind':'factual','scores':{p:1 for p in registry()['personas']},'calibration_ref':'c1'}
        r=select_roster({'n':4,'task_kind':'factual'},calibration=c)
        self.assertEqual(r['calibration_state'],'uncalibrated')
        r=select_roster({'n':4,'task_kind':'factual'},calibration=c,calibration_verifier=lambda c,r:True)
        self.assertEqual(r['calibration_state'],'exact')

    def test_archived_top_five_already_contains_rival(self):
        archive=resource_json('casting/casting.legacy.json')
        top=archive['best_for_task']['design_review']
        self.assertIn(archive['best_rival'][top[0]],top)
        roster=select_roster({'n':5,'task_kind':'engineering','locked_personas':top,'selection':{'require_challenger':True}})
        self.assertEqual([m['actor_id'] for m in roster['members']],top)
        self.assertEqual(len(roster['members']),5)

    def test_legacy_bytes_and_arithmetic_audit(self):
        import hashlib
        from minds.resources import resource_root
        archive=resource_json('casting/casting.legacy.json'); meta=resource_json('casting/legacy.metadata.json')
        self.assertEqual(hashlib.sha256((resource_root()/'casting/casting.legacy.json').read_bytes()).hexdigest(),meta['sha256'])
        ids=list(archive['fitness'])
        for task in archive['tasks']:
            self.assertEqual(sorted(ids,key=lambda p:-archive['fitness'][p][task])[:5],archive['best_for_task'][task])
        pairs=0
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                pairs+=1; self.assertEqual(archive['chemistry'][a][b],archive['chemistry'][b][a])
            expected=max((b for b in ids if b!=a),key=lambda b:archive['partner_effect'][b]+archive['distance_beta']*sum(x!=y for x,y in zip(a,b)))
            self.assertEqual(expected,archive['best_rival'][a])
        self.assertEqual(pairs,120)
