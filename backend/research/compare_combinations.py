"""Component/standard-method comparisons, not reproductions of cyber papers."""
from pathlib import Path
import hashlib
import json

import numpy as np
from scipy.special import logsumexp
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

import evidence_pilot as pilot

OUT = pilot.ROOT / "experiments" / "combination_comparison"
LABELS = {
    "raw": "BN-HMM, separate reports",
    "exact": "BN-HMM, exact deduplication",
    "hard": "BN-HMM, deterministic grouping",
    "soft": "BN-HMM, uncertain association prototype",
    "direct_logistic": "Direct logistic, current counts",
    "bn_no_filter": "BN observation + onset projection, no filter",
    "standard_hmm": "Conventional factorized categorical HMM",
    "temporal_logistic": "Logistic, causal temporal counts",
    "temporal_boosting": "Gradient boosting, causal temporal counts",
}


def temporal_features(obs):
    x = np.einsum("ncb,b->nc", obs, np.arange(5))
    cumulative = np.vstack([np.zeros((1, x.shape[1])), np.cumsum(x, axis=0)])
    ends = np.arange(1, len(x) + 1)
    features = [x]
    for window in [5, 15]:
        starts = np.maximum(0, ends - window)
        features.append((cumulative[ends] - cumulative[starts]) / (ends - starts)[:, None])
    return np.concatenate(features, axis=1)


def no_filter_forecast(model, obs, prior):
    transition, emissions, _ = model
    likelihood = np.einsum("ncb,scb->ncs", obs, emissions)
    lp = np.log(np.clip(likelihood, 1e-300, 1)).sum(axis=1) + np.log(prior)
    posterior = np.exp(lp - logsumexp(lp, axis=1, keepdims=True))
    q = transition[:-1, :-1]
    survival = np.stack([np.linalg.matrix_power(q, h) @ np.ones(len(q)) for h in pilot.HORIZONS])
    return np.clip(posterior[:, :-1].sum(axis=1)[:, None] - posterior[:, :-1] @ survival.T, 0, 1)


def standard_hmm_forecast(model, obs):
    # One-hot exact-dedup buckets permit the ordinary categorical likelihood.
    assert np.all((obs == 0) | (obs == 1)) and np.all(obs.sum(axis=-1) == 1)
    a, b, belief = model
    symbols = obs.argmax(axis=-1)
    emission = b[:, np.arange(b.shape[1])[None, :], symbols].transpose(1, 0, 2)
    loglik = np.log(emission).sum(axis=-1)
    q = a[:-1, :-1]
    risk_by_state = np.stack([1 - np.linalg.matrix_power(q, h).sum(axis=1) for h in pilot.HORIZONS])
    result = np.empty((len(obs), len(pilot.HORIZONS)))
    belief = belief.copy()
    for i, ll in enumerate(loglik):
        lp = np.log(np.clip(belief @ a, 1e-300, 1)) + ll
        belief = np.exp(lp - logsumexp(lp))
        result[i] = risk_by_state @ belief[:-1]
    return np.clip(result, 0, 1)


def checks():
    rng = np.random.default_rng(5)
    symbols = rng.integers(0, 5, size=(40, 12))
    obs = np.eye(5)[symbols]
    a = rng.dirichlet(np.ones(5), size=5)
    a[-1] = np.eye(5)[-1]
    b = rng.dirichlet(np.ones(5), size=(5, 12))
    model = (a, b, np.array([.9, .025, .025, .025, .025]))
    assert np.allclose(standard_hmm_forecast(model, obs), pilot.forecast(model, obs), atol=1e-12)
    assert np.array_equal(temporal_features(obs)[:20], temporal_features(obs[:20]))
    risk = no_filter_forecast(model, obs, np.ones(5) / 5)
    assert np.all((risk >= 0) & (risk <= 1)) and np.all(np.diff(risk, axis=1) >= -1e-12)
    print("Combination checks passed: HMM equivalence, feature causality, probability bounds/horizons", flush=True)


def run():
    checks()
    OUT.mkdir(parents=True, exist_ok=True)
    episodes = pilot.load_scenarios()
    observations = {name: pilot.observation_distributions(ep, ep["events"], "exact") for name, ep in episodes.items()}
    features = {name: temporal_features(obs) for name, obs in observations.items()}
    existing = json.loads((pilot.OUT / "fold_results.json").read_text())
    results = [r for r in existing if r["condition"] == "natural"]
    equivalence = []
    for fold, test in enumerate(pilot.SCENARIOS):
        val = pilot.SCENARIOS[(fold + 1) % len(pilot.SCENARIOS)]
        train = [n for n in pilot.SCENARIOS if n not in [test, val]]
        model = pilot.fit_forecaster(episodes, train, observations)
        prior = np.ones(5)
        for name in train:
            prior += np.bincount(episodes[name]["truth"], minlength=5)
        prior /= prior.sum()
        prediction_pairs = {
            "bn_no_filter": (no_filter_forecast(model, observations[val], prior), no_filter_forecast(model, observations[test], prior)),
            "standard_hmm": (standard_hmm_forecast(model, observations[val]), standard_hmm_forecast(model, observations[test])),
        }
        original = pilot.forecast(model, observations[test])
        difference = float(np.max(np.abs(original - prediction_pairs["standard_hmm"][1])))
        assert difference < 1e-12
        old = next(r for r in results if r["test"] == test and r["mode"] == "exact")
        fresh = pilot.score(episodes[test], original, [v["threshold"] for v in old["scores"].values()])
        for h in ["5", "15", "30"]:
            assert abs(fresh[h]["brier"] - old["scores"][h]["brier"]) < 1e-12
        equivalence.append({"test": test, "max_absolute_forecast_difference": difference})
        x = np.concatenate([features[n][pilot.preonset(episodes[n])] for n in train])
        for mode in ["temporal_logistic", "temporal_boosting"]:
            vp, tp = [], []
            for h in pilot.HORIZONS:
                y = np.concatenate([pilot.targets(episodes[n], h)[pilot.preonset(episodes[n])] for n in train])
                if mode == "temporal_logistic":
                    estimator = LogisticRegression(C=1, max_iter=1000)
                else:
                    estimator = HistGradientBoostingClassifier(max_iter=100, learning_rate=.08,
                        max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1,
                        early_stopping=False, random_state=1729)
                estimator.fit(x, y)
                vp.append(estimator.predict_proba(features[val])[:, 1])
                tp.append(estimator.predict_proba(features[test])[:, 1])
            prediction_pairs[mode] = (np.maximum.accumulate(np.stack(vp, axis=1), axis=1),
                                      np.maximum.accumulate(np.stack(tp, axis=1), axis=1))
        for mode, (vp, tp) in prediction_pairs.items():
            cvp, cp = pilot.calibrate(episodes[val], vp, tp)
            thresholds = [pilot.select_threshold(episodes[val], vp[:, j], h) for j, h in enumerate(pilot.HORIZONS)]
            cthresholds = [pilot.select_threshold(episodes[val], cvp[:, j], h) for j, h in enumerate(pilot.HORIZONS)]
            results.append({"test": test, "validation": val, "train": train, "mode": mode, "condition": "natural",
                            "scores": pilot.score(episodes[test], tp, thresholds),
                            "calibrated_scores": pilot.score(episodes[test], cp, cthresholds)})
        (OUT / "fold_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Component comparison fold {fold + 1}/8: {test} finished", flush=True)
    (OUT / "hmm_equivalence.json").write_text(json.dumps(equivalence, indent=2), encoding="utf-8")
    summary = {}
    for mode in LABELS:
        rows = [r for r in results if r["mode"] == mode]
        assert len(rows) == 8
        summary[mode] = {}
        for scoring in ["scores", "calibrated_scores"]:
            summary[mode][scoring] = {}
            for h in ["5", "15", "30"]:
                values = [r[scoring][h] for r in rows]
                summary[mode][scoring][h] = {
                    "mean_brier": float(np.mean([v["brier"] for v in values])),
                    "mean_average_precision": float(np.mean([v["pr_auc"] for v in values])),
                    "warned_episodes": sum(v["warning_recall"] for v in values),
                    "false_warning_episodes": sum(v["false_warning_episodes"] for v in values),
                    "negative_warning_minutes": sum(v["negative_warning_minutes"] for v in values),
                    "mean_modeled_decision_cost": float(np.mean([v["modeled_decision_cost"] for v in values])),
                }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for mode, values in summary.items():
        print(mode, json.dumps(values["calibrated_scores"]["15"]), flush=True)
    hashes = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
              for name in ["compare_combinations.py", "evidence_pilot.py"]}
    (OUT / "source_sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
