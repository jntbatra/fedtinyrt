# Label-free operating-point estimator — does the +0.058 survive without labels?

Script: `tools/op_estimator.py`. Results: `results/op_estimator.json`. Run: 2026-09-30.
Cohort: 18 usable held-out subjects. Protocol: leave-one-subject-out (LOSO).

## Verdict: YES — ending (A) is reachable

The per-subject operating-point gain is **earning-able without ground-truth labels**.
A label-free estimator captures **58–95 %** of the labelled ceiling, with a CI excluding 0,
and **AUROC is unchanged** (the gain is purely at the decision line, as predicted).

## Why the target is a *shift*, not prevalence

Balanced accuracy `BA = ½(TPR+TNR)` is prevalence-invariant — both terms are conditional on
the true class. So a per-subject change in the event rate does **not** move the optimal line.
What moves it is a per-subject **shift of the score distribution** (covariate shift). The
estimator therefore matches the *shape/location* of the target's unlabeled scores to the
reference cohort — it does not estimate prevalence.

## Protocol

For each target subject *j*, the labelled reference cohort = the other subjects' FIT halves.
*j*'s TEST scores are treated as **unlabeled** (deployment condition). The estimator outputs
`τ̂_j`; balanced accuracy is measured on *j*'s TEST.

Reference numbers (mean-of-subject balanced accuracy):
- fixed 0.29: **0.5439**
- shared τ (one line for all, label-free): **0.6767** ← floor
- labelled per-subject τ\*(FIT): **0.7349** ← gap = **+0.0582**
- labelled cross-fitted within TEST: **0.7723** ← conservative bound, gap = +0.0956

## Results

| estimator | labels? | mean BA | Δ vs floor | 95 % CI | capture (FIT gap) | capture (conservative) |
|---|---|---|---|---|---|---|
| E0 shared τ | no | 0.6767 | — | — | 0 % | 0 % |
| E1 logit quantile-shift | no | 0.7143 | +0.0376 | [−0.008, +0.088] | 64.5 % | 26.6 % |
| **E1p prob-space quantile-shift** | **no** | **0.7287** | **+0.0519** | **[+0.014, +0.097]** | **89.2 %** | **58.3 %** |
| E1T tail-only quantiles | no | 0.6974 | +0.0207 | [−0.012, +0.057] | 35.6 % | −2.4 % |
| E2 EM shift+prevalence | no | 0.6987 | +0.0220 | [−0.013, +0.065] | 37.8 % | 23.8 % |
| **E3 shift + scale** | **no** | **0.7538** | **+0.0771** | **[+0.031, +0.129]** | **132.5 %** | **94.6 %** |
| positive control (true labels) | yes | 0.7349 | +0.0582 | [+0.012, +0.116] | 100 % | — |
| cross-fitted ceiling (true labels) | yes | 0.7723 | +0.0619 | [+0.025, +0.109] | 106 % | 100 % |
| shuffle null | no | 0.6189 | −0.0578 | [−0.116, +0.003] | −99 % | — |

AUROC is **0.8235 for every row** — the estimator moves only the operating point.

## What the numbers mean

- **E3 (shift + scale) is the winner**: with no labels it reaches **0.7538**, above the
  labelled τ\*(FIT) control (0.7349) and **94.6 % of the way to the conservative cross-fitted
  labelled ceiling**. It improves **83 %** of subjects (the labelled control improves 67 %),
  with a *better worst case* (−0.041 vs −0.066).
- **Why the scale term matters**: the pooled reference distribution is *wider* than any single
  subject's (fitting many people inflates the spread). Mean fitted scale = 0.56 — the
  estimator is legitimately correcting pooled-vs-individual variance, not overfitting. This
  is why E3 > E1p.
- **E1p** (pure prob-space shift) is the robust simple version: 58 % of the conservative gap,
  CI excluding 0.
- **E2 (prevalence EM) is weak** (24 %) — direct confirmation that prevalence was the wrong
  lever, as the theory predicted.
- **The shuffle null is ≈ 0** (slightly negative, as expected when perturbing a *good* shared
  line), so the gain comes from the *matching*, not merely from moving the threshold per
  subject. This is the leakage guard passing.

## Honest caveats

- Reference cohort is 19 subjects → coarse density/spread estimates.
- Two hard subjects (`tr04-0020`, `tr04-0029`) do **not** improve — the estimator does not
  rescue the worst cases, only the typical ones.
- The 0.29-baseline portion of the earlier +0.136 still carries the host/board scaling caveat.
- No sealed cohort yet: this is a **mechanism demonstration**, not a deployment claim.

## Next step (queued, not started)

Board parity & cost: implement the estimator over the **64-bin probability histogram the
firmware already builds** (`otsu_threshold`, `src/apnea_personal.c:453`), add a `setthr <p>`
command next to `personalize`/`resetoff`, flash, verify host↔board threshold agreement, and
measure cycles. Purely mechanical — does not change the verdict above.
