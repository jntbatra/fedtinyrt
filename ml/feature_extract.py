"""
Feature extraction for FedTinyRT — shared definition.

This is the SAME math the device runs in Step 7 (FFT + statistics).
Keep it identical on both sides: the PC trains on these features and the
firmware must reproduce them, or the golden-vector validation will fail.

A "window" is a 1-D float array of raw accelerometer samples.
Output is a fixed-length float32 feature vector.
"""

import numpy as np

# --- Config (must match the device) ---
WINDOW = 2048          # samples per window
N_FFT_BINS = 32        # FFT magnitude downsampled to this many bands
# Final feature layout: [N_FFT_BINS band energies] + [6 time stats]
N_STATS = 6
N_FEATURES = N_FFT_BINS + N_STATS


def time_stats(w):
    """6 time-domain statistics used in bearing-fault detection."""
    rms = np.sqrt(np.mean(w * w))
    peak = np.max(np.abs(w))
    std = np.std(w)
    # guard against divide-by-zero on flat windows
    crest = peak / rms if rms > 1e-9 else 0.0
    mean = np.mean(w)
    m2 = np.mean((w - mean) ** 2)
    m4 = np.mean((w - mean) ** 4)
    kurt = m4 / (m2 * m2) if m2 > 1e-12 else 0.0
    m3 = np.mean((w - mean) ** 3)
    skew = m3 / (m2 ** 1.5) if m2 > 1e-12 else 0.0
    return np.array([rms, peak, std, crest, kurt, skew], dtype=np.float32)


def fft_bands(w):
    """Real FFT magnitude, averaged down into N_FFT_BINS contiguous bands."""
    mag = np.abs(np.fft.rfft(w * np.hanning(len(w))))  # [WINDOW/2 + 1]
    # drop DC, split the rest into N_FFT_BINS equal bands, take mean energy
    mag = mag[1:]
    bands = np.array_split(mag, N_FFT_BINS)
    return np.array([b.mean() for b in bands], dtype=np.float32)


def extract(w):
    """Full feature vector for one window."""
    w = np.asarray(w, dtype=np.float64)
    return np.concatenate([fft_bands(w), time_stats(w)]).astype(np.float32)


def windows_from_signal(sig, window=WINDOW, hop=None):
    """Split a long 1-D signal into non-overlapping (or hopped) windows."""
    hop = hop or window
    n = (len(sig) - window) // hop + 1
    return [sig[i * hop: i * hop + window] for i in range(max(n, 0))]
