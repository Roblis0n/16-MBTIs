import unittest
from unittest.mock import patch
from experiments.multimodel import multimodel_experiment

class MultimodelTests(unittest.TestCase):
    def test_no_auth_zero_calls(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            r=multimodel_experiment({},None,0)
        self.assertEqual(r['status'],'not_run'); self.assertEqual(r['external_calls'],0)
    def test_second_provider_private_field_denied(self):
        p={'baseline_completed':True,'experiment_approval_ref':'fixture','providers':['a','b'],'models':{'a':'m','b':'m'},'data_fields':['private_code'],'maximum_cost':1}
        auth={'a':{'api_authorized':True,'approval_ref':'fixture','model_ids':['m'],'fields':['private_code']}}
        r=multimodel_experiment(p,auth,1)
        self.assertFalse(r['preflight_valid']); self.assertTrue(any('b' in x for x in r['limitations']))
        self.assertEqual(r['external_calls'],0)
    def test_valid_metadata_still_not_execution_authority(self):
        p={'baseline_completed':True,'experiment_approval_ref':'fixture','providers':['a'],'models':{'a':'m'},'data_fields':['synthetic'],'maximum_cost':1}
        a={'a':{'api_authorized':True,'approval_ref':'fixture','model_ids':['m'],'fields':['synthetic']}}
        r=multimodel_experiment(p,a,1)
        self.assertTrue(r['preflight_valid']); self.assertEqual(r['status'],'not_run')
        self.assertEqual(r['productization'],'no_go')
    def test_budget(self):
        with self.assertRaises(ValueError): multimodel_experiment({},None,-1)
