"""
Cross-machine test WITH per-machine baseline normalization.

Each machine calibrates on its OWN healthy startup data (first 20% of life =
normal) and standardizes its features by that baseline (mu/sd). This makes
features RELATIVE to each machine, so "1.5x baseline" means the same thing on
any machine -> the model should transfer. On-device this is a one-time
calibration phase at install (assume the machine is healthy at first boot).

Compare against xmachine_train.py (absolute features, which failed at ~52%).
"""
import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, classification_report)

ART = os.path.join(os.path.dirname(__file__), "artifacts")
CLASSES = ["normal", "degrading", "fault"]
BASE_FRAC = 0.20


def load(n):
    d = np.load(os.path.join(ART, n))
    return d["X"].astype(np.float32), d["y"].astype(np.int64), d["groups"].astype(np.int64)


def baseline_norm(X, groups):
    """standardize by the machine's own healthy baseline (first 20% of files)."""
    files = np.unique(groups)
    base_files = set(files[: max(1, int(len(files) * BASE_FRAC))])
    mask = np.array([g in base_files for g in groups])
    mu, sd = X[mask].mean(0), X[mask].std(0) + 1e-6
    return (X - mu) / sd


def report(tag, yt, yp):
    print(f"\n=== {tag} ===")
    print(f"acc={accuracy_score(yt, yp):.4f} balanced={balanced_accuracy_score(yt, yp):.4f}")
    print("confusion rows=true:\n", confusion_matrix(yt, yp, labels=[0, 1, 2]))
    print(classification_report(yt, yp, labels=[0, 1, 2],
                                target_names=CLASSES, digits=3, zero_division=0))


def main():
    XA, yA, gA = load("machine_A.npz")
    XB, yB, gB = load("machine_B.npz")
    XA = baseline_norm(XA, gA)            # each machine normalized by ITS OWN baseline
    XB = baseline_norm(XB, gB)

    tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=42).split(XA, yA, gA))
    counts = np.bincount(yA[tr], minlength=3)
    cw = {i: len(yA[tr]) / (3 * c) if c else 0.0 for i, c in enumerate(counts)}

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(XA.shape[1],)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(3),
    ])
    model.compile(optimizer="adam",
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                  metrics=["accuracy"])
    model.fit(XA[tr], yA[tr], epochs=60, batch_size=64, verbose=0, class_weight=cw)

    report("A held-out (same machine)", yA[va], model.predict(XA[va], verbose=0).argmax(1))
    report("B CROSS-MACHINE (baseline-normalized)", yB, model.predict(XB, verbose=0).argmax(1))


if __name__ == "__main__":
    main()
