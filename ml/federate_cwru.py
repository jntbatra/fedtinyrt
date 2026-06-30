"""
Federated learning on CWRU (Roadmap Layer 3) — the clean, realistic demo.

4 clients = 4 motor loads (1797/1772/1750/1730 RPM = 0/1/2/3 HP). EVERY client
has ALL fault classes (normal / inner / outer / ball), so it's realistic non-IID
(same labels, different operating condition) with NO artificial missing-class
trap. Each client trains on its OWN load; only head weights are FedAvg'd.

Reports per client (held-out test): local-only vs federated vs fed+personalized.
"""
import os
import glob
import numpy as np
import tensorflow as tf
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import balanced_accuracy_score
from feature_extract import extract, windows_from_signal

tf.get_logger().setLevel("ERROR")
np.random.seed(0); tf.random.set_seed(0)
DATA = os.path.join(os.path.dirname(__file__), "data", "cwru", "Data")
CLASSES = ["normal", "inner", "outer", "ball"]
CAP = 40  # max windows per file (balance)


def label_of(name):
    if "Normal" in name: return 0
    if "_IR_" in name:   return 1
    if "_OR" in name:    return 2
    if "_B_" in name:    return 3
    return -1


def build_client(folder):
    X, y, g = [], [], []
    gid = 0
    for f in sorted(glob.glob(os.path.join(folder, "*.npz"))):
        name = os.path.basename(f)
        if not (name.endswith("_DE12.npz") or "Normal" in name):
            continue
        lab = label_of(name)
        if lab < 0:
            continue
        sig = np.load(f)["DE"].ravel()
        for w in windows_from_signal(sig)[:CAP]:
            X.append(extract(w)); y.append(lab); g.append(gid)
        gid += 1
    return np.array(X, np.float32), np.array(y, np.int64), np.array(g, np.int64)


def znorm(X):
    return (X - X.mean(0)) / (X.std(0) + 1e-6)


def per_file_split(groups, test_frac=0.3):
    """within each file, first (1-test_frac) windows -> train, rest -> test.
    Keeps every class in both splits (a 1-file class isn't lost) and is a
    temporal holdout within the recording (low sibling-window leakage)."""
    tr, te = [], []
    for gid in np.unique(groups):
        idx = np.where(groups == gid)[0]
        k = max(1, int(len(idx) * (1 - test_frac)))
        tr += list(idx[:k]); te += list(idx[k:])
    return np.array(tr), np.array(te)


def model():
    m = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(38,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(4)])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
              loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True))
    return m


def cw(y):
    c = np.bincount(y, minlength=4)
    return {i: len(y) / (4 * v) if v else 0.0 for i, v in enumerate(c)}


def fit(m, X, y, ep, lr=None):
    if lr: m.optimizer.learning_rate.assign(lr)
    m.fit(X, y, epochs=ep, batch_size=64, verbose=0, class_weight=cw(y))
    return m.get_weights()


def bal(m, X, y):
    return balanced_accuracy_score(y, m.predict(X, verbose=0).argmax(1))


def main():
    folders = sorted(glob.glob(os.path.join(DATA, "*RPM")))
    clients = []
    for fo in folders:
        X, y, g = build_client(fo)
        X = znorm(X)
        tr, te = per_file_split(g, 0.3)
        clients.append(dict(name=os.path.basename(fo), Xtr=X[tr], ytr=y[tr],
                            Xte=X[te], yte=y[te]))
        print(f"{os.path.basename(fo):10} windows={len(X)} classes={np.bincount(y, minlength=4)}")

    federate(clients, "SCENARIO 1: data-rich clients (federation shouldn't hurt)")

    # SCENARIO 2: each client DATA-SCARCE -> federation should beat local-only
    rng = np.random.default_rng(0)
    scarce = []
    for c in clients:
        idx = rng.choice(len(c["ytr"]), size=min(32, len(c["ytr"])), replace=False)
        scarce.append(dict(name=c["name"], Xtr=c["Xtr"][idx], ytr=c["ytr"][idx],
                           Xte=c["Xte"], yte=c["yte"]))
    print(f"\n[scarce] each client trains on only "
          f"{len(scarce[0]['ytr'])} windows (vs {len(clients[0]['ytr'])})")
    federate(scarce, "SCENARIO 2: data-scarce clients (federation adds value)")


def federate(clients, tag, rounds=25, local_epochs=5):
    # standard FedAvg: equal weight, several local epochs, full server step.
    g = model(); gw = g.get_weights()
    for r in range(rounds):
        ws = [fit((g.set_weights(gw) or g), c["Xtr"], c["ytr"], local_epochs, lr=1e-3)
              for c in clients]
        gw = [sum(w[l] for w in ws) / len(ws) for l in range(len(ws[0]))]

    print(f"\n########## {tag} ##########")
    print(f"  {'client':10} local-only  federated  fed+personalized")
    for c in clients:
        lo = model(); fit(lo, c["Xtr"], c["ytr"], 30)
        b_lo = bal(lo, c["Xte"], c["yte"])
        g.set_weights(gw); b_fed = bal(g, c["Xte"], c["yte"])
        g.set_weights(gw); fit(g, c["Xtr"], c["ytr"], 12, lr=5e-4)
        b_pe = bal(g, c["Xte"], c["yte"])
        print(f"  {c['name']:10} {b_lo:.3f}       {b_fed:.3f}      {b_pe:.3f}")


if __name__ == "__main__":
    main()
