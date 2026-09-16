"""Versioned features from aligned 1 Hz *summaries*, not raw audio/PPG.

Columns: SpO2 percent, respiratory amplitude envelope, motion magnitude,
audio RMS envelope. Sensor-specific waveform-to-envelope DSP is upstream.
Missing/invalid values are masked, never treated as healthy measurements.
"""
import numpy as np

MODALITIES = ("spo2", "respiration", "motion", "audio")
FEATURE_NAMES = tuple(f"{m}_{s}" for m in MODALITIES for s in ("mean", "std", "slope")) + (
    "delta_spo2", "relative_respiration", "spo2_present", "respiration_present",
    "motion_present", "audio_present")
SCHEMA = "sleep-envelope-v1"
MASK_INDICES = np.arange(14, 18)
MODALITY_FEATURES = ((0, 1, 2, 12), (3, 4, 5, 13), (6, 7, 8), (9, 10, 11))


def extract(epoch, quality, baseline, sample_hz=1.0):
    """Return 18 float32 features. Baseline is [SpO2, resp amplitude]."""
    epoch, quality, baseline = map(np.asarray, (epoch, quality, baseline))
    if (epoch.ndim != 2 or epoch.shape[1] != 4 or len(epoch) < 2
            or quality.shape != epoch.shape or baseline.shape != (2,)):
        raise ValueError("Expected epoch/quality [T,4], T>=2, baseline [2]")
    if (not np.isfinite(sample_hz) or sample_hz <= 0 or not np.isfinite(baseline).all()
            or not 50 <= baseline[0] <= 100 or baseline[1] <= 0):
        raise ValueError("Invalid sample rate or calibration baseline")
    valid = np.isfinite(epoch) & np.isfinite(quality) & (quality >= .5) & (quality <= 1)
    valid[:, 0] &= (epoch[:, 0] >= 50) & (epoch[:, 0] <= 100)
    valid[:, 1:] &= epoch[:, 1:] >= 0
    x = np.zeros(len(FEATURE_NAMES), dtype=np.float32)
    for m in range(4):
        good = valid[:, m]
        # Need >=80% coverage; a numeric zero and absent stream are different.
        if good.mean() < .8:
            continue
        t = np.flatnonzero(good).astype(float) / sample_hz
        v = epoch[good, m]
        tc = t - t.mean()
        x[3*m:3*m+3] = v.mean(), v.std(), np.dot(tc, v-v.mean()) / np.dot(tc, tc)
        x[14+m] = 1
    if x[14]:
        x[12] = x[0] - baseline[0]
    if x[15]:
        x[13] = x[3] / baseline[1]
    if not np.isfinite(x).all():
        raise ValueError("Features overflowed float32; inspect source units/calibration")
    return x


def fit_scaler(x):
    """Training rows only; fit each modality using present rows only."""
    mean, std = np.zeros(x.shape[1], np.float32), np.ones(x.shape[1], np.float32)
    for m, cols in enumerate(MODALITY_FEATURES):
        rows = x[:, 14+m] == 1
        if rows.any():
            mean[list(cols)] = x[rows][:, cols].mean(0)
            std[list(cols)] = np.maximum(x[rows][:, cols].std(0), 1e-6)
    return mean, std


def normalize(x, mean, std):
    z = ((x - mean) / std).astype(np.float32)
    for m, cols in enumerate(MODALITY_FEATURES):
        z[np.ix_(x[:, 14+m] == 0, cols)] = 0
    z[:, MASK_INDICES] = x[:, MASK_INDICES]
    return z


def modality_dropout(z, rng, probability=.2):
    z = z.copy()
    for m, cols in enumerate(MODALITY_FEATURES):
        rows = rng.random(len(z)) < probability
        z[np.ix_(rows, (*cols, 14+m))] = 0
    return z
