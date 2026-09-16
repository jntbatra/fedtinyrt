"""Strict local NPZ contract and deterministic subject-only partitions."""
from pathlib import Path
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from .feature_extract import extract


def load(path):
    with np.load(path, allow_pickle=False) as data:
        required = {"epochs", "quality", "baselines", "labels", "subjects", "sample_hz", "dataset_version", "synthetic"}
        if required - set(data.files):
            raise ValueError(f"Missing dataset fields: {sorted(required-set(data.files))}")
        d = {k: data[k] for k in required}
    epochs, y, subjects = d["epochs"], d["labels"], d["subjects"]
    n = len(epochs)
    if (epochs.ndim != 3 or epochs.shape[2] != 4 or n == 0 or y.shape != (n,)
            or subjects.shape != (n,) or subjects.dtype.kind not in "US"
            or d["quality"].shape != epochs.shape or d["baselines"].shape != (n, 2)):
        raise ValueError("Invalid dataset shapes or non-string subject IDs")
    if not np.isin(y, [0, 1]).all() or any(not str(s).strip() for s in subjects):
        raise ValueError("Labels must be binary; subject IDs must be nonempty")
    if d["synthetic"].shape != () or d["synthetic"].dtype.kind != "b":
        raise ValueError("synthetic must be an explicit scalar boolean")
    hz = float(d["sample_hz"])
    x = np.stack([extract(e, q, b, hz) for e, q, b in zip(epochs, d["quality"], d["baselines"])])
    return x, y.astype(np.int64), subjects, {
        "dataset_version": str(d["dataset_version"]), "synthetic": bool(d["synthetic"]),
        "sample_hz": hz, "window_seconds": epochs.shape[1]/hz,
        "dataset_file": Path(path).name,
    }


def split_subjects(y, subjects, seed=42):
    if len(np.unique(subjects)) < 5:
        raise ValueError("At least five subjects required for train/validation/test")
    # Never retry seeds based on test labels or tune using the test partition.
    trainval, test = next(GroupShuffleSplit(1, test_size=.2, random_state=seed).split(y, y, subjects))
    a, b = next(GroupShuffleSplit(1, test_size=.25, random_state=seed).split(y[trainval], y[trainval], subjects[trainval]))
    parts = {"train": trainval[a], "validation": trainval[b], "test": test}
    for name, rows in parts.items():
        if len(np.unique(y[rows])) != 2:
            raise ValueError(f"{name} lacks a class; supply more subjects or a reviewed split")
    return parts


def partition_sites(subjects, count, seed=42):
    unique = np.unique(subjects)
    if count < 2 or count > len(unique):
        raise ValueError("Need 2..number_of_subjects sites")
    np.random.default_rng(seed).shuffle(unique)
    return [np.flatnonzero(np.isin(subjects, group)) for group in np.array_split(unique, count)]
