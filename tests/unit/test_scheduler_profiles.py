"""Cross-entry CLI regressions for frozen profile enforcement (synthetic only)."""
import json
import os
import subprocess
import sys
import unittest
from copy import deepcopy
from tests.unit.test_contracts import fixture
from runtime.minds.casting import select_roster
from runtime.minds.context import _digest

class SchedulerProfileTests(unittest.TestCase):
    def call(self,command,data):
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        p=subprocess.run([sys.executable,'-B','-m','runtime.minds',command],input=json.dumps(data),text=True,capture_output=True,env=env)
        return p.returncode,json.loads(p.stdout)

    def inputs(self):
        request=fixture('request'); request.update(profile='code-review',voice='neutral')
        request['permissions']['network']=True
        caps=fixture('capabilities');caps.update(native_delegation='observed',isolation_status='verified_clean',open_thread_cap=1,close_supported=True)
        roster=select_roster(request);roster['run_id']='profile-regression'
        return {'request':request,'capabilities':caps,'run_id':'profile-regression','roster':roster,'common_facts':{'checked_scope':{'paths':['synthetic.py']},'snapshot_hash':'a'*64}}

    def prepare(self,command,data):
        if command=='scheduler': data={'op':'prepare',**data}
        code,result=self.call(command,data)
        self.assertEqual(code,0,result)
        return result['state'] if command=='execute' else result['result']

    def test_both_public_routes_narrow_profile_tools(self):
        for command in ('execute','scheduler'):
            with self.subTest(command=command):
                state=self.prepare(command,self.inputs())
                profile=state['common_facts']['profile_contract']
                self.assertEqual(profile['main']['effective_tools'],['read_supplied'])
                code,result=self.call('scheduler',{'op':'verify','state':state,'task':{'kind':'network','question':'Synthetic lookup','source_ref':'https://example.invalid/synthetic'},'permission_ref':'synthetic-grant'})
                self.assertEqual(code,3,result);self.assertEqual(result['error']['machine_code'],'E_PERMISSION')
                code,result=self.call('scheduler',{'op':'actions','state':state})
                self.assertEqual(code,0,result);self.assertIsNone(result['result'][0]['context']['persona'])
                code,result=self.call('scheduler',{'op':'verify','state':state,'task':{'kind':'supplied_material','question':'Read synthetic scope','source_ref':'synthetic.py'},'permission_ref':'synthetic-grant'})
                self.assertEqual(code,0,result)

    def test_injected_verification_plan_is_revalidated(self):
        from runtime.minds.adapter_contract import prepare_action
        state=self.prepare('scheduler',self.inputs())
        task={'kind':'network','question':'Synthetic lookup','source_ref':'https://example.invalid/synthetic'}
        intent=prepare_action(state['reducer']['run'],None,1,kind='verify',payload_ref='sha256:'+_digest(task),permission_ref='synthetic-grant',host_schema_hash=state['capabilities']['tool_schema_hash'])
        state['verification_plans'][intent['action_id']]={'intent':intent,'attempt_id':'verification-1','task':task}
        code,result=self.call('scheduler',{'op':'actions','state':state})
        self.assertEqual(code,3,result);self.assertEqual(result['error']['machine_code'],'E_PERMISSION')

    def test_required_inputs_both_routes_and_forged_contract(self):
        for command in ('execute','scheduler'):
            data=self.inputs();data.pop('common_facts')
            if command=='scheduler':data={'op':'prepare',**data}
            code,result=self.call(command,data)
            self.assertNotIn('state',result); self.assertNotEqual(result.get('status'),'ok')
        state=self.prepare('scheduler',self.inputs())
        # Changing both the public snapshot and its checksum cannot turn a
        # profile's read-only category into a broader registered profile.
        state['common_facts']['profile_contract']['main']['effective_tools'].append('public_retrieval')
        state['snapshots']['1']['common_facts']=deepcopy(state['common_facts'])
        snap=state['snapshots']['1'];value={k:v for k,v in snap.items() if k!='snapshot_hash'};snap['snapshot_hash']=_digest(value)
        code,result=self.call('scheduler',{'op':'actions','state':state})
        self.assertEqual(code,2,result);self.assertEqual(result['error']['machine_code'],'E_CONTEXT_INCOMPLETE')

if __name__=='__main__':unittest.main()
