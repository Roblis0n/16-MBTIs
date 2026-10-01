"""Actual negative-control subprocesses: format success cannot mask bad content.

These are synthetic reporting/CI environments, not missing-feature claims about
this current host. Full target-host smoke remains separately not_run.
"""
import json,os,subprocess,sys,tempfile,unittest,uuid,datetime,hashlib
from pathlib import Path
from runtime.minds.normalize import normalize_request
from runtime.minds.budget import preflight
from runtime.minds.errors import MindsError
ROOT=Path(__file__).resolve().parents[2]
class ReportingBoundariesTests(unittest.TestCase):
 def test_wp01_02_missing_delegation_preserves_unsupported(self):
  caps=json.loads((ROOT/'tests/fixtures/contracts/positive/capabilities.valid.json').read_text())
  caps.update(native_delegation='unsupported',isolation_status='unavailable')
  before=json.dumps(caps,sort_keys=True)
  with self.assertRaises(MindsError) as caught:preflight(normalize_request('one -- synthetic'),caps)
  self.assertEqual(caught.exception.code,'E_CAPABILITY');self.assertEqual(json.dumps(caps,sort_keys=True),before)
  self.assertNotIn('native_parallel',caught.exception.as_dict()['error']['public_message'])
 def test_wp20_01_real_empty_path_ci_discloses_not_run(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as tmp:
   code="""import sys,json,shutil
sys.path.insert(0,sys.argv[1])
from runtime.minds.normalize import normalize_request
assert normalize_request('one -- synthetic')['n']==1
found=shutil.which('codex')
print(json.dumps({'unit_assertion':'pass','host_smoke':'not_run' if found is None else 'available','reason':'CLI absent on isolated PATH' if found is None else None}))
"""
   env=dict(os.environ);env['PATH']=tmp;env.pop('PYTHONPATH',None)
   p=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT)],cwd=tmp,env=env,capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr);result=json.loads(p.stdout)
   self.assertEqual(result['unit_assertion'],'pass');self.assertEqual(result['host_smoke'],'not_run');self.assertTrue(result['reason'])
 def test_wp20_02_actual_failing_semantic_quality_gate(self):
  code="""import sys,unittest
sys.path.insert(0,sys.argv[1])
from runtime.minds.text_invariants import writing_result,text_hash,CATEGORIES
from runtime.minds.contracts import validate_shape
source='很多人反馈方便';body='半数用户好评'
review={'source_hash':text_hash(source),'draft_hash':text_hash(body),'reviewed_categories':sorted(CATEGORIES),'reason':'Unprovided numeric proportion and changed sentiment','status':'violation','diff':[{'category':'number','source_span':None,'before':'很多人','after':'半数','status':'violation','reason':'No supplied proportion'}]}
result=writing_result(run_id='synthetic-negative',body=body,operation='rewrite',source=source,source_version=text_hash(source),semantic_review=review)
validate_shape('writing_result',result)
class Gate(unittest.TestCase):
 def test_semantic_fidelity(self):self.assertEqual(result['invariant_status'],'preserved')
suite=unittest.defaultTestLoader.loadTestsFromTestCase(Gate)
r=unittest.TextTestRunner().run(suite)
raise SystemExit(0 if r.wasSuccessful() else 1)
"""
  p=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT)],capture_output=True,text=True)
  evidence=ROOT/'reports/one-shot/negative-controls';evidence.mkdir(parents=True,exist_ok=True)
  record={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'data_nature':'synthetic negative control','command':['python','-I','-B','-c',code,'REPO_ROOT'],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr.replace(str(ROOT),'REPO_ROOT'),'expected_failure':True,'test_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
  (evidence/(str(uuid.uuid4())+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
  self.assertEqual(p.returncode,1,p.stderr);self.assertIn('FAILED (failures=1)',p.stderr);self.assertIn('violation',p.stderr)
if __name__=='__main__':unittest.main()
