import unittest
from runtime.minds.invalidation import invalidate,cache_key,CACHE_FIELDS
class InvalidationTests(unittest.TestCase):
    def graph(self):
        return {'complete':True,'nodes':{x:{'kind':k,'dependencies_known':True} for x,k in [('e','evidence'),('c','claim'),('d','decision'),('other','claim')]},'edges':[['e','c'],['c','d']]}
    def test_downstream_and_unknown(self):
        g=self.graph(); self.assertEqual(invalidate({'changed_ids':['e']},g)['affected_nodes'],['c','d','e'])
        g['complete']=False; self.assertEqual(len(invalidate({'changed_ids':['e']},g)['affected_nodes']),4)
    def test_cycle_goal_and_freshness(self):
        g=self.graph(); self.assertEqual(invalidate({'goal_changed':True},g)['affected_nodes'],['d'])
        g['nodes']['e']['time_varying']=True; self.assertEqual(invalidate({},g)['affected_nodes'],['c','d','e'])
        g['edges'].append(['d','e']); self.assertEqual(invalidate({},g)['mode'],'full_conservative')
    def test_cache_content_and_unknown(self):
        c={k:'v1' for k in CACHE_FIELDS}; a=cache_key(c); c['content_hash']='v2'
        self.assertNotEqual(a,cache_key(c)); self.assertIsNone(cache_key(c,True)); c['model']=None; self.assertIsNone(cache_key(c))
    def test_peer_reversed_graph_is_conservative(self):
        g=self.graph();g['edges']=[['c','e'],['d','c']]
        self.assertEqual(invalidate({'changed_ids':['e']},g)['mode'],'full_conservative')
        self.assertEqual(len(invalidate({'changed_ids':['e']},g)['affected_nodes']),4)
    def test_all_cache_fingerprint_dimensions_change(self):
        c={k:'v1' for k in CACHE_FIELDS};old=cache_key(c)
        for field in CACHE_FIELDS:
            changed={**c,field:'v2'};self.assertNotEqual(old,cache_key(changed))
        c['settings']={'seed':None};self.assertIsNone(cache_key(c))
    def test_wp26_03_missing_graph_requires_fresh_public_path(self):
        import json
        import subprocess
        import sys
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        for payload in ({'evidence_change':{'changed_ids':['E1']}}, {'evidence_change':{'changed_ids':['E1']},'dependency_graph':None}):
            completed=subprocess.run([sys.executable,'-B',str(root/'tools/minds_cli.py'),'invalidate'],input=json.dumps(payload),text=True,capture_output=True,check=False)
            self.assertEqual(completed.returncode,0,completed.stdout)
            result=json.loads(completed.stdout)['result']
            self.assertEqual(result['mode'],'full_conservative');self.assertTrue(result['fresh_required'])
            self.assertFalse(result['reuse_allowed']);self.assertEqual(result['affected_scope'],'unknown')
            self.assertIsNone(result['affected_nodes']);self.assertEqual(result['node_status'],{});self.assertEqual(result['rechecked_nodes'],[])
    def test_missing_graph_does_not_relax_supplied_validation(self):
        from runtime.minds.invalidation import dispatch
        from runtime.minds.errors import MindsError
        for graph in (False,[],{}, {'nodes':{},'edges':[],'complete':'unknown'}):
            with self.subTest(graph=graph), self.assertRaises(MindsError):dispatch({'evidence_change':{},'dependency_graph':graph})
        for change in ({'unknown_field':True},{'changed_ids':'E1'},{'goal_changed':'true'}):
            with self.subTest(change=change), self.assertRaises(MindsError):dispatch({'evidence_change':change})
