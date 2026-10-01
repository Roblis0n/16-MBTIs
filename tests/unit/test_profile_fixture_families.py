"""Six authored code/control processes and three synthetic premortem scenarios.

-I isolates Python import configuration; it is not an OS/network sandbox.
Every executed snippet is checked-in, tiny, stdlib-only, and authored for this
suite. No repository-discovered script, third-party package or real data runs.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from runtime.minds.profiles import review_findings, premortem

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'tests/fixtures/code-review'
CASES=json.loads((FIXTURES/'cases.json').read_text())['cases']
HARNESS=r'''
import json, runpy, sys
m=runpy.run_path(sys.argv[1]); family=sys.argv[2]
if family=='timer':
    m['mount']();m['unmount']();m['mount']();m['unmount']()
    observed=len(m['active']); expected=0
elif family=='default':
    m['add_item']('A'); observed=m['add_item']('B'); expected=['B']
elif family=='parser':
    assert m['parse_cost']('3.5')==3.5
    try:
        m['parse_cost']('NaN'); observed='accepted_nonfinite'
    except ValueError: observed='rejected_nonfinite'
    expected='rejected_nonfinite'
else: raise AssertionError('Unknown authored fixture family')
try:
    assert observed==expected, 'Authored regression assertion failed'
except AssertionError:
    print(json.dumps({'observed':observed,'expected':expected,'collected':1,'executed':1,'failed':1,'skipped':0}));sys.exit(1)
print(json.dumps({'observed':observed,'expected':expected,'collected':1,'executed':1,'failed':0,'skipped':0}))
'''

def run_case(case):
    source=FIXTURES/case['file']; raw=source.read_bytes()
    with tempfile.TemporaryDirectory(prefix='minds-authored-review-') as cwd:
        p=subprocess.run([sys.executable,'-I','-B','-c',HARNESS,str(source),case['family']],cwd=cwd,text=True,capture_output=True,timeout=10)
    result=json.loads(p.stdout)
    if p.returncode!=case['expected_assertion_exit']:
        raise AssertionError((case['case_id'],p.returncode,p.stdout,p.stderr))
    if result['collected']!=1 or result['executed']!=1 or result['failed']!=case['expected_assertion_exit']:
        raise AssertionError('Execution counter mismatch')
    findings=json.loads(json.dumps(case['finding_drafts']))
    for f in findings:
        f['execution_receipt']={'receipt_ref':'authored-fixture:'+case['case_id'],'collected':result['collected'],'executed':result['executed'],'failed':result['failed']}
        if not (1<=f['location']['start_line']<=f['location']['end_line']<=len(raw.decode().splitlines())):
            raise AssertionError('Finding line range does not exist')
    scope={'paths':[case['file']],'snapshot_hash':hashlib.sha256(raw).hexdigest(),'blind_spots':['Only this authored snippet and one explicit regression condition were checked.']}
    reviewed=review_findings(findings,scope)
    if len(reviewed['findings'])!=case['expected_assertion_exit'] or reviewed['confirmed_count']!=case['expected_assertion_exit']:
        raise AssertionError('Positive/control finding mismatch')
    return {'case_id':case['case_id'],'source_ref':str(source.relative_to(ROOT)),'source_sha256':scope['snapshot_hash'],'command':['python','-I','-B','-c','<HARNESS in test_profile_fixture_families.py>',str(source.relative_to(ROOT)),case['family']],'exit_code':p.returncode,'actual_output':result,'reviewed_output':reviewed,'process_scope':'isolated Python import context and temporary cwd; not OS isolation','status':'pass'}

def run_premortem(name):
    path=ROOT/'tests/behavior/premortem'/f'{name}.json';fixture=json.loads(path.read_text())
    result=premortem(fixture['model_authored_output']['paths'],fixture['model_authored_output']['plan'])
    p=result['failure_paths'][0]
    assert p['status']=='hypothesis' and p['probability'] is None
    assert p['constraint_fit']=='within_stated_budget' and result['guaranteed_success'] is False
    assert p['new_costs_and_risks'] and p['stop_condition']
    for action in ('prevention','response'):
        assert set(p[action])=={'owner_role','resources','earliest_time','verification'}
    assert fixture['actual_activity_execution']=='not_run' and fixture['unknown_resources_are_not_confirmed']
    return {'scenario':name,'source_ref':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'validated_model_output':result,'actual_activity_execution':'not_run','status':'pass'}

class AuthoredCodeReviewFixtureTests(unittest.TestCase):
    def test_timer_bug(self): run_case(CASES[0])
    def test_timer_control(self): run_case(CASES[1])
    def test_mutable_default_bug(self): run_case(CASES[2])
    def test_mutable_default_control(self): run_case(CASES[3])
    def test_nonfinite_parser_bug(self): run_case(CASES[4])
    def test_nonfinite_parser_control(self): run_case(CASES[5])

class AuthoredPremortemFixtureTests(unittest.TestCase):
    def test_activity_scenario(self): run_premortem('activity')
    def test_project_scenario(self): run_premortem('project')
    def test_research_scenario(self): run_premortem('research')
