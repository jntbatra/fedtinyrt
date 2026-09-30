# Consultation Brief v2 — On-Device Learning + Federated Learning on an Embedded Apnea Detector

**Date:** 2026-09-30
**Prepared by:** the project's own agent, for an outside model/engineer to critique.
**What I want from you:** see §11. Short version — tell me whether the null below is real or an
artifact of my experimental design, and what single change has the highest chance of producing a
*defensible* positive result.

This document is **self-contained**. You have no access to the repo. Everything you need is here.

---

## 0. Executive summary (read this if you read nothing else)

We built a small **INT8 neural-network apnea/hypopnea detector** and deployed it to a
**Renesas RA8P1** microcontroller (Arm Cortex-M85, no OS, bare metal). The research question is:

> **Can an embedded device learn from the unlabeled data it sees locally — alone, and then
> federated with other devices — and beat the frozen, centrally-trained model it shipped with?**

**The empirical answer so far is a clean null, and it is now a null on three independent axes:**

| Axis | Result |
|---|---|
| 20-subject host protocol, label-free on-device adaptation (M0–M5) | null — all \|Δ AUROC\| ≤ 0.006, every CI includes 0, every p ≥ 0.18 |
| Label-supervised **oracle** on-device (true labels, same 17 parameters) | null — +0.0146, CI [−0.004, +0.043], p = 0.77 |
| **On real silicon**, Phase 5, every route (train / fed / fedavg / fedrounds / entropy / temporal) | null — max +0.0005 AUROC vs a CI half-width of ~0.08; and **worse** at the deployed operating point |

We also **improved the base model substantially** (a feature-pruning change, +0.03 mean AUROC,
which mostly removes a catastrophic failure subject), and deployed it with bit-exact board parity.
That was a prerequisite, not the research result.

**My current explanation** is that the binding constraint is not labels, not head size, and not
federation — it is **FIT→TEST transfer (night-to-night drift)** plus an **information ceiling** in the
feature set. I have diagnostics that support this (§6, §7) but I am not certain I have not simply
built an experiment that cannot show a win. **That is the main thing I want you to attack.**

---

## 1. Hardware

| Part | Detail |
|---|---|
| Board | Renesas **RA8P1** (EK-RA8P1 class) |
| Main core | **Cortex-M85** (Helium/MVE), assumed 1 GHz for cycle→time conversion |
| Secondary core | **Cortex-M33** |
| NPU | **Arm Ethos-U55** — present in silicon, **never used**: no FSP driver integrated, firmware is pure CPU |
| Debug | On-board SEGGER J-Link over SWD, USB "Debug1" port; J-Link device string **`R7KA8P1AF`** |
| Console | SCI_B virtual COM → `/dev/ttyACM0` @ 115200 |
| FSP | Renesas Flexible Software Package **6.6.0** |
| Camera / display | A small camera and an LCD are physically attached; we ran a demo that put camera output on the LCD (project `cam2lcd/`). Not part of the ML work. |

**No OS.** There is no Linux, no scheduler, no filesystem. The firmware is a single bare-metal
image: reset vector → FSP `main()` → a serial command loop. There is no MMU and no dynamic
loading. This matters for the ML story: everything the "device" can do at runtime is code that was
compiled into the image (plus RAM state).

### 1.1 What the board can do at runtime (verified live via serial commands)

```
run / runraw      replay fixed test vectors, compare against expected INT8 codes
bench             time the inference kernel
labels            teacher-label / proxy-label diagnostics vs oracle labels
evalhead          score the active head against 256 oracle labels
evalci            evalhead + Wilson / bootstrap 95% CIs
train A|B <src>   head-only gradient descent; src = teacher | proxy | entropy | temporal
                  (entropy and temporal are label-free; teacher and proxy are not)
fed A|B <src>     local train starting from the federated head, store the result
fedavg            n-weighted FedAvg of the two stored site heads
fedrounds <R> <src>  R rounds of (local train + n-weighted FedAvg)
showhead          print the active 17-parameter head
sethead <17 floats>|global   push a head (rollback path)
cycrep            repeated timing of the training inner loop
resetoff          clear re-centring offsets, threshold back to 0.29
personalize       label-free recentre + Otsu re-threshold
```

**Critical caveat about the on-board test set:** the "sites" A and B in `train`/`fed` are an
**artificial index split of a single subject** — A = windows 0..127, B = 128..255 of subject
`tr03-0322`. The firmware itself prints `sites: index split ..., not physical`. So the on-board
self-test is **one subject, 256 windows**. Nothing measured there can satisfy the pre-registered
protocol (§5). It measures **mechanism and cost**, not deployment benefit.

---

## 2. Host toolchain (fully headless, no GUI)

| Tool | Version / location |
|---|---|
| OS | **Fedora 43** (dnf; the original "Ubuntu/apt" guide we were handed was wrong) |
| cmake | 3.31.11 |
| ninja | 1.13.1 |
| arm-none-eabi-gcc | Arm GNU Toolchain **13.2.rel1** |
| J-Link | **V9.78** (V796 from the original guide is dead) |
| RASC | Renesas RA Smart Configurator, from the FSP 6.6.0 installer, headless under `xvfb-run` |
| Host Python | `/tmp/cincenv/bin/python` (numpy 2.5.3, scipy 1.18.1, h5py, wfdb, pyserial) |
| Host CPU | i5-7500T, 4 cores, 15 GB RAM, **no GPU** |

Build/flash recipe (for reproducibility):

```bash
export ARM_GCC_TOOLCHAIN_PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
cd apnea_deploy && rm -rf build/Release
cmake --preset ReleaseCI && cmake --build --preset ReleaseCI
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink
```

Pitfalls that cost real time, in case you are reproducing: J-Link V9.78 **rejects** `-device
R7KA8P1` (must be `R7KA8P1AF`); the toolchain directory is `Rel1` with a capital R; **RASC has no
command-line "create new project"** — it only regenerates an existing `configuration.xml`, so the
"`rasc -g` makes you a project" recipe from the original guide is fiction.

---

## 3. Data

- **PhysioNet / Computing in Cardiology Challenge 2018** (apnea detection from ECG + SpO2),
  training partition, v1.0.0. ~1,000 labeled records available; **we use ~100**.
- Per record we extract **60 s windows at a 30 s stride** (50% overlap), each labeled apnea /
  non-apnea.
- Subject split: `central_train` 70, `final_test` 10, `validation` 10, `pi_client` 5,
  `renesas_client` 5.
- **20 subjects are held out** and used as the evaluation set throughout (`final_test` +
  `validation`).
- The dominant class is **weak positives** — apnea events with no deep desaturation — which turn
  out to be where all the residual error lives (§6.2).

---

## 4. Model

Feature-based MLP, quantised to INT8, executed on CPU.

| Property | v1 "legacy21" | v2 "spo2_10" (current, deployed) |
|---|---|---|
| Inputs | 21 hand-crafted ECG + SpO2 features | **10 features** (SpO2-dominant) |
| Layers | 21 → 32 → 16 → 1 | 10 → 32 → 16 → 1 |
| Parameters | 1,249 | **897** |
| Trainable on-device | final layer only (**17 params** = 16 weights + 1 bias) | same 17 params |
| Output | 1 logit → sigmoid | same |
| Quantisation | INT8 weights/activations, int32 accumulators, double scales | same |
| Deployed threshold | 0.29 (fixed) | 0.29 (fixed) |
| On-board throughput | 7,753.88 cycles/inference | **6,718.29 cycles/inference** (6.71 µs @1 GHz, 148,847 inf/s; varies ~±0.5% run to run) |

**Feature ablation (this is central to the whole story):**

| Feature set | AUROC (weak positives) | AUROC (strong positives) |
|---|---|---|
| **ECG-only (11 features)** | **0.5604** | 0.6573 |
| **SpO2-only (10 features)** | **0.8465** | 0.9758 |
| legacy 21 | 0.7610 | 0.9592 |

**The ECG contributes essentially nothing.** Functionally this model is an **SpO2 desaturation
detector**. "Did SpO2 drop?" is close to a deterministic threshold on one signal.

**The head is the only thing that adapts on-device.** The 32- and 16-wide hidden stages are frozen
in the firmware. So on-device training can only **re-weight an already-good feature set**; it
cannot learn new representations. (Nothing in the hardware forces this — 897 params + gradients +
momentum in fp32 is ~15 KB and a few thousand MACs per step, trivial for an M85. Head-only was a
design choice.)

---

## 5. Evaluation protocol

- Unit: **mean-of-subject AUROC** (AUROC computed within subject, then averaged). Subject is the
  statistical unit. This was chosen because pooled AUROC is inflated by between-subject offsets.
- Per subject: chronological **FIT (first half of the night) → TEST (second half)**. Every
  adaptation recipe is fit on FIT and scored on TEST.
- The fair reference `M0` = the **frozen head scored on the same TEST windows**.
- Statistics: paired t, Wilcoxon signed-rank, per-subject DeLong (Stouffer-combined), bootstrap
  CIs, plus calibration (Brier, 10-bin ECE) and the operating point at the deployed threshold 0.29.
- **Pre-registered minimum effect of interest (MEOI), fixed before looking at results:**
  **+0.02 AUROC** (ranking claim, "claim b") **or a few points of balanced accuracy at the fixed
  0.29 threshold** (operating-point claim, "claim a"). These two claims are kept strictly separate
  and are never conflated.

**Known protocol inconsistency I have not fully cleaned up (flag this if it matters to you):**
several numbers in circulation (0.902 SpO2-only ablation, 0.8358 SpO2 logistic regression, 0.843
frozen-on-TEST, 0.880 board `evalhead`) mix **pooled vs mean-of-subject** and different partitions.
`DIAGNOSTICS.md` §4 has a reconciliation table:

| Quantity | pooled | mean-of-subject |
|---|---|---|
| global head | 0.8715 | 0.8295 ± 0.1134 |
| SpO2-only LR | 0.8791 | 0.8436 ± 0.1070 |

The pooled-vs-mean gap is **0.042**. If that gap is real, between-subject differences carry
ranking signal my metric throws away.

---

## 6. Results timeline (what actually happened, in order)

### 6.1 The original null (20 subjects, label-free on-device adaptation)

| Model / baseline | AUROC (mean ± sd) |
|---|---|
| prevalence | 0.5000 ± 0.0000 |
| SpO2 threshold (`spo2_min < 92`) | 0.7729 ± 0.1580 |
| SpO2-only logistic regression | 0.8358 ± 0.1296 |
| **frozen global head (M0)** | **0.8430 ± 0.1059** |
| M2 / M3 / M4 / M5 (label-free adaptation) | 0.8431 / 0.8456 / 0.8484 / 0.8452 |
| **ORACLE (true labels, same 17 params)** | **0.8431 ± 0.1007** |

**Protocol note (important):** every number in this §6.1 table is produced by
`tools/cross_subject_eval.py`, which **rebuilds the 21 features from raw** and scores
mean-of-subject AUROC on the held-out subjects available at that time (n = 18–20). It is a
*different harness* from §6.2/§5, which uses the cached v2 features (`central_v2_metrics.json`)
and gives M0 = **0.8295**. So this table's "M0 = 0.8430" is **not** the same quantity as the
0.8295 deployed reference; both are mean-of-subject on overlapping-but-not-identical subject
sets and feature pipelines. Treat 0.84 and 0.83 as the *same null at two measurement
resolutions*, and quote the protocol with every AUROC.

Same-window paired Δ vs global: all \|Δ\| ≤ 0.006, every 95% CI includes 0, every test p ≥ 0.18.

**The ORACLE row is the most important number here.** True labels on the same 17 parameters buy
**nothing**. So label-freeness is not what is blocking us — labels wouldn't help this head either.
That is a strong constraint and it is why I stopped treating "get labels on-device" as the fix.

### 6.2 Diagnostics: the oracle ladder, headroom, and lag (`DIAGNOSTICS.md`, n = 18)

| Rung | AUROC | Δ vs M0 | 95% CI | Wilcoxon p |
|---|---|---|---|---|
| M0 global head | 0.8235 ± 0.1172 | — | — | — |
| ORACLE — true labels, head-only, FIT→TEST, λ=0.01 | 0.8381 ± 0.0891 | +0.0146 | [−0.004, +0.043] | 0.77 |
| **IN-SAMPLE — fit *and score* on TEST (head-only ceiling)** | **0.8736 ± 0.0681** | **+0.0501** | **[+0.009, +0.105]** | **0.007** |
| ALL-LAYERS — refit 21→32→16→1 from frozen init, FIT→TEST | 0.8177 ± 0.1256 | −0.0058 | [−0.073, +0.054] | 0.64 |

**Headroom decomposition (TEST windows):**

| Subset | n positives | AUROC |
|---|---|---|
| Strong (deep desaturation) | 212 | **0.9897 ± 0.0114** |
| **Weak (no deep desaturation)** | **1,417** | **0.8035 ± 0.1238** |
| Weak, using only `spo2_min` | 1,417 | 0.7134 ± 0.1520 |

**Lag sweep** on `spo2_min` alone, ±4 windows (±2 min):

| k | −4 | −3 | −2 | −1 | 0 | +1 | +2 | +3 | +4 |
|---|---|---|---|---|---|---|---|---|---|
| AUROC | 0.7364 | 0.7359 | 0.7360 | 0.7361 | 0.7361 | 0.7361 | 0.7362 | 0.7361 | 0.7360 |

**Lag is dead** (total spread 0.0005). A proposed "per-subject circulatory delay" personalisation
parameter has no signal in this data.

**Reading:** the head-only ceiling is +0.05 above M0 and is *statistically real* (p = 0.007), but
it is only reachable **in-sample**. The gap between the in-sample ceiling (0.8736) and the
oracle (0.8381) is the **transfer gap** — it is a night-drift problem, not a capacity problem. And
the residual error is concentrated on **weak positives** (1,417 of 1,629), which are exactly the
events SpO2 can't see.

### 6.3 The retrain (Phase 1–3): fixing the base model

Motivated by 6.2, we tested whether changing **the inputs the frozen head sees** could raise the
ceiling. Three candidate levers: baseline-relative SpO2, new ECG features (CVHR / EDR), and
shift-robust head fitting.

**Feature-set comparison, leave-one-subject-out (fresh MLP, n = 20 folds):**

| feature set | all | weak | strong |
|---|---|---|---|
| legacy21 | 0.7909 | 0.7610 | 0.9592 |
| ecg11 | 0.5733 | 0.5604 | 0.6573 |
| **spo2_10** | **0.8692** | **0.8465** | **0.9758** |
| legacy + extECG (CVHR/EDR etc.) | 0.8024 | 0.7752 | 0.9439 |
| legacy + extSpO2 (baseline-relative) | 0.7481 | 0.7242 | 0.8938 |
| all | 0.7532 | 0.7248 | 0.9020 |

Paired Δ vs legacy21: **ecg11 −0.2176 (p<1e-4)**, **spo2_10 +0.0784 (p=0.0017)**,
legacy+extEcg +0.0116 (p=0.87, n.s.), legacy+extSpO2 −0.0428 (p=0.12),
all −0.0377 (p=0.011).

**So: the new ECG features (CVHR, EDR, HR surge) did NOT help.** Feature hygiene showed why —
`cvhr_std`, `cvhr_ptp`, `edr_rr_std`, `edr_amp_std`, `hr_surge` all have |corr(y)| ≤ 0.11, i.e. no
signal. And the baseline-relative SpO2 features *hurt* when added to legacy21, largely because
`spo2_drop_rel` is perfectly collinear with `−spo2_min_rel`.

**The one thing that worked was pruning 21 → 10 SpO2-dominant features.**

Retrain on the 70 `central_train` subjects, test on the 20 held-out:

| Model | mean-of-subject AUROC | sd |
|---|---|---|
| M0 (deployed, shipped INT8) | 0.8295 | 0.1134 |
| legacy21 retrain on all 70 (3 seeds) | 0.8392 | 0.1460 |
| **spo2_10 retrain on all 70** | **0.8706** | **0.0688** |

Headline Δ = **+0.0297 mean**, but **median Δ only +0.0013**, Wilcoxon **p = 0.546 (n.s.)**,
bootstrap 95% CI **[−0.0033, +0.0841]**, and **excluding one subject `tr04-0029` the Δ is +0.0051
(≈ 0)**.

Two different Δ's appear above and they are **not** interchangeable — state the protocol each time:
- **+0.0297** = mean over the **20 subjects** of the paired per-subject Δ from the **8-seed K=70**
  run (`results/phase3_robust.json`, `delta = 0.02966`).
- **+0.0314** = simple difference of the two *table-entry* means (0.8706 − 0.8392), which mixes
  the 8-seed spo2_10 mean with the legacy21 mean from a differently-seeded run.
Use **+0.0297** as the headline; the arithmetic 0.8706 − 0.8392 = 0.0314 is a different, weaker
quantity and should not be quoted as the paired effect.

**The honest interpretation: the mean gain is almost entirely the removal of one catastrophic
failure, not a broad improvement.**

| subject | legacy21 mean [min–max over **8 seeds**] | spo2_10 mean [min–max] |
|---|---|---|
| `tr04-0029` | **0.407** [0.274–0.823], sd 0.179 | **0.902** [0.899–0.906], sd 0.003 |
| `tr04-0020` | 0.730, sd 0.183 | 0.777, sd 0.024 |
| `tr06-0122` | 0.777, sd 0.042 | 0.874, sd 0.009 |
| **worst subject** | **0.407** | **0.689** |
| **worst over seeds** | **0.274** | **0.683** |
| mean per-subject sd | 0.0284 | **0.0046** |

So the real, defensible claim from the retrain is: **spo2_10 removes a seed-unstable catastrophic
failure and cuts per-subject variance ~6×.** That is a robustness claim, not an accuracy claim.

### 6.4 Learning curve — Gate G2 (this is what closes the "federation as more data" route)

Central training, mean-of-subject AUROC on the 20 held-out, as a function of how many subjects the
centre saw:

| K (subjects) | legacy21 | spo2_10 |
|---|---|---|
| 5 | 0.6606 ± 0.0583 | 0.8280 ± 0.0229 |
| 10 | 0.7469 ± 0.0182 | 0.8314 ± 0.0169 |
| 20 | 0.7673 ± 0.0368 | 0.8561 ± 0.0116 |
| 30 | 0.8148 ± 0.0287 | 0.8632 ± 0.0064 |
| 40 | 0.8115 ± 0.0213 | 0.8603 ± 0.0041 |
| 50 | 0.8308 ± 0.0101 | 0.8672 ± 0.0034 |
| 60 | 0.8429 ± 0.0138 | 0.8692 ± 0.0029 |
| 70 | 0.8362 ± 0.0157 | 0.8703 ± 0.0017 |

Last-4-point slope: legacy21 **+0.00086/subject** (and 60→70 is *negative*), spo2_10
**+0.00032/subject**. **Both curves are saturated by ~60 subjects.**

**Consequence:** classic FedAvg ≈ pooled central training. If the curve is flat, federation over
clients that hold data from the same distribution **cannot** add ranking AUROC. This is the gate
that the plan itself said would decide whether to run a federation phase — and it said *don't*.

### 6.5 Phase 4 — deploying the v2 head (base-model work, not the research result)

Quantised the spo2_10 head to INT8 and published 4 generated headers. Gates:

- float seed-0 held-out: mean-of-subject AUROC **0.8710 ± 0.0683** (n = 20)
- INT8 held-out: **0.8699**, Δ = **−0.0011**
- fixed-vector decision agreement **0.9961** (255/256), held-out decision agreement **0.9878**
  (8922/9032)
- balanced accuracy @0.29: INT8 **0.7798** vs float **0.7741** (+0.0057)
- quantisation scales: input 0.063458 (zp −15), a1 0.037546, a2 0.050872, head 0.094107 (zp 39),
  out 1/256 (zp −128), threshold_q −53; 897 params; 0/2560 inputs clipped.

**Board parity (the load-bearing proof):** `run` and `runraw` replay fixed vectors and compare
against expected INT8 codes → **0 mismatches** on both. Device INT8 arithmetic is bit-identical to
the host float64 emulation (int32 accumulators, double scales on both sides). Throughput improved
**≈13%** (7,753.88 → 6,718.29 cycles/inference) purely from the 21→10 input width, with no kernel
optimisation.

I should be explicit about a **weakness**: the "reference" for INT8 correctness is **our own float64
emulation**. There is **no `.tflite` file and no third-party reference interpreter** for this head.
So `run` proving 0 mismatches proves our emulation and our firmware agree — not that either matches
an independent implementation.

### 6.6 Phase 5 — the actual on-device training + federation measurement (2026-09-30, this session)

Everything above was host-side or base-model work. This is the first time the *research question*
was measured on silicon with the v2 model.

Protocol: 256-window on-board self-test, subject `tr03-0322`, sites A/B = artificial index split.
Baseline = frozen global head. Board started clean (`drift L2 0.0000`, threshold 0.29).

| route | AUROC | balanced acc @0.29 | sensitivity | precision | drift L2 |
|---|---|---|---|---|---|
| **frozen global head (baseline)** | **0.8927** | **0.7751** | 0.6000 | 0.4286 | 0.0000 |
| train A, teacher labels | 0.8929 | 0.7418 | 0.5333 | 0.4000 | 0.6205 |
| train A + B, teacher labels | 0.8927 | 0.7438 | 0.5333 | 0.4211 | 0.6185 |
| **federation** — fedavg (A, B teacher) | 0.8929 | 0.7438 | 0.5333 | 0.4211 | 0.6183 |
| **federation** — fedrounds 3 teacher | 0.8929 | 0.7438 | 0.5333 | 0.4211 | 0.6265 |
| label-free — entropy | 0.8932 | 0.7438 | 0.5333 | 0.4211 | 0.4908 |
| label-free — temporal | 0.8927 | 0.7209 | 0.4667 | 0.5385 | 0.4949 |

- Baseline bootstrap CI95 on AUROC: **[0.7901, 0.9583]** (200 resamples). Baseline sens CI95
  [0.3575, 0.8018], prec CI95 [0.2447, 0.6345].
- **Largest ranking delta anywhere: +0.0005** — about **170×** smaller than the CI half-width
  (0.084 / 0.0005 = 168; earlier drafts said 300×, which was wrong).
- `fedrounds` per-round AUROC: **[0.8929, 0.8929, 0.8929]**. The rounds converge immediately and
  then do nothing.
- **Every adapted head is worse at the deployed threshold** (bal 0.7209–0.7438 vs 0.7751 frozen).
  The underlying counts are **one fewer TP and one fewer FP** (baseline tp 9 / fp 12 → adapted
  tp 8 / fp 11), with sensitivity CI95 [0.3575, 0.8018]. So claim (a) on this single subject is
  ***unresolved*, not negative** — the direction is unfavourable but n_pos = 15 cannot separate it
  from a tie.

**Cost — the one genuinely good number from this run:**

| quantity | value |
|---|---|
| timing runs (cycles, 5 × site-A teacher, n=122, 800 iters) | 80982636, 80977625, 80978168, 81430489, 80983517 |
| median cycles / gradient iteration | **101,228** |
| median cycles / local adaptation (800 iters) | **≈ 81.0 M** |
| median time per local adaptation @1 GHz | **≈ 81 ms** |
| spread across 5 runs | within 0.6% |

So on-device training is **cheap and stable** — it just does not help. RAM was not separately
instrumented this run (head is 17 fp32 params ≈ 68 B plus gradients/momentum). **No energy or
power figure — there is no probe on this board, so I refuse to quote one.**

**This run's own caveat, stated plainly:** one subject, artificial index split, 256 windows. It
cannot satisfy the pre-registered MEOI. It is a mechanism-and-cost measurement.

---

## 7. What I now believe is settled, and what is still open

### Settled (I would defend these)

1. **Label-freeness is not the blocker.** The label-supervised oracle on the same 17 parameters
   buys +0.0146 (n.s.). True labels cannot beat an oracle. So "pseudo-label, then train
   supervised" is capped near the oracle **unless the trainable set or the inputs change**.
2. **Head-only capacity is not the blocker either, on its own.** ALL-LAYERS refit was *worse*
   (0.8177 vs 0.8235) than the frozen head at FIT→TEST. More parameters made transfer worse.
3. **Federation-as-more-data is closed.** The learning curve is saturated by ~60 subjects. FedAvg
   over same-distribution clients cannot add ranking AUROC. Phase 5 confirms this on silicon.
4. **Lag is dead.** ±2 min sweep moves AUROC by 0.0005.
5. **The new ECG features (CVHR/EDR/HR-surge) carry no signal in this data.** |corr(y)| ≤ 0.11.
6. **The base model improved for robustness reasons, not accuracy reasons.** The mean gain is one
   subject's catastrophic failure; the median gain is ≈ 0.

### Open / genuinely uncertain

1. **Is the transfer gap fixable?** The in-sample head-only ceiling is 0.8736 (p = 0.007 real) vs
   FIT→TEST oracle 0.8381. That 0.035 is night drift. I have not found an input-side alignment
   that closes it — but baseline-relative SpO2 *hurt* in my hands, which may be an implementation
   artifact (perfect collinearity between `spo2_drop_rel` and `−spo2_min_rel`).
2. **Is the metric hiding the real effect?** Pooled vs mean-of-subject differ by 0.042. Per-subject
   AUROC is invariant to monotone recalibration, so it **cannot see** the thing that most plausibly
   differs between subjects (baseline offset / gain). Claim (a) — operating point at threshold
   0.29 — is where a real personalisation gain should show up, and it is *untested properly* at the
   20-subject level.
3. **Federation-as-personalisation (FedPer/FedRep) is untested.** Splitting "personal" parameters
   (calibration, threshold, baseline) from "shared" ones (the representation, fusion weights) is a
   *different mechanism* from FedAvg-as-more-data, and the saturated curve does not rule it out.
4. **Is 20 subjects enough to see anything?** With 20 subjects, "p ≥ 0.18" means *unresolved*, not
   *zero*. A +0.005 effect could be real and simply invisible here.
5. **Would a non-IID construction make federation help?** My test gave the fleet data from the same
   distribution the centre already saw. If non-IID must live in P(x|y) rather than the label prior,
   I have not constructed a fair test.
6. **Is the whole task ceiling-bound?** ECG-only 0.578 shows *these 21 features* miss ECG
   information, not that ECG has none. Apneas are scored from airflow, not SpO2, and hypopnea
   criteria can be arousal-based, so some positives genuinely have no desaturation. If the
   positives I'm failing are information-theoretically invisible to SpO2, no amount of learning
   fixes them.

---

## 8. The six structural reasons I originally proposed (for you to attack)

This was my first attempt at explaining the null. I now think several are overstated. Please grade
them.

1. **AUROC is rank-invariant**, so a whole class of monotone "adaptation" (recentre, re-threshold,
   shift/scale) **cannot** change it by construction — they only move the operating point.
   *My own caveat:* this holds for output-space monotone maps; it does **not** cover input-side
   normalisation, non-monotone head changes, temporal context, or fixed-threshold metrics. Purely
   output-monotone recipes tie *by identity*, so they are not evidence about anything.
2. **The model is at the signal's information ceiling.** ECG-only 0.578, SpO2-only 0.902 →
   functionally a desaturation detector, and "did SpO2 drop below ~92%?" is near-deterministic.
3. **Only the last layer (17 params) is trained.** No representation learning possible.
   *My caveat:* nothing in the hardware forces this; and ALL-LAYERS was worse, so this may not be
   the binding constraint.
4. **Label-free objectives carry no new information.** Entropy minimisation induces confidence, not
   correctness; temporal consistency is nearly free at 50% overlap (adjacent windows share half
   their samples).
5. **Federation adds nothing here** because the centre already saw the data.
   *My caveat:* true under IID, but stated as a law it's too strong.
6. **Cross-subject variation is calibration, not representation** — i.e. a per-subject offset/scale,
   which is AUROC-invisible.
   *My caveat:* true only for per-subject AUROC. For fixed-threshold metrics it matters a great
   deal. Issues 5 and 6 may be one finding: heterogeneity exists, but in a place my metric can't see.

---

## 9. What I have *not* done

- No multi-subject on-device experiment. Phase 5 is one subject.
- No held-out-night protocol (only chronological FIT/TEST within a night).
- No FedProx / Ditto / FedPer / FedRep comparison. Only plain FedAvg.
- No fleet larger than the centre. Only 2 artificial sites.
- No external-site validation (e.g. UCD/St Vincent's, SHHS, MESA).
- No power/energy measurement. No probe exists.
- No NPU execution. No FSP Ethos-U55 driver.
- No third-party INT8 reference interpreter.
- Single training seed for the deployed model (per-seed sd ≈ 0.0046 from Phase 3).
- Protocol inconsistency between pooled and mean-of-subject numbers in older documents.

---

## 10. My proposed order of work (critique this too)

1. **Metric audit.** Put M0–M5 on one protocol (mean-of-subject, float logits, one partition) and
   additionally report calibration (Brier/ECE), balanced accuracy / MCC at 0.29, subject-level AHI
   error and severity-class accuracy. This is where claim (a) lives.
2. **Decision gate.** If the learning curve *and* the oracle ladder are flat even with new features,
   the honest deliverable is ceiling analysis + operating-point calibration + on-board cost.
3. **Widen the trainable set only if the ladder justifies it** — input norm + first-layer bias +
   head, with shrinkage toward global, evaluated on unseen subjects and held-out nights.
4. **Federation-as-personalisation**, with a fleet larger than the centre and structured shift.
5. **External-site validation.**

---

## 11. Questions for you

1. **Is the null real, or is my experiment incapable of showing a win?** Specifically: is
   mean-of-subject AUROC the right primary, or is it structurally blind to the effect I'm looking
   for?
2. **The ORACLE row (+0.0146, n.s.) caps the "labels" lever.** Is that reasoning airtight, or can
   you construct a supervised on-device scheme that beats an oracle on the *same* parameter set?
3. **The transfer gap** (in-sample 0.8736 vs FIT→TEST 0.8381) is the biggest real number I have.
   What is the highest-probability way to close it? My baseline-relative SpO2 attempt *hurt* — is
   that likely a real result or my implementation (collinearity between `spo2_drop_rel` and
   `−spo2_min_rel`)?
4. **Which single change has the highest chance of a defensible positive result**, given that
   labels, head capacity, lag, and FedAvg-as-more-data are all closed?
5. **Is "federation adds nothing" actually closed**, or is there a non-IID construction (living in
   P(x|y), not the label prior) that would make FedAvg genuinely help here?
6. **Is the whole thing ceiling-bound?** If the failing positives are information-theoretically
   invisible to SpO2, should I stop chasing AUROC and pivot the deliverable to operating-point
   calibration + on-board cost?
7. **Anything in §7 "settled" that you think is actually wrong?**

---

## 12. Artifacts and reproducibility

Host repo: `/home/jbatra/tron/`

| Path | Contents |
|---|---|
| `apnea_deploy/src/apnea.c` | firmware, serial command loop, inference + training kernels |
| `apnea_deploy/src/apnea_personal.c` | `train`/`fed`/`fedavg`/`fedrounds`/`personalize`/`evalhead`/`evalci` |
| `apnea_deploy/src/apnea_model.h` + 2 normalisation headers + `apnea_selftest_vectors.h` | generated, INT8 model + fixed test vectors |
| `apnea_deploy/tools/phase4_quantize.py` | float→INT8 quantiser + fidelity gates (the float64 reference) |
| `apnea_deploy/tools/phase3_curve.py` | learning curve |
| `apnea_deploy/tools/serial_cmd.py` | sends commands to `/dev/ttyACM0` |
| `apnea_deploy/results/*.json` | every number quoted here is machine-readable on disk |
| `apnea_deploy/RESULTS_PROTOCOL.md` | append-only protocol/results record |
| `apnea_deploy/RETRAIN_PLAN.md` | the phase plan and its gates |
| `apnea_deploy/RETRAIN_RESULTS.md` | Phase 1–4 write-up |
| `apnea_deploy/DIAGNOSTICS.md` | oracle ladder, headroom, lag, protocol reconciliation |
| `/home/jbatra/tron/PROGRESS_LOG.md` | consolidated dated log of everything |
| `/home/jbatra/tron/SETUP_NOTES.md` | toolchain/setup corrections |

Reproduce the headline host result:

```bash
/tmp/cincenv/bin/python tools/cross_subject_eval.py \
  --ref --baselines --delong --calibration --operating-point \
  --partitions final_test,validation --tag P5 --write
```

Reproduce the on-device result:

```bash
cd /home/jbatra/tron/apnea_deploy
/tmp/cincenv/bin/python tools/serial_cmd.py "sethead global" evalhead \
  "train A teacher" "train B teacher" evalhead fedavg evalhead \
  "fedrounds 3 teacher" evalhead cycrep "sethead global" evalhead
```

---

## 13. The one-line version

> A bare-metal Cortex-M85 apnea detector where on-device training is cheap (~81 ms per adaptation)
> and works exactly as designed, but produces **no measurable benefit** — and I have evidence that
> labels, head capacity, temporal lag, and federated averaging are all *individually* insufficient
> explanations. I suspect night-to-night transfer plus a SpO2 information ceiling, but I want you
> to tell me if I have instead built an experiment that cannot show a win.
