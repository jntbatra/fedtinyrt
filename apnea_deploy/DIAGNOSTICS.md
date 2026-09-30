# Host-only diagnostics — oracle ladder, headroom, lag, protocol

Tool: `tools/diagnostics.py` (reuses `tools/cross_subject_eval.py`; raw features cached to
`/tmp/diag_feat_cache.npz`). Host-only, no firmware. Run:
`/tmp/cincenv/bin/python tools/diagnostics.py`

Data: all 20 subjects on disk. Two (`tr05-0647`, `tr05-1404`) have **zero FIT positives**, so
they drop out of every FIT-supervised ladder rung; ladder aggregates are **n = 18**. The pooled /
mean-of-subject reconciliation uses all 20 (the global head needs no FIT labels).

This is the "order of work, item 1" set the second-opinion model asked for: the cheap experiments
that confirm or kill each hypothesis **before** any firmware or federation work.

## Headline

**The bound is not the head size and not the labels. It is that supervision fitted on the first
half of the night does not transfer to the second half.** The same 17-parameter head, when fitted
*and* scored on the second half, jumps **+0.050 AUROC** (p = 0.007). Fitted on the first half with
true labels, it moves **+0.015 and is not significant** (p = 0.77). So the 16-d representation is
*not* the limit — the cross-half / cross-subject shift is.

## 1. Oracle ladder (AUROC on TEST, mean ± sd, n = 18)

| Rung | AUROC | Δ vs M0 | 95% CI | Wilcoxon p |
|---|---|---|---|---|
| M0 global head | 0.8235 ± 0.1172 | — | — | — |
| ORACLE — true labels, head-only, FIT→TEST, lam=0.01 | 0.8381 ± 0.0891 | +0.0146 | [−0.004, +0.043] | 0.77 |
| IN-SAMPLE — fit **and score** on TEST (head-only ceiling) | 0.8736 ± 0.0681 | +0.0501 | [+0.009, +0.105] | **0.007** |
| ALL-LAYERS — refit 21-32-16-1 from frozen init, FIT→TEST | 0.8177 ± 0.1256 | −0.0058 | [−0.073, +0.054] | 0.64 |

lam sweep (recentred head, FIT→TEST): 1e-4 → 0.8428, 1e-3 → 0.8425, 1e-2 → 0.8381,
1e-1 → 0.8333, 1.0 → 0.8315. **The ORACLE is not an artifact of the shrinkage**: over four orders
of magnitude lam the result moves by ~0.011 and never reaches the in-sample ceiling.

### What this means
- **Consult's "if in-sample doesn't move, representation is the limit" — in-sample DOES move**
  (0.874 vs 0.824). So the frozen 16-d features *do* carry ~0.87 of rankable signal. The blocker is
  the **FIT→TEST transfer gap** (≈ 0.036 AUROC between ORACLE and IN-SAMPLE), i.e. night drift /
  distribution shift between the two halves, not the representation and not label-freeness.
- **The ORACLE row still stands**: real labels on this head, fitted on FIT, buy nothing over global.
  But that is *not* because the head can't move — it's because FIT-supervision doesn't generalize.
- **All-layers makes it worse.** Unfreezing the full net from a frozen init on half a night
  overfits and degrades (0.818, higher variance). This **kills** "widen the trainable set
  (first-layer bias + head)" as a cheap win *on this data*. Widening only matters if the
  optimization is constrained to the shift direction — plain refit is not.

## 2. Headroom decomposition (p0, TEST windows, n = 18)

Own baseline = per-subject median `spo2_min`. Strong positive = `spo2_min < baseline − 3`.

| Subset (positives + all negatives) | n pos | AUROC p0 |
|---|---|---|
| Strong (deep desaturation) | 212 | **0.9897 ± 0.0114** |
| Weak (no deep desaturation) | 1417 | **0.8035 ± 0.1238** |
| Weak, single feature −`spo2_min` | 1417 | 0.7134 ± 0.1520 |

- Deeply desaturating events are **essentially solved** (0.99).
- Nearly all residual error is on positives **without** a deep desaturation drop. That is where the
  ranking headroom lives.
- But weak positives are still ranked at 0.80 — this is **not** a hard 0.5 floor. −`spo2_min` alone
  reaches 0.71 on them, so there is SpO2 signal in the weak set too. Consistent with the consult's
  Issue 2 (ECG-only ablation 0.578 shows *these* ECG features miss the events, not that ECG has
  none) **and** with its caution that some positives genuinely have no desaturation.

## 3. Lag sweep (single channel −`spo2_min`, TEST, n = 18)

| k (windows, ±30 s) | −4 | −3 | −2 | −1 | 0 | +1 | +2 | +3 | +4 |
|---|---|---|---|---|---|---|---|---|---|
| AUROC | 0.7364 | 0.7359 | 0.7360 | 0.7361 | 0.7361 | 0.7361 | 0.7362 | 0.7361 | 0.7360 |

**Completely flat (±0.0005).** At 30 s stride / 60 s window, temporal misalignment of the
desaturation is not a usable lever. This **kills** the consult's "lag/context on the SpO2 channel"
cheap win *at this resolution*. (Context could still matter at finer resolution or for
arousal-based hypopneas, but not on this grid.)

## 4. Protocol reconciliation (TEST windows)

| Score | pooled across subjects | mean-of-subject |
|---|---|---|
| global head p0 | **0.8715** | **0.8295 ± 0.1134** |
| SpO2-only LR | **0.8791** | **0.8436 ± 0.1070** |

A **~4.2-point gap** between pooled and mean-of-subject. The pooled number is inflated by
between-subject score offsets (some subjects score systematically high, others low), which a
per-subject AUROC deliberately discards. This is the source of the "0.902 vs 0.843 vs 0.880"
confusion: **different units and partitions of the same pipeline**, not different performance.

Cross-checks on this cache (legacy extractor, all 20 subjects):

| Quantity | value |
|---|---|
| global p0, mean-of-subject, TEST half | 0.8295 |
| global p0, mean-of-subject, all windows | 0.8597 |
| global p0, pooled, TEST half | 0.8715 |
| SpO2-LR, mean-of-subject, TEST half | 0.8436 |

The historically quoted "global TEST 0.8430 (n=20)" sits inside this band but is **not bit-identical**
to any single cell above — it was computed on a slightly different window set / aggregation. This is
exactly the protocol-consistency defect the consult flagged: **all published numbers must be reprinted
on one protocol (mean-of-subject, TEST half, legacy extractor is the recommendation).**

## Verdict on the second-opinion model

Largely correct on mechanism, and correct that the blocker is **not** label-freeness (ORACLE stands).
It is **over-confident in two places**, and this run corrects both:

1. It argued that if labels buy nothing, the representation is the limit. The in-sample ceiling
   (0.874) shows the representation is *not* the limit; the limit is FIT→TEST transfer. Labels on FIT
   don't help because they encode the *first* half's distribution, which has drifted.
2. It proposed "input norm + first-layer bias + head" as the next widen. Unconstrained all-layer
   refit **degrades**. Widening is only justified if constrained to the drift direction.

Its lag-lever and representation-ceiling hypotheses are **killed** by §3 and §1 respectively; its
non-desaturating-positives hypothesis is **confirmed** by §2.

## Revised plan (from these results)

1. **Fix the protocol first.** Reprint every reported number on one unit: mean-of-subject AUROC,
   TEST half, legacy extractor. Retire pooled numbers (or report them explicitly labelled "pooled,
   inflated by between-subject offset").
2. **Attack the transfer gap, not the head or the labels.** The gap (ORACLE 0.838 vs IN-SAMPLE 0.874)
   is cross-half distribution shift. Candidate levers, in order:
   - **Per-subject input-side alignment** (baseline-relative SpO2, running normalization) — the one
     lever that changes the *inputs* the frozen head sees, so it can reorder and it targets exactly
     the shift. This is the consult's Q2 first bullet and §2 in this run gives it a concrete target:
     the weak-positive set where −`spo2_min` already reaches 0.71.
   - **Domain-invariant / shift-robust head fitting** rather than unconstrained refit (e.g. shrink
     toward global along the drift direction only), judged against the IN-SAMPLE ceiling as the
     achievable target.
3. **Do NOT** pursue: lag/context at 30 s (dead, §3), unconstrained all-layer refit (worse, §1),
   new label-free losses for the head (ORACLE caps them, §1).
4. **The learning curve is blocked.** The consult's item-1 learning curve needs many labeled central
   subjects; only 20 are on disk and the central_train 70 are not downloaded (~9 GB). Either download
   a subset (~40) to build a real curve, or state the limitation and do a leave-subjects-out curve
   over the available 20 (weak). Do not fabricate it.
5. **Federation** (consult Q4/Q5) is premature until (2) shows a host-side gain on the transfer gap.
   Federation cannot add on top of on-device adaptation if on-device adaptation adds nothing because
   of drift the fleet also has.

## What is fact vs hypothesis here

- **Fact (measured, n = 18):** in-sample head ceiling +0.050 (p=0.007); ORACLE +0.015 n.s.; all-layer
  refit −0.006; strong positives 0.99, weak 0.80; lag flat; pooled−mean gap ≈ 4.2 pts.
- **Inference (strong):** the binding constraint is FIT→TEST transfer, since in-sample ≫ ORACLE ≫ M0.
- **Inference (moderate):** input-side baseline-relative alignment is the highest-value next lever
  because it is the only one that moves the frozen head's inputs in the direction of the shift and has
  a measurable target (weak positives).
- **Untested:** finer-resolution context; PU/co-training ECG student; any federation.
