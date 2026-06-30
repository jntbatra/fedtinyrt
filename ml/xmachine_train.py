"""
Cross-machine test: train on machine A (2nd_test), evaluate on a DIFFERENT
machine B (3rd_test). This is the honest generalization number — the model has
never seen machine B's data or baseline.

Reports BOTH:
  - A held-out (same-machine, grouped split)  -> upper bound
  - B full set (cross-machine)                -> the real number
"""
import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             confusion_matrix, classification_report)

ART = os.path.join(os.path.dirname(__file__), "artifacts")
CLASSES = ["normal", "degrading", "fault"]


def load(n):
    d = np.load(os.path.join(ART, n))
    return d["X"].astype(np.float32), d["y"].astype(np.int64), d["groups"].astype(np.int64)


def report(tag, ytrue, ypred):
    print(f"\n=== {tag} ===")
    print(f"acc={accuracy_score(ytrue, ypred):.4f} "
          f"balanced={balanced_accuracy_score(ytrue, ypred):.4f}")
    print("confusion rows=true [normal,degrading,fault]:\n",
          confusion_matrix(ytrue, ypred, labels=[0, 1, 2]))
    print(classification_report(ytrue, ypred, labels=[0, 1, 2],
                                target_names=CLASSES, digits=3, zero_division=0))


def main():
    XA, yA, gA = load("machine_A.npz")
    XB, yB, gB = load("machine_B.npz")
    print(f"A: {XA.shape} counts {np.bincount(yA, minlength=3)}")
    print(f"B: {XB.shape} counts {np.bincount(yB, minlength=3)}")

    # grouped split inside A for a same-machine reference
    tr, va = next(GroupShuffleSplit(1, test_size=0.2, random_state=42).split(XA, yA, gA))
    Xtr, ytr = XA[tr], yA[tr]
    Xva, yva = XA[va], yA[va]

    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    Z = lambda X: (X - mu) / sd

    counts = np.bincount(ytr, minlength=3)
    cw = {i: len(ytr) / (3 * c) if c else 0.0 for i, c in enumerate(counts)}
    print("class weights:", {k: round(v, 2) for k, v in cw.items()})

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(XA.shape[1],)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(3),
    ])
    model.compile(optimizer="adam",
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                  metrics=["accuracy"])
    model.fit(Z(Xtr), ytr, validation_data=(Z(Xva), yva),
              epochs=60, batch_size=64, verbose=0, class_weight=cw)

    report("A held-out (same machine, upper bound)", yva, model.predict(Z(Xva), verbose=0).argmax(1))
    report("B full (CROSS-MACHINE, the real number)", yB, model.predict(Z(XB), verbose=0).argmax(1))


if __name__ == "__main__":
    main()
