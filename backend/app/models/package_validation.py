"""Structural validation for trusted locally generated research model packages."""
import math
import numpy as np

KEYS={'aminer','suricata','wazuh','aminer+suricata','aminer+wazuh','suricata+wazuh','aminer+suricata+wazuh'}
HORIZONS=[1,2,5,10,15,30]


def validate_package(package):
    if package['version']!=1 or set(package['experts'])!=KEYS:raise ValueError('Incomplete expert package')
    if not isinstance(package['scope'],str) or not isinstance(package['test'],str):raise ValueError('Missing package metadata')
    train=package['train']
    if len(train)!=6 or len(set(train))!=6 or package['test'] in train or package['validation'] in train:
        raise ValueError('Invalid model fitting split')
    for key,item in package['experts'].items():
        if not math.isfinite(item['threshold']) or item['threshold']<0:raise ValueError('Invalid threshold')
        bundle=item['bundle'];names=bundle['vocabulary'];columns=np.asarray(bundle['columns'])
        if bundle['available']!=key or not names or len(set(names))!=len(names):raise ValueError('Invalid vocabulary')
        expected=np.array([i for i,name in enumerate(names) if name.split(':')[0] in key.split('+')],dtype=int)
        if columns.ndim!=1 or len(columns)==0 or not np.array_equal(columns,expected):raise ValueError('Expert availability does not match columns')
        if len(bundle['edges'])!=len(names):raise ValueError('Invalid detector edges')
        for edges in bundle['edges']:
            edges=np.asarray(edges)
            if edges.shape!=(4,) or not np.isfinite(edges).all() or (np.diff(edges)<0).any():raise ValueError('Invalid count discretization')
        model=bundle['state_model'];pi=np.asarray(model['pi']);a=np.asarray(model['a']);b=np.asarray(model['b']);n=len(pi)
        if pi.shape!=(n,) or a.shape!=(n,n) or b.shape!=(n,len(names),5):raise ValueError('Invalid state-model shape')
        if not all(np.isfinite(value).all() for value in (pi,a,b)) or (pi<0).any() or (a<0).any() or (b<=0).any():raise ValueError('Invalid state probabilities')
        if not np.isclose(pi.sum(),1) or not np.allclose(a.sum(axis=1),1) or not np.allclose(b.sum(axis=2),1):raise ValueError('Unnormalized state model')
        calibration=item['calibrators']
        if [c['horizon'] for c in calibration]!=HORIZONS:raise ValueError('Invalid calibration horizons')
        for c in calibration:
            if not math.isfinite(c['slope']) or c['slope']<0 or not math.isfinite(c['intercept']):raise ValueError('Invalid calibrator')
            prior=c['constant_prior']
            if prior is not None and (not math.isfinite(prior) or not 0<=prior<=1):raise ValueError('Invalid calibration prior')
            if set(c['fitting_campaigns'])!=set(train):raise ValueError('Calibration fitting split mismatch')
        for branch,width in [('available_boosting',4*len(columns)),('state_augmented_boosting',4*(len(columns)+n))]:
            estimators=bundle['estimators'][branch]
            if len(estimators)!=6:raise ValueError('Missing forecast estimators')
            for estimator in estimators:
                if estimator.n_features_in_!=width or not np.array_equal(estimator.classes_,[0,1]):raise ValueError('Invalid estimator dimensions or classes')
    return package
