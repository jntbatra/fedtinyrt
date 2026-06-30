"""
Build features for TWO different machines (run-to-failures) with physically
grounded labels, for a cross-machine generalization test.

Fixes the three caveats of the time-% labeling:
  1. Labels from a HEALTH INDICATOR with principled thresholds, not arbitrary %:
       - degrading onset = HI exceeds baseline mean + 3*sigma (statistical anomaly)
       - fault onset     = HI exceeds 2x baseline mean (vibration energy doubled)
     plus MONOTONIC enforcement (bearing damage never heals -> state can't decrease),
     which also absorbs noisy dips.
  2. Two machines: train on A (2nd_test), TEST on B (3rd_test) -> real generalization.
  3. Corrupt files filtered (near-zero / non-finite RMS = sensor dropout).

Output: artifacts/machine_A.npz, artifacts/machine_B.npz  (X, y, groups)
"""
import os
import glob
import numpy as np
from feature_extract import extract, windows_from_signal

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data", "data" if False else "extracted")
ART = os.path.join(HERE, "artifacts")

BASELINE_FRAC = 0.20   # first 20% of life = healthy reference
SIGMA_K = 3.0          # degrading onset = mu + 3*sigma
FAULT_MULT = 2.0       # fault onset = 2x baseline mean RMS


def list_files(test_root):
    """deepest dir with the most timestamp files, sorted chronologically."""
    best, best_n = None, 0
    for d, _, files in os.walk(test_root):
        cnt = sum(1 for f in files
                  if len(f.split(".")) >= 5 and all(p.isdigit() for p in f.split(".")))
        if cnt > best_n:
            best, best_n = d, cnt
    files = sorted(f for f in glob.glob(os.path.join(best, "*")) if os.path.isfile(f))
    return files


def pick_failing_channel(files, ncols):
    """failing bearing = channel whose end-of-life RMS rises most vs start."""
    head = files[: max(1, len(files) // 10)]
    tail = files[-max(1, len(files) // 10):]
    def rms_cols(fs):
        acc = np.zeros(ncols)
        for f in fs:
            a = np.loadtxt(f)
            acc += np.sqrt((a ** 2).mean(axis=0))
        return acc / len(fs)
    ratio = rms_cols(tail) / (rms_cols(head) + 1e-9)
    col = int(np.argmax(ratio))
    print(f"  failing channel = col {col} (end/start RMS ratio {ratio[col]:.1f})")
    return col


def build(test_root, col=None, name=""):
    files = list_files(test_root)
    a0 = np.loadtxt(files[0])
    ncols = a0.shape[1] if a0.ndim > 1 else 1
    if col is None:
        col = pick_failing_channel(files, ncols)
    print(f"[{name}] {len(files)} files, channel {col}")

    # pass 1: health indicator (RMS) per file, drop corrupt.
    # store only the scalar HI + path (NOT the raw signal) to avoid OOM on 6k files.
    hi, kept = [], []
    for f in files:
        a = np.loadtxt(f)
        sig = a[:, col] if a.ndim > 1 else a
        r = np.sqrt(np.mean(sig * sig))
        if not np.isfinite(r) or r < 1e-3:      # dropout / corrupt
            continue
        hi.append(r); kept.append(f)
    hi = np.array(hi)
    nb = max(1, int(len(hi) * BASELINE_FRAC))
    mu, sd = hi[:nb].mean(), hi[:nb].std()
    t_degr = mu + SIGMA_K * sd
    t_fault = FAULT_MULT * mu
    if t_fault <= t_degr:                         # keep ordering sane
        t_fault = max(t_fault, t_degr * 1.3)
    print(f"  baseline mu={mu:.4f} sd={sd:.4f} | t_degr={t_degr:.4f} t_fault={t_fault:.4f} "
          f"| dropped {len(files)-len(kept)} corrupt")

    # pass 2: monotonic labels + features (re-read files, no big RAM hold)
    X, y, groups = [], [], []
    state = 0
    for gi, (f, r) in enumerate(zip(kept, hi)):
        s = 2 if r >= t_fault else (1 if r >= t_degr else 0)
        state = max(state, s)                     # damage never heals
        a = np.loadtxt(f)
        sig = a[:, col] if a.ndim > 1 else a
        for w in windows_from_signal(sig):
            X.append(extract(w)); y.append(state); groups.append(gi)
    X = np.array(X, np.float32); y = np.array(y, np.int64); groups = np.array(groups, np.int64)
    print(f"  class counts = {np.bincount(y, minlength=3)}")
    return X, y, groups


def main():
    os.makedirs(ART, exist_ok=True)
    XA, yA, gA = build(os.path.join(DATA, "2nd_test"), col=0, name="A=2nd_test b1")
    np.savez(os.path.join(ART, "machine_A.npz"), X=XA, y=yA, groups=gA)
    XB, yB, gB = build(os.path.join(DATA, "3rd_test"), col=None, name="B=3rd_test")
    np.savez(os.path.join(ART, "machine_B.npz"), X=XB, y=yB, groups=gB)
    print("saved machine_A.npz, machine_B.npz")


if __name__ == "__main__":
    main()
