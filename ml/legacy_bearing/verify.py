"""
Sanity-check the dataset and split. Answers: are the time-based labels real,
and is the grouped split leak-free?
"""
import os
import numpy as np
from sklearn.model_selection import GroupShuffleSplit

ART = os.path.join(os.path.dirname(__file__), "artifacts")
d = np.load(os.path.join(ART, "dataset.npz"), allow_pickle=True)
X, y, groups = d["X"], d["y"].astype(int), d["groups"].astype(int)

# RMS feature is index 32 (after 32 FFT bands). Aggregate per file (group).
RMS = 32
files = np.unique(groups)
rms_per_file = np.array([X[groups == g, RMS].mean() for g in files])
lab_per_file = np.array([y[groups == g][0] for g in files])
n = len(files)

# 1) split disjointness
tr, te = next(GroupShuffleSplit(1, test_size=0.2, random_state=42).split(X, y, groups))
overlap = set(groups[tr]) & set(groups[te])
print(f"[split] train files={len(set(groups[tr]))} test files={len(set(groups[te]))} "
      f"OVERLAP={len(overlap)}  -> {'LEAK!' if overlap else 'disjoint OK'}")

# 2) where does vibration actually rise? print RMS trajectory in 20 bins
print("\n[RMS trajectory across run-to-failure] (file% : mean RMS : label)")
base = rms_per_file[: n // 5].mean()
for i in range(0, n, max(1, n // 20)):
    pct = 100 * i / n
    lab = ["normal", "degrad", "FAULT"][lab_per_file[i]]
    bar = "#" * int(rms_per_file[i] / base * 10)
    print(f"  {pct:5.1f}%  rms={rms_per_file[i]:.4f} ({rms_per_file[i]/base:4.1f}x)  {lab:6} {bar}")

# 3) class separability in RMS: do the label bands actually differ?
for c, name in enumerate(["normal", "degrading", "fault"]):
    v = rms_per_file[lab_per_file == c]
    print(f"\n{name:9}: files={len(v)} RMS mean={v.mean():.4f} "
          f"min={v.min():.4f} max={v.max():.4f}")

# 4) the real question: does 'degrading' (70-90%) look different from 'normal'?
norm = rms_per_file[lab_per_file == 0]
degr = rms_per_file[lab_per_file == 1]
ratio = degr.mean() / norm.mean()
print(f"\n[verdict] degrading RMS is {ratio:.2f}x normal RMS.")
print("  if ~1.0x -> 'degrading' is physically identical to normal -> label is fiction.")
print("  if >>1.0x -> vibration really changed there -> labels track real degradation.")
