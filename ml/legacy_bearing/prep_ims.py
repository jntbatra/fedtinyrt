"""
Prepare the NASA IMS bearing dataset into (features, labels) for training.

IMS = run-to-failure vibration. We use one bearing's channel, walk the files in
chronological order, and derive normal/degrading/fault labels from how far the
vibration energy (RMS) has risen above the healthy baseline. Then each file is
split into windows and turned into feature vectors (feature_extract.extract).

Run:  py ml/prep_ims.py
Output: ml/artifacts/dataset.npz  (X, y, classes)
"""

import os
import glob
import numpy as np

from feature_extract import extract, windows_from_signal

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")  # preserve existing downloads
ART = os.path.join(HERE, "artifacts")

# IMS channel layout: 2nd_test has 4 cols (1 per bearing); bearing 1 = col 0.
# 1st_test has 8 cols (2 per bearing); bearing 1 = col 0.
BEARING_COL = 0

# Time-based labels (independent of the vibration features -> no label leakage).
# The run ends at failure; label by position in the run-to-failure timeline.
#   normal:    first part of life
#   degrading: middle
#   fault:     final stretch before failure
FAULT_FRAC = 0.90      # last 10% of timeline = fault
DEGRADE_FRAC = 0.70    # 70%-90% = degrading; before = normal


def find_test_dir(root):
    """Find the folder of timestamp-named ASCII data files."""
    best, best_n = None, 0
    for d, _, files in os.walk(root):
        # data files are extensionless timestamp names like 2004.02.12.10.32.39
        data_files = [f for f in files if f.count(".") >= 4 and "." not in os.path.splitext(f)[1][1:]]
        # simpler: count files that parse as all-numeric-dotted
        cnt = 0
        for f in files:
            parts = f.split(".")
            if len(parts) >= 5 and all(p.isdigit() for p in parts):
                cnt += 1
        if cnt > best_n:
            best, best_n = d, cnt
    print(f"selected test dir: {best}  ({best_n} files)")
    return best


def file_rms(path, col):
    arr = np.loadtxt(path)
    if arr.ndim == 1:
        sig = arr
    else:
        sig = arr[:, col]
    return np.sqrt(np.mean(sig * sig)), sig


def main():
    os.makedirs(ART, exist_ok=True)
    # extracted root: anything under data/ that isn't the zip
    roots = [p for p in glob.glob(os.path.join(DATA, "*")) if os.path.isdir(p)]
    if not roots:
        raise SystemExit("No extracted dataset under ml/data/. Extract ims.zip first.")
    # pick the deepest dir that actually holds the timestamp data files
    test_dir = None
    best_n = 0
    for r in roots:
        d = find_test_dir(r)
        if d:
            n = len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))])
            if n > best_n:
                test_dir, best_n = d, n
    if not test_dir:
        raise SystemExit("Could not locate IMS data files.")

    files = sorted(glob.glob(os.path.join(test_dir, "*")))  # chronological order
    files = [f for f in files if os.path.isfile(f)]
    n = len(files)
    print(f"{n} snapshot files (chronological run-to-failure)")

    def label_of(idx):
        frac = idx / (n - 1)  # 0 = start of life, 1 = failure
        if frac >= FAULT_FRAC:
            return 2  # fault
        if frac >= DEGRADE_FRAC:
            return 1  # degrading
        return 0      # normal

    # single pass: time-based label per file, windows -> features.
    # groups = file index, so the split can keep all windows of a file together
    # (no sibling-window leakage between train and test).
    X, y, groups = [], [], []
    for idx, f in enumerate(files):
        arr = np.loadtxt(f)
        sig = arr[:, BEARING_COL] if arr.ndim > 1 else arr
        lab = label_of(idx)
        for w in windows_from_signal(sig):
            X.append(extract(w))
            y.append(lab)
            groups.append(idx)
        if idx % 100 == 0:
            print(f"  {idx}/{n}")
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int64)
    groups = np.array(groups, dtype=np.int64)
    print(f"\nfeatures: {X.shape}, class counts = {np.bincount(y)}, "
          f"groups(files) = {len(np.unique(groups))}")

    np.savez(os.path.join(ART, "dataset.npz"),
             X=X, y=y, groups=groups,
             classes=np.array(["normal", "degrading", "fault"]))
    print("saved", os.path.join(ART, "dataset.npz"))


if __name__ == "__main__":
    main()
