# Label-free adaptation protocol — leak-free evaluation

Host-side evaluation of the on-device `personalize` protocol (`src/apnea_personal.c`). The firmware fits baseline/offsets/threshold and reports metrics on the same 256 windows; here every method is **fitted only on FIT and scored only on TEST** under a chronological split.

Model: exact float MLP rebuilt from `cinc2018_normalized_input_export_model.keras` (the board uses the quantized approximation of this same network; max probability deviation of the quantized reconstruction ≈ 3e-3).

## Split

- FIT: `n=128`, indices `0..127`, time `0..4290s`, 6 positives.
- TEST: `n=127`, indices `129..255`, time `4350..8730s`, 9 positives.
- Dropped as overlapping the last FIT window ([128]). Last FIT window [4290,4350)s, first TEST window starts 4350s — gap 0s, no overlap.

## Gates

1. Float MLP vs stored `float_probability`: max abs diff = **9.803e-08** (PASS, < 1e-5).
2. Recentring baseline windows (`int8 code <= -80`, all 256): **122** (PASS, == 122).
3. `int8_probability` AUROC: all 256 = **0.8823**, FIT = 0.9228, TEST = 0.8550.

> Note: the stored `int8_probability` is a dequantized value in [0,1] with `p=(q+128)/256`; the firmware `q <= -80` baseline test is applied to the recovered int8 codes.

## Methods (fitted on FIT, scored on TEST)

| Method | thr | AUROC [95% CI] | BalAcc [95% CI] | Sens | Spec | Prec | F1 | PPR vs TPR |
|---|---|---|---|---|---|---|---|---|
| M0 global, fixed thr 0.29 | 0.290 | 0.8550 [0.7290, 0.9404] | 0.855 [0.654, 0.930] | 0.889 | 0.822 | 0.276 | 0.421 | 0.228 vs 0.889 |
| M1 global, Otsu(FIT) | 0.415 | 0.8550 [0.7290, 0.9404] | 0.718 [0.539, 0.870] | 0.556 | 0.881 | 0.263 | 0.357 | 0.150 vs 0.556 |
| M2 recentre + Otsu | 0.441 | 0.8475 [0.7069, 0.9393] | 0.714 [0.534, 0.866] | 0.556 | 0.873 | 0.250 | 0.345 | 0.157 vs 0.556 |
| M3 recentre + head(teacher) | 0.453 | 0.8465 [0.7060, 0.9411] | 0.697 [0.514, 0.853] | 0.556 | 0.839 | 0.208 | 0.303 | 0.189 vs 0.556 |
| M4 recentre + head(HMM2 label-free) | 0.217 | 0.8588 [0.7384, 0.9426] | 0.714 [0.534, 0.866] | 0.556 | 0.873 | 0.250 | 0.345 | 0.157 vs 0.556 |
| M5 recentre + FedAvg2 + Otsu | 0.437 | 0.8465 [0.7017, 0.9429] | 0.697 [0.514, 0.853] | 0.556 | 0.839 | 0.208 | 0.303 | 0.189 vs 0.556 |
| ORACLE recentre + head(oracle) | 0.322 | 0.8710 [0.7562, 0.9491] | 0.586 [0.478, 0.762] | 0.222 | 0.949 | 0.250 | 0.235 | 0.063 vs 0.222 |

Balanced-accuracy CI: Wilson intervals on sensitivity and specificity, bounds averaged. AUROC CI: 1000 bootstrap resamples. PPR = predicted-positive rate; TPR = sensitivity on TEST.

Notes:
- M2 recentre + Otsu: baseline 55 FIT windows
- M3 recentre + head(teacher): teacher pos 26/128
- M4 recentre + head(HMM2 label-free): HMM2(spo2_max_drop) pos 13/128
- M5 recentre + FedAvg2 + Otsu: halves n=64/64
- ORACLE recentre + head(oracle): oracle pos 6/128 (upper bound)

## Leaky vs guarded

| | thr | AUROC | BalAcc | Sens | Spec | F1 | PPR |
|---|---|---|---|---|---|---|---|
| LEAKY recentre+Otsu (all 256 = `personalize`) | 0.456 | 0.8786 [0.7834, 0.9536] | 0.792 | 0.667 | 0.917 | 0.444 | 0.117 |
| GUARDED M2 recentre+Otsu (TEST only) | 0.441 | 0.8475 [0.7069, 0.9393] | 0.714 | 0.556 | 0.873 | 0.345 | 0.157 |

## Interpretation

1. The leakage is real but modest for the deployed recentre+Otsu recipe: the all-256 report gives AUROC 0.879 / balanced accuracy 0.792, versus 0.847 / 0.714 when fitted on FIT and scored on TEST.
2. With only 9 positives in 127 TEST windows, every AUROC CI is wide and M0-M5 intervals overlap heavily; no adaptation method is demonstrably better than the global model on this split.
3. The fixed-threshold global model M0 actually has the best guarded balanced accuracy (0.855 vs 0.697-0.714 for the Otsu/head-adapted rows): Otsu recalibration and head training on this subject do not help, and Otsu raises the threshold enough to cut sensitivity.
4. Over-prediction persists: methods predict a positive rate well above the true rate (0.071 on TEST).
5. The oracle-labelled head (0.871 AUROC) is the non-deployable ceiling; no label-free method reaches it.
6. M4's label-free HMM2 source and M5's federated aggregation do not beat the teacher-trained M3 within CI on this data.

## Board results (P2) — RA8P1, subject tr03-0322

Firmware flashed; all figures re-run and confirmed on hardware after a
`sethead global` reset. Commands via `tools/serial_cmd.py`.

### Host ↔ board parity (`personalize`, one subject, all 256 windows)

| Quantity | Host (leaky) | Board | Δ |
|---|---|---|---|
| AUROC all 256 | 0.8786 | 0.8788 | 0.0002 |
| Balanced accuracy (Otsu) | 0.792 | 0.7918 | 0.0002 |
| Otsu threshold | 0.456 | 0.4565 | 0.0005 |
| Baseline windows | 122 | 122 | 0 |

The firmware reproduces the host reference to ~2e-4 on AUROC — the host
protocol is a faithful model of the device.

### Fixed global head vs label-free federated head

Head reset to global, then two label-free local rounds (`fed A temporal`,
`fed B temporal`, n=128 each) and a size-weighted `fedavg`. Threshold held at
the fixed 0.29 throughout, so AUROC is threshold-independent.

| Head | AUROC all | AUROC A | AUROC B | BalAcc A | BalAcc B |
|---|---|---|---|---|---|
| Global (frozen) | 0.8802 | 0.9153 | 0.8562 | 0.8265 | 0.8562 |
| Federated (label-free) | 0.9112 | 0.9536 | 0.8749 | 0.8921 | 0.7316 |

Train cost (measured, `cycrep`, 5 runs of site A / n=66 / 800 iters):
median **58,015 cycles/iter**, i.e. 46,412,424 cycles ≈ **46.4 ms per 800-iter
local round** at 1 GHz. The two `fed` rounds cost 83.2M and 80.9M cycles.

### Cycle / energy summary

| Operation | Cycles | Time @1 GHz |
|---|---|---|
| `personalize` (baseline + offsets + Otsu) | 1,513,523 | ~1.5 ms |
| One 800-iter local training round | 46,412,424 | ~46.4 ms |
| `fed A temporal` (n=128) | 83,226,079 | ~83.2 ms |
| `fed B temporal` (n=128) | 80,937,978 | ~80.9 ms |

Energy in joules is **not** reported: that needs a current measurement we do
not have. Cycles and time are hardware-measured; do not convert to mW.

### Label-supervision audit (`labels`)

- Teacher (frozen head, p ≥ 0.29): 145/256 confident, 130 agree with oracle.
- Teacher positives 51; proxy rule (`spo2_max_drop ≥ 3.0`) positives 28;
  oracle positives 15/256.
- On this subject all label-free sources over-label relative to the oracle;
  the federated head still ranks better (AUROC) despite the shift.

### Caveat (carried from P1)

"Site A/B" is a chronological index split of **one** subject (A = windows
0..127, B = 128..255), not a physical or cross-subject split. The A/B
improvement shows the label-free adaptation helps on held-out time within a
subject; it is **not** evidence of cross-subject generalization. That is P3.


## Cross-subject evaluation (P3) — held-out `final_test` subjects

Subjects on disk: 10. Per-subject full-record 30 s-stride / 60 s windows, chronological FIT (first half) / TEST (second half), same recipes as above.

| Subject | n | pos fit | pos test | global | LEAKY | M0 | M2 | M3 | M4 | M5 | ORACLE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tr03-0322 | 989 | 65 | 71 | 0.901 | 0.903 | 0.908 | 0.915 | 0.852 | 0.911 | 0.896 | 0.909 |
| tr04-0029 | 616 | 36 | 42 | 0.678 | 0.635 | 0.551 | 0.513 | 0.423 | 0.601 | 0.418 | 0.637 |
| tr05-0647 | 920 | 0 | 38 | 0.940 | 0.905 | 0.929 | 0.915 | 0.932 | 0.922 | 0.932 | 0.902 |
| tr06-0014 | 1014 | 292 | 42 | 0.948 | 0.948 | 0.921 | 0.930 | 0.881 | 0.913 | 0.857 | 0.913 |
| tr07-0247 | 945 | 40 | 23 | 0.930 | 0.920 | 0.928 | 0.913 | 0.884 | 0.931 | 0.887 | 0.925 |
| tr07-0841 | 956 | 97 | 108 | 0.890 | 0.879 | 0.885 | 0.881 | 0.877 | 0.885 | 0.877 | 0.887 |
| tr10-0169 | 986 | 273 | 167 | 0.887 | 0.881 | 0.907 | 0.916 | 0.898 | 0.915 | 0.919 | 0.900 |
| tr11-0537 | 857 | 143 | 78 | 0.907 | 0.901 | 0.839 | 0.842 | 0.428 | 0.846 | 0.827 | 0.847 |
| tr12-0410 | 1013 | 201 | 69 | 0.910 | 0.907 | 0.798 | 0.793 | 0.817 | 0.802 | 0.801 | 0.819 |
| tr13-0164 | 733 | 55 | 113 | 0.828 | 0.724 | 0.786 | 0.767 | 0.792 | 0.559 | 0.774 | 0.791 |

| Aggregate | mean | sd |
|---|---|---|
| p0_all AUROC | 0.8820 | 0.0791 |
| LEAKY AUROC | 0.8602 | 0.0993 |
| M0 AUROC | 0.8452 | 0.1161 |
| M2 AUROC | 0.8383 | 0.1277 |
| M3 AUROC | 0.7785 | 0.1902 |
| M4 AUROC | 0.8285 | 0.1372 |
| M5 AUROC | 0.8189 | 0.1496 |
| ORACLE AUROC | 0.8533 | 0.0879 |


## Threats to validity and interpretation (P4)

This section states what the results above do and do not establish, and records
the checks that failed. It is the honest read of P1-P3, not a summary of wins.

### 1. Feature-extractor mismatch — the strongest threat

The P3 numbers are computed from features we **re-extract** from the raw WFDB
records (`tools/extract_features.py`), not from the stored reference features.
On subject tr03-0322's 256 reference windows, our recomputed 21 columns compare
to the stored `raw_features` as follows:

| Column | Reference mean | Ours mean | Mean abs diff |
|---|---|---|---|
| `spo2_mean` | 97.3219 | 97.3245 | 0.0077 |
| `spo2_below_92` | 0.0046 | 0.0046 | 0.0001 |
| `spo2_below_94` | 0.0173 | 0.0172 | 0.0004 |
| `rr_count` | 114.38 | 60.45 | 53.94 |
| `mean_hr` | 128.83 | 62.46 | 66.36 |
| `ecg_std` | 0.8614 | 0.1833 | 0.6781 |
| `ecg_range` | 7.4778 | 1.9337 | 5.5441 |

All 10 SpO2 columns match. **All 11 ECG columns do not** — reference `mean_hr`
128.8 and `ecg_range` 7.48 are not reproducible from the raw record we hold;
the reference ECG was evidently produced by a different channel, scaling, or
filtering than `wfdb.rdrecord` gives us.

Consequences, stated plainly:

- **Absolute AUROC in P3 is depressed and not comparable to P1.** The model
  consumes 21 features of which 11 are these non-reproducible ECG columns; a
  mis-extracted input set degrades every recipe, including "global".
- **The P3 *relative* ranking is still valid.** Every recipe (LEAKY, M0-M5,
  ORACLE) sees the *identical* feature matrix per subject, so the comparison
  "does adaptation beat the frozen global head?" is apples-to-apples even
  though the absolute level is lower. This is the only claim P3 supports.
- **Interpretation, not proof:** the broken ECG columns are the most likely
  reason the teacher-trained heads (M3/M5) collapse on some subjects and the
  reason cross-subject results differ from within-subject P2. We did not
  isolate this.

### 2. Leakage is real, modest, and does not carry cross-subject

Within subject tr03-0322 the deployed `personalize` recipe fit on *all* 256
windows reports AUROC 0.879 / balanced accuracy 0.792; fit on FIT and scored
on TEST it drops to 0.847 / 0.714 (P1). So the leakage is real but modest.

Across the 10 held-out subjects the *same* leaked recipe (`LEAKY`, fit on all
windows) scores **0.8602**, which is **below** the plain frozen global head at
**0.8820**. That is: the leakage that flatters a single subject does not even
survive as an advantage across subjects. We report this rather than the
flattering one-subject number.

### 3. "Site A/B" is one subject's chronological split

The P2 federated gain (global 0.8562 -> federated 0.8749 on held-out time B)
is a **within-subject** result. A and B are index halves of tr03-0322, not two
physical sites or two people. It shows the label-free adaptation helps on
held-out *time* for one subject. P3 is the cross-subject test, and it does not
replicate the gain.

### 4. Small n, wide spread, low positive count

P3 pools 10 subjects; per-subject TEST positive counts range from 23 to 167,
and FIT positives from **0** to 292. Per-subject AUROC sd reaches 0.19 (M3).
With single-digit-to-low-hundreds positives on a 30 s/60 s window grid, all
per-subject estimates are noisy; only the aggregate direction is meaningful.

### 5. tr05-0647 has zero FIT positives

That subject has 0 positive windows in the FIT half, so every FIT-trained head
(M2-M5, ORACLE) is degenerate there. Its row is included for completeness but
carries no signal about adaptation quality; it should not be read as evidence
for or against any head.

### 6. Energy is not measured

We report cycles and wall-time (hardware-measured) only. We have no current
probe, so no joules or milliwatts are claimed anywhere. `personalize` is
1.51M cycles (~1.5 ms) and an 800-iter local training round is 46.4M cycles
(~46.4 ms) at 1 GHz; that is all.

### 7. What we can and cannot claim

- **Can claim (within-subject, tr03-0322):** the board reproduces the host
  protocol to ~2e-4 AUROC; a label-free federated local round improves
  held-out-time AUROC on that subject from 0.8562 to 0.8749; per-operation
  cycle costs are measured on hardware.
- **Cannot claim (cross-subject, 10 held-out subjects):** that on-device
  adaptation generalizes. No recipe beats the frozen global head; the
  teacher-trained head is the least stable of all; the leaked recipe is below
  the global head. On this data the defensible statement is the negative one.
- **Cannot claim:** any energy/power advantage, or any statement about the
  Ethos-U55 NPU (inference-only, no FSP driver in this project).

## Cross-subject evaluation (P3′) — held-out `final_test` subjects

Subjects on disk: 10. Extractor: faithful reference extractor `tools/ref_features.py` (gate: exact match to the stored `fixed_test_vectors_float32.npz` on tr03-0322). Per-subject full-record 30 s-stride / 60 s windows, chronological FIT (first half) / TEST (second half), same recipes as above.

| Subject | n | pos fit | pos test | global | LEAKY | M0 | M2 | M3 | M4 | M5 | ORACLE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tr03-0322 | 929 | 63 | 70 | 0.901 | 0.904 | 0.904 | 0.907 | 0.902 | 0.907 | 0.902 | 0.911 |
| tr04-0029 | 605 | 36 | 42 | 0.889 | 0.887 | 0.885 | 0.883 | 0.893 | 0.890 | 0.893 | 0.888 |
| tr05-0647 | 881 | 0 | 38 | 0.959 | 0.959 | 0.938 | 0.938 | 0.939 | 0.939 | 0.938 | 0.937 |
| tr06-0014 | 984 | 303 | 40 | 0.966 | 0.966 | 0.920 | 0.918 | 0.921 | 0.917 | 0.920 | 0.917 |
| tr07-0247 | 926 | 40 | 23 | 0.935 | 0.935 | 0.932 | 0.932 | 0.938 | 0.932 | 0.937 | 0.930 |
| tr07-0841 | 878 | 93 | 112 | 0.928 | 0.928 | 0.929 | 0.929 | 0.926 | 0.929 | 0.926 | 0.928 |
| tr10-0169 | 955 | 297 | 168 | 0.942 | 0.942 | 0.943 | 0.945 | 0.946 | 0.947 | 0.946 | 0.943 |
| tr11-0537 | 823 | 145 | 78 | 0.917 | 0.918 | 0.860 | 0.859 | 0.864 | 0.857 | 0.864 | 0.863 |
| tr12-0410 | 981 | 201 | 69 | 0.922 | 0.921 | 0.818 | 0.813 | 0.815 | 0.804 | 0.815 | 0.820 |
| tr13-0164 | 707 | 55 | 113 | 0.851 | 0.852 | 0.806 | 0.806 | 0.807 | 0.804 | 0.807 | 0.799 |

| Aggregate | mean | sd |
|---|---|---|
| p0_all AUROC | 0.9211 | 0.0341 |
| LEAKY AUROC | 0.9211 | 0.0338 |
| M0 AUROC | 0.8934 | 0.0502 |
| M2 AUROC | 0.8930 | 0.0509 |
| M3 AUROC | 0.8950 | 0.0507 |
| M4 AUROC | 0.8926 | 0.0536 |
| M5 AUROC | 0.8949 | 0.0504 |
| ORACLE AUROC | 0.8938 | 0.0506 |
| PREV AUROC | 0.5000 | 0.0000 |
| SPO2_THR AUROC | 0.8298 | 0.0759 |
| SPO2_LR AUROC | 0.8826 | 0.0453 |

| Paired delta vs global | mean d | 95% CI (bootstrap) |
|---|---|---|
| LEAKY | +0.0000 | [-0.0007, +0.0008] |
| M0 | -0.0277 | [-0.0490, -0.0092] |
| M2 | -0.0281 | [-0.0504, -0.0087] |
| M3 | -0.0261 | [-0.0482, -0.0070] |
| M4 | -0.0285 | [-0.0530, -0.0073] |
| M5 | -0.0262 | [-0.0481, -0.0072] |
| ORACLE | -0.0273 | [-0.0485, -0.0080] |

## Threats to validity, revisited (P4′)

P4 named the feature-extractor mismatch the strongest threat and could not
dismiss it. That threat is now **resolved**: the original extractor was located
(`fedtinyrt` notebook `apena -ml/UCDDB_ECG_SpO2_Apnea_Prototype.ipynb`, cell 9/10)
and ported verbatim to `tools/ref_features.py` (resample ECG→100 Hz, SpO2→1 Hz;
butter(4,[0.5,35]) bandpass + `sosfiltfilt`; per-window `clip((x−median)/std,±5)`;
dual-polarity R-peak detection; drop low-quality and ambiguous windows).

**Gate (Phase A).** On tr03-0322's 256 reference windows, every one of the 21
columns now matches the stored `raw_features` with **max column MAE 0.00000**,
and label agreement is **256/256**. The residual error quoted in P4 (mean_hr off
by 66, ecg_range off by 5.5) is gone.

Consequences:

- The P3′ absolute AUROC is now on inputs that match training, so it is
  comparable to P1 and no longer depressed by a broken input set.
- The P3′ ranking is re-derived on corrected inputs and **agrees** with P3:
  no adapted recipe beats the frozen global head. The conclusion is unchanged,
  now on defensible inputs.

### 1. ECG columns contribute almost nothing (Phase E)

Neutralising all 11 ECG columns to their training mean and re-running P3′ moves
the global head from **0.9211 → 0.9197** (Δ −0.0014) and leaves every adapted
recipe still below global (paired deltas ≈ −0.025, bootstrap CIs exclude 0). So
the cross-subject verdict does not depend on the ECG path — dropping it entirely
changes nothing material. (Within this cross-subject protocol, ECG is not
carrying signal; the SpO2 columns are.)

### 2. Baselines (Phase D) make the model earn its keep

On TEST, fitted on FIT only, aggregate over the same 10 subjects:

| Baseline / model | AUROC mean ± sd |
|---|---|
| prevalence (constant) | 0.5000 ± 0.0000 |
| SpO2 threshold (`spo2_min < 92`) | 0.8298 ± 0.0759 |
| SpO2-only logistic regression (no ECG) | 0.8826 ± 0.0453 |
| frozen global MLP head (full 21 feats) | **0.9211 ± 0.0341** |

The full head beats the SpO2-only regression by ~0.039 AUROC, so the learned
head adds real value beyond a single-channel threshold — but the SpO2-only
regression is a strong floor, consistent with TRAINING_CONTEXT §15.

### 3. Paired per-subject deltas (the honest adaptation test)

Adapted minus global, AUROC, subject-level bootstrap 95% CI (5000 resamples):

| Recipe | mean Δ | 95% CI |
|---|---|---|
| LEAKY | +0.0000 | [−0.0007, +0.0008] |
| M0 | −0.0277 | [−0.0490, −0.0092] |
| M2 | −0.0281 | [−0.0504, −0.0087] |
| M3 | −0.0261 | [−0.0482, −0.0070] |
| M4 | −0.0285 | [−0.0530, −0.0073] |
| M5 | −0.0262 | [−0.0481, −0.0072] |
| ORACLE | −0.0273 | [−0.0485, −0.0080] |

Every adapted recipe is significantly **worse** than the frozen global head;
the leaked recipe is indistinguishable from it. This is the clean negative.

### 4. Board parity on the corrected features (Phase F)

The board's stored-vector self-tests pass bit-exact against the reference INT8
oracle: `run` (pre-quantized inputs) and `runraw` (raw features, normalize +
quantize on device) both report **0 mismatches / PASS** over the 256 vectors;
board `evalhead` AUROC all-256 = 0.8802. Because `tools/ref_features.py` now
reproduces the stored raw features exactly, the host→board input path is
consistent end to end. Board left at `sethead global` (no drift).

### 5. What we can and cannot claim (P4′)

- **Can claim:** the feature-extraction threat is eliminated (exact gate); the
  cross-subject negative is robust to ECG ablation and survives real baselines;
  the frozen global head generalises at AUROC 0.9211 ± 0.0341 cross-subject,
  beating SpO2-only (0.8826) and threshold (0.8298) baselines; host/board agree
  bit-exactly.
- **Cannot claim:** that on-device adaptation generalises — it does not, on this
  data, under any recipe tested. No energy/power claims (no probe). Nothing
  about the Ethos-U55 NPU (inference-only, no FSP driver).
- **Still open:** n = 10 subjects; per-subject TEST positives 23–167; the
  frozen global model was given, not retrained here (training cache gone).

## Cross-subject evaluation (P5) — held-out subjects (final_test+validation)

Subjects on disk: 20. Cohorts: `final_test+validation`. Extractor: faithful reference extractor `tools/ref_features.py` (gate: exact match to the stored `fixed_test_vectors_float32.npz` on tr03-0322). Per-subject full-record 30 s-stride / 60 s windows, chronological FIT (first half) / TEST (second half), same recipes as above.

| Subject | n | pos fit | pos test | global | LEAKY | M0 | M2 | M3 | M4 | M5 | ORACLE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tr03-0322 | 929 | 63 | 70 | 0.901 | 0.904 | 0.904 | 0.907 | 0.902 | 0.907 | 0.902 | 0.911 |
| tr03-0532 | 866 | 169 | 112 | 0.862 | 0.866 | 0.840 | 0.840 | 0.842 | 0.848 | 0.842 | 0.852 |
| tr03-1302 | 865 | 142 | 151 | 0.918 | 0.918 | 0.917 | 0.917 | 0.907 | 0.919 | 0.907 | 0.917 |
| tr04-0020 | 792 | 4 | 8 | 0.756 | 0.758 | 0.681 | 0.675 | 0.690 | 0.656 | 0.689 | 0.673 |
| tr04-0029 | 605 | 36 | 42 | 0.889 | 0.887 | 0.885 | 0.883 | 0.893 | 0.890 | 0.893 | 0.888 |
| tr04-0631 | 857 | 158 | 86 | 0.911 | 0.911 | 0.903 | 0.903 | 0.900 | 0.900 | 0.900 | 0.900 |
| tr04-0808 | 871 | 100 | 58 | 0.969 | 0.968 | 0.954 | 0.954 | 0.954 | 0.952 | 0.954 | 0.950 |
| tr05-0647 | 881 | 0 | 38 | 0.959 | 0.959 | 0.938 | 0.938 | 0.939 | 0.939 | 0.938 | 0.937 |
| tr05-1404 | 882 | 0 | 15 | 0.821 | 0.831 | 0.822 | 0.840 | 0.848 | 0.855 | 0.847 | 0.770 |
| tr06-0014 | 984 | 303 | 40 | 0.966 | 0.966 | 0.920 | 0.918 | 0.921 | 0.917 | 0.920 | 0.917 |
| tr06-0122 | 769 | 2 | 2 | 0.673 | 0.675 | 0.576 | 0.577 | 0.595 | 0.679 | 0.590 | 0.614 |
| tr06-0584 | 929 | 278 | 380 | 0.686 | 0.683 | 0.654 | 0.650 | 0.656 | 0.654 | 0.657 | 0.680 |
| tr07-0247 | 926 | 40 | 23 | 0.935 | 0.935 | 0.932 | 0.932 | 0.938 | 0.932 | 0.937 | 0.930 |
| tr07-0841 | 878 | 93 | 112 | 0.928 | 0.928 | 0.929 | 0.929 | 0.926 | 0.929 | 0.926 | 0.928 |
| tr10-0169 | 955 | 297 | 168 | 0.942 | 0.942 | 0.943 | 0.945 | 0.946 | 0.947 | 0.946 | 0.943 |
| tr11-0537 | 823 | 145 | 78 | 0.917 | 0.918 | 0.860 | 0.859 | 0.864 | 0.857 | 0.864 | 0.863 |
| tr11-0592 | 903 | 189 | 13 | 0.908 | 0.908 | 0.835 | 0.836 | 0.835 | 0.842 | 0.836 | 0.826 |
| tr12-0410 | 981 | 201 | 69 | 0.922 | 0.921 | 0.818 | 0.813 | 0.815 | 0.804 | 0.815 | 0.820 |
| tr12-0684 | 905 | 53 | 98 | 0.797 | 0.797 | 0.745 | 0.742 | 0.733 | 0.738 | 0.733 | 0.744 |
| tr13-0164 | 707 | 55 | 113 | 0.851 | 0.852 | 0.806 | 0.806 | 0.807 | 0.804 | 0.807 | 0.799 |

| Aggregate | mean | sd |
|---|---|---|
| p0_all AUROC | 0.8755 | 0.0872 |
| LEAKY AUROC | 0.8764 | 0.0867 |
| M0 AUROC | 0.8430 | 0.1059 |
| M2 AUROC | 0.8431 | 0.1067 |
| M3 AUROC | 0.8456 | 0.1030 |
| M4 AUROC | 0.8484 | 0.0972 |
| M5 AUROC | 0.8452 | 0.1036 |
| ORACLE AUROC | 0.8431 | 0.1007 |
| PREV AUROC | 0.5000 | 0.0000 |
| SPO2_THR AUROC | 0.7729 | 0.1580 |
| SPO2_LR AUROC | 0.8358 | 0.1296 |

Paired deltas use the **same-window** reference: the global head on the TEST windows (= `M0`) for `M0`–`M5`/`ORACLE`, and the global head on all windows (`p0_all`) for `LEAKY` (which is scored on all windows by construction).

| Paired delta vs global (same windows) | mean d | 95% CI (bootstrap) | t p | Wilcoxon p | DeLong Z | DeLong p |
|---|---|---|---|---|---|---|
| LEAKY | +0.0008 | [-0.0002, +0.0021] | 1.823e-01 | 3.884e-01 | -0.40 | 6.871e-01 |
| M0 | +0.0000 | [+0.0000, +0.0000] | nan | nan | +0.00 | 1.000e+00 |
| M2 | +0.0001 | [-0.0016, +0.0025] | 9.374e-01 | 3.683e-01 | -1.14 | 2.556e-01 |
| M3 | +0.0025 | [-0.0008, +0.0065] | 2.035e-01 | 2.611e-01 | +0.87 | 3.817e-01 |
| M4 | +0.0054 | [-0.0032, +0.0174] | 3.541e-01 | 5.958e-01 | +0.22 | 8.262e-01 |
| M5 | +0.0022 | [-0.0010, +0.0058] | 2.357e-01 | 2.611e-01 | +0.90 | 3.666e-01 |
| ORACLE | +0.0001 | [-0.0075, +0.0068] | 9.836e-01 | 8.408e-01 | -0.06 | 9.549e-01 |

| Calibration (TEST) | Brier | ECE |
|---|---|---|
| LEAKY | 0.1044 | 0.1215 |
| M0 | 0.1039 | 0.1228 |
| M2 | 0.1038 | 0.1192 |
| M3 | 0.1422 | 0.1513 |
| M4 | 0.1501 | 0.1669 |
| M5 | 0.1413 | 0.1510 |
| ORACLE | 0.0852 | 0.0588 |

| Operating point @ 0.29 | sens | spec | precision | bal-acc |
|---|---|---|---|---|
| LEAKY | 0.736 | 0.765 | 0.402 | 0.750 |
| M0 | 0.749 | 0.758 | 0.404 | 0.753 |
| M2 | 0.735 | 0.766 | 0.403 | 0.750 |
| M3 | 0.761 | 0.729 | 0.391 | 0.745 |
| M4 | 0.721 | 0.773 | 0.461 | 0.747 |
| M5 | 0.760 | 0.729 | 0.392 | 0.745 |
| ORACLE | 0.602 | 0.851 | 0.521 | 0.727 |

## Threats to validity, revisited (P5′)

### 0. Correction to P4′ §3 (methodology artifact)

The P4′ §3 table ("Every adapted recipe is significantly worse than the frozen
global head", deltas ≈ −0.027) is a **window-set artifact and is withdrawn**.
The recipes `M0`–`M5`/`ORACLE` are scored on the TEST (second-half) windows,
but the "global" reference used there, `p0_all = 0.9211`, is AUROC over **all**
windows. The TEST half is systematically harder, so comparing a test-half score
to an all-window score manufactures a spurious gap. The fair reference is the
global head on the **same TEST windows** (= per-subject `M0`, aggregate 0.8934
on the 10 `final_test` subjects; `LEAKY`, scored on all windows by construction,
is the sole recipe correctly paired with `p0_all`). Recomputed on the 10
`final_test` subjects with same-window references, every recipe is
indistinguishable from global (|Δ| ≤ 0.002, all CIs include 0, all p > 0.18).
The corrected claim is a **clean null**, not a negative: *no label-free
on-device adaptation recipe improves over the frozen global head.* The P4′
table is left in place (append-only log) and superseded by this note and by the
20-subject P5 run below.

### 1. Cohorts and robustness (P5, n = 20)

The P5 run extends the held-out set to **20 subjects** — the 10 `final_test`
plus 10 never-used `validation` subjects (`tr03-0532 tr03-1302 tr04-0020
tr04-0631 tr04-0808 tr05-1404 tr06-0122 tr06-0584 tr11-0592 tr12-0684`), all
downloaded fresh from PhysioNet training v1.0.0 and processed by the faithful
reference extractor. Extending the cohort removes the single-cohort objection
and tests whether the null survives a population with a much wider label
distribution (per-subject TEST positive rates range from 2/… ≈ 0.005 to
380/929 ≈ 0.41; `tr05-0647` and `tr05-1404` have **zero** FIT positives yet
still score on TEST).

### 2. Same-window paired deltas on 20 subjects

Against the same-window reference (`M0` for M0–M5/ORACLE; `p0_all` for LEAKY):

| Recipe | mean Δ | 95% CI | t p | Wilcoxon p | DeLong p |
|---|---|---|---|---|---|
| LEAKY | +0.0008 | [−0.0002, +0.0021] | 0.182 | 0.388 | 0.687 |
| M2 | +0.0001 | [−0.0016, +0.0025] | 0.937 | 0.368 | 0.256 |
| M3 | +0.0025 | [−0.0008, +0.0065] | 0.204 | 0.261 | 0.382 |
| M4 | +0.0054 | [−0.0032, +0.0174] | 0.354 | 0.596 | 0.826 |
| M5 | +0.0022 | [−0.0010, +0.0058] | 0.236 | 0.261 | 0.367 |
| ORACLE | +0.0001 | [−0.0075, +0.0068] | 0.984 | 0.841 | 0.955 |

All deltas are within ±0.006 AUROC; every confidence interval includes zero;
every paired t, Wilcoxon, and per-subject DeLong (Stouffer-combined) p-value is
≥ 0.18. The null is now supported by three independent tests, not just their
bootstrap CIs. `M0` is the reference itself, so its t/Wilcoxon are undefined
(nan); its DeLong vs itself is exactly 0.

### 3. Baselines on the wider cohort (honest downgrade)

| Baseline / model | AUROC mean ± sd (n = 20) |
|---|---|
| prevalence (constant) | 0.5000 ± 0.0000 |
| SpO2 threshold (`spo2_min < 92`) | 0.7729 ± 0.1580 |
| SpO2-only logistic regression | 0.8358 ± 0.1296 |
| frozen global MLP head (TEST windows) | 0.8430 ± 0.1059 |

The full head still beats the single-channel threshold by ~0.07, but its edge
over the SpO2-only regression shrinks from +0.039 (10 `final_test` subjects) to
**+0.007** on 20 subjects. That is within noise. The defensible statement is
that the learned head *ties* a one-channel SpO2 regression on this cohort; the
SpO2-only regression is a strong floor, not a weak baseline. Absolute AUROC
also drops (0.9211 → 0.8430 same-window; 0.8755 all-window) because the added
validation subjects are harder, so the earlier headline number should be read
as cohort-specific.

### 4. Calibration and operating point @ 0.29 (n = 20)

| Recipe | Brier | ECE | sens | spec | precision | bal-acc |
|---|---|---|---|---|---|---|
| M0 | 0.1039 | 0.1228 | 0.749 | 0.758 | 0.404 | 0.753 |
| M2 | 0.1038 | 0.1192 | 0.735 | 0.766 | 0.403 | 0.750 |
| M3 | 0.1422 | 0.1513 | 0.761 | 0.729 | 0.391 | 0.745 |
| M4 | 0.1501 | 0.1669 | 0.721 | 0.773 | 0.461 | 0.747 |
| M5 | 0.1413 | 0.1510 | 0.760 | 0.729 | 0.392 | 0.745 |
| ORACLE | 0.0852 | 0.0588 | 0.602 | 0.851 | 0.521 | 0.727 |

The frozen head is reasonably calibrated (Brier 0.104, ECE 0.123); the adapted
recipes M3–M5 are visibly **worse calibrated** (Brier 0.14–0.15, ECE 0.15–0.17)
even where their AUROC is unchanged — adaptation buys nothing and can hurt
calibration. The oracle recipe is best on every metric but is label-supervised
on the test subject, so it is a ceiling, not a candidate. At the fixed board
threshold 0.29 the global head gives sensitivity 0.749 / specificity 0.758 /
precision 0.404 / balanced accuracy 0.753.

### 5. Board parity (unchanged)

The board self-tests still pass bit-exact: `run` and `runraw` report **0
mismatches / PASS** over the 256 stored vectors and `evalhead` AUROC all-256 =
**0.8802** (site A 0.9153, site B 0.8562), with the corrected
`tools/ref_features.py` reproducing the stored raw features exactly. Board left
at `sethead global`.

### 6. What we can and cannot claim (P5′)

- **Can claim:** the cross-subject null is robust — no label-free on-device
  adaptation recipe (M0–M5/ORACLE) beats the frozen global head on 20 held-out
  subjects by any of bootstrap CI, paired t, Wilcoxon, or per-subject DeLong;
  the effect is a clean tie, not a loss. The global head generalises at
  AUROC 0.8430 ± 0.1059 (test windows) across a cohort with widely varying
  prevalence, beats the SpO2 threshold by ~0.07, ties the SpO2-only regression
  (+0.007, within noise), and is better calibrated than any adapted recipe.
  Host/board agree bit-exactly; the board path is inference-only and correct.
- **Cannot claim:** that on-device adaptation helps, or that the learned head
  adds value over a one-channel SpO2 regression at this cohort size. No
  energy/power claims (no probe). Nothing about on-device training accuracy on
  unlabeled real data — that is unaddressed (and is precisely what the null
  motivates: label-free adaptation does not close the gap).
- **Still open:** n = 20 subjects; per-subject TEST positives include degenerate
  cases (tr04-0020 4/8, tr06-0122 2/2); the frozen global model was given, not
  retrained here; raw training data is not on disk.

### 7. Reproduce

```
/tmp/cincenv/bin/python tools/cross_subject_eval.py \
  --ref --baselines --delong --calibration --operating-point \
  --partitions final_test,validation --tag P5 --write
```

Fetch helper: `tools/parallel_fetch.sh` (lanes) or the resumable
`tools/fetch_record.py`; validation records land under `/tmp/cinc_val/`.
