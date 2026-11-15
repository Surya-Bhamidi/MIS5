"""Bounded-memory, one-minute inference with availability-specific frozen experts."""
from collections import deque
import math
import numpy as np

import extended_study as study
import robust_forecasting as robust
import selective_fusion as selective


class ExpertStream:
    def checkpoint(self):
        # Advance creates new arrays; saved history entries are never modified.
        return dict(belief=self.belief.copy(),counts=self.counts.copy(),states=self.states.copy(),
                    count_sums=self.count_sums.copy(),state_sums=self.state_sums.copy(),steps=self.steps)

    def restore(self,checkpoint):
        for name,value in checkpoint.items():setattr(self,name,value)

    def __init__(self, bundle, calibrators):
        self.bundle, self.calibrators = bundle, calibrators
        self.mapping = {n:i for i,n in enumerate(bundle['vocabulary'])}
        self.reset()

    def reset(self):
        self.belief = self.bundle['state_model']['pi'].copy()
        self.counts = deque(maxlen=60)
        self.states = deque(maxlen=60)
        self.count_sums = deque([np.zeros(len(self.bundle['columns']))],maxlen=61)
        self.state_sums = deque([np.zeros(len(self.belief))],maxlen=61)
        self.steps = 0

    @staticmethod
    def features(history, sums, steps):
        # Preserve the batch cumsum/subtract order: tiny rounding differences
        # from recomputing a mean can cross a fitted tree's split threshold.
        return np.concatenate([history[-1]] + [(sums[-1]-sums[-min(size,steps)-1])/min(size,steps)
                                               for size in (5,15,60)])

    def advance(self, counts):
        """Update causal history without evaluating an unused forecast expert."""
        b = self.bundle
        aligned = np.zeros(len(b['vocabulary']))
        mapping = self.mapping
        for token, value in counts.items():
            key = token if token in mapping else token.split(':')[0]+':OTHER'
            if key in mapping:
                aligned[mapping[key]] += value
        columns = b['columns']
        symbols = study.symbols_for(aligned[None,:], b['edges'])[0]
        model = b['state_model']
        ll = sum((np.log(model['b'][:,j,symbols[j]]) for j in columns), np.zeros(len(self.belief)))
        ll /= np.sqrt(len(columns))
        logits = np.log(np.clip(self.belief@model['a'], 1e-300, 1))+ll
        self.belief = np.exp(logits-logits.max())
        self.belief /= self.belief.sum()
        self.counts.append(np.log1p(aligned[columns]))
        self.states.append(self.belief.copy())
        self.count_sums.append(self.count_sums[-1]+self.counts[-1])
        self.state_sums.append(self.state_sums[-1]+self.states[-1])
        self.steps += 1

    def predict(self):
        if not self.steps:raise ValueError('No observations are available')
        b = self.bundle
        base = self.features(self.counts,self.count_sums,self.steps)
        augmented = np.r_[base,self.features(self.states,self.state_sums,self.steps)]
        branches = []
        for mode, features in [('available_boosting',base),('state_augmented_boosting',augmented)]:
            branches.append(np.maximum.accumulate([m.predict_proba(features[None,:])[0,1] for m in b['estimators'][mode]]))
        risk = selective.calibrate((.75*branches[0]+.25*branches[1])[None,:], self.calibrators)[0]
        return risk

    def step(self, counts):
        self.advance(counts)
        return self.predict()


class ForecastStream:
    def checkpoint(self):
        return dict(last_time=self.last_time,contiguous=self.contiguous.copy(),
                    experts={key:expert.checkpoint() for key,expert in self.experts.items()})

    def restore(self,checkpoint):
        self.last_time=checkpoint['last_time'];self.contiguous=checkpoint['contiguous']
        for key,value in checkpoint['experts'].items():self.experts[key].restore(value)

    """Missing heartbeats are outages; a present empty counts object is zero evidence.

    Reset an expert after a gap in its required inputs. Never fill an outage with
    zero observations or feed stale trailing evidence into a recovered expert.
    """
    def __init__(self, package):
        self.experts = {key:ExpertStream(item['bundle'],item['calibrators']) for key,item in package['experts'].items()}
        self.thresholds = {key:item['threshold'] for key,item in package['experts'].items()}
        self.last_time = None
        self.contiguous = {key:False for key in self.experts}

    def step(self, timestamp, counts, healthy):
        try:
            if not isinstance(counts,dict) or any(not isinstance(k,str) or ':' not in k or not k.partition(':')[2].strip()
                or k.split(':')[0] not in robust.SENSORS or not math.isfinite(v) or v<0 for k,v in counts.items()):
                raise ValueError('Invalid detector counts')
            if not math.isfinite(math.fsum(counts.values())):raise ValueError('Detector total is not finite')
        except (TypeError,OverflowError) as error:raise ValueError('Invalid detector counts') from error
        healthy = set(healthy)
        key = robust.subset_key(healthy)
        if key!='none' and key not in self.experts:raise ValueError('No expert for healthy sensor subset')
        if not math.isfinite(timestamp) or (self.last_time is not None and timestamp <= self.last_time):
            raise ValueError('Stream timestamps must be finite and strictly increasing')
        delta = None if self.last_time is None else timestamp-self.last_time
        if delta is not None and (delta<59.999 or not math.isclose(delta,round(delta/60)*60,abs_tol=.001,rel_tol=0)):
            raise ValueError('Stream observations must use one-minute buckets')
        gap = delta is not None and not math.isclose(delta,60,abs_tol=.001,rel_tol=0)
        self.last_time = timestamp
        for expert_key, expert in self.experts.items():
            usable = set(expert_key.split('+')) <= healthy
            if usable:
                if gap or not self.contiguous[expert_key]:expert.reset()
                expert.advance(counts)
            self.contiguous[expert_key] = usable
        if key == 'none':
            return dict(status='insufficient_sensors', available=key, risk=None, threshold=None, recommended_action=None)
        risk = self.experts[key].predict()
        losses = study.decision_costs(risk[None,:],True,20,.8,1)[0]
        return dict(status='ok',available=key,risk=risk.tolist(),threshold=self.thresholds[key],
                    recommended_action=study.ACTIONS[int(losses.argmin())][0],modeled_losses=losses.tolist(),
                    history_minutes=len(self.experts[key].counts))
