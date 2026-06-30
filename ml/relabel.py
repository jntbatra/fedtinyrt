"""
Relabel machine_A / machine_B from their saved features (fast, no raw re-read).
Uses RELATIVE health-indicator thresholds so labels are comparable across
machines with different baseline amplitudes:
    degrading: HI >= max(1.2*baseline, baseline+3sigma)
    fault:     HI >= 1.5*baseline
plus monotonic enforcement (damage never heals).
RMS is feature column 32 (after 32 FFT bands).
"""
import os
import numpy as np

ART = os.path.join(os.path.dirname(__file__), "artifacts")
RMS = 32
BASE_FRAC = 0.20
DEGR_X, FAULT_X = 1.2, 1.5


def relabel(fn):
    d = np.load(os.path.join(ART, fn))
    X, groups = d["X"], d["groups"].astype(int)
    files = np.unique(groups)
    hi = np.array([X[groups == g, RMS].mean() for g in files])  # per-file HI
    nb = max(1, int(len(hi) * BASE_FRAC))
    mu, sd = hi[:nb].mean(), hi[:nb].std()
    t_d = max(DEGR_X * mu, mu + 3 * sd)
    t_f = FAULT_X * mu
    # per-file monotonic state
    state, file_lab = 0, {}
    for g, r in zip(files, hi):
        s = 2 if r >= t_f else (1 if r >= t_d else 0)
        state = max(state, s)
        file_lab[g] = state
    y = np.array([file_lab[g] for g in groups], dtype=np.int64)
    np.savez(os.path.join(ART, fn), X=X, y=y, groups=d["groups"])
    print(f"{fn}: mu={mu:.4f} t_degr={t_d:.4f} t_fault={t_f:.4f} "
          f"-> counts {np.bincount(y, minlength=3)}")


relabel("machine_A.npz")
relabel("machine_B.npz")
