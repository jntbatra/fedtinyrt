"""
Federated learning simulation (Roadmap Layer 3).

Nodes = real distinct machines (A=2nd_test, B=3rd_test). Each node trains a head
on ITS OWN data (raw vibration never leaves the node); only head weights are
averaged (FedAvg). Then each node does a few LOCAL personalization steps.

Reports per node, on held-out test:
  - local-only            (no sharing)
  - federated (FedAvg)    (shared global head)
  - federated+personalized(global head + local fine-tune)  <- deployment

Also a DATA-POOR scenario: a node with very little local data — shows federation
lifts it using the other node's knowledge (the point of federation).
"""
import os
import numpy as np
import tensorflow as tf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import balanced_accuracy_score, confusion_matrix

tf.get_logger().setLevel("ERROR")
ART = os.path.join(os.path.dirname(__file__), "artifacts")
BASE_FRAC = 0.20
np.random.seed(0)
tf.random.set_seed(0)


def load(n):
    d = np.load(os.path.join(ART, n))
    return d["X"].astype(np.float32), d["y"].astype(np.int64), d["groups"].astype(np.int64)


def base_norm(X, g):
    files = np.unique(g)
    bset = set(files[: max(1, int(len(files) * BASE_FRAC))])
    m = np.array([x in bset for x in g])
    mu, sd = X[m].mean(0), X[m].std(0) + 1e-6
    return (X - mu) / sd


def split(X, y, g, test=0.3, seed=0):
    tr, te = next(GroupShuffleSplit(1, test_size=test, random_state=seed).split(X, y, g))
    return tr, te


def head(d):
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(d,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(3)])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True))
    return m


def cw(y):
    c = np.bincount(y, minlength=3)
    return {i: len(y) / (3 * v) if v else 0.0 for i, v in enumerate(c)}


def local_fit(m, X, y, epochs, lr=None):
    if lr:
        m.optimizer.learning_rate.assign(lr)
    m.fit(X, y, epochs=epochs, batch_size=64, verbose=0, class_weight=cw(y))
    return m.get_weights()


def fedavg(weights, ns):
    tot = float(sum(ns))
    return [sum(w[l] * (n / tot) for w, n in zip(weights, ns))
            for l in range(len(weights[0]))]


def bal(m, X, y):
    return balanced_accuracy_score(y, m.predict(X, verbose=0).argmax(1))


def fault_recall(m, X, y):
    p = m.predict(X, verbose=0).argmax(1)
    cm = confusion_matrix(y, p, labels=[0, 1, 2])
    tot = cm[2].sum()
    return cm[2, 2] / tot if tot else float("nan")


def run(nodes, rounds=20, local_epochs=1, server_lr=0.7, tag=""):
    """nodes: list of dicts {name, Xtr,ytr, Xte,yte}"""
    dim = nodes[0]["Xtr"].shape[1]
    g = head(dim)
    glob = g.get_weights()

    # FedAvg rounds. EQUAL weight per node (a large fault-blind client can't
    # dominate), 1 local epoch + server-side damping (server_lr<1) so no single
    # client can yank the global far in one round -> rare-class knowledge from
    # one node survives aggregation (FedProx-style robustness to non-IID).
    for r in range(rounds):
        ws = []
        for nd in nodes:
            g.set_weights(glob)
            ws.append(local_fit(g, nd["Xtr"], nd["ytr"], local_epochs, lr=5e-4))
        avg = fedavg(ws, [1] * len(nodes))
        glob = [w + server_lr * (a - w) for w, a in zip(glob, avg)]

    print(f"\n########## {tag} ##########")
    print(f"  {'node':16} {'method':18} balanced  fault-recall")
    for nd in nodes:
        def show(name, m):
            print(f"  {nd['name']:16} {name:18} {bal(m, nd['Xte'], nd['yte']):.3f}     "
                  f"{fault_recall(m, nd['Xte'], nd['yte']):.3f}")
        # local-only baseline
        lo = head(dim); local_fit(lo, nd["Xtr"], nd["ytr"], rounds * local_epochs)
        show("local-only", lo)
        # federated global (shared head, no local fine-tune)
        g.set_weights(glob); show("federated", g)
        # federated + gentle local personalization
        g.set_weights(glob); local_fit(g, nd["Xtr"], nd["ytr"], 6, lr=2e-4)
        show("fed+personalized", g)


def main():
    XA, yA, gA = load("machine_A.npz"); XA = base_norm(XA, gA)
    XB, yB, gB = load("machine_B.npz"); XB = base_norm(XB, gB)
    trA, teA = split(XA, yA, gA)
    trB, teB = split(XB, yB, gB)

    # --- Scenario 1: two full machine-nodes ---
    nodes = [
        dict(name="A(2nd_test)", Xtr=XA[trA], ytr=yA[trA], Xte=XA[teA], yte=yA[teA]),
        dict(name="B(3rd_test)", Xtr=XB[trB], ytr=yB[trB], Xte=XB[teB], yte=yB[teB]),
    ]
    run(nodes, tag="Scenario 1: two full nodes")

    # --- Scenario 2: node B has NEVER locally seen a fault ---
    # keep only B's healthy/degrading windows for training (no fault class).
    # Its TEST set still contains faults -> can it flag a failure mode it never
    # locally experienced? Only federation (peer A knows faults) can provide that.
    keep = trB[yB[trB] != 2]
    nodes2 = [
        dict(name="A(has faults)", Xtr=XA[trA], ytr=yA[trA], Xte=XA[teA], yte=yA[teA]),
        dict(name="B(fault-unseen)", Xtr=XB[keep], ytr=yB[keep], Xte=XB[teB], yte=yB[teB]),
    ]
    print(f"\n[fault-unseen B] train counts={np.bincount(yB[keep], minlength=3)} "
          f"(no fault in local data); test has {np.sum(yB[teB]==2)} fault windows")
    run(nodes2, tag="Scenario 2: federation teaches B a failure mode it never saw")


if __name__ == "__main__":
    main()
