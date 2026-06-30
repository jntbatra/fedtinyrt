"""
Stage 1 — Personalization (the FedTinyRT deployment model).

A node ships with a model pre-trained on machine A, then fine-tunes on a small
slice of its OWN machine B (on-device incremental training), and runs on the
rest of B. This is exactly what on-device training + federation are for.

Reports B BEFORE adapt (zero-shot) vs AFTER adapt (personalized).
"""
import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import balanced_accuracy_score, accuracy_score, confusion_matrix, classification_report

ART = os.path.join(os.path.dirname(__file__), "artifacts")
CLASSES = ["normal", "degrading", "fault"]
BASE_FRAC = 0.20


def load(n):
    d = np.load(os.path.join(ART, n))
    return d["X"].astype(np.float32), d["y"].astype(np.int64), d["groups"].astype(np.int64)


def base_norm(X, g):
    files = np.unique(g)
    bset = set(files[: max(1, int(len(files) * BASE_FRAC))])
    m = np.array([x in bset for x in g])
    mu, sd = X[m].mean(0), X[m].std(0) + 1e-6
    return (X - mu) / sd


def mlp(d):
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(d,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(3)])
    m.compile(optimizer="adam",
              loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
              metrics=["accuracy"])
    return m


def cw(y):
    c = np.bincount(y, minlength=3)
    return {i: len(y) / (3 * v) if v else 0.0 for i, v in enumerate(c)}


def rep(tag, yt, yp):
    print(f"\n=== {tag} ===  acc={accuracy_score(yt, yp):.4f} "
          f"balanced={balanced_accuracy_score(yt, yp):.4f}")
    print(confusion_matrix(yt, yp, labels=[0, 1, 2]))
    print(classification_report(yt, yp, labels=[0, 1, 2], target_names=CLASSES,
                                digits=3, zero_division=0))


def main():
    XA, yA, gA = load("machine_A.npz")
    XB, yB, gB = load("machine_B.npz")
    XA, XB = base_norm(XA, gA), base_norm(XB, gB)

    base = mlp(XA.shape[1])
    base.fit(XA, yA, epochs=60, batch_size=64, verbose=0, class_weight=cw(yA))

    # split B: small ADAPT slice (on-device labels) vs held-out TEST
    adapt, test = next(GroupShuffleSplit(1, test_size=0.7, random_state=0).split(XB, yB, gB))
    print(f"B adapt windows={len(adapt)} (counts {np.bincount(yB[adapt], minlength=3)}), "
          f"test windows={len(test)}")

    rep("B zero-shot (no adaptation)", yB[test], base.predict(XB[test], verbose=0).argmax(1))

    # personalize: fine-tune on B adapt slice (low LR = incremental)
    base.optimizer.learning_rate.assign(3e-4)
    base.fit(XB[adapt], yB[adapt], epochs=40, batch_size=32, verbose=0, class_weight=cw(yB[adapt]))
    rep("B PERSONALIZED (after on-device fine-tune)", yB[test],
        base.predict(XB[test], verbose=0).argmax(1))


if __name__ == "__main__":
    main()
