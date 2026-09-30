# Defensible-results plan v2 — after the P1–P4 findings

v1 answered the within-subject question and falsified the cross-subject claim.
P4 named the reason it could not be trusted: **our feature extractor does not
reproduce the reference features**. This plan fixes that first, then re-asks the
cross-subject question on inputs that match training, and adds the baselines and
uncertainty a reviewer will demand.

## What v1 established (do not redo)

- Board reproduces host to ~2e-4 AUROC; cycle costs measured (`personalize`
  1.51M cyc ≈1.5 ms, 800-iter round 46.4M cyc ≈46.4 ms @1 GHz).
- Within tr03-0322: label-free federated round lifts held-out-time AUROC
  0.8562 → 0.8749.
- Cross-subject (10 held-out subjects): **no recipe beats the frozen global
  head**; leaked recipe (0.860) < global (0.882); teacher head least stable.

## Root cause found (this session)

The original CinC-2018 feature extractor was located: `fedtinyrt` notebook
`apena -ml/UCDDB_ECG_SpO2_Apnea_Prototype.ipynb` (cell 9 `extract_window_features`,
cell 10 `process_subject`). Its ECG path is materially different from ours:

| Step | Reference (notebook) | Our `tools/extract_features.py` |
|---|---|---|
| ECG rate | resample to **100 Hz** (`resample_poly`) | native rate, untouched |
| ECG filter | **butter(4,[0.5,35]) bandpass**, `sosfiltfilt` | none |
| ECG per-window | `clip((x−median)/std, −5, 5)` | raw amplitude |
| SpO2 rate | resample to **1 Hz** | native rate |
| R-peak | `find_peaks` on **both polarities**, keep the one with more peaks, `prominence≈0.45` | single-polarity simple detector |
| Windows | drop low-quality (`valid<0.90`) and ambiguous (`0<overlap<5 s`) | keep all |
| Labels | `arousal` events, resp_* apnea/hypopnea, overlap ≥5 s | same rule (ok) |

Expected effect: ECG columns (`rr_count`, `mean_hr`, `ecg_std`, `ecg_range`, …)
should match `fixed_test_vectors_float32.npz:raw_features` on tr03-0322, and the
SpO2 columns we already match should stay matched (`spo2_diff_std` should also
improve once SpO2 is at 1 Hz).

## Priority order (highest leverage first)

### Phase A — Faithful feature pipeline  ← enables everything else
1. Port `process_subject` verbatim into `tools/ref_features.py` (numpy/scipy/wfdb;
   no TensorFlow needed). Output: per-window 21 features, labels, `start_sec`,
   exactly as the notebook cache.
2. **Gate A (must pass):** on tr03-0322, `raw_features` mean-abs-diff < 1e-2 per
   column vs the stored array, and label agreement with the stored 256 labels
   ≥ 250/256. If the gate fails, stop and reconcile before any downstream run —
   this is the whole point.
3. Record the residual per-column error in `RESULTS_PROTOCOL.md`.

### Phase B — Faithful within-subject re-run (P1′)
Re-run the leak-free FIT/TEST protocol using `ref_features` outputs for
tr03-0322. Expect it to line up with the stored `int8_probability` gate
(AUROC all-256 ≈0.8823) far more tightly than v1. Confirms the model + protocol
are correct once features are correct.

### Phase C — Faithful cross-subject re-run (P3′)  ← the headline
Same 10 held-out subjects, same FIT/TEST recipes (global, LEAKY, M0–M5,
ORACLE), but on Phase-A features. Append to `RESULTS_PROTOCOL.md` as **P3′**
and keep P3 side-by-side so the effect of fixing features is visible.
- Report per-subject AUROC with subject-level bootstrap CIs.
- Report the **paired per-subject delta** (adapted − global), not just means.
- State the verdict either way; a clean negative is still a defensible result.

### Phase D — Real baselines (reviewer will ask)
Add to the same table, all on TEST, all fitted on FIT only:
- prevalence baseline (predict the positive rate),
- **SpO2 threshold** rule (e.g. `spo2_min < 92`), and
- **SpO2-only logistic regression** (no ECG).
TRAINING_CONTEXT §15 says SpO2 alone ≈ full model; this makes the MLP earn its
keep and gives an extraction-independent floor.

### Phase E — ECG-ablation cross-check
Since §15 says ECG is near chance, re-run Phase C with the 11 ECG columns set to
their training mean (i.e. neutralised) and compare. If the cross-subject ranking
is unchanged, the feature-mismatch threat stops mattering to the conclusion.

### Phase F — Board parity re-confirmation
Flash, `resetoff`, `sethead global`; confirm host↔board parity on Phase-A
features for one subject (expect ~2e-4 again). No energy claims without a probe.

### Phase G — Honest write-up (P4′)
Rewrite the P4 section against the new evidence: the feature threat is resolved
(with the residual error quoted), and the cross-subject verdict is restated on
inputs that match training. Keep the v1 numbers for the record.

## Explicitly out of scope

- Retraining the global model: the 100-subject training cache is gone and the
  raw training set is a ~15 GB download (previously ruled out). The frozen model
  is given; we evaluate and adapt it.
- Ethos-U55 NPU: inference-only, no FSP driver.
- Energy in joules/mW: no current probe.

## Commands

```bash
# Phase A gate
/tmp/cincenv/bin/python tools/ref_features.py --gate tr03-0322
# Phase B
/tmp/cincenv/bin/python tools/protocol_eval.py --ref
# Phase C/D
/tmp/cincenv/bin/python tools/cross_subject_eval.py --ref --baselines --write
# Phase F
/tmp/cincenv/bin/python tools/serial_cmd.py "resetoff" "sethead global" ...
```

Rebuild/flash unchanged from v1. Board must be reset (`resetoff`) before any
adaptation experiment; leave it at `sethead global`.
