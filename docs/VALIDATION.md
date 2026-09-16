# Sleep migration validation

Software checks used Python 3.13.13, NumPy 2.5.3, scikit-learn 1.9.1,
TensorFlow 2.21.0, pytest 9.1.1 and Zig 0.16.0.

- Six Python tests pass: subject/site separation, deterministic splits, quality
  masks, baseline features, masked normalization/dropout, saturated INT8,
  federation corruption checks and invalid labels.
- C host harness passes: normal/event/recovery/fault replay, exact event and time
  counters, overflow/order, missing/stale/NaN inputs, timestamp rejection,
  inference failure, baseline-relative triggers, short events, gaps and retrigger
  suppression.
- Synthetic two-epoch MLP training and full INT8 conversion completed. The model
  is 4,944 bytes. Metadata, preprocessing, splits, float/quantized metrics and C
  arrays are generated locally under ignored `ml/sleep/artifacts/`.
- All 25 exported golden vectors pass through the actual PC INT8 interpreter,
  including normalization and quantized inputs.
- A three-site, one-round synthetic federation smoke run completed local
  training, checked averaging, global redistribution, adaptation and site metrics.
- `src/usermain.c` compiles to a Cortex-M85 object against the actual pinned
  µT-Kernel headers with the existing Debug include/define settings.

These are software checks, not real sleep-model performance evidence. No real
dataset is selected/imported. Board inference uses scripted scores. Full e2 studio
link/flash, boot, sensors, RAM, stack high-water marks, deadlines, power and NPU
measurements remain unverified. Legacy results were preserved, not rerun.
