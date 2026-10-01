#!/usr/bin/env python3
"""Black-box smoke of one exact ZIP in a fresh different-cwd directory.

All execution receipts below are explicitly synthetic protocol fixtures, not
native-host tool receipts. No user database, configuration, or model API is used.
"""
import argparse,datetime,hashlib,json,os,stat,subprocess,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--zip',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
 archive=Path(args.zip).resolve();output=Path(args.output).resolve()
 if output.exists():raise FileExistsError('Evidence already exists')
 calls=[]; checks=[]
 with tempfile.TemporaryDirectory(prefix='16minds-package-',dir=ROOT/'tests') as t:
  temp=Path(t);install=temp/'中文 安装';install.mkdir();cwd=temp/'other cwd';cwd.mkdir()
  with zipfile.ZipFile(archive) as z:
   assert z.testzip() is None
   seen=set()
   for i in z.infolist():
    p=PurePosixPath(i.filename);assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename
    assert i.filename.casefold() not in seen;seen.add(i.filename.casefold());assert not stat.S_ISLNK(i.external_attr>>16)
   z.extractall(install)
  package=install/'16-minds';manifest=json.loads((package/'build-manifest.json').read_text())
  for rel,h in manifest['files'].items():assert hashlib.sha256((package/rel).read_bytes()).hexdigest()==h
  checks.append('CRC/inventory/member hashes')
  env=dict(os.environ);env.update(PYTHONPATH='',PYTHONDONTWRITEBYTECODE='1',HOME=str(cwd/'absent-home'),USERPROFILE=str(cwd/'absent-home'))
  def call(command,data=None,skill='minds',expect=0):
   helper=package/'skills'/skill/'scripts/minds_cli.py'
   p=subprocess.run([sys.executable,'-I','-B',str(helper),command],input=json.dumps(data,ensure_ascii=False).encode() if data is not None else b'',capture_output=True,cwd=cwd,env=env)
   v=json.loads(p.stdout);calls.append({'skill':skill,'command':command,'input':data,'exit_code':p.returncode,'output':v,'stderr':p.stderr.decode(),'data_nature':'synthetic','argv':['python','-I','-B','INSTALLED_SKILL/scripts/minds_cli.py',command],'cwd':'ISOLATED_OTHER_CWD'})
   assert p.returncode==expect,(command,v);assert len(p.stdout.splitlines())==1;return v
  for skill in sorted((package/'skills').iterdir()):
   assert call('version',skill=skill.name)['version']==manifest['version']
   assert 'execute' in call('help',skill=skill.name)['commands']
   r=call('normalize',{'raw_text':'one -- 合成问题'},skill=skill.name)['request']
   call('validate',{'kind':'request','payload':r},skill=skill.name)
  assert list(cwd.iterdir())==[];checks.append('Eight self-contained helpers + no-record zero cwd writes')
  r=call('normalize',{'raw_text':'one -- 合成事实分析'})['request']
  caps={'schema_version':'1.0.0','host_surface':'synthetic-driver','host_version':None,'os':'synthetic','python_version':None,'native_delegation':'observed','tool_schema_hash':'a'*64,'open_thread_cap':1,'isolation_status':'verified_clean','read_only_status':'unknown','close_supported':False,'observed_at':'2026-01-01T00:00:00Z','evidence_refs':['synthetic-fixture'],'limitations':['Declared synthetic capabilities, not actual host evidence']}
  state=call('execute',{'request':r,'capabilities':caps,'run_id':'synthetic-package-loop'})['state']
  action=call('scheduler',{'op':'actions','state':state})['result'][0]
  state=call('step',{'state':state,'event':{'kind':'intent','intent':action['intent'],'attempt_id':action['attempt_id']}})['state']
  state=call('record',{'state':state,'event':{'kind':'receipt','action_id':action['intent']['action_id'],'host_thread_id':'synthetic-thread','receipt_ref':'synthetic-receipt'}})['state']
  result={'run_id':'synthetic-package-loop','actor_id':action['intent']['actor_id'],'round':1,'attempt_id':action['attempt_id'],'action_id':action['intent']['action_id'],'result_revision':1,'input_hash':action['intent']['input_hash'],'persona_revision':action['context']['persona_revision'],'claims':[],'stance_change':'initial','summary':'合成协议输出，没有新增发现。','limitations':['Synthetic replay; no actual model dispatch.'],'score_records':[]}
  state=call('record',{'state':state,'event':{'kind':'result','result':result}})['state']
  for status in ['synthesizing','completed']:state=call('step',{'state':state,'event':{'kind':'transition','to':status}})['state']
  assert state['reducer']['run']['spent_agent_turns']==1;assert state['reducer']['run']['residual_thread_ids']==['synthetic-thread'];checks.append('Intent/receipt/result/terminal loop preserves residual cleanup')
  counts=call('write',{'run_id':'synthetic-write','body':'合成🙂\n不保证完成','operation':'write'})['result'];assert counts['actual_length']==len(counts['body']);checks.append('Final body actual Unicode count')
  call('storage',{'action':'create','root':str(cwd),'persist':False},expect=3);assert list(cwd.iterdir())==[]
  (cwd/'.gitignore').write_text('.16minds/runs/\n')
  saved=call('storage',{'action':'create','root':str(cwd),'persist':True})['result']['run_id']
  path='.16minds/runs/'+saved+'/summary.json'
  call('storage',{'action':'export','root':str(cwd),'path':path,'payload':{'summary':'Synthetic permitted artifact'},'persist':True})
  call('storage',{'action':'export','root':str(cwd),'path':path,'payload':{'summary':'Different'},'persist':True},expect=2)
  preview=call('storage',{'action':'delete','root':str(cwd),'run_id':saved})['result']
  call('storage',{'action':'delete','root':str(cwd),'run_id':saved,'confirmed':True,'preview_digest':preview['preview_digest']})
  assert not (cwd/'.16minds/runs'/saved).exists();checks.append('Authorized synthetic save/export/no-overwrite/preview delete')
  bad=dict(caps,native_delegation='unsupported',isolation_status='unavailable')
  call('execute',{'request':r,'capabilities':bad,'run_id':'synthetic-blocked'},expect=3);checks.append('Missing capability honest refusal')
 evidence={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'archive':archive.name,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'status':'pass','checks':checks,'check_count':len(checks),'actual_cli_calls':len(calls),'calls':calls,'host_installation':'not established by this test'}
 # Redact only this temporary location; actual argv mapping remains disclosed.
 raw=json.dumps(evidence,ensure_ascii=False,indent=2).replace(str(temp),'ISOLATED_ROOT')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(raw+'\n')
 print(json.dumps({k:v for k,v in evidence.items() if k!='calls'},ensure_ascii=False))
if __name__=='__main__':main()
