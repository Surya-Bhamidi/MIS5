"""Isolated, causal AIT-ADS pilot. Does not import/mutate the app or SQLite.

The bounded association-mixture observation model is an exploratory prototype,
not a validated global probabilistic event-association algorithm.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.special import logsumexp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research" / "ait_ads"
OUT = ROOT / "experiments" / "evidence_pilot"
STEP = 60
HORIZONS = [5, 15, 30]
MODES = ["raw", "exact", "hard", "soft"]
KINDS = ["scan", "web", "authentication", "privilege", "shell", "file",
         "network", "malware", "error", "scheduled", "update", "other"]
SCENARIOS = ["fox", "harrison", "russellmitchell", "santos", "shaw", "wardbeck", "wheeler", "wilson"]
DTYPE = np.dtype([("t", "f8"), ("kind", "i1"), ("sensor", "i1"),
                  ("record", "u8"), ("content", "u8"), ("origin", "u8")])
SYSLOG_TIME = re.compile(r"^[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+")
PID = re.compile(r"\[\d+\]")


def digest(text):
    return int.from_bytes(hashlib.blake2b(text.encode(), digest_size=8).digest(), "little")


def kind_from_text(text):
    # Observable messages only; no phase labels, host addresses, or filenames.
    text = text.lower()
    tests = [
        ("scan", ("scan", "nmap", "recon", "dirb", "wpscan")),
        ("privilege", ("sudo", "su:", "su[", "uid=0", "root login")),
        ("shell", ("webshell", "reverse shell", "command execution", "cmd=", "shell.php")),
        ("web", ("http", "apache", "wordpress", "web attack", "sql injection", "access.log")),
        ("authentication", ("sshd", "authentication", "login", "password", "pam_unix")),
        ("malware", ("malware", "trojan", "virus found")),
        ("file", ("file integrity", "file added", "file deleted", "file modified", "syscheck")),
        ("network", ("suricata", "dns", "network", "firewall", "icmp", "tcp", "udp")),
        ("update", ("update", "freshclam", "apt-get", "package")),
        ("scheduled", ("cron", "scheduled", "systemd")),
        ("error", ("error", "failed", "failure", "warning")),
    ]
    for name, words in tests:
        if any(word in text for word in words):
            return KINDS.index(name)
    return len(KINDS) - 1


def parse_record(e, sensor_default):
    if sensor_default == 2:
        ld = e.get("LogData", {})
        times = ld.get("DetectionTimestamp") or ld.get("Timestamps") or []
        if not times:
            return None
        t = max(float(x) for x in times)
        raw = "\n".join(str(x) for x in ld.get("RawLogData", []))
        # Raw event text shared with other sensors where available.
        sensor = 2
        identity = json.dumps(e, sort_keys=True, separators=(",", ":"))
    else:
        t = datetime.fromisoformat(e["@timestamp"].replace("Z", "+00:00")).timestamp()
        raw = str(e.get("full_log", ""))
        if not raw:
            raw = json.dumps(e.get("data", {}), sort_keys=True, separators=(",", ":"))
        sensor = 1 if "suricata" in e.get("rule", {}).get("groups", []) else 0
        identity = str(e.get("id")) if e.get("id") else json.dumps(e, sort_keys=True)
    normalized = PID.sub("[PID]", SYSLOG_TIME.sub("", raw)).strip()
    # Same classifier for each sensor: rule descriptions are deliberately absent.
    kind = kind_from_text(normalized)
    record = digest(f"{sensor}|{identity}")
    return (t, kind, sensor, record, digest(normalized), record)


def load_labels():
    labels = defaultdict(dict)
    with (DATA / "labels.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            labels[row["scenario"]][row["attack"]] = (float(row["start"]), float(row["end"]))
    for name in SCENARIOS:
        phases = labels[name]
        required = ["network_scans", "webshell", "reverse_shell", "privilege_escalation"]
        starts = [phases[x][0] for x in required]
        if starts != sorted(starts) or len(set(starts)) != len(starts):
            raise ValueError(f"Endpoint ordering invalid: {name}: {starts}")
    return labels


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    cache = DATA / "compact"
    cache.mkdir(exist_ok=True)
    labels = load_labels()
    manifest = {}
    with zipfile.ZipFile(DATA / "ait_ads.zip") as archive:
        for name in SCENARIOS:
            path = cache / f"{name}_v1.npz"
            if path.exists():
                print(f"Cached {name}", flush=True)
                continue
            rows = []
            dropped = 0
            endpoint = labels[name]["privilege_escalation"][0]
            for suffix, sensor in [("wazuh", 0), ("aminer", 2)]:
                with archive.open(f"{name}_{suffix}.json") as stream:
                    for line in stream:
                        try:
                            parsed = parse_record(json.loads(line), sensor)
                        except (KeyError, ValueError, TypeError):
                            dropped += 1
                            continue
                        if parsed is not None and parsed[0] <= endpoint + 1800:
                            rows.append(parsed)
            events = np.array(rows, dtype=DTYPE)
            events.sort(order=["t", "record"])
            start = math.floor(float(events["t"].min()) / 86400) * 86400
            end = math.ceil((endpoint + 1800) / STEP) * STEP
            times = np.arange(start + STEP, end + STEP / 2, STEP)
            truth = np.zeros(len(times), dtype="i1")
            for stage, attack in enumerate(["network_scans", "webshell", "reverse_shell", "privilege_escalation"], 1):
                truth[times >= labels[name][attack][0]] = stage
            np.savez_compressed(path, events=events, times=times, truth=truth,
                                onset=endpoint, dropped=dropped)
            manifest[name] = {"events": len(events), "bins": len(times), "onset": endpoint,
                              "sensor_counts": dict(Counter(int(x) for x in events["sensor"])),
                              "dropped": dropped}
            print(f"Prepared {name}: {len(events)} records, {len(times)} clock bins", flush=True)
    for name in SCENARIOS:
        with np.load(cache / f"{name}_v1.npz") as item:
            manifest[name] = {"events": len(item["events"]), "bins": len(item["times"]),
                              "onset": float(item["onset"]), "dropped": int(item["dropped"]),
                              "sensor_counts": dict(Counter(int(x) for x in item["events"]["sensor"]))}
    (OUT / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_scenarios():
    episodes = {}
    for name in SCENARIOS:
        with np.load(DATA / "compact" / f"{name}_v1.npz") as item:
            episodes[name] = {k: item[k].copy() for k in ["events", "times", "truth"]}
            episodes[name]["onset"] = float(item["onset"])
    return episodes


def pair_features(delta, same_sensor):
    return [math.log1p(abs(delta)), float(same_sensor)]


def fit_matcher(episodes, train_names):
    """Constructed replay positives; distinct stored records are proxy negatives.

    Natural records may share an underlying event: this imperfect proxy is an
    explicit limitation. No test phase labels or hidden origin IDs are features.
    """
    rng = np.random.default_rng(314159)
    features, targets = [], []
    for name in train_names:
        previous = {}
        for row in episodes[name]["events"]:
            content = int(row["content"])
            if content in previous:
                old = previous[content]
                delta = row["t"] - old["t"]
                if delta <= 5 and row["record"] != old["record"]:
                    features.append(pair_features(delta, row["sensor"] == old["sensor"]))
                    targets.append(0)
            previous[content] = row
        # Fixed positive distribution for the constructed alias-copy mechanism.
        for _ in range(2000):
            features.append(pair_features(float(rng.uniform(0.05, 2.0)), rng.random() < 0.8))
            targets.append(1)
    # Bound fitting expense and make class balancing explicit.
    features, targets = np.array(features), np.array(targets)
    negative = np.flatnonzero(targets == 0)
    positive = np.flatnonzero(targets == 1)
    if len(negative) > 12000:
        negative = rng.choice(negative, 12000, replace=False)
    selected = np.r_[negative, positive]
    matcher = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
    matcher.fit(features[selected], targets[selected])
    return matcher, {"constructed_positive_pairs": int(len(positive)),
                     "proxy_negative_pairs": int(len(negative)),
                     "intercept": matcher.intercept_.tolist(), "coefficients": matcher.coef_.tolist(),
                     "probabilities_not_validated_on_real_event_identity": True}


def transform(events, condition, seed):
    if condition == "natural":
        return events
    rng = np.random.default_rng(seed)
    selected = rng.choice(len(events), size=max(1, len(events) // 10), replace=False)
    copies = events[selected].copy()
    if condition == "exact_replay":
        return np.sort(np.concatenate([events, copies, copies]), order=["t", "record"])
    if condition == "alias_jitter":
        copies["t"] += rng.uniform(0.05, 2.0, len(copies))
        copies["record"] = rng.integers(1, np.iinfo(np.int64).max, len(copies), dtype="u8")
        # Keep sensor and content unchanged: these are aliased copies of reports,
        # not independent sensors or new attacker actions.
        return np.sort(np.concatenate([events, copies]), order=["t", "record"])
    raise ValueError(condition)


def bucket_counts(values):
    return np.searchsorted([0.5, 1.5, 4.5, 15.5], values).astype("i1")


def observation_distributions(episode, events, mode, matcher=None, tolerance=2.0):
    """Distribution of count buckets, marginalizing bounded disjoint pairs.

    A mixture of association hypotheses provides a likelihood over count-bucket
    explanations. This approximates association as state-independent; it is not
    a fully specified generative model of all sensor error dependencies.
    """
    times = episode["times"]
    n, c = len(times), len(KINDS)
    distributions = np.zeros((n, c, 5))
    distributions[:, :, 0] = 1.0
    bins = np.searchsorted(times, events["t"], side="left")
    valid = bins < n
    events, bins = events[valid], bins[valid]
    if mode != "raw":
        # Exact identity deduplication is global, before windows/association.
        _, indices = np.unique(events["record"], return_index=True)
        indices.sort()
        events, bins = events[indices], bins[indices]
    boundaries = np.r_[0, np.flatnonzero(np.diff(bins)) + 1, len(bins)]
    for begin, end in zip(boundaries[:-1], boundaries[1:]):
        if begin == end:
            continue
        index = int(bins[begin])
        rows = events[begin:end]
        for kind in np.unique(rows["kind"]):
            group = rows[rows["kind"] == kind]
            probabilities = []
            merged = 0
            previous = {}
            if mode in ("hard", "soft"):
                for row in group:
                    key = int(row["content"])
                    old = previous.get(key)
                    if old is not None and row["t"] - old["t"] <= tolerance:
                        if mode == "hard":
                            merged += 1
                            # Hard grouping can consolidate more than two records.
                            continue
                        # Disjoint pairs and at most 64 uncertain pairs per kind.
                        if len(probabilities) < 64:
                            feature = pair_features(row["t"] - old["t"], row["sensor"] == old["sensor"])
                            z = matcher.intercept_[0] + np.dot(matcher.coef_[0], feature)
                            p_shared = float(1 / (1 + math.exp(-float(np.clip(z, -30, 30)))))
                            probabilities.append(p_shared)
                            previous.pop(key)
                            continue
                    previous[key] = row
            if mode == "soft" and probabilities:
                weights = np.array([1.0])
                for p_shared in probabilities:
                    # Number removed is one with P(shared), zero with P(distinct).
                    weights = np.convolve(weights, [1 - p_shared, p_shared])
                counts = len(group) - np.arange(len(weights))
                dist = np.bincount(bucket_counts(counts), weights=weights, minlength=5)
            else:
                dist = np.eye(5)[int(bucket_counts(len(group) - merged))]
            distributions[index, int(kind)] = dist
    return distributions


def fit_forecaster(episodes, train_names, train_obs):
    nstates, nc = 5, len(KINDS)
    counts = np.full((nstates, nc, 5), 1.0)
    transitions = np.eye(nstates) * 1.0
    initial = np.full(nstates, 0.1)
    for name in train_names:
        truth = episodes[name]["truth"]
        initial[truth[0]] += 1
        np.add.at(transitions, (truth[:-1], truth[1:]), 1.0)
        for state in range(nstates):
            counts[state] += train_obs[name][truth == state].sum(axis=0)
    # Training labels are used only for parameters; target is absorbing for
    # first-onset prediction. No hard-coded target posterior pin or IP boosts.
    transitions[-1] = np.eye(nstates)[-1]
    transitions /= transitions.sum(axis=1, keepdims=True)
    emissions = counts / counts.sum(axis=-1, keepdims=True)
    initial /= initial.sum()
    return transitions, emissions, initial


def forecast(model, obs):
    transition, emissions, belief = model
    likelihood = np.einsum("ncb,scb->ncs", obs, emissions)
    loglik = np.log(np.clip(likelihood, 1e-300, 1)).sum(axis=1)
    forecasts = np.empty((len(obs), len(HORIZONS)))
    q = transition[:-1, :-1]
    survival = np.stack([np.linalg.matrix_power(q, horizon) @ np.ones(len(q)) for horizon in HORIZONS])
    belief = belief.copy()
    for i, ll in enumerate(loglik):
        lp = np.log(np.clip(belief @ transition, 1e-300, 1)) + ll
        belief = np.exp(lp - logsumexp(lp))
        # Joint probability that onset is still ahead and occurs within horizon.
        # Existing-target probability is explicitly excluded from future onset.
        forecasts[i] = belief[:-1].sum() - survival @ belief[:-1]
    return np.clip(forecasts, 0, 1)


def targets(episode, horizon):
    t = episode["times"]
    return ((t < episode["onset"]) & (t + horizon * STEP >= episode["onset"])).astype(int)


def preonset(episode):
    return episode["times"] < episode["onset"]


def warning_metrics(episode, p, horizon, threshold):
    mask = preonset(episode)
    times = episode["times"][mask]
    p = p[mask]
    y = targets(episode, horizon)[mask]
    warning = p >= threshold
    starts = np.flatnonzero(warning & ~np.r_[False, warning[:-1]])
    # A persistent false-warning episode may later become a valid warning;
    # report first warning inside the valid forecast horizon for recall/lead.
    positive = np.flatnonzero(warning & (y == 1))
    false = int(np.sum(y[starts] == 0))
    exposure = max(float(np.sum(y == 0) * STEP / 3600), 1e-9)
    return {"warning_recall": int(len(positive) > 0),
            "lead_minutes": None if not len(positive) else float((episode["onset"] - times[positive[0]]) / 60),
            "false_warning_episodes": false, "negative_exposure_hours": exposure,
            "false_warnings_per_24h": false / exposure * 24,
            "negative_warning_minutes": float(np.sum(warning & (y == 0))),
            "threshold": float(threshold)}


def select_threshold(episode, p, horizon):
    candidates = np.unique(np.r_[0.0, np.linspace(0.001, 0.999, 100), 1.000001])
    best, chosen = None, None
    for threshold in candidates:
        result = warning_metrics(episode, p, horizon, threshold)
        if result["false_warnings_per_24h"] > 1.0 or result["negative_warning_minutes"] > 5:
            continue
        rank = (result["warning_recall"], result["lead_minutes"] or 0,
                -result["negative_warning_minutes"], -result["false_warning_episodes"], threshold)
        if best is None or rank > best:
            best, chosen = rank, threshold
    return float(chosen)


def score(episode, predictions, thresholds):
    scores = {}
    mask = preonset(episode)
    for j, horizon in enumerate(HORIZONS):
        y = targets(episode, horizon)[mask]
        p = predictions[mask, j]
        result = warning_metrics(episode, predictions[:, j], horizon, thresholds[j])
        result.update(brier=float(brier_score_loss(y, p)),
                      pr_auc=float(average_precision_score(y, p)),
                      positive_clock_bins=int(y.sum()), clock_bins=len(y),
                      # Common hypothetical cost: false block=1, missed imminent
                      # outcome=20. It is a framewise decision, not prevention.
                      modeled_decision_cost=float(np.mean(np.where(p >= 1 / 21,
                                                                  (1 - y), 20 * y))),
                      decision_assumptions={"false_action_cost": 1, "miss_cost": 20,
                                            "assumed_perfect_action_effect": True})
        scores[str(horizon)] = result
    return scores


def calibrate(val_episode, val_predictions, test_predictions):
    mask = preonset(val_episode)
    val_out = val_predictions.copy()
    test_out = test_predictions.copy()
    for j, horizon in enumerate(HORIZONS):
        def feature(p):
            p = np.clip(p, 1e-8, 1 - 1e-8)
            return np.log(p / (1 - p)).reshape(-1, 1)
        reg = LogisticRegression(C=1.0, max_iter=1000)
        reg.fit(feature(val_predictions[mask, j]), targets(val_episode, horizon)[mask])
        # Reject a negative slope: no inversions of a probability ranking.
        if reg.coef_[0, 0] < 0:
            prior = float(targets(val_episode, horizon)[mask].mean())
            val_out[:, j], test_out[:, j] = prior, prior
        else:
            val_out[:, j] = reg.predict_proba(feature(val_predictions[:, j]))[:, 1]
            test_out[:, j] = reg.predict_proba(feature(test_predictions[:, j]))[:, 1]
    # Separate horizon fits could cross; enforce monotonicity for predictions.
    return np.maximum.accumulate(val_out, axis=1), np.maximum.accumulate(test_out, axis=1)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    episodes = load_scenarios()
    all_results, matcher_details = [], {}
    conditions = ["natural", "exact_replay", "alias_jitter"]
    static_obs = {}

    def observations(name, mode, matcher, tolerance, condition="natural", seed=1729):
        # Deterministic observations do not depend on fitted matcher/fold.
        # Cache them so each fair baseline is evaluated once per input variant.
        key = (name, mode, tolerance, condition, seed if condition != "natural" else 0)
        if mode != "soft" and key in static_obs:
            return static_obs[key]
        events = transform(episodes[name]["events"], condition, seed)
        result = observation_distributions(episodes[name], events, mode, matcher, tolerance)
        if mode != "soft":
            static_obs[key] = result
        return result

    for fold, test_name in enumerate(SCENARIOS):
        val_name = SCENARIOS[(fold + 1) % len(SCENARIOS)]
        train_names = [name for name in SCENARIOS if name not in [test_name, val_name]]
        matcher, details = fit_matcher(episodes, train_names)
        matcher_details[test_name] = details
        for mode in MODES:
            # Hard-group tolerance is selected on validation Brier, all methods
            # otherwise share model capacity and train/calibration/test split.
            candidates = [0.0, 0.5, 2.0, 5.0] if mode == "hard" else [5.0 if mode == "soft" else 0.0]
            choices = []
            for tolerance in candidates:
                train_obs = {name: observations(name, mode, matcher, tolerance) for name in train_names}
                model = fit_forecaster(episodes, train_names, train_obs)
                val_obs = observations(val_name, mode, matcher, tolerance)
                vp = forecast(model, val_obs)
                mask = preonset(episodes[val_name])
                loss = np.mean([brier_score_loss(targets(episodes[val_name], h)[mask], vp[mask, j])
                                for j, h in enumerate(HORIZONS)])
                choices.append((loss, tolerance, model, vp))
            _, tolerance, model, vp = min(choices, key=lambda x: (x[0], x[1]))
            natural_predictions = None
            for condition in conditions:
                obs = observations(test_name, mode, matcher, tolerance, condition, 1729 + fold)
                prediction = forecast(model, obs)
                if condition == "natural":
                    natural_predictions = prediction.copy()
                cvp, cp = calibrate(episodes[val_name], vp, prediction)
                thresholds = [select_threshold(episodes[val_name], vp[:, j], h) for j, h in enumerate(HORIZONS)]
                calibrated_thresholds = [select_threshold(episodes[val_name], cvp[:, j], h) for j, h in enumerate(HORIZONS)]
                all_results.append({"test": test_name, "validation": val_name, "train": train_names,
                                    "mode": mode, "condition": condition, "tolerance_seconds": tolerance,
                                    "scores": score(episodes[test_name], prediction, thresholds),
                                    "calibrated_scores": score(episodes[test_name], cp, calibrated_thresholds),
                                    "max_forecast_change_from_natural": float(np.max(np.abs(prediction - natural_predictions)))})
            print(f"Fold {fold + 1}/8 {test_name}: {mode} completed", flush=True)
        # Shared input direct forecast baseline: ordinary exact-dedup count bins,
        # no attack-state oracle or future features.
        xtrain, ytrain = [], []
        for name in train_names:
            obs = observations(name, "exact", matcher, 0.0)
            x = np.einsum("ncb,b->nc", obs, np.arange(5))
            mask = preonset(episodes[name])
            xtrain.append(x[mask])
            ytrain.append(np.stack([targets(episodes[name], h)[mask] for h in HORIZONS], axis=1))
        xv = np.einsum("ncb,b->nc", observations(val_name, "exact", matcher, 0.0), np.arange(5))
        direct_models = []
        vp = np.empty((len(xv), len(HORIZONS)))
        for j in range(len(HORIZONS)):
            reg = LogisticRegression(C=1.0, max_iter=1000)
            reg.fit(np.concatenate(xtrain), np.concatenate(ytrain)[:, j])
            direct_models.append(reg)
            vp[:, j] = reg.predict_proba(xv)[:, 1]
        vp = np.maximum.accumulate(vp, axis=1)
        natural_predictions = None
        for condition in conditions:
            xt = np.einsum("ncb,b->nc", observations(test_name, "exact", matcher, 0.0, condition, 1729 + fold), np.arange(5))
            prediction = np.maximum.accumulate(np.stack([reg.predict_proba(xt)[:, 1] for reg in direct_models], axis=1), axis=1)
            if condition == "natural":
                natural_predictions = prediction.copy()
            cvp, cp = calibrate(episodes[val_name], vp, prediction)
            thresholds = [select_threshold(episodes[val_name], vp[:, j], h) for j, h in enumerate(HORIZONS)]
            cthresholds = [select_threshold(episodes[val_name], cvp[:, j], h) for j, h in enumerate(HORIZONS)]
            all_results.append({"test": test_name, "validation": val_name, "train": train_names,
                                "mode": "direct_logistic", "condition": condition,
                                "scores": score(episodes[test_name], prediction, thresholds),
                                "calibrated_scores": score(episodes[test_name], cp, cthresholds),
                                "max_forecast_change_from_natural": float(np.max(np.abs(prediction - natural_predictions)))})
        (OUT / "fold_results.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    summary = summarize(all_results)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "matcher_details.json").write_text(json.dumps(matcher_details, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


def summarize(results):
    summary = {}
    for condition in ["natural", "exact_replay", "alias_jitter"]:
        summary[condition] = {}
        for mode in MODES + ["direct_logistic"]:
            rows = [r for r in results if r["condition"] == condition and r["mode"] == mode]
            entry = {}
            for score_name in ["scores", "calibrated_scores"]:
                entry[score_name] = {}
                for horizon in HORIZONS:
                    values = [r[score_name][str(horizon)] for r in rows]
                    entry[score_name][str(horizon)] = {
                        "episodes": len(values),
                        "mean_brier": float(np.mean([v["brier"] for v in values])),
                        "mean_pr_auc": float(np.mean([v["pr_auc"] for v in values])),
                        "warned_episodes": sum(v["warning_recall"] for v in values),
                        "median_lead_minutes_when_warned": None if not any(v["warning_recall"] for v in values) else float(np.median([v["lead_minutes"] for v in values if v["lead_minutes"] is not None])),
                        "false_warning_episodes": sum(v["false_warning_episodes"] for v in values),
                        "negative_exposure_hours": sum(v["negative_exposure_hours"] for v in values),
                        "negative_warning_minutes": sum(v["negative_warning_minutes"] for v in values),
                        "mean_modeled_decision_cost": float(np.mean([v["modeled_decision_cost"] for v in values]))}
            entry["max_replay_change"] = max(r["max_forecast_change_from_natural"] for r in rows)
            summary[condition][mode] = entry
    return summary


def checks():
    # Meaningful invariants: causality, identity replay, probability coherence,
    # train-only fitting and correct marginalization in the bounded prototype.
    times = np.array([60., 120., 180.])
    rows = np.array([(10., 0, 0, 1, 11, 1), (11., 0, 0, 2, 11, 2),
                     (130., 1, 1, 3, 12, 3)], dtype=DTYPE)
    episode = {"times": times, "events": rows, "truth": np.array([0, 1, 4]), "onset": 150.}
    replay = np.sort(np.concatenate([rows, rows]), order=["t", "record"])
    exact = observation_distributions(episode, rows, "exact")
    assert np.array_equal(exact, observation_distributions(episode, replay, "exact"))
    assert np.array_equal(exact[:2], observation_distributions(episode, rows[:2], "exact")[:2])
    matcher = LogisticRegression().fit([[0., 1], [1., 1], [4., 0], [5., 0]], [1, 1, 0, 0])
    soft = observation_distributions(episode, rows, "soft", matcher, 5)
    assert np.allclose(soft.sum(axis=-1), 1)
    assert np.array_equal(soft, observation_distributions(episode, replay, "soft", matcher, 5))
    assert 0 < soft[0, 0, 1] < 1 and 0 < soft[0, 0, 2] < 1
    model = fit_forecaster({"x": episode}, ["x"], {"x": exact})
    risk = forecast(model, exact)
    assert np.all((risk >= 0) & (risk <= 1))
    assert np.all(np.diff(risk, axis=1) >= -1e-12)
    assert np.allclose(model[0].sum(axis=1), 1)
    assert np.allclose(model[1].sum(axis=-1), 1)
    print("All 9 research-pilot invariants passed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "run", "checks"])
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "checks": checks}[args.command]()
