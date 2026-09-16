"""Synthetic fixtures ONLY. Not physiological simulation or efficacy evidence."""
import argparse
from pathlib import Path
import numpy as np


def generate(path, subjects=15, epochs_per_subject=24, seconds=30, seed=42):
    if subjects < 5 or epochs_per_subject < 4 or seconds < 2:
        raise ValueError("Need >=5 subjects, >=4 epochs per subject and >=2 seconds")
    rng = np.random.default_rng(seed)
    epochs, quality, baselines, labels, ids = [], [], [], [], []
    for subject in range(subjects):
        # Baselines are generated separately, never fitted using event/test labels.
        spo2, resp = rng.uniform(95, 99), rng.uniform(.5, 1.5)
        for index in range(epochs_per_subject):
            event = index % 4 == 0
            e = np.column_stack((spo2+rng.normal(0, .25, seconds),
                                 resp+rng.normal(0, .05, seconds),
                                 rng.uniform(0, .15, seconds), rng.uniform(.1, .3, seconds)))
            if event:
                e[:, 0] -= np.linspace(0, rng.uniform(3, 7), seconds)
                e[:, 1] *= rng.uniform(.15, .5)
            q = np.ones_like(e)
            if index % 7 == 1:
                e[:, 3] = np.nan
                q[:, 3] = 0
            if index % 11 == 2:
                q[:, 0] = .1
            epochs.append(e); quality.append(q); baselines.append([spo2, resp])
            labels.append(int(event)); ids.append(f"synthetic-{subject:03d}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, epochs=np.asarray(epochs, np.float32), quality=np.asarray(quality, np.float32),
                        baselines=np.asarray(baselines, np.float32), labels=labels, subjects=ids,
                        sample_hz=1., dataset_version="synthetic-smoke-v1", synthetic=True)
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("ml/sleep/data/synthetic.npz"))
    args = p.parse_args()
    print("SYNTHETIC SOFTWARE FIXTURE:", generate(args.output))
