"""Freeze the same 27 cost/effect settings used by the original benchmark."""
import json
import numpy as np

import extended_study as study
from run_robust_forecasting import OUT

def run():
    episodes=study.load('ait');rows=[]
    folds=json.loads((OUT/'fold_results.json').read_text());assert len(folds)==168
    for fold in folds:
        test=fold['test'];available=fold['available'];mode=fold['mode']
        with np.load(OUT/'predictions'/f'ait_{test}_{available}_{mode}.npz') as saved:p=saved['calibrated']
        for damage in [10.,20.,50.]:
            for effect in [.5,.8,1.]:
                for disruption in [.5,1.,2.]:
                    aware=study.realized_decision_cost(episodes[test],p,True,damage,effect,disruption)
                    blind=study.realized_decision_cost(episodes[test],p,False,damage,effect,disruption)
                    rows.append({'scenario':test,'mode':mode,'available':available,'damage':damage,
                        'effect_scale':effect,'disruption_scale':disruption,'delay_aware':aware,'ignores_delay':blind,
                        'improvement':blind['mean_assumed_cost']-aware['mean_assumed_cost'],
                        'status':'assumed framewise costs; no executed prevention'})
    (OUT/'decisions.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print('Rescored',len(rows),'same 27-setting Decision Network cases; forecasts unchanged',flush=True)

if __name__=='__main__':run()
