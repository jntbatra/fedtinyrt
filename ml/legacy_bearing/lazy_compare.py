"""
Run LazyPredict over the IMS features to see which ML methods work best.
This gives the ACCURACY CEILING. The device must use a neural net (NPU only
runs NNs), so RF/SVM results are a reference target for our MLP, not the pick.

Run:  py ml/lazy_compare.py
"""

import os
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from lazypredict.Supervised import LazyClassifier

ART = os.path.join(os.path.dirname(__file__), "artifacts")

d = np.load(os.path.join(ART, "dataset.npz"), allow_pickle=True)
X, y, groups = d["X"].astype(np.float32), d["y"].astype(np.int64), d["groups"]
print(f"{X.shape[0]} samples, {X.shape[1]} features, class counts {np.bincount(y)}")

# grouped split by file — no sibling-window leakage
tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2,
                                random_state=42).split(X, y, groups))
Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
sc = StandardScaler().fit(Xtr)
Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)

clf = LazyClassifier(verbose=0, ignore_warnings=True, predictions=False)
models, _ = clf.fit(Xtr, Xte, ytr, yte)
print("\n=== ranked classifiers (accuracy ceiling) ===")
print(models.to_string())
models.to_csv(os.path.join(ART, "lazy_ranking.csv"))
print("\nsaved", os.path.join(ART, "lazy_ranking.csv"))
