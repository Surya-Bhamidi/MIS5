"""Exploratory BN / HMM-duration / Decision Network research benchmark."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import math
import time

import numpy as np
from scipy.sparse import csr_matrix
from scipy.special import logsumexp
from scipy.stats import lognorm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss

import evidence_pilot as pilot
from prepare_extended_data import OUT as DATA

OUT = pilot.ROOT / "experiments" / "extended_study"
HORIZONS = [1, 2, 5, 10, 15, 30]
MODES = ["static_bn", "detector_hmm", "duration_hmm", "temporal_logistic", "temporal_boosting"]
ACTIONS = [("Monitor", 0, 0., 0.), ("Restrict", 2, .45, .1),
           ("Block", 5, .8, .5), ("Isolate", 1, .95, 2.)]


def load(dataset):
    names = pilot.SCENARIOS if dataset == "ait" else ["1.0", "2.0.2"]
    episodes = {}
    for name in names:
        path = DATA / (f"ait_{name}_v2.npz" if dataset == "ait" else f"darpa_{name}.npz")
        with np.load(path) as item:
            episodes[name] = {k: item[k].copy() for k in ["counts", "times", "truth", "names"]}
            episodes[name]["onset"] = float(item["onset"])
    return episodes


def aligned_counts(episodes, train):
    total = Counter()
    for name in train:
        ep = episodes[name]
        total.update({str(token):float(count) for token,count in zip(ep["names"], ep["counts"].sum(axis=0))})
    selected = sorted(k for k,v in total.items() if v >= 3)
    # Only fitting vocabulary; unseen detector outputs enter sensor-specific OTHER.
    sensors = sorted(set(k.split(":")[0] for k in selected))
    names = selected + [s + ":OTHER" for s in sensors]
    mapping = {k:i for i,k in enumerate(names)}
    counts = {}
    for name, ep in episodes.items():
        x = np.zeros((len(ep["times"]), len(names)))
        for j, token in enumerate(ep["names"]):
            token = str(token)
            key = token if token in mapping else token.split(":")[0] + ":OTHER"
            if key in mapping:
                x[:, mapping[key]] += ep["counts"][:, j]
        counts[name] = x
    return counts, names


def count_edges(counts, train):
    x = np.concatenate([counts[n] for n in train])
    edges = []
    for j in range(x.shape[1]):
        positive = x[:, j][x[:, j] > 0]
        edges.append(np.r_[.5, np.quantile(positive, [.5, .9, .99]) if len(positive) else [1, 2, 3]])
    return edges


def symbols_for(x, edges):
    return np.stack([np.searchsorted(edge, x[:, j], side="right") for j,edge in enumerate(edges)], axis=1)


def temporal_features(x):
    x = np.log1p(x)
    sums = np.vstack([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)])
    ends = np.arange(1, len(x) + 1)
    columns = [x]
    for size in [5, 15, 60]:
        starts = np.maximum(0, ends - size)
        columns.append((sums[ends] - sums[starts]) / (ends - starts)[:, None])
    return np.concatenate(columns, axis=1)


def fit_model(episodes, train, symbols):
    states = max(int(episodes[n]["truth"].max()) for n in train) + 1
    columns = symbols[train[0]].shape[1]
    counts = np.ones((states, columns, 5))
    transitions = np.eye(states)
    initial = np.full(states, .01)
    occupancy = np.ones(states)
    durations = [[] for _ in range(states)]
    for name in train:
        truth = episodes[name]["truth"]
        initial[truth[0]] += 1
        occupancy += np.bincount(truth, minlength=states)
        np.add.at(transitions, (truth[:-1], truth[1:]), 1)
        for state in range(states):
            selected = symbols[name][truth == state]
            for j in range(columns):
                counts[state, j] += np.bincount(selected[:, j], minlength=5)
            length = int(np.sum(truth == state))
            if length > 0:
                durations[state].append(length)
    transitions[-1] = np.eye(states)[-1]
    transitions /= transitions.sum(axis=1, keepdims=True)
    return {"a": transitions, "b": counts / counts.sum(axis=-1, keepdims=True),
            "pi": initial / initial.sum(), "prior": occupancy / occupancy.sum(), "durations": durations}


def emission_loglik(model, symbols):
    result = np.zeros((len(symbols), model["b"].shape[0]))
    for j in range(symbols.shape[1]):
        result += np.log(model["b"][:, j, symbols[:, j]].T)
    return result


def duration_transition(model):
    a = model["a"]
    lengths = [1]
    for state in range(1, len(a) - 1):
        lengths.append(min(1800, max(10, math.ceil(max(model["durations"][state] or [1]) * 3))))
    lengths.append(1)
    offsets = np.r_[0, np.cumsum(lengths)]
    row, col, values = [], [], []
    for state, length in enumerate(lengths):
        if state in [0, len(a) - 1]:
            for destination, probability in enumerate(a[state]):
                if probability > 0:
                    row.append(int(offsets[state])); col.append(int(offsets[destination])); values.append(probability)
            continue
        duration = np.array(model["durations"][state] or [1])
        location = float(np.log(duration).mean())
        scale = max(.5, float(np.log(duration).std()))
        cdf = lognorm.cdf(np.arange(length + 1), s=scale, scale=np.exp(location))
        hazards = np.clip(np.diff(cdf) / np.clip(1 - cdf[:-1], 1e-12, 1), 1e-9, 1)
        hazards[-1] = 1
        exit_prob = a[state].copy()
        exit_prob[:state + 1] = 0
        if exit_prob.sum() == 0:
            exit_prob[state + 1] = 1
        exit_prob /= exit_prob.sum()
        for age, hazard in enumerate(hazards):
            current = int(offsets[state] + age)
            if age + 1 < length:
                row.append(current); col.append(current + 1); values.append(1 - hazard)
            for destination in np.flatnonzero(exit_prob):
                row.append(current); col.append(int(offsets[destination])); values.append(hazard * exit_prob[destination])
    transition = csr_matrix((values, (row, col)), shape=(int(offsets[-1]), int(offsets[-1])))
    state_map = np.repeat(np.arange(len(a)), lengths)
    initial = np.zeros(len(state_map))
    initial[offsets[:-1]] = model["pi"]
    assert np.allclose(np.asarray(transition.sum(axis=1)).ravel(), 1)
    return transition, initial, state_map


def forecast(model, symbols, mode):
    ll = emission_loglik(model, symbols)
    if mode == "duration_hmm":
        a, belief, state_map = duration_transition(model)
    else:
        a, belief, state_map = csr_matrix(model["a"]), model["pi"].copy(), np.arange(len(model["a"]))
    non_target = (state_map != len(model["a"]) - 1).astype(float)
    survivor, projections = non_target.copy(), []
    for minute in range(1, max(HORIZONS) + 1):
        survivor = np.asarray(a @ survivor).ravel()
        if minute in HORIZONS:
            projections.append(non_target - survivor)
    projections = np.stack(projections, axis=1)
    prediction = np.empty((len(symbols), len(HORIZONS)))
    for i, values in enumerate(ll):
        if mode == "static_bn":
            prior = model["prior"]
        else:
            prior = np.asarray(a.T @ belief).ravel()
        lp = np.log(np.clip(prior, 1e-300, 1)) + values[state_map]
        belief = np.exp(lp - logsumexp(lp))
        prediction[i] = belief @ projections
    return np.clip(prediction, 0, 1)


def choose_threshold(ep, p, horizon):
    mask = pilot.preonset(ep)
    scores = p[mask]
    positive = pilot.targets(ep, horizon)[mask] == 1
    candidates = np.unique(np.r_[0, np.quantile(scores, np.linspace(0, 1, 257)),
                                scores[positive], np.nextafter(scores[positive], np.inf), 1.000001])
    best, chosen = None, 1.000001
    for threshold in candidates:
        result = pilot.warning_metrics(ep, p, horizon, threshold)
        if result["false_warnings_per_24h"] > 1 or result["negative_warning_minutes"] > 5:
            continue
        rank = (result["warning_recall"], result["lead_minutes"] or 0,
                -result["negative_warning_minutes"], -result["false_warning_episodes"], threshold)
        if best is None or rank > best:
            best, chosen = rank, threshold
    return float(chosen)


def decision_costs(p, delays=True, damage=20., effect_scale=1., disruption_scale=1.):
    chance = p[:, HORIZONS.index(30)]
    costs = []
    for _, delay, effect, disruption in ACTIONS:
        late = p[:, HORIZONS.index(delay)] if delays and delay else np.zeros(len(p))
        preventable = np.maximum(0, chance - late)
        costs.append(disruption * disruption_scale + damage * (chance - min(1, effect * effect_scale) * preventable))
    return np.stack(costs, axis=1)


def realized_decision_cost(ep, p, respect_delays=True, damage=20., effect_scale=1., disruption_scale=1.):
    mask = pilot.preonset(ep)
    selected = decision_costs(p[mask], respect_delays, damage, effect_scale, disruption_scale).argmin(axis=1)
    remaining = (ep["onset"] - ep["times"][mask]) / 60
    imminent = remaining <= 30
    losses = np.empty(len(remaining))
    for i, (_, delay, effect, disruption) in enumerate(ACTIONS):
        action_mask = selected == i
        # Realized effects always have delay, including the policy ignoring it.
        prevented = imminent & (remaining > delay)
        losses[action_mask] = disruption * disruption_scale + damage * (imminent[action_mask] -
            min(1, effect * effect_scale) * prevented[action_mask])
    return {"mean_assumed_cost": float(losses.mean()),
            "actions": {a[0]:int(np.sum(selected == i)) for i,a in enumerate(ACTIONS)}}


def score(ep, p, thresholds):
    mask = pilot.preonset(ep)
    scores = {}
    for j,h in enumerate(HORIZONS):
        y = pilot.targets(ep, h)[mask]
        metrics = pilot.warning_metrics(ep, p[:,j], h, thresholds[j])
        metrics.update(brier=float(brier_score_loss(y,p[mask,j])),
                       average_precision=float(average_precision_score(y,p[mask,j])),
                       positive_clock_bins=int(y.sum()), clock_bins=int(mask.sum()))
        scores[str(h)] = metrics
    decisions = {}
    for damage in [10.,20.,50.]:
        for disruption in [.5,1.,2.]:
            key = f"damage={damage};disruption={disruption}"
            decisions[key] = {"delay_aware":realized_decision_cost(ep,p,True,damage,1.,disruption),
                             "ignores_delay":realized_decision_cost(ep,p,False,damage,1.,disruption)}
    fixed = {str(t):{str(h):pilot.warning_metrics(ep,p[:,j],h,t) for j,h in enumerate(HORIZONS)}
             for t in [.01,.05,.1,.5]}
    return scores, decisions, fixed


def checks():
    x = np.arange(180).reshape(60,3) % 7
    assert np.array_equal(temporal_features(x)[:20],temporal_features(x[:20]))
    episode = {"counts":x,"truth":np.r_[np.zeros(35,dtype=int),np.ones(10,dtype=int),np.full(10,2),np.full(5,3)]}
    symbols = symbols_for(x, count_edges({"x":x},["x"]))
    model = fit_model({"x":episode},["x"],{"x":symbols})
    for mode in ["static_bn","detector_hmm","duration_hmm"]:
        risk = forecast(model,symbols,mode)
        assert np.all((risk>=0)&(risk<=1)) and np.all(np.diff(risk,axis=1)>=-1e-12)
        assert np.allclose(risk[:20],forecast(model,symbols[:20],mode))
    p = np.tile(np.linspace(.01,.5,len(HORIZONS)),(3,1))
    aware = decision_costs(p,True)
    blind = decision_costs(p,False)
    assert np.all(aware >= blind-1e-12)
    assert np.allclose(decision_costs(np.zeros_like(p))[:,0],0)
    print("Extended checks passed: causal features/filtering, probability bounds, horizon coherence, duration rows and delayed utility",flush=True)


def run(dataset):
    checks()
    pilot.HORIZONS = HORIZONS
    OUT.mkdir(parents=True,exist_ok=True)
    prediction_dir = OUT / "predictions"
    prediction_dir.mkdir(exist_ok=True)
    episodes = load(dataset)
    results, metadata = [], []
    for fold,test in enumerate(episodes):
        if dataset == "ait":
            val = pilot.SCENARIOS[(fold+1)%8]
            train = [n for n in episodes if n not in [test,val]]
        else:
            train = [n for n in episodes if n != test]
            val = train[0]
        start = time.monotonic()
        counts,names = aligned_counts(episodes,train)
        edges = count_edges(counts,train)
        symbols = {n:symbols_for(x,edges) for n,x in counts.items()}
        model = fit_model(episodes,train,symbols)
        features = {n:temporal_features(x) for n,x in counts.items()}
        pairs = {mode:(forecast(model,symbols[val],mode),forecast(model,symbols[test],mode))
                 for mode in MODES[:3]}
        xt = np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
        for mode in MODES[3:]:
            vp,tp = [],[]
            for horizon in HORIZONS:
                y = np.concatenate([pilot.targets(episodes[n],horizon)[pilot.preonset(episodes[n])] for n in train])
                estimator = (LogisticRegression(C=1,max_iter=1000) if mode == "temporal_logistic" else
                    HistGradientBoostingClassifier(max_iter=100,learning_rate=.08,max_leaf_nodes=15,
                        min_samples_leaf=20,l2_regularization=1,early_stopping=False,random_state=1729))
                estimator.fit(xt,y)
                vp.append(estimator.predict_proba(features[val])[:,1]);tp.append(estimator.predict_proba(features[test])[:,1])
            pairs[mode]=(np.maximum.accumulate(np.stack(vp,axis=1),axis=1),
                         np.maximum.accumulate(np.stack(tp,axis=1),axis=1))
        for mode,(vp,tp) in pairs.items():
            cvp,cp = pilot.calibrate(episodes[val],vp,tp) if dataset == "ait" else (vp.copy(),tp.copy())
            result={"dataset":dataset,"test":test,"validation":val,"train":train,"mode":mode,
                    "threshold_source":"held-out validation" if dataset=="ait" else "fitting campaign (no independent validation)"}
            for label,validation,prediction in [("raw",vp,tp),("calibrated",cvp,cp)]:
                thresholds=[choose_threshold(episodes[val],validation[:,j],h) for j,h in enumerate(HORIZONS)]
                result[label],result[label+"_decisions"],result[label+"_fixed_thresholds"] = score(episodes[test],prediction,thresholds)
            results.append(result)
            np.savez_compressed(prediction_dir/f"{dataset}_{test}_{mode}.npz",raw=tp,calibrated=cp,
                                validation_raw=vp,validation_calibrated=cvp,times=episodes[test]["times"],
                                onset=episodes[test]["onset"],horizons=np.array(HORIZONS))
        metadata.append({"test":test,"validation":val,"train":train,"vocabulary":names,
                         "bucket_edges":[e.tolist() for e in edges],"durations":model["durations"],
                         "seconds":time.monotonic()-start})
        (OUT/f"{dataset}_fold_results.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
        print(f"{dataset} fold {fold+1}/{len(episodes)} {test} completed ({time.monotonic()-start:.1f}s)",flush=True)
    (OUT/f"{dataset}_metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    for mode in MODES:
        rows=[r for r in results if r["mode"]==mode]
        print(mode,json.dumps({h:{"brier":float(np.mean([r['calibrated'][h]['brier'] for r in rows])),
            "ap":float(np.mean([r['calibrated'][h]['average_precision'] for r in rows])),
            "warned":sum(r['calibrated'][h]['warning_recall'] for r in rows),
            "false":sum(r['calibrated'][h]['false_warning_episodes'] for r in rows)} for h in ['5','15','30']}),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("dataset",choices=["ait","darpa","checks"])
    args=parser.parse_args()
    checks() if args.dataset=="checks" else run(args.dataset)
