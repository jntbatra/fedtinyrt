"""
Train the FedTinyRT classifier head on extracted features, quantize to INT8,
export a .tflite model + golden validation vectors + C arrays for the firmware.

Input:  ml/artifacts/dataset.npz  (X float32 [N,F], y int [N], classes [3])
Output: ml/artifacts/
          model_int8.tflite        - the device model (Vela + TFLite-Micro input)
          scaler.npz               - feature mean/std (device must apply these)
          golden_vectors.json      - input->expected output for on-device tests
          model_data.c / .h        - tflite as a C byte array (baked into firmware)

Run:  py ml/train_tflite.py
"""

import json
import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, classification_report)

ART = os.path.join(os.path.dirname(__file__), "artifacts")
CLASSES = ["normal", "degrading", "fault"]


def load():
    d = np.load(os.path.join(ART, "dataset.npz"), allow_pickle=True)
    return (d["X"].astype(np.float32), d["y"].astype(np.int64),
            d["groups"].astype(np.int64))


def main():
    X, y, groups = load()
    print(f"dataset: {X.shape[0]} samples, {X.shape[1]} features, "
          f"class counts={np.bincount(y)}")

    # split by FILE (group), so no window's siblings straddle train/test
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    tr, te = next(gss.split(X, y, groups))
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
    print(f"train files={len(np.unique(groups[tr]))} "
          f"test files={len(np.unique(groups[te]))}; "
          f"test class counts={np.bincount(yte)}")

    # --- standardize (device replays these exact mean/std) ---
    mu = Xtr.mean(axis=0)
    sd = Xtr.std(axis=0) + 1e-6
    Xtr_n = (Xtr - mu) / sd
    Xte_n = (Xte - mu) / sd
    np.savez(os.path.join(ART, "scaler.npz"), mean=mu, std=sd)

    # --- model: frozen-ish small head, INT8-friendly ---
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(X.shape[1],)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(len(CLASSES)),  # logits
    ])
    model.compile(
        optimizer="adam",
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"])
    # class weights — fault is rare (~2%), so weight it up or it gets ignored
    counts = np.bincount(ytr)
    cw = {i: len(ytr) / (len(counts) * c) for i, c in enumerate(counts)}
    print("class weights:", {k: round(v, 2) for k, v in cw.items()})
    model.fit(Xtr_n, ytr, validation_data=(Xte_n, yte),
              epochs=60, batch_size=64, verbose=2, class_weight=cw)

    # --- float accuracy (report BALANCED acc + per-class, given imbalance) ---
    pf = model.predict(Xte_n, verbose=0).argmax(1)
    print(f"\nfloat32 acc={accuracy_score(yte, pf):.4f} "
          f"balanced={balanced_accuracy_score(yte, pf):.4f}")

    # --- INT8 full-integer quantization ---
    def rep_data():
        for i in range(min(300, len(Xtr_n))):
            yield [Xtr_n[i:i + 1].astype(np.float32)]

    # Keras 3 + TF 2.16 crashes on from_keras_model INT8; go via SavedModel.
    sm_dir = os.path.join(ART, "saved_model")
    model.export(sm_dir)
    conv = tf.lite.TFLiteConverter.from_saved_model(sm_dir)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep_data
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    tfl = conv.convert()
    with open(os.path.join(ART, "model_int8.tflite"), "wb") as f:
        f.write(tfl)

    # --- evaluate the quantized model + build golden vectors ---
    interp = tf.lite.Interpreter(model_content=tfl)
    interp.allocate_tensors()
    inp = interp.get_input_details()[0]
    out = interp.get_output_details()[0]
    in_scale, in_zp = inp["quantization"]
    out_scale, out_zp = out["quantization"]

    def infer_int8(xn):
        q = np.round(xn / in_scale + in_zp).astype(np.int8)
        interp.set_tensor(inp["index"], q.reshape(inp["shape"]))
        interp.invoke()
        return interp.get_tensor(out["index"])[0]  # int8 logits

    preds, golden = [], []
    for i in range(len(Xte_n)):
        o = infer_int8(Xte_n[i])
        preds.append(int(np.argmax(o)))
        if i < 20:  # 20 golden vectors for device validation
            golden.append({
                "feat_norm": [round(float(v), 6) for v in Xte_n[i]],
                "in_int8": [int(np.round(v / in_scale + in_zp)) for v in Xte_n[i]],
                "out_int8": [int(v) for v in o],
                "label": int(yte[i]),
                "pred": int(np.argmax(o)),
            })
    print(f"\nINT8 acc={accuracy_score(yte, preds):.4f} "
          f"balanced={balanced_accuracy_score(yte, preds):.4f}")
    print("confusion (int8) rows=true [normal,degrading,fault]:\n",
          confusion_matrix(yte, preds))
    print(classification_report(yte, preds, target_names=CLASSES, digits=3))

    json.dump({
        "in_scale": float(in_scale), "in_zero_point": int(in_zp),
        "out_scale": float(out_scale), "out_zero_point": int(out_zp),
        "classes": CLASSES, "vectors": golden,
    }, open(os.path.join(ART, "golden_vectors.json"), "w"), indent=2)

    # --- C array for the firmware ---
    emit_c(tfl, mu, sd)
    print("\nartifacts written to", ART)


def emit_c(tfl, mu, sd):
    h = "#ifndef MODEL_DATA_H\n#define MODEL_DATA_H\n#include <stdint.h>\n"
    h += f"#define MODEL_N_FEATURES {len(mu)}\n"
    h += "extern const unsigned char g_model_int8[];\n"
    h += "extern const unsigned int g_model_int8_len;\n"
    h += "extern const float g_feat_mean[MODEL_N_FEATURES];\n"
    h += "extern const float g_feat_std[MODEL_N_FEATURES];\n#endif\n"
    open(os.path.join(ART, "model_data.h"), "w").write(h)

    c = '#include "model_data.h"\n'
    c += "const unsigned char g_model_int8[] = {\n"
    for i in range(0, len(tfl), 12):
        c += "  " + ",".join(f"0x{b:02x}" for b in tfl[i:i + 12]) + ",\n"
    c += "};\n"
    c += f"const unsigned int g_model_int8_len = {len(tfl)};\n"
    c += "const float g_feat_mean[] = {" + ",".join(f"{v:.8f}f" for v in mu) + "};\n"
    c += "const float g_feat_std[]  = {" + ",".join(f"{v:.8f}f" for v in sd) + "};\n"
    open(os.path.join(ART, "model_data.c"), "w").write(c)


if __name__ == "__main__":
    main()
