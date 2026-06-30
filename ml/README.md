# FedTinyRT — PC training pipeline (Step 8)

Pre-trains the bearing-fault classifier on the **NASA IMS** dataset and exports an
INT8 `.tflite` model + golden validation vectors + C arrays for the firmware.

## Result (NASA IMS 2nd_test, bearing 1)

- 9,840 windows, 38 features, classes `normal / degrading / fault` (counts 6890 / 1960 / 990)
- **Labels are time-based** (position in the run-to-failure timeline), NOT thresholded
  from the vibration — so the label is independent of the features (no label leakage).
- **Split is grouped by file** (GroupShuffleSplit) — a window's siblings never straddle
  train/test (no sibling-window leakage).
- Accuracy ceiling (LazyPredict, grouped split, SVC/RF): **~98.3% balanced**
- Our model (MLP 38→32→16→3): **INT8 acc 98.4%, balanced 96.6%**
- Per-class recall: normal 99.1%, degrading 97.1%, fault 93.6%
- Model size: **4.1 KB** (fits MCU, NPU-eligible)

### Honesty caveat
Train/test files come from the **same single run-to-failure** (one bearing, one condition),
interleaved in time — so the model interpolates within one run it has seen. Cross-machine
generalization is **untested**. Proper next test: train on bearing 1, evaluate on a different
bearing/run (2nd_test bearings 2-4; 1st/3rd_test). This is also what federation models —
different nodes = different machines.

### History
A first pass scored 99.5% but was inflated by two leaks: (1) labels were thresholded from
RMS while RMS was also a feature, and (2) random window split put sibling windows of one file
in both train and test. Both removed above; the honest number is ~96.6% balanced.

## Why this model

NN required because the **Ethos-U55 NPU only runs neural nets** (not RF/SVM). The MLP
already sits at the accuracy ceiling, so no heavier model is needed. Features (FFT bands
+ time statistics) are computed on-device in firmware Step 7 — `feature_extract.py` is the
shared reference definition; keep both sides identical or golden-vector tests fail.

## Files

| File | Purpose |
|------|---------|
| `feature_extract.py` | FFT + statistics — shared math, mirrored in firmware |
| `prep_ims.py` | parse IMS, RMS-based labeling, window → features → `dataset.npz` |
| `train_tflite.py` | train, INT8 quantize, export model + golden vectors + C arrays |
| `lazy_compare.py` | LazyPredict ranking (accuracy ceiling reference) |
| `artifacts/model_int8.tflite` | device model (Vela + TFLite-Micro input) |
| `artifacts/model_data.c/.h` | model as C array + feature mean/std for firmware |
| `artifacts/golden_vectors.json` | input→expected output, for on-device validation |
| `artifacts/scaler.npz` | feature normalization (device applies same mean/std) |

## Reproduce

```bash
# 1. download IMS (~1GB), extract nested zip→7z→rar to ml/data/extracted/2nd_test/
# 2. build features
py ml/prep_ims.py
# 3. (optional) see accuracy ceiling
py ml/lazy_compare.py
# 4. train + quantize + export
py ml/train_tflite.py
```

Requires: `tensorflow-cpu`, `numpy`, `scipy`, `scikit-learn`, `lazypredict`, `py7zr`.

## Notes / next

- Toolchain: TF 2.16 + Keras 3 crashes on `from_keras_model` INT8 — we convert via
  SavedModel (`model.export()` → `from_saved_model`). Keep that path.
- Sampling rate: IMS is 20 kHz; the device accel runs lower. Resampling/feature parity
  is handled at the `sample_next()` seam (firmware Step 5).
- Next: feed `model_int8.tflite` to **Vela** for the Ethos-U55 (firmware Step 10), and use
  `golden_vectors.json` to validate device inference against this PC oracle (Steps 9–10).
