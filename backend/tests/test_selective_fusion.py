"""Information exclusion, selective blending and campaign-calibration contracts."""
import sys
import unittest
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import selective_fusion as selective
import robust_forecasting as robust
import extended_study as study


class TestSelectiveFusion(unittest.TestCase):
    def fixture(self):
        episodes={};held={}
        for i,n in enumerate(['a','b','c','unused_test']):
            length=80+i*10;times=np.arange(1,length+1)*60.;onset=times[-1]+60
            ep={'times':times,'onset':onset};episodes[n]=ep
            y=np.stack([((onset-times)<=h*60).astype(float) for h in study.HORIZONS],axis=1)
            held[n]=(y*.6+.2,y*.9+.05)
        return episodes,held

    def test_selector_ignores_campaigns_outside_the_fitting_list(self):
        episodes,held=self.fixture();train=['a','b','c']
        original=selective.select_weights(episodes,held,train)
        episodes['unused_test']['onset']=-1;held['unused_test']=(np.ones((110,6)),np.zeros((110,6)))
        self.assertEqual(original,selective.select_weights(episodes,held,train))
        self.assertEqual(original[0],[1.]*6)
        # Identical branches must choose zero, rather than imply state value.
        identical={n:(p[0],p[0]) for n,p in held.items()}
        self.assertEqual(selective.select_weights(episodes,identical,train)[0],[0.]*6)

    def test_per_horizon_blending_is_causal_bounded_and_ordered(self):
        rng=np.random.default_rng(1729)
        a=np.sort(rng.uniform(size=(40,6)),axis=1);b=np.sort(rng.uniform(size=(40,6)),axis=1)
        weights=[0,1,.25,.1,.5,0]
        full=selective.mix(a,b,weights)
        np.testing.assert_array_equal(full[:17],selective.mix(a[:17],b[:17],weights))
        np.testing.assert_array_equal(a,selective.mix(a,b,[0]*6))
        self.assertTrue(np.all(np.diff(full,axis=1)>=0));self.assertTrue(np.all((full>=0)&(full<=1)))
        with self.assertRaises(ValueError):selective.mix(a,b,[0,0,0,0,0,2])

    def test_calibration_has_equal_campaign_weight_and_no_test_dependency(self):
        episodes,held=self.fixture();train=['a','b','c'];predictions={n:p[0] for n,p in held.items()}
        scores,y,weights=selective.fitting_arrays(episodes,{n:p[:,0] for n,p in predictions.items()},train,1)
        starts=np.r_[0,np.cumsum([len(episodes[n]['times']) for n in train])]
        totals=[weights[starts[i]:starts[i+1]].sum() for i in range(3)]
        np.testing.assert_allclose(totals,np.full(3,len(y)/3))
        parameters=selective.fit_calibration(episodes,predictions,train)
        episodes['unused_test']['onset']=-999;predictions['unused_test'][:]=0
        self.assertEqual(parameters,selective.fit_calibration(episodes,predictions,train))
        full=selective.calibrate(predictions['a'],parameters)
        np.testing.assert_array_equal(full[:17],selective.calibrate(predictions['a'][:17],parameters))
        self.assertTrue(np.all((full>=0)&(full<=1)));self.assertTrue(np.all(np.diff(full,axis=1)>=0))

    def test_negative_slope_falls_back_to_prior(self):
        episodes,held=self.fixture();train=['a','b','c']
        predictions={n:1-p[0] for n,p in held.items()}
        parameters=selective.fit_calibration(episodes,predictions,train)
        self.assertTrue(all(p['rejected_negative_slope'] for p in parameters))
        out=selective.calibrate(predictions['a'],parameters)
        np.testing.assert_allclose(out,np.tile(np.maximum.accumulate([p['constant_prior'] for p in parameters]),(80,1)))

    def test_inner_state_features_exclude_the_held_campaign(self):
        episodes={}
        for i,n in enumerate(['a','b','c','d','e','held']):
            counts=np.zeros((70,2));counts[40+i:,0]=1;counts[50+i:,1]=3
            episodes[n]={'counts':counts,'times':np.arange(1,71)*60.,'onset':60*60.,
                'truth':np.r_[np.zeros(55,dtype=int),np.ones(15,dtype=int)],
                'names':np.array(['aminer:x','wazuh:y'])}
        with threadpool_limits(limits=2):
            predictions,bundle,meta=robust.fit_predict(episodes,['a','b','c','d','e'],['held'],['aminer','wazuh'])
            for split in meta['state_crossfit_splits']:
                self.assertEqual(len(split['fitting_campaigns']),4)
                self.assertNotIn(split['prediction_campaign'],split['fitting_campaigns'])
                self.assertNotIn('held',split['fitting_campaigns'])
            changed={**episodes['held'],'truth':np.full(70,999),'onset':-1.}
            output=robust.predict_model(bundle,changed,['aminer','wazuh'])
            calibrators={mode:[{'slope':1.,'intercept':0.,'constant_prior':None} for _ in study.HORIZONS]
                for mode in ['pooled_counts','pooled_state','pooled_fixed_blend','pooled_selective']}
            weights=[.1,.1,.25,.25,.5,.5]
            original=selective.predict_selective(bundle,episodes['held'],['aminer','wazuh'],weights,calibrators)
            actual=selective.predict_selective(bundle,changed,['aminer','wazuh'],weights,calibrators)
            np.testing.assert_array_equal(original['risk'],actual['risk'])
            self.assertEqual(original['recommended_action'],actual['recommended_action'])
            absent=selective.predict_selective(bundle,changed,[],weights,calibrators)
            self.assertIsNone(absent['risk']);self.assertIsNone(absent['recommended_action'])
            fixed_parameters={'pooled_fixed_blend':calibrators['pooled_fixed_blend']}
            current=selective.predict_current(bundle,changed,['aminer','wazuh'],fixed_parameters)
            expected=.75*predictions['available_boosting']['held']+.25*predictions['state_augmented_boosting']['held']
            np.testing.assert_allclose(current['risk'],expected,rtol=0,atol=1e-12)
            self.assertEqual(current['weights'],[.25]*6)
            self.assertEqual(current['primary_horizon_minutes'],30)
            self.assertEqual(current['forecast_mode'],'pooled_fixed_blend')
            self.assertIsNone(selective.predict_current(bundle,changed,[],fixed_parameters)['recommended_action'])
        for mode in predictions:np.testing.assert_array_equal(output['risk'][mode],predictions[mode]['held'])


if __name__=='__main__':unittest.main()
