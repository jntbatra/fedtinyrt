# FINAL RESULTS — on-device calibration and federation (shipped model, tiered improvement pass)

Run: 2026-09-30. Everything here uses **the model the board actually runs**: the spo2_10
float MLP (10 SpO2 inputs, 897 params) trained exactly as `tools/phase4_quantize.py` does
(`train_mlp`, iters=400, seed=0) on the 70 `central_train` subjects of
`data/feat_v2_cache.npz`. Donors for the shared reference are the **67 usable central
subjects**.

Scripts (new in this pass):

| tier | item | script | output |
|---|---|---|---|
| 2 | 3 — donors-per-site crossover | `tools/site_crossover.py` | `results/site_crossover.json` |
| 1 | 2 — label-free reference | `tools/labelfree_ref.py` | `results/labelfree_ref.json` |
| 1 | 1 + 2/4/5 — sealed cohort + extended metrics | `tools/sealed_cohort.py` | `results/sealed_cohort.json` |
| — | label-free board constants | `tools/opref_labelfree.py` | `results/opref_labelfree.json` |

Supersedes the earlier exploratory numbers in `CEIL_DIAGNOSTICS.md` / `OP_ESTIMATOR.md`, which
used the legacy 21-feature host model.

---

## Tier summary

| tier | item | outcome |
|---|---|---|
| 1 | 1. Sealed cohort | **done** — 27 unused CinC records, all byte-verified, 25 evaluable; the effect survives but shrinks to +0.035; see §5 |
| 1 | 2. Remove the label dependency | **done** — label-free reference matches the labelled one on unseen data (+0.0347 vs +0.0359); see §4, §5 |
| 2 | 3. Donors-per-site crossover | **done** — no crossover; pooling wins at every donor count tested; see §2b |
| 2 | 4. More subjects | **done** — n = 18 → 25 sealed, plus the 18 in-manifest |
| 2 | 5. Metrics beyond balanced accuracy | **done** — MCC degrades reproducibly, AHI unresolved; see §3, §5 |
| 3 | 6. Board-scale efficacy | **blocked** — needs a data path; see §6 |
| 3 | 7. Energy | **blocked, unclaimed** — no probe exists; see §6 |

**Headline after the sealed check:** the on-device, label-free recalibration is a real but
**modest** operating-point gain — **+0.035 balanced accuracy** on unseen subjects, CI excluding
zero — which is **about half** the figure the in-manifest cohort gave and **below the
pre-registered +0.02 MEOI's lower CI bound**. It does not make the model better (AUROC unchanged,
MCC worse, AHI unresolved), and it is a recentring rule rather than learning.

---

## 1. On-device calibration — a balanced-accuracy win

Label-free per-session calibration on the 18 in-manifest held-out subjects, balanced accuracy:

| method | labels? | mean BA | Δ vs fixed | 95 % CI |
|---|---|---|---|---|
| fixed 0.29 (shipped) | no | 0.7201 | — | — |
| fixed τ\* from the fleet | no | 0.7201 | +0.0000 | — |
| single-donor reference | no | 0.7302 | +0.0101 | [−0.026, +0.052] |
| **full-fleet reference (E4)** | **labelled ref** | **0.7833** | **+0.0632** | **[+0.027, +0.111]** |
| labelled τ\*(own FIT) — upper bound | yes | 0.7410 | +0.0209 | — |
| cross-fitted labelled ceiling — upper bound | yes | 0.7934 | +0.0733 | — |

The device side of this estimator is already label-free: a target session's median logit and
p90-minus-median spread come from its own unlabelled FIT half. AUROC is unchanged — the whole
gain is at the decision line.

---

## 2. Federation

### 2a. More devices into one shared reference

| donors m | mean BA | Δ vs m=1 | 95 % CI |
|---|---|---|---|
| 1 | 0.7354 | — | — |
| 2 | 0.7679 | +0.0325 | [+0.027, +0.038] |
| 3 | 0.7622 | +0.0268 | [+0.022, +0.032] |
| 5 | 0.7714 | +0.0360 | [+0.029, +0.044] |
| 10 | 0.7796 | +0.0442 | [+0.035, +0.054] |
| 20 | 0.7826 | +0.0472 | [+0.038, +0.057] |
| 40 | 0.7843 | +0.0489 | [+0.039, +0.059] |
| **70 (full fleet)** | **0.7833** | **+0.0479** | **[+0.036, +0.060]** |

Pooling devices is worth **+4.8 points** over a single donor, CI excluding 0, saturating around
20–40 devices.

### 2b. The donors-per-site crossover — pooling wins (Tier 2 item 3)

The earlier write-up compared per-site references (10x fewer donors) against one global
reference (67 donors), which confounds *site matching* with *donor count*. `site_crossover.py`
removes the confound by comparing at **matched donor count**:

- `per-site(m)` — reference from m donors in the target's own `record_group`
- `pooled-random(m)` — reference from m donors drawn from the whole fleet

| m | targets | per-site | pooled(m) | global(67) | per-site − pooled | 95 % CI |
|---|---|---|---|---|---|---|
| 2 | 18 | 0.7539 | 0.7652 | 0.7833 | −0.0113 | [−0.0290, +0.0042] |
| 3 | 17 | 0.7362 | 0.7605 | 0.7784 | −0.0243 | [−0.0543, +0.0002] |
| 4 | 17 | 0.7486 | 0.7709 | 0.7784 | −0.0223 | [−0.0482, −0.0010] |
| 5 | 16 | 0.7454 | 0.7750 | 0.7835 | −0.0296 | [−0.0763, +0.0089] |
| 6 | 10 | 0.7879 | 0.7818 | 0.7911 | +0.0060 | [−0.0016, +0.0142] |
| 7 | 8 | 0.7729 | 0.7656 | 0.7742 | +0.0072 | [−0.0081, +0.0231] |
| 8 | 5 | 0.7509 | 0.7496 | 0.7552 | +0.0014 | [−0.0054, +0.0068] |

Fixed-composition control (targets held constant on the 8 sites with ≥5 donors, 16 targets):

| m | per-site | pooled(m) | global(67) | per-site − pooled | 95 % CI |
|---|---|---|---|---|---|
| 2 | 0.7511 | 0.7691 | 0.7835 | −0.0180 | [−0.0404, +0.0017] |
| 3 | 0.7390 | 0.7655 | 0.7835 | −0.0264 | [−0.0582, −0.0001] |
| 4 | 0.7529 | 0.7745 | 0.7835 | −0.0216 | [−0.0489, +0.0009] |
| 5 | 0.7425 | 0.7722 | 0.7835 | −0.0296 | [−0.0749, +0.0076] |

**Result: no crossover.** Per-site splitting is measurably *worse* than pooling at matched
donor count for m ≤ 5, and a statistical wash for m = 6–8 (which is the whole range the real
grouping supports). Neither ever beats the single global reference.

**Design rule:** pool every device into one shared reference. Do not split into per-site
references on this data at any donor count the grouping can support. The earlier synthetic
"+2.4 points at heterogeneity 2.0" was per-site *undoing an injected corruption* with 22
donors — a mechanism demo, not a design rule.

---

## 3. Metrics beyond balanced accuracy (Tier 2 item 5)

18 in-manifest held-out subjects, TEST half only. `sens@90` = sensitivity at the threshold that
gives 90 % specificity on that subject.

| method | BA | sens | spec | MCC | sens@90 | AHI MAE (win) | AHI MAE (run) | sev agree (win/run) |
|---|---|---|---|---|---|---|---|---|
| fixed 0.29 (shipped) | 0.7201 | 0.508 | 0.932 | **0.4531** | 0.996 | **8.64** | 13.47 | 0.61 / 0.22 |
| E4 labelled reference | **0.7833** | 0.710 | 0.856 | 0.4438 | 0.996 | 15.04 | **12.92** | 0.22 / **0.39** |
| LF-proxy-cal (BA-anchored, label-free) | 0.7698 | 0.666 | 0.873 | 0.4390 | 0.996 | 13.25 | 13.09 | 0.28 / 0.28 |
| LF-proxy (event-rate-anchored, label-free) | 0.7367 | 0.538 | 0.936 | 0.4392 | 0.996 | 9.60 | 13.98 | 0.33 / 0.33 |

Mean true AHI 18.34/h. Two counters are reported because they disagree:

- **win** — predicted positive windows per hour (one window ≈ one event)
- **run** — contiguous runs of positive windows collapsed to one event (1-window gap tolerance)

**Reading.** Recalibration buys sensitivity by spending specificity. The two AHI counters
disagree in direction — window-counting favours the shipped threshold (8.64 vs 15.04), while
run-counting favours the recalibrated one (12.92 vs 13.47), as does severity agreement under
run-counting (0.39 vs 0.22). **Neither counter is decisive**, so the AHI result here is
"unresolved", not "worse". What is unambiguous:

- **MCC degrades** under recalibration (0.4531 → 0.4438 for E4) — a small but consistent sign
  flip.
- **`sens@90` is saturated** at ~0.996 for every method and cannot discriminate; it should not
  be used as a co-primary on this data.
- The choice of *which operating point to transport* is a real design decision: anchoring to
  the desaturation event rate (LF-proxy) preserves the window-count AHI (9.60) at the cost of
  most of the BA gain (0.7367 vs 0.7833).

**Honest reading:** on-device calibration does something measurable, but against the
pre-registered claim (a) — the deployed operating point judged by balanced accuracy *and* AHI
error *and* severity agreement — it **passes on balanced accuracy, is neutral-to-unresolved on
AHI, and slightly negative on MCC**. Event-level scoring with real durations and a clinical
scoring convention (not a proxy) is required to settle AHI.

---

## 4. Removing the label dependency (Tier 1 item 2)

The only labelled quantity left in the pipeline was the shared reference's threshold-offset
term `roff = median_k(logit(τ*_k) − med_k)`. Three label-free surrogates were built and scored
against the labelled version on the 18 held-out subjects:

| reference offset | roff | mean BA | Δ vs E4 labelled | 95 % CI | Δ vs fixed 0.29 | 95 % CI |
|---|---|---|---|---|---|---|
| labelled (current) | 1.460 | 0.7833 | — | — | +0.0632 | [+0.027, +0.111] |
| LF-const (a-priori) | 2.356 | 0.7452 | −0.0381 | [−0.051, −0.024] | +0.0251 | [−0.019, +0.082] |
| LF-proxy (desaturation anchor) | 2.627 | 0.7367 | −0.0466 | [−0.064, −0.029] | +0.0166 | [−0.033, +0.079] |
| **LF-proxy-cal** | **1.666** | **0.7698** | **−0.0136** | **[−0.021, −0.007]** | **+0.0496** | **[+0.015, +0.098]** |

LF-proxy-cal is the working surrogate: set each donor's threshold from the fraction of its FIT
windows whose SpO2 drawdown exceeds 3 % (a label-free physiologic anchor), rescaled by a single
scalar `c = 1.31`. `c` is estimated on the central cohort leave-one-donor-out, so it transfers
rather than being fitted in place. Nothing about the *deployed* pipeline needs labels: the
device uses its own unlabelled FIT half, and the fleet reference is built from label-free
per-donor anchors plus one centrally-fitted scalar.

**Outcome: a fully label-free reference retains 78 % of the labelled gain and is itself a
significant win over the shipped threshold (+0.0496, CI [+0.015, +0.098]).**

### Board parity for the label-free reference

`tools/opref_labelfree.py` derived the same triple in the board's INT8 score space; the
labelled triple reproduces the firmware's compiled constants exactly, which validates the
derivation:

```
labelled    setthr -3.293730 -0.094107 -1.947199   (== firmware g_opref_*)
label-free  setthr -3.293730 -0.094107 -1.505705   (c = 1.316)
```

Pushed to hardware over the existing `setthr` command (no re-flash needed):

```
>>> setthr -3.293730 -0.094107 -1.505705
  sess med -4.1752 p90 -1.5570 scale 0.8183
  threshold 0.2900 -> 0.0623  (75875 cycles)
  before  bal 0.7751  f1 0.5000  sens 0.6000  predpos 21
  after   bal 0.7794  f1 0.3922  sens 0.6667  predpos 36
```

The board reproduces the host's threshold (0.0623) to 4 decimals and shows the same
BA-up / F1-down pattern as the host cohort. The board was then restored to the labelled
reference and `resetoff` (threshold 0.29).

---

## 5. Sealed cohort (Tier 1 item 1, Tier 2 item 4) — the selection-bias check

**Complete.** 27 CinC 2018 records that appear nowhere in `subject_split_manifest.csv`, chosen
label-blind (2 per `record_group`, interleaved). The method is frozen: shipped spo2_10 model,
the 67 central donors, and the calibration recipes exactly as published in §1 and §4. Nothing
was tuned on these records. **25 evaluable** (2 dropped by the both-classes-in-FIT filter).

Chain of custody: the extractor was shown to reproduce `data/feat_v2_cache.npz` bit-exactly
(`tools/extract_features.py` for `tr03-0052`: max abs diff 0.0), and **every record was
byte-verified against the server** before entering the cohort — `tools/verify_mat.py` re-fetches
three short byte ranges per record and compares. 27/27 verified, 0 mismatches.

The verification is not ceremony. The downloader assembles a record from N range-downloaded
`.part` files, and **a chunk-count change between runs scrambles the assembled file at an
unchanged total size**, so the existing size check cannot catch it. That hazard was hit and
fixed mid-pass (partial data wiped, chunk count then held fixed).

### Results on the sealed cohort (n = 25)

| method | BA | sens | spec | MCC | Δ vs shipped | 95% CI |
|---|---|---|---|---|---|---|
| fixed 0.29 (shipped) | 0.7910 | 0.654 | 0.928 | 0.5442 | — | — |
| E4 labelled reference | 0.8269 | 0.801 | 0.853 | 0.4629 | +0.0359 | [+0.0080, +0.0656] |
| **LF-proxy-cal (label-free)** | **0.8256** | 0.778 | 0.873 | 0.4701 | **+0.0347** | **[+0.0057, +0.0651]** |
| LF-proxy (event-rate-anchored) | 0.7909 | 0.648 | 0.933 | 0.4675 | −0.0001 | [−0.0424, +0.0431] |
| cross-fitted labelled ceiling | 0.8241 | — | — | — | — | per-subject τ, labelled |

| method | true AHI | predWin | errWin | predRun | errRun | sev (win/run) |
|---|---|---|---|---|---|---|
| fixed 0.29 | 18.16 | 22.27 | **11.29** | 4.46 | 13.80 | 0.48 / 0.28 |
| E4 labelled | 18.16 | 31.72 | 15.38 | 7.65 | **12.48** | 0.24 / 0.24 |
| LF-proxy-cal | 18.16 | 28.87 | 13.32 | 7.33 | 12.55 | 0.32 / 0.28 |
| LF-proxy | 18.16 | 18.14 | **8.64** | 5.51 | 13.66 | **0.56** / 0.24 |

### What the sealed cohort establishes

1. **The balanced-accuracy gain survives out of sample.** +0.0359 (labelled) and +0.0347
   (label-free), both CIs excluding zero, on subjects nothing was tuned on.
2. **The effect is smaller than the in-manifest number.** +0.035 here against +0.0632 there.
   Part of that is selection bias in the older number; part is that these subjects have a higher
   baseline (0.7910 vs 0.7201), so there is less headroom. n = 25 cannot separate the two, and
   the honest reading is the smaller figure.
3. **Dropping labels costs nothing out of sample.** LF-proxy-cal (+0.0347) matches the labelled
   reference (+0.0359) to within noise. On the in-manifest cohort it gave up 0.014.
4. **Neither variant clears the pre-registered MEOI of +0.02 balanced accuracy.** The CI lower
   bounds are +0.0080 and +0.0057. Both exclude zero; neither excludes +0.02. By the project's
   own pre-registered rule this is **unresolved, not confirmed**.
5. **MCC degrades, reproducibly.** 0.5442 → 0.4629 (labelled) / 0.4701 (label-free). This is now
   the same sign flip on both cohorts.
6. **AHI remains counter-dependent and therefore unresolved.** The window counter favours the
   shipped threshold (11.29 vs 15.38 / 13.32); the run counter favours the recalibrated one
   (12.48 / 12.55 vs 13.80). Severity agreement follows the same split.
7. **The fleet reference beats a per-subject threshold fitted with that subject's own labels**
   (0.8269 / 0.8256 vs 0.8241). `crossfit_bal` fits τ per subject inside the session using true
   labels; the reference methods use none. The gap is 0.003–0.006 at n = 25 — suggestive, not
   established — but it is the clearest federation signal in the project, and it is the one place
   where pooling information across devices beats what a single device can learn about itself.
8. **The event-rate-anchored variant is a different operating point, not a better one.** LF-proxy
   has the best window-count AHI error (8.64) and severity agreement (0.56) but essentially no
   balanced-accuracy gain (−0.0001). The choice of which operating point to transport is a real
   design decision with measurable consequences.

---

## 6. Tier 3 — blocked, stated plainly

**Item 6, board-scale efficacy — BLOCKED.** The chip currently calibrates only the compiled-in
256-window self-test buffer. Running a cohort of sessions *on the board* requires a data path
from host to flash/PSRAM: a `loadvec`-style command to stream one night (~960 windows × 10
features ≈ 10 KB, about a second at 115200 baud) plus training-step parity against the host.
Until that exists, every efficacy number in this document is host-side, and the board numbers
prove mechanism, cost and parity only. Concrete next engineering step: implement `loadvec`.

**Item 7, energy — BLOCKED, NEVER CLAIMED.** No current probe or power monitor is attached to
the board, so there is no measurement to report. Reported cost is **cycles and RAM only**
(77,429 cycles ≈ 77 µs at 1 GHz, ~2 KB RAM per session). Any joule figure in this project would
be an estimate from datasheet numbers, not a measurement, and is therefore left unclaimed.

---

## 7. Limitations (state these plainly)

1. **The balanced-accuracy win does not survive contact with event-rate metrics.** See §3 —
   MCC, AHI MAE and severity agreement all get *worse* under the BA-optimal calibration.
2. **The 18 subjects used for §1–§4 have been used throughout the project.** Feature-set
   selection, threshold choice and estimator design all saw them. §5 is the check on that.
3. **AHI is a proxy, not a scored index.** It compares annotated respiratory-event counts per
   hour against predicted positive windows per hour on the TEST half; it assumes one positive
   window ≈ one event and splits the night in half.
4. **`record_group` (tr03…tr14) is a grouping in the released data whose physical meaning
   (site? device batch? collection epoch?) is not documented** in anything on disk. §2b is
   therefore a test on a real *grouping*, not provably on real *sites*.
5. **The board was exercised on one session.** Mechanism, cost and parity — not efficacy.
6. Device-count curve is non-monotone at m=2→3 (0.7679 → 0.7622) — Monte-Carlo noise at 40–60
   repeats, within the reported CIs.
7. **Every cohort is filtered to subjects with both classes present in their FIT half.** A
   subject with no annotated event in the first half of the night cannot have a threshold
   calibrated on that half, so it is dropped. This is a label-dependent inclusion rule, applied
   identically to every cohort, and it is why the evaluable N is always below the cohort size.
8. **The sealed cohort validates the frozen pipeline; it does not validate the design.** The
   estimator's form, the frozen model, the labelled-vs-label-free choice and the scalar `c`
   were all settled on the 18 in-manifest subjects and the 67 central donors. The sealed
   cohort tests whether those choices transfer to records nothing in the project has seen.
9. **The sealed cohort is 25 subjects, not the 100–200 the reviewer asked for.** PhysioNet
   throttles this IP to ≈1 MB/s aggregate (independently verified: 48 and 128 concurrent
   connections gave 57 and 61 MB/min, a single stream gets 0 when the pool is saturated, while
   the same host reaches 3.5 MB/s from cdn.kernel.org). Records are 118–152 MB, so 27 records
   took ≈110 min. The CI half-width is ±0.030, against ±0.042 at n = 18 — better, not tight.
10. **The smaller sealed effect has two candidate explanations that n = 25 cannot separate:**
    selection bias in the older number, or a higher-baseline (easier) cohort with less headroom.
    Both are consistent with the data. The conservative reading is the smaller figure.

## 8. What is NOT claimed

**On-device *training* of the model does not help.** A purged refit given true labels does not
beat the frozen head (`CEIL_DIAGNOSTICS.md` D1); federated averaging of head weights converges
in one round with no gain (`phase5_ondevice.json`). Bounded negative result with a measured
explanation: only ~27 % of positives desaturate, so the ranking ceiling is set by the label
definition, not the model.

**The MEOI is not met.** The pre-registered minimum effect of interest was +0.02 balanced
accuracy. On the sealed cohort the CI lower bounds are +0.0080 (labelled) and +0.0057
(label-free). Both exclude zero; neither excludes +0.02.

**No clinical-metric improvement.** MCC degrades reproducibly on both cohorts. The AHI proxy is
counter-dependent and therefore unresolved.

**No AUROC improvement.** The gain is entirely at the decision line; ranking is unchanged.

**Quantization does not change anything.** Float vs INT8 differ by ±0.0002 through the whole
calibration and federation pipeline (`tools/quant_vs_fed.py`); int8 was marginally *better* on
the 256 self-test AUROC (0.8988 vs 0.8927). Dropped as a lever.

**No energy claim.** See §6.
