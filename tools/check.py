#!/usr/bin/env python3
"""Run every test_*.py in tests, independent of package __init__ presence.

Produces new uniquely labelled evidence; never overwrites an earlier result.
Counts unittest methods separately from plan T-ID coverage and subtests.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, io, json, os, platform, subprocess, unittest
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def run(label):
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',label): raise ValueError('invalid unique label')
    out=ROOT/'reports/one-shot/tests'/label
    out.mkdir(parents=True,exist_ok=False)
    files=sorted(p for p in (ROOT/'tests').rglob('test_*.py') if not any(x in {'tmp','__pycache__','临时 中文路径'} for x in p.parts))
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for base in ('runtime','source','tools','tests') for p in (ROOT/base).rglob('*') if p.is_file() and not any(x in {'tmp','__pycache__','临时 中文路径'} for x in p.parts)}
    commands=[]
    for cmd in ([sys.executable,'-B','tools/build.py'],[sys.executable,'-B','tools/build.py','--check']):
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        commands.append({'command':cmd[1:],'cwd':'REPO_ROOT','exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
    suite=unittest.TestSuite(); errors=[]
    for index,path in enumerate(files):
        name='minds_test_'+str(index)
        try:
            spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        except Exception as exc:
            import traceback
            errors.append({'path':path.relative_to(ROOT).as_posix(),'error':type(exc).__name__,'traceback':traceback.format_exc()})
    stream=io.StringIO(); result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unittest.log').write_text(stream.getvalue(),encoding='utf8')
    evidence={'label':label,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'environment':{'os':platform.system(),'python':platform.python_version()},'data_nature':'synthetic','commands':commands,'test_files':[p.relative_to(ROOT).as_posix() for p in files],'hashes':hashes,'method_count':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'collection_errors':errors,'success':result.wasSuccessful() and not errors and all(p['exit_code']==0 for p in commands),'original_TID_coverage':'separate traceability matrix; not inferred from method_count'}
    (out/'results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('hashes','test_files','commands')},ensure_ascii=False))
    return 0 if evidence['success'] else 1
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args();raise SystemExit(run(args.label))
