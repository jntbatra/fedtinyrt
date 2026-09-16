"""Sleep adaptation of legacy_bearing/train_tflite.py: MLP -> SavedModel -> INT8.

Independent subject validation/test, training-only scaling/calibration, clipped
quantization, probability metrics and versioned deployment/golden artifacts.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from .dataset import load, split_subjects
from .feature_extract import (FEATURE_NAMES, MODALITIES, SCHEMA, MODALITY_FEATURES,
                              fit_scaler, normalize, modality_dropout)
from .metrics import evaluate


def quantize(x, scale, zero):
    if scale <= 0 or not np.isfinite(scale) or not -128 <= zero <= 127:
        raise ValueError("Invalid INT8 quantization parameters")
    if not np.isfinite(x).all():
        raise ValueError("Cannot quantize non-finite input")
    # Saturate BEFORE casting (legacy export could wrap out-of-range values).
    return np.clip(np.rint(np.asarray(x)/scale + zero), -128, 127).astype(np.int8)


def build_model(dim):
    import tensorflow as tf
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(dim,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid")])
    model.compile(optimizer="adam", loss="binary_crossentropy")
    return model


def fit(model, x, y, epochs, validation=None):
    # Explicit batches avoid a per-epoch tf.data threadpool on constrained hosts.
    counts = np.bincount(y, minlength=2)
    weights = np.asarray([len(y)/(2*counts[v]) for v in y], np.float32)
    rng = np.random.default_rng(42)
    for _ in range(epochs):
        order = rng.permutation(len(y))
        for start in range(0, len(y), 64):
            rows = order[start:start+64]
            model.train_on_batch(x[rows], y[rows], sample_weight=weights[rows])
    if validation is not None:
        return evaluate(validation[1], predict(model, validation[0]))


def predict(model, x):
    return np.concatenate([np.asarray(model(x[i:i+256], training=False)).reshape(-1)
                           for i in range(0, len(x), 256)])


def emit_c(directory, blob, mean, std):
    """Retains the existing C model/scaler export, with sleep-specific symbols."""
    header = ("#ifndef SLEEP_MODEL_DATA_H\n#define SLEEP_MODEL_DATA_H\n"
              f"#define SLEEP_MODEL_N_FEATURES {len(mean)}\n"
              "extern const unsigned char g_sleep_model_int8[];\n"
              "extern const unsigned int g_sleep_model_int8_len;\n"
              "extern const float g_sleep_feat_mean[SLEEP_MODEL_N_FEATURES];\n"
              "extern const float g_sleep_feat_std[SLEEP_MODEL_N_FEATURES];\n#endif\n")
    lines = ['#include "model_data.h"', '#if defined(__GNUC__)\n__attribute__((aligned(16)))\n#endif',
             'const unsigned char g_sleep_model_int8[] = {']
    lines += ["  " + ",".join(f"0x{b:02x}" for b in blob[i:i+12]) + "," for i in range(0, len(blob), 12)]
    lines += ["};", f"const unsigned int g_sleep_model_int8_len = {len(blob)};"]
    for name, values in (("mean", mean), ("std", std)):
        lines += [f"const float g_sleep_feat_{name}[] = {{" + ",".join(f"{float(v):.9e}f" for v in values) + "};"]
    (directory/"model_data.h").write_text(header, encoding="utf-8")
    (directory/"model_data.c").write_text("\n".join(lines)+"\n", encoding="utf-8")


def run(dataset, output, epochs=20, seed=42, allow_synthetic=False):
    import tensorflow as tf
    if epochs < 1:
        raise ValueError("epochs must be positive")
    tf.keras.utils.set_random_seed(seed)
    x, y, subjects, metadata = load(dataset)
    if metadata["synthetic"] and not allow_synthetic:
        raise ValueError("Synthetic fixture: pass --allow-synthetic for software testing only")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    parts = split_subjects(y, subjects, seed)
    tr, va, te = (parts[n] for n in ("train", "validation", "test"))
    mean, std = fit_scaler(x[tr])
    z = normalize(x, mean, std)
    augmented = modality_dropout(z[tr], np.random.default_rng(seed))
    train_x, train_y = np.concatenate((z[tr], augmented)), np.tile(y[tr], 2)
    model = build_model(x.shape[1])
    validation = fit(model, train_x, train_y, epochs, (z[va], y[va]))
    float_scores = predict(model, z[te])
    model.export(str(output/"saved_model"))
    conv = tf.lite.TFLiteConverter.from_saved_model(str(output/"saved_model"))
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    rep = np.random.default_rng(seed).permutation(len(train_x))[:300]
    conv.representative_dataset = lambda: ([train_x[i:i+1]] for i in rep)
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    blob = conv.convert()
    (output/"model_int8.tflite").write_bytes(blob)
    interp = tf.lite.Interpreter(model_content=blob)
    interp.allocate_tensors()
    inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
    si, zi = inp["quantization"]
    so, zo = out["quantization"]

    def infer(row):
        q = quantize(row, si, zi)
        interp.set_tensor(inp["index"], q.reshape(inp["shape"]))
        interp.invoke()
        result = interp.get_tensor(out["index"])[0]
        return q, result, float((int(result[0])-zo)*so)

    scores = np.asarray([infer(row)[2] for row in z[te]])
    # Include explicit missing-modality and low-quality cases as software probes.
    cases = [(f"heldout-{i}", x[i], int(y[i])) for i in te[:20]]
    for label in (0, 1):
        i = te[np.flatnonzero(y[te] == label)[0]]
        cases.append(("normal" if label == 0 else "event", x[i], label))
    closest = te[np.argmin(np.abs(scores-.5))]
    cases.append(("closest-to-threshold", x[closest], int(y[closest])))
    for m in (0, 3):
        probe = x[te[0]].copy()
        probe[list(MODALITY_FEATURES[m])] = 0
        probe[14+m] = 0
        cases.append(("low-quality-spo2" if m == 0 else "missing-audio", probe, None))
    golden = []
    for name, raw, label in cases:
        row = normalize(raw[None], mean, std)[0]
        q, result, score = infer(row)
        golden.append({"case": name, "features": raw.tolist(), "feat_norm": row.tolist(),
                       "in_int8": q.tolist(), "out_int8": result.tolist(), "event_probability": score,
                       "expected_class": int(score >= .5), "label": label,
                       "quality_status": "UNCERTAIN" if not raw[14:16].all() else "MODEL_ELIGIBLE"})
    metrics = {"validation_float": validation, "test_float": evaluate(y[te], float_scores),
               "test_int8": evaluate(y[te], scores),
               "per_subject_int8": {s: evaluate(y[te][subjects[te] == s], scores[subjects[te] == s]) for s in np.unique(subjects[te])}}
    metrics["quantization_auprc_change"] = metrics["test_int8"]["auprc_average_precision"]-metrics["test_float"]["auprc_average_precision"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    metadata.update(model_name="fedtinyrt_sleep_v1", model_version="0.1.0", schema=SCHEMA,
                    feature_names=list(FEATURE_NAMES), modalities=list(MODALITIES), quantization="int8",
                    input_shape=inp["shape"].tolist(), input_scale=si, input_zero_point=zi,
                    output_scale=so, output_zero_point=zo, threshold=.5, seed=seed,
                    model_bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
                    created_at=datetime.now(timezone.utc).isoformat(), git_commit=commit.stdout.strip(),
                    tensorflow_version=tf.__version__, board_verified=False,
                    purpose="synthetic software test only" if metadata["synthetic"] else "research screening experiment")
    preprocessing = {"schema": SCHEMA, "feature_names": list(FEATURE_NAMES), "mean": mean.tolist(),
                     "std": std.tolist(), "missing_policy": "zero normalized modality features; preserve masks",
                     "baseline_policy": "independent stable pre-session calibration; never event labels",
                     "minimum_quality": .5, "minimum_coverage": .8}
    for filename, content in (("metadata.json", metadata), ("metrics.json", metrics),
                              ("preprocessing.json", preprocessing),
                              ("splits.json", {n: sorted(np.unique(subjects[v]).tolist()) for n, v in parts.items()}),
                              ("golden_vectors.json", {"metadata": metadata, "output_tolerance_lsb": 1, "vectors": golden})):
        (output/filename).write_text(json.dumps(content, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    np.savez(output/"scaler.npz", mean=mean, std=std)
    emit_c(output, blob, mean, std)
    return metadata, metrics


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("ml/sleep/artifacts"))
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--allow-synthetic", action="store_true")
    args = p.parse_args()
    metadata, metrics = run(args.data, args.output, args.epochs, allow_synthetic=args.allow_synthetic)
    print(json.dumps({"purpose": metadata["purpose"], "metrics": metrics}, indent=2))
