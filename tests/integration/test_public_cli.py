"""Actual CLI processes. Synthetic inputs; no model/host success inferred."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class PublicCliTests(unittest.TestCase):
 def call(self,cmd,value=None,raw=None,cwd=None):
  env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=''
  data=raw if raw is not None else json.dumps(value,ensure_ascii=False).encode()
  p=subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/minds_cli.py'),cmd],input=data,capture_output=True,cwd=cwd or ROOT.parent,env=env)
  self.assertNotIn(b'Traceback',p.stderr)
  v=json.loads(p.stdout.decode('utf8'));self.assertEqual(len(p.stdout.splitlines()),1)
  return p.returncode,v
 def test_all_data_commands_strict_json(self):
  _,h=self.call('help')
  for c in h['commands']:
   if c in ('help','version'):continue
   for raw in [b'{"x":1,"x":2}',b'NaN',b'{"x":Infinity}',b'[]',b'null',b'{"x":"\xff"}',b'{"x":'+b'['*55+b'0'+b']'*55+b'}']:
    with self.subTest(command=c,raw=raw[:30]):
     code,v=self.call(c,raw=raw);self.assertEqual(code,2);self.assertEqual(v['error']['machine_code'],'E_SCHEMA')
 def test_missing_and_unknown_never_internal(self):
  for c in ['execute','step','record','scheduler','cast','aggregate','pair','synthesis','decide','vote','write','ask','authorize','storage','render','sensitivity','journal','invalidate','profile']:
   for d in ({},{'unexpected':True}):
    with self.subTest(command=c,data=d):
     code,v=self.call(c,d)
     if c=='profile' and d=={}:
      self.assertEqual(code,0);self.assertTrue(v['result']['profiles'])  # documented read-only list default
     else:
      self.assertIn(code,(2,3));self.assertNotEqual(v['error']['machine_code'],'E_INTERNAL')
 def test_cast_normalize_and_no_write(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as t:
   before=list(Path(t).rglob('*'))
   code,v=self.call('normalize',{'raw_text':'many --n 3 -- 分析合成工程风险','explicit_options':{'task_kind':'engineering'}},cwd=t)
   self.assertEqual(code,0);request=v['request']
   code,v=self.call('cast',{'request':request},cwd=t);self.assertEqual(code,0,v)
   result=v['result'];roster=result.get('roster',result)
   self.assertEqual(roster['requested_n'],3);self.assertEqual(len(roster['members']),3)
   self.assertEqual(list(Path(t).rglob('*')),before)
   code,v=self.call('execute',{'request':request},cwd=t);self.assertEqual(code,3)
 def test_real_execute_intent_roundtrip(self):
  code,v=self.call('normalize',{'raw_text':'one -- 合成问题'});self.assertEqual(code,0)
  request=v['request']
  caps=json.loads((ROOT/'tests/fixtures/contracts/positive/capabilities.valid.json').read_text())
  caps.update(native_delegation='observed',isolation_status='verified_clean',open_thread_cap=1,close_supported=True)
  # Synthetic declared capabilities exercise software only, not authentication.
  code,v=self.call('execute',{'request':request,'capabilities':caps,'run_id':'synthetic-cli-1'});self.assertEqual(code,0,v)
  state=v['state'];code,v=self.call('scheduler',{'op':'actions','state':state});self.assertEqual(code,0,v)
  action=v['result'][0];code,v=self.call('step',{'state':state,'event':{'kind':'intent','intent':action['intent'],'attempt_id':action['attempt_id']}});self.assertEqual(code,0,v)
  self.assertEqual(v['state']['reducer']['run']['spent_agent_turns'],1)
  self.assertEqual(v['state']['reducer']['run']['run_id'],'synthetic-cli-1')
 def test_profile_route_requires_inputs_and_neutral(self):
  code,v=self.call('normalize',{'raw_text':'many --profile code-review --voice neutral -- 查看合成代码'})
  self.assertEqual(code,0,v);r=v['request'];self.assertEqual(r['task_kind'],'engineering');self.assertEqual(r['voice'],'neutral')
  caps=json.loads((ROOT/'tests/fixtures/contracts/positive/capabilities.valid.json').read_text())
  caps.update(native_delegation='observed',isolation_status='verified_clean',open_thread_cap=4,close_supported=True)
  code,v=self.call('execute',{'request':r,'capabilities':caps,'run_id':'profile-missing-1'})
  self.assertEqual(code,2,v);self.assertEqual(v['error']['machine_code'],'E_CONTEXT_INCOMPLETE')
  code,v=self.call('execute',{'request':[],'capabilities':caps,'run_id':'bad-request'});self.assertEqual(code,2)
 def test_unregistered_extra_and_oversize(self):
  code,v=self.call('normalize',{'raw_text':'x','arbitrary':1});self.assertEqual(code,2)
  code,v=self.call('normalize',raw=b'"'+b'x'*1048576+b'"');self.assertEqual(code,2)
  code,v=self.call('unknown',{});self.assertEqual(code,2)
if __name__=='__main__':unittest.main()
