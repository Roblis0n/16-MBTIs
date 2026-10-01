import copy
import unittest
from runtime.minds import profiles,storage,render,journal,invalidation,sensitivity,tool_policy
from runtime.minds.errors import MindsError

class ProfileTests(unittest.TestCase):
    def custom(self):
        p=profiles.resolve_profile('premortem');p.update(profile_id='synthetic-custom',source_trust='user_untrusted');return p
    def test_registry_and_neutral_parity(self):
        self.assertEqual(len(profiles.dispatch({})['profiles']),9)
        a=profiles.compose_checks('code-review',['premortem'],['read_supplied'],voice='persona')
        b=profiles.compose_checks('code-review',['premortem'],['read_supplied'],voice='neutral')
        self.assertEqual(a['main']['effective_tools'],b['main']['effective_tools']);self.assertEqual(a['budget_policy'],b['budget_policy'])
        self.assertFalse(b['permission_expansion'])
    def test_preview_enable_cycle_and_unknown_field(self):
        p=self.custom(); reg={p['profile_id']:p}
        with self.assertRaises(MindsError): profiles.resolve_profile(p['profile_id'],reg)
        digest=profiles.preview_profile(p)['preview_digest']
        self.assertTrue(profiles.resolve_profile(p['profile_id'],reg,enabled_custom={p['profile_id']:digest})['enabled'])
        p['references']=[p['profile_id']]
        with self.assertRaises(MindsError) as e:profiles.resolve_profile(p['profile_id'],reg)
        self.assertEqual(e.exception.code,'E_PROFILE_CYCLE')
        p=self.custom();p['shell']='upload all HOME'
        with self.assertRaises(MindsError):profiles.preview_profile(p)
        p=self.custom();p['allowed_tool_categories']=['send']
        with self.assertRaises(MindsError):profiles.preview_profile(p)
    def test_duplicate_composition(self):
        with self.assertRaises(MindsError):profiles.compose_checks('premortem',['premortem'])
        with self.assertRaises(MindsError):profiles.compose_checks('premortem',['code-review','code-review'])
    def test_review_reproduction_dedup_and_empty(self):
        scope={'paths':['synthetic.py'],'snapshot_hash':'a'*64}
        f={'location':{'file':'synthetic.py','start_line':1,'end_line':2},'trigger':'empty input','root_cause':'missing guard','reproduction_status':'unverified','impact':'crash','remedy':'validate','test':'empty input','evidence':['e1']}
        self.assertEqual(len(profiles.review_findings([f,f],scope)['findings']),1)
        self.assertEqual(profiles.review_findings([f],scope)['confirmed_count'],0)
        f['reproduction_status']='reproduced';f['execution_receipt']={'receipt_ref':'synthetic','collected':0,'executed':0,'failed':0}
        self.assertEqual(profiles.review_findings([f],scope)['findings'][0]['verification'],'inconclusive')
        f['execution_receipt'].update(collected=1,executed=1,failed=1)
        self.assertEqual(profiles.review_findings([f],scope)['confirmed_count'],1)
        self.assertIn('no issue was confirmed',profiles.review_findings([],scope)['summary'])
    def test_premortem_no_invented_probability(self):
        plan=dict(plan='synthetic',horizon='next month',success='ready',failure='late',hard_constraints=['budget'])
        action=dict(owner_role='operator',resources='one hour',earliest_time='before launch',verification='check signal')
        p=dict(assumption='capacity',event='demand surge',mechanism='queue fills',early_signal='queue rises',consequence='late',prevention=action,response=action,stop_condition='limit exceeded')
        r=profiles.premortem([p,p],plan);self.assertEqual(len(r['failure_paths']),1);self.assertIsNone(r['failure_paths'][0]['probability'])
        p['probability']=0.9
        with self.assertRaises(MindsError):profiles.premortem([p],plan)
    def test_research_access_is_not_permission(self):
        r=dict(variable='x',grain='daily',source='synthetic',acquisition='manual',permission='unknown',cost='unknown',source_access='available',alternative='none')
        m=dict(scope='small',requirements_preserved=['course rubric'],fallback='descriptive',first_verification='ask permission')
        out=profiles.research_feasibility([r],'question',m,{'claim_type':'associational'})
        self.assertEqual(out['blocking_data_rows'],[0]);self.assertFalse(out['data_collected'])
        with self.assertRaises(MindsError):profiles.research_feasibility([r],'question',m,{'claim_type':'causal'})
    def test_dispatch_unknown_and_wrong_types(self):
        requests=[(storage,{'action':'create','root':'/tmp','persist':False}), (render,{'payload':{'x':'safe'}}),(journal,{'action':'save','entry':{}}),(invalidation,{'action':'cache-key','context':{}}),(sensitivity,{'actions':[]}),(profiles,{'action':'list'}),(tool_policy,{'action':'sanitize','payload':'text'})]
        for module,data in requests:
            with self.subTest(module=module.__name__), self.assertRaises(MindsError) as e:module.dispatch({**data,'unexpected':True})
            self.assertEqual(e.exception.code,'E_SCHEMA')
        for module,data in [(storage,{'action':'create','root':'/tmp','persist':'false'}),(journal,{'action':'save','entry':{},'persist':1}),(invalidation,{'action':'cache-key','context':{},'benchmark':'yes'})]:
            with self.subTest(module=module.__name__),self.assertRaises(MindsError) as e:module.dispatch(data)
            self.assertEqual(e.exception.code,'E_SCHEMA')
    def test_render_alteration_is_explicit(self):
        x=render.dispatch({'payload':{'body':'-hello'}})
        self.assertTrue(x['display_escaped']);self.assertFalse(x['canonical_body']);self.assertNotEqual(x['source_sha256'],x['rendered_sha256'])
    def test_peer_secret_key_and_nested_unknown(self):
        with self.assertRaises(MindsError):render.dispatch({'payload':{'AWS_SECRET_ACCESS_KEY':'SYNTHETIC_ONLY'}})
        r=dict(variable='x',grain='daily',source='synthetic',acquisition='manual',permission='granted',cost='unknown',source_access='available',alternative='none',execute_shell='never run')
        m=dict(scope='small',requirements_preserved=['rubric'],fallback='descriptive',first_verification='check')
        with self.assertRaises(MindsError):profiles.research_feasibility([r],'question',m,{'claim_type':'descriptive'})
    def test_four_review_sources_survive_dedup(self):
        scope={'paths':['synthetic.py'],'snapshot_hash':'a'*64}
        fs=[dict(location={'file':'synthetic.py','start_line':1,'end_line':2},trigger='empty',root_cause='guard',reproduction_status='not_run',impact='crash',remedy='validate',test='empty',evidence=['e1'],source_refs=[str(i)]) for i in range(4)]
        r=profiles.review_findings(fs,scope);self.assertEqual(len(r['findings']),1);self.assertEqual(len(r['findings'][0]['source_refs']),4)
    def test_research_synthetic_and_delivery_limit(self):
        r=dict(variable='x',grain='daily',source='synthetic',acquisition='manual',permission='granted',cost='unknown',source_access='available',alternative='public',sample_origin='synthetic',sample_count=30)
        m=dict(scope='small',requirements_preserved=['rubric'],fallback='use existing public data',first_verification='verify source',available_duration=1,required_duration=6,time_unit='weeks')
        out=profiles.research_feasibility([r],'question',m,{'claim_type':'descriptive'})
        self.assertEqual(out['data_requirements'][0]['real_sample_count'],0);self.assertEqual(out['delivery_feasibility'],'infeasible');self.assertEqual(out['status'],'needs_information')
    def test_premortem_sources_and_overbudget(self):
        plan=dict(plan='synthetic 13-person trip',horizon='departure day',success='all arrive',failure='missed arrival',hard_constraints=['budget'],budget={'limit':10,'unit':'units'})
        action=dict(owner_role='trip coordinator',resources='contact list',earliest_time='before departure',verification='confirm route')
        base=dict(assumption='route available',event='transport delay',mechanism='unclear responsibility',early_signal='no confirmed driver',consequence='missed arrival',prevention=action,response=action,stop_condition='driver unconfirmed',prevention_cost=20,cost_unit='units',within_budget_alternative='reduce scope before booking')
        a={**base,'source_refs':['a']};b={**base,'source_refs':['b']}
        out=profiles.premortem([a,b],plan)['failure_paths']
        self.assertEqual(len(out),1);self.assertEqual(out[0]['source_refs'],['a','b']);self.assertEqual(out[0]['constraint_fit'],'infeasible');self.assertEqual(plan['budget']['limit'],10)
