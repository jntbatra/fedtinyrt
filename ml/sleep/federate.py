"""Adapted PC FedAvg: disjoint subjects, fresh local optimizers, checked updates.

In-process simulation only: it is not a network or hardware privacy boundary.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from .dataset import load, split_subjects, partition_sites
from .feature_extract import fit_scaler, normalize, modality_dropout
from .metrics import evaluate
from .train_tflite import build_model, fit, predict


def fedavg(payloads, shapes, round_id, version="sleep-v1", max_norm=1e4):
    if not payloads:
        raise ValueError("Empty federation round")
    seen = set()
    for p in payloads:
        if (p["round_id"] != round_id or p["model_version"] != version or p["client_id"] in seen
                or type(p["sample_count"]) is not int or p["sample_count"] <= 0
                or len(p["shared_weights"]) != len(shapes)):
            raise ValueError("Invalid/stale/duplicate federation payload")
        seen.add(p["client_id"])
        for w, shape in zip(p["shared_weights"], shapes):
            if w.shape != shape or not np.isfinite(w).all() or np.linalg.norm(w.astype(float)) > max_norm:
                raise ValueError("Invalid weight shape, finite values or norm")
    total = sum(p["sample_count"] for p in payloads)
    return [sum(p["shared_weights"][i].astype(np.float64)*(p["sample_count"]/total) for p in payloads).astype(np.float32)
            for i in range(len(shapes))]


def run(dataset, output, sites=3, rounds=3, local_epochs=1, allow_synthetic=False):
    import tensorflow as tf
    tf.keras.utils.set_random_seed(42)
    if rounds < 1 or local_epochs < 1:
        raise ValueError("Positive round/epoch counts required")
    x, y, subjects, metadata = load(dataset)
    if metadata["synthetic"] and not allow_synthetic:
        raise ValueError("Pass --allow-synthetic for a software smoke test")
    nodes, partitions = [], []
    for site, rows in enumerate(partition_sites(subjects, sites)):
        part = split_subjects(y[rows], subjects[rows])
        nodes.append({n: rows[r] for n, r in part.items()})
        partitions.append({n: sorted(np.unique(subjects[rows[r]]).tolist()) for n, r in part.items()})
    # Shared coordinate system uses a designated reference site's training only.
    # These scaler constants are development configuration, not federated updates.
    mean, std = fit_scaler(x[nodes[0]["train"]])
    z = normalize(x, mean, std)
    global_model = build_model(z.shape[1])
    initial = global_model.get_weights()
    weights = initial
    history = []
    for r in range(rounds):
        payloads = []
        for site, node in enumerate(nodes):
            local = build_model(z.shape[1])  # no optimizer state crossing clients
            local.set_weights(weights)
            tr = node["train"]
            augmented = modality_dropout(z[tr], np.random.default_rng(42+r+site))
            fit(local, np.concatenate((z[tr], augmented)), np.tile(y[tr], 2), local_epochs)
            payloads.append(dict(round_id=r, client_id=f"site-{site}", model_version="sleep-v1",
                                 sample_count=len(tr), shared_weights=local.get_weights()))
        weights = fedavg(payloads, [w.shape for w in initial], r)
        global_model.set_weights(weights)
        history.append({f"site-{i}": evaluate(y[n["validation"]], predict(global_model, z[n["validation"]]))
                        for i, n in enumerate(nodes)})
    results = {}
    for site, node in enumerate(nodes):
        tr, te = node["train"], node["test"]
        local = build_model(z.shape[1]); local.set_weights(initial)
        fit(local, z[tr], y[tr], rounds*local_epochs)
        personal = build_model(z.shape[1]); personal.set_weights(weights)
        fit(personal, z[tr], y[tr], local_epochs)
        results[f"site-{site}"] = {name: evaluate(y[te], predict(m, z[te])) for name, m in
                                   (("local_only", local), ("federated", global_model), ("personalized", personal))}
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    report = {"dataset": metadata, "partitions": partitions, "validation_rounds": history,
              "test": results, "leave_one_site_out": "not implemented", "transport": "in-process weights only",
              "scaler_source": "site-0 training subjects; frozen development configuration"}
    (output/"federation.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    np.savez(output/"global_weights.npz", **{f"tensor_{i}": w for i, w in enumerate(weights)})
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("ml/sleep/artifacts"))
    p.add_argument("--sites", type=int, default=3)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--allow-synthetic", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.data, a.output, a.sites, a.rounds, allow_synthetic=a.allow_synthetic)["test"], indent=2))
