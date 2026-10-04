"""Causality, missing-evidence and split-isolation contracts for revised forecasts."""
import sys
import unittest
from pathlib import Path

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import robust_forecasting as robust
import extended_study as study
from context_baselines import context_features
from separated_alarm import alarm_score,choose_gate,gated_metrics

class TestRobustForecasting(unittest.TestCase):
    def test_unavailable_observation_is_marginalized(self):
        model={'pi':np.array([.7,.3]),'a':np.array([[.9,.1],[0,1.]]),
            'b':np.array([[[.8,.2],[.2,.8]],[[.3,.7],[.9,.1]]])}
        symbols=np.array([[0,0],[1,0],[1,1],[0,1]])
        changed=symbols.copy();changed[:,1]=1-changed[:,1]
        a=robust.state_filter(model,symbols,np.array([0]))
        b=robust.state_filter(model,changed,np.array([0]))
        np.testing.assert_array_equal(a,b)
        prior=model['pi']@model['a'];expected=prior*model['b'][:,0,0];expected/=expected.sum()
        np.testing.assert_allclose(a[0],expected)
        no_evidence=robust.state_filter(model,symbols,np.array([],dtype=int))
        np.testing.assert_allclose(no_evidence[0],prior)
        self.assertFalse(np.allclose(a,no_evidence))

    def test_filter_and_state_summaries_are_prefix_causal(self):
        model={'pi':np.array([.8,.2]),'a':np.array([[.97,.03],[0,1.]]),
            'b':np.array([[[.9,.1]],[[.2,.8]]])}
        symbols=np.arange(100).reshape(-1,1)%2
        full=robust.state_filter(model,symbols,np.array([0]))
        short=robust.state_filter(model,symbols[:17],np.array([0]))
        np.testing.assert_array_equal(full[:17],short)
        np.testing.assert_array_equal(robust.stage_features(full)[:17],robust.stage_features(short))
        np.testing.assert_allclose(full.sum(axis=1),1)

    def test_blending_preserves_bounds_and_horizon_order(self):
        a=np.tile(np.linspace(.01,.3,6),(4,1));b=np.tile(np.linspace(.1,.9,6),(4,1))
        for w in [0,.25,.5,.75,1]:
            p=robust.blend_predictions(a,b,w)
            self.assertTrue(np.all((p>=0)&(p<=1)));self.assertTrue(np.all(np.diff(p,axis=1)>=0))
        with self.assertRaises(ValueError):robust.blend_predictions(a,b,1.1)

    def test_context_controls_use_only_elapsed_time_and_past_counts(self):
        x=np.arange(180,dtype=float).reshape(60,3);times=np.arange(1,61)*60.
        for mode in ['clock_only_boosting','long_history_boosting']:
            np.testing.assert_array_equal(context_features(x,times,mode)[:17],context_features(x[:17],times[:17],mode))
        np.testing.assert_array_equal(context_features(x,times,'clock_only_boosting'),
            context_features(x*999,times,'clock_only_boosting'))
        self.assertEqual(context_features(x,times,'long_history_boosting').shape[1],7*3+1)

    def test_state_confirmation_changes_alarms_without_changing_probabilities(self):
        ep={'times':np.arange(1,31)*60.,'onset':31*60.}
        p=np.full(30,.8);original=p.copy();q=np.linspace(0,1,30)
        belief=np.c_[1-q,q]
        chosen,_=choose_gate(ep,p,belief,5,0)
        self.assertEqual(chosen['level'],.9)
        result=gated_metrics(ep,p,belief,5,chosen)
        self.assertEqual(result['strict_warning_recall'],1)
        self.assertEqual(result['false_warning_episodes'],0)
        y=(ep['onset']-ep['times']<=5*60).astype(int)
        self.assertAlmostEqual(result['brier'],np.mean((original-y)**2))
        np.testing.assert_array_equal(p,original)
        np.testing.assert_array_equal(alarm_score(p,belief,0),p)

    def test_fitted_pipeline_abstains_and_uses_no_test_truth(self):
        episodes={}
        for i,n in enumerate(['a','b','c','d']):
            counts=np.zeros((75,2));counts[45+i:,0]=1;counts[50+i:,1]=3
            episodes[n]={'counts':counts,'times':np.arange(1,76)*60.,'onset':60*60.,
                'truth':np.r_[np.zeros(55,dtype=int),np.ones(20,dtype=int)],
                'names':np.array(['aminer:x','wazuh:y'])}
        predictions,bundle,metadata=robust.fit_predict(episodes,['a','b','c'],['d'],['aminer','wazuh'])
        for split in metadata['state_crossfit_splits']:
            self.assertNotIn(split['prediction_campaign'],split['fitting_campaigns'])
            self.assertNotIn('d',split['fitting_campaigns'])
        changed={**episodes['d'],'truth':np.full(75,999),'onset':1.}
        actual=robust.predict_model(bundle,changed,['aminer','wazuh'])
        for mode in predictions:np.testing.assert_array_equal(actual['risk'][mode],predictions[mode]['d'])
        shortened={**changed,'counts':changed['counts'][:17],'times':changed['times'][:17]}
        prefix=robust.predict_model(bundle,shortened,['aminer','wazuh'])
        for mode in predictions:np.testing.assert_allclose(prefix['risk'][mode],actual['risk'][mode][:17],atol=1e-12)
        self.assertIsNone(robust.predict_model(bundle,changed,[])['risk'])
        zero={**changed,'counts':np.zeros_like(changed['counts'])}
        self.assertEqual(robust.predict_model(bundle,zero,['aminer','wazuh'])['status'],'ok')
        with self.assertRaises(ValueError):robust.predict_model(bundle,changed,['aminer'])

if __name__=='__main__':unittest.main()
