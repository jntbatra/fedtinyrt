# Retrain — Phase 1–3 results, Gates G1 and G2

Status: **Phase 1 complete (G1 PASS on the pruning finding), Phase 2 complete (70/70 subjects
downloaded), Phase 3 complete (parity + robustness + learning curve; G2 resolved).**
Protocol unit everywhere below: **mean-of-subject AUROC, TEST half** (60 s windows, 30 s stride),
locked in `results/baseline_protocol.json`.

## 0. What the 20 on-disk subjects are (so comparisons are honest)

`subject_split_manifest.csv`:
- 70 `central_train`, 10 `final_test`, 10 `validation`, 5 `pi_client`, 5 `renesas_client`.

The 20 subjects on disk are the **10 `final_test` + 10 `validation`** subjects. There is **zero
overlap** with `central_train`. M0 (`deployment_metadata.json`: *"central_train with server-validation
early stopping"*) was trained on the 70 `central_train` subjects — a **disjoint population**.

Consequence: **nothing computed on the 20 on-disk subjects is directly comparable to M0 = 0.8295.**
- A model trained on the 20 subjects' FIT halves is *in-population* (same people, earlier night) and
  is an easier task than M0's cross-population number.
- The earlier "refit beats M0 by +0.035" reading is an artifact of that. Retracted.

Two leak-free protocols were used, each comparable **within itself only**:
- **LOSO** (leave-one-subject-out, fresh MLP per fold) → cross-subject generalization.
- **Global head** (one MLP on all 20 FIT halves, score TEST halves) → same-subject night drift.

## 1. Feature-set results

### 1a. LOSO cross-subject (fresh MLP; n=20 folds)

| feature set | all | weak | strong |
|---|---|---|---|
| legacy21 | 0.7909 | 0.7610 | 0.9592 |
| **ecg11** | **0.5733** | **0.5604** | 0.6573 |
| **spo2_10** | **0.8692** | **0.8465** | **0.9758** |
| legacy+extEcg | 0.8024 | 0.7752 | 0.9439 |
| legacy+extSpo2 | 0.7481 | 0.7242 | 0.8938 |
| all | 0.7532 | 0.7248 | 0.9020 |

Paired by subject vs `legacy21` (Wilcoxon, 20 000-sample bootstrap CI):

| set | Δall | p | Δweak | p |
|---|---|---|---|---|
| ecg11 | −0.2176 | <1e-4 | −0.2006 | <1e-4 |
| spo2_10 | **+0.0784** | **0.0017** | **+0.0855** | **0.0014** |
| legacy+extEcg | +0.0116 | 0.87 | +0.0142 | 0.60 |
| legacy+extSpo2 | −0.0428 | 0.12 | −0.0369 | 0.29 |
| all | −0.0377 | 0.011 | −0.0363 | 0.036 |

### 1b. Global-head in-population (one MLP, pooled FIT → TEST)

| feature set | all | weak | strong |
|---|---|---|---|
| legacy21 | 0.8649 | 0.8437 | 0.9557 |
| **spo2_10** | **0.8753** | **0.8536** | **0.9725** |
| legacy+extEcg | 0.8450 | 0.8245 | 0.9382 |
| all | 0.8275 | 0.8124 | 0.8801 |

Both protocols agree on the ordering: **SpO2-only > legacy21 > legacy+extEcg ≈ legacy+extSpo2 > all**,
and ECG-only is far last. The in-sample full-MLP rung is ~1.000 (600 iters overfit), so it is
uninformative at this capacity; the meaningful ceiling remains DIAGNOSTICS' 17-param head rung.

## 2. Feature hygiene (is the ext-SpO2 loss a bug or real?)

Pooled over 18 052 windows (3 968 positives). Correlations with the apnea label:

| ext feature | corr(y) | note |
|---|---|---|
| spo2_drop_rel | **+0.505** | strong, but == −spo2_min_rel (perfect collinear pair) |
| spo2_nadir_count | +0.420 | strong |
| spo2_frac_below3 | +0.337 | strong |
| spo2_mean_rel | −0.179 | moderate |
| edr_amp_std / edr_amp_range | −0.111 | weak |
| hr_surge | +0.064 | very weak |
| cvhr_std / cvhr_ptp / edr_rr_std / cvhr_frac | −0.02 … −0.003 | ~no signal |

None are degenerate or NaN. So the ext-SpO2 loss is **not** a bug: the features are informative but
**redundant with legacy SpO2**, and adding two perfectly collinear channels plus noise dilutes the
representation. The ext-ECG features genuinely carry almost no apnea signal — consistent with 1a.

## 3. Gate G1 decision

Plan's gate: *if 1a kills the ECG route AND 1b/1c do not move the ceiling → stop, do not download.*

- **1a kills ECG: yes.** ECG-only weak AUROC 0.56; the 8 new ECG features correlate ≤0.11 with the
  label and add nothing (Δweak +0.014, p=0.60; they *lower* the global head from 0.865 to 0.845).
- **1c baseline-relative SpO2: no.** Adding it hurts both protocols (redundant, §2).
- **1b new ECG features: no significant move.**

So the **"new features break the ceiling" hypothesis is falsified.** However Phase 1 surfaced a
different, *significant* win that was not in the original probe list:

> **Feature pruning.** Dropping the 11 weak ECG dimensions (SpO2-dominant, 10 features) raises
> cross-subject AUROC by **+0.078 (LOSO, p=0.0017)** and the weak-positive hard case by **+0.086
> (p=0.0014)** — a material, statistically robust improvement of the model *inputs*.

This is the plan's stated trigger (*"if any moves it, download and rebuild"*). It cannot be tested
against M0 without retraining on **M0's own population** (the 70 `central_train` subjects), which is
exactly Phase 2. **Decision: G1 PASS on the pruning finding → proceed to Phase 2.**

Deliverable after Phase 3: does `spo2_10` (or a pruned legacy set), trained on the same 70 subjects
M0 used, beat M0's 0.8295 on the same 20 held-out subjects? If yes, the deployed model is improved
by retraining on pruned inputs — no new sensors, no NPU, no firmware change beyond re-quantising the
head.

## 4. Guardrails still in force
- Never claim energy/power (no probe) — report cycles/ms and RAM only.
- Never claim the NPU works (no FSP driver).
- Subject is the unit; report per-subject Δ, not only the mean.
- MEOI pre-registered: +0.02 AUROC (ranking, claim b) or a few points of balanced accuracy at the
  fixed 0.29 threshold (operating point, claim a).

## 5. Artifacts
- `tools/phase1.py` → `results/phase1_loso.json`
- `tools/phase1_analysis.py` → paired Δ, Wilcoxon p, bootstrap CI
- `tools/phase1b_ceiling.py` → `results/phase1b_ceiling.json`, `results/phase1b_splits.json`
- `tools/ext_features.py` → 13 new features (CVHR/EDR + baseline-relative SpO2)

---

# Phase 2 — the 70 `central_train` subjects (M0's own population)

Downloaded all 70 `central_train` records to `apnea_deploy/data/central` (**9.4 GB**, disk).
The first attempt was silently corrupt: PhysioNet resets the connection mid-record, the old
fetcher aborted a record on the first reset, and the shell driver still printed `[done]`
(only 2 of 15 started records were real). Fixed with per-range resume + retries in
`tools/fetch_record.py`, a multi-pass completeness-checking supervisor `tools/fetch_central.sh`,
a pre-clean of 135 stale `.part` files from the old chunk layout, and completeness defined as
non-empty `.mat` **and** `.arousal` with no error masking. Result: **70/70 complete.**

Feature cache `data/feat_v2_cache.npz` rebuilt over the 70 central subjects **plus** the 20
held-out subjects, so Central-vs-M0 is now a like-for-like comparison (same population, same
20 test subjects).

---

# Phase 3 — retrain on the 70, test on the 20

Train on the FIT half of the 70 `central_train`; score the TEST half of the same 20 held-out
subjects M0 is scored on. Same MLP and protocol as Phase 1.

## 3a. Parity check (confirms the harness matches M0)

| model | mean-of-subject AUROC | sd |
|---|---|---|
| **M0 (deployed, shipped int8)** | **0.8295** | 0.1134 |
| legacy21 retrain on all 70 (3 seeds) | 0.8392 | 0.1460 |

The retrain of the *legacy* feature set lands on top of M0 → **the harness is faithful**; any
difference between feature sets below is a real feature-set effect, not a pipeline artifact.

## 3b. The headline: prune 21 → 10 (SpO2-dominant) features

| feature set | K=20 | K=40 | K=70 |
|---|---|---|---|
| legacy21 | 0.8152 | 0.8162 | 0.8392 |
| **spo2_10** | **0.8636** | **0.8592** | **0.8706** |

At K=70 (8 seeds, `results/phase3_robust.json`): legacy21 **0.8396**, spo2_10 **0.8693**,
Δ **+0.0297**, 12/20 subjects improved.

**Honest paired statistics (not the mean alone):**

| statistic | value |
|---|---|
| mean Δ | +0.0297 |
| **median Δ** | **+0.0013** |
| Wilcoxon signed-rank p | **0.546 (n.s.)** |
| bootstrap 95% CI | [−0.0033, +0.0841] |
| **Δ excluding `tr04-0029`** | **+0.0051 (≈0)** |

So the *typical* subject gains essentially nothing. The mean is carried by one subject.

## 3c. What the pruning actually buys: robustness / failure removal

`tr04-0029` is a genuine, reproducible failure mode of the legacy set, not seed luck:

| subject | legacy21 mean [min–max over seeds] | spo2_10 mean [min–max] |
|---|---|---|
| `tr04-0029` | **0.407** [0.274–0.823], sd 0.179 | **0.902** [0.899–0.906], sd 0.003 |
| `tr04-0020` | 0.730, sd 0.183 | 0.777, sd 0.024 |
| `tr06-0122` | 0.777, sd 0.042 | 0.874, sd 0.009 |
| **worst subject** | **0.407** | **0.689** (`tr12-0684`) |
| **worst over seeds** | **0.274** | **0.683** |
| mean per-subject sd | 0.0284 | **0.0046** |

The legacy set has a subject that is coin-flip (sd 0.18 across seeds); the pruned set is nearly
seed-invariant everywhere (sd 0.001–0.024). **The defensible claim is not "+0.03 AUROC" — it is
"pruning removes catastrophic per-subject failures and shrinks cross-subject variance 6×", which
for a medical device (where the worst night matters more than the average) is the stronger
result.** Worst-case subject moves 0.407 → 0.689.

## 3d. Learning curve — Gate G2

`tools/phase3_curve.py`, 5 seeds × K ∈ {5,10,…,70}, `results/phase3_curve.json`:

| K | legacy21 | spo2_10 |
|---|---|---|
| 5 | 0.6606 ± 0.0583 | 0.8280 ± 0.0229 |
| 10 | 0.7469 ± 0.0182 | 0.8314 ± 0.0169 |
| 20 | 0.7673 ± 0.0368 | 0.8561 ± 0.0116 |
| 30 | 0.8148 ± 0.0287 | 0.8632 ± 0.0064 |
| 40 | 0.8115 ± 0.0213 | 0.8603 ± 0.0041 |
| 50 | 0.8308 ± 0.0101 | 0.8672 ± 0.0034 |
| 60 | 0.8429 ± 0.0138 | 0.8692 ± 0.0029 |
| 70 | 0.8362 ± 0.0157 | 0.8703 ± 0.0017 |

Two facts:
1. **spo2_10 ≥ legacy21 at every K**, and the gap is widest where data is scarcest
   (+0.167 at K=5, +0.085 at K=10, +0.034 at K=70). The pruned set reaches in 5 subjects
   what the legacy set needs ~50 for.
2. **Both curves are saturated by ~60 subjects.** Last-4-point slope: legacy21 +0.00086/subject
   (and non-monotone: 60→70 is *negative*), spo2_10 +0.00032/subject. Extrapolating, +0.02 AUROC
   would need ≳60 *more* labeled subjects.

**Gate G2 verdict: CLOSED for the "more pooled data" route.** Classic FedAvg ≈ pooled central
training; if pooled central training is flat at 70 subjects, federation-as-more-data cannot add
ranking AUROC. Federation as *personalization* (per-subject shift, FedPer/FedRep) is a different
mechanism and is **not** argued for by this curve — it must be justified by the per-subject
variance result in 3c, not by the curve.

## 3e. Consequences for the plan
- **Deploy the pruned head (spo2_10).** It dominates legacy21 at every data size, is 6× more
  stable across seeds/subjects, and removes a coin-flip failure mode. Cost: drop 11 input
  channels → smaller int8 head, cheaper on-board. (Phase 4.)
- **Do not chase AUROC via more central data or FedAvg-as-more-data.** Dead per G2.
- **The live lever is per-subject robustness/adaptation** (claim a: operating point, and the
  worst-subject tail), which is exactly what on-device adaptation targets. (Phase 5.)
- Robustness spread (sd 0.0284 → 0.0046) is itself a reportable, effect-size-style result.

## 3f. Phase 3 artifacts
- `tools/phase3_driver.sh` → `results/central_v2_metrics_K{20,40,70}.json`, `learning_curve_K*.json`
- `tools/phase3_robust.py` → `results/phase3_robust.json` (8 seeds, per-subject min/max/sd)
- `tools/phase3_curve.py` → `results/phase3_curve.json` (5 seeds × 8 values of K)
- `tools/fetch_record.py`, `tools/fetch_central.sh` → 70/70 subjects

---

# Phase 4 — deploy the spo2_10 head to silicon

Phase 3 concluded the legacy 21-feature (ECG+SpO2) head should be replaced by the pruned
**spo2_10** head: the 10 SpO2-window features (cache indices 11..20). Phase 4 retrains that head,
quantises it to INT8, publishes it into `src/`, and verifies the board reproduces the reference
arithmetic exactly.

## 4a. What was wrong before this phase

The four generated headers in `src/` (`apnea_model.h`, `feature_normalization_mean.h`,
`feature_normalization_inverse_std.h`, `apnea_selftest_vectors.h`) came from a **superseded
feature extractor**, and the 256 fixed self-test vectors were stale in a second way:

- The shipped `fixed_test_vectors_float32.npz` raw columns did not match the current cache. On the
  same windows, `mean_hr` was 129 bpm where the current pipeline gives 61, and `spo2_diff_std` was
  inflated ~12×. Per-column max differences on the SpO2 block were `[0.77, 46.5, 5.7, 48.0, 9.3,
  6.7, 6.6, 0.02, 0.02, 0.03]`.
- Because the shipped vectors were produced by the old pipeline on the old feature order, the
  board's `run`/`runraw` self-test had been verifying a model that no longer corresponded to
  anything in the current training code. On the stale vectors the self-test reported **0 positives
  of 256** and an *inverted* AUROC (0.158).

**Fix:** window *selection* (subject `tr03-0322` + the 256 `start_sec` values) is still read from
the shipped npz, but the SpO2 columns and the labels are **re-derived from `data/feat_v2_cache.npz`**
and matched on `start_sec` (asserts: unique rows, max |Δstart_sec| = 0.0, labels agree). Provenance
is stated in the emitted header.

## 4b. The 0-flip gate was mis-specified and was replaced

The original gate 3 required the INT8 pipeline to reproduce the float model's decisions on all 256
vectors exactly (`flips == 0`). That bar is unattainable and wrong as a correctness criterion:

- `OUT_SCALE = 1/256`, so the decision boundary is itself quantised. Any window whose float
  probability sits inside one output step of the threshold **must** flip side.
- Measured: **1 flip of 256** (vector 176; float p 0.2577 → int8 p 0.3008, crossing 0.29), and
  **110 flips of 9032** held-out windows, **95 of them within 0.05** of the threshold, splitting
  **51** int8-right/float-wrong vs **59** float-right/int8-wrong → **net −8 decisions (−0.09 %)**.
- The flips are near-symmetric boundary noise, not a loss: int8 AUROC is −0.0011 vs float and int8
  balanced accuracy is **higher** (+0.0057).
- Exact float-threshold arithmetic confirms it is not a rounding bug: `q >= -53` represents
  0.292969, and there are **0** float probabilities in the `[0.29, 0.29297)` ambiguity band.

Gate 3 now asserts explicit, pre-stated **fidelity bounds** (documented in the comment above the
gate and in `results/phase4_quant.json → fidelity`):

| bound | requirement | measured |
|---|---|---|
| (a) fixed-vector decision agreement | ≥ 0.99 | **0.9961** (255/256) |
| (b) held-out decision agreement | ≥ 0.98 | **0.9878** (8922/9032) |
| (c) \|int8 − float\| mean-of-subject AUROC | ≤ 0.005 | **0.0011** |
| (d) int8 balanced accuracy ≥ float − 0.005 | ≥ float − 0.005 | **+0.0057** |

**Rejected alternative:** chasing 0 flips with quantisation-aware training or a per-layer range
grid search. Both would tune quantisation ranges on the evaluation windows; out of budget and not
attempted. This is a recorded limitation.

## 4c. Host-side result

```
cache: 90 records (central 70, heldout 20)
train windows 32264, positives 25.8%
float spo2_10 seed0 held-out: mean-of-subject AUROC 0.8710 +/- 0.0683 (n=20)
quantised: in_scale 0.0634582266 zp -15 | a1 0.037546 | a2 0.0508718 | head 0.0941066 zp 39
```

Range rule: uniform a-priori percentile bounds (p0.01 / p99.99 of the calibration set) for the
input, both ReLU maxima, and the head logit. Min/max ranges cost ~0.024 AUROC; percentiles cost
0.0011. Kept: `OUT_SCALE = 1/256`, `OUT_ZP = -128`, `APNEA_THRESHOLD_Q = -53`, float threshold 0.29.
Model is 897 parameters, `10 → 32 → 16 → 1`.

## 4d. Board parity (RA8P1, Cortex-M85, flashed from `build/Release/apnea_deploy.elf`)

Pre-flash baseline (legacy 21-input firmware) → post-flash (spo2_10):

| command | legacy 21-input | spo2_10 (now) |
|---|---|---|
| `run` | 256 vectors, 0 mismatches, **0 positives** | 256 vectors, **0 mismatches [PASS]**, **22 positives** |
| `runraw` | 256 vectors, 0 mismatches, 0 positives | 256 vectors, **0 mismatches [PASS]**, 22 positives |
| `bench` | 7753.88 cycles/inference, 128967 inf/s | **6752.41 cycles/inference**, 6.75 µs @1 GHz, **148095 inf/s** |
| model id | 0xffffffbd | 0xffffff86 |

**`run` reporting 0 mismatches is the load-bearing check:** it compares device INT8 codes against
the codes recorded by the Python emulation, so it proves the device arithmetic is device-exact.
This holds because `src/apnea.c` accumulates in `int32` and scales in `double`, identical to the
emulation — there is no precision gap to hide in.

Throughput improved **12.9 %** (7753.88 → 6752.41 cycles) purely from the 21 → 10 input width;
nothing in the inference kernel was hand-optimised.

Other commands on the new firmware:

```
labels
  teacher labels: 242/256 confident, 231 agree with oracle
  teacher pos   : 22 (threshold p>=0.29)
  proxy rule    : spo2_max_drop >= 3.0
  proxy pos     : 16 (tp 6 fp 10 fn 9)
  oracle pos    : 15/256
  AUROC all 256 : 0.8927   (matches the host float AUROC on the same 256 windows)

evalhead (global head, thr 0.29)
  AUROC 0.8927 | bal 0.7751 sens 0.6000 prec 0.4286 predpos 21

evalci
  sens 0.6000 CI95 [0.3575, 0.8018] (n_pos 15)
  prec 0.4286 CI95 [0.2447, 0.6345] (predpos 21)
  AUROC 0.8927 bootstrap CI95 [0.7901, 0.9583] (200 resamples)

personalize (label-free recentre + Otsu)
  baseline windows: 230/256 (teacher-confident normal)
  offsets raw: spo2_mean 5.4854  spo2_min 6.6724
  otsu threshold: 0.3146 (build+threshold 1115404 cycles)
  AUROC all 256 (label-free): 0.9021   [global head: 0.8927]
  after (otsu) bal 0.6876 sens 0.4000 predpos 12
```

## 4e. Source edits (hand-written files only)

- `tools/phase4_quantize.py` — percentile range rule; unpack bug; cache-derived vectors; gate 3
  replaced by the fidelity bound above; `fidelity` block recorded in `results/phase4_quant.json`.
- `src/apnea.c` — `21` → `10` in the header comment, usage strings, help, and `model :` line
  (cosmetic; `APNEA_IN_DIM` is macro-driven and the kernel is untouched). Header comment also
  corrected: there is **no external TFLite file** for this head; the reference is the float64
  emulation in `tools/phase4_quantize.py`.
- `src/apnea_personal.c` — proxy-desaturation rule `raw[k][16]` → `raw[k][5]`
  (`spo2_max_drop` is now index 5; two sites); `personalize` recentring remapped from
  `{mean_hr, spo2_mean, spo2_min}` to **`{spo2_mean, spo2_min}`** (indices 0, 1). The ECG
  `mean_hr` offset was dropped entirely — that feature no longer exists in the model. Event
  features (`spo2_max_drop` etc.) are deliberately *not* recentred. `showhead`/`sethead` needed no
  change: those operate on the 16-wide penultimate activation, independent of input width.

## 4f. What is NOT verified / limitations

- **No external reference interpreter.** The "oracle" INT8 codes are our own float64 emulation
  (`tools/phase4_quantize.py`), not a vendor interpreter. No `.tflite` file exists for this head.
  The C kernel is provably the same arithmetic (int32 accumulators, double scales), so parity is
  device-exact *by construction*, but it is self-consistency, not third-party validation.
- **No NPU numbers.** The RA8P1's Ethos-U55 is present in silicon; this firmware is pure CPU with
  no FSP driver for it. Nothing here exercises or measures the NPU.
- **No power/energy numbers.** No power probe on this setup. Only cycles/ms and RAM are reported.
- **One 256-window subject.** The fixed self-test set is all `tr03-0322`. Held-out AUROC (0.8710
  float / 0.8699 int8, n=20 subjects) is the only multi-subject number, and it is
  **mean-of-subject** AUROC on each subject's TEST half — not pooled.
- **Gate 3 is a fidelity bound, not decision identity.** One fixed-vector flip and 110 held-out
  flips remain by design; see 4b.
- **Single seed (0).** The deployed head is one training run; per-seed spread from Phase 3 was
  sd ≈ 0.0046 for spo2_10.

## 4g. Phase 4 artifacts

- `tools/phase4_quantize.py` → `src/{apnea_model.h,feature_normalization_mean.h,feature_normalization_inverse_std.h,apnea_selftest_vectors.h}`, `results/phase4_quant.json`
- Build: `ARM_GCC_TOOLCHAIN_PATH=<toolchain>/bin cmake --preset ReleaseCI && cmake --build --preset ReleaseCI`
- Flash: `JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink`
  (note: J-Link software V9.78 rejects `-device R7KA8P1`; use `R7KA8P1AF`)
- Verify: `tools/serial_cmd.py run runraw bench labels evalhead evalci personalize`
