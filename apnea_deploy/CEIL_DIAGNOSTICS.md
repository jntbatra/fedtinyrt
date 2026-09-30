# Ceiling diagnostics — is any on-device headroom real?

Host-only, no firmware. Script: `tools/ceil_diagnostics.py`
Results JSON: `results/ceil_diagnostics.json`. Run: 2026-09-30.
Cohort: the 20 held-out CinC subjects on disk (18 non-degenerate; `tr05-0647`
and `tr05-1404` have zero positive windows in the first half and are skipped).

These four tests were requested by the external review (Wexler critique) and
decide whether the "on-device adaptation wins" ending is reachable at all.

---

## D1. Purged cross-fit ceiling inside TEST — is a head refit worth anything?

Fit the 17-parameter head on part of TEST, score a **purged** held-out part of
the *same night* (2-window / 60 s purge at each scored-block boundary, to kill
the 50 % window-overlap leak). Per-subject AUROC, mean ± sd over 18 subjects.

| Rung | AUROC | note |
|---|---|---|
| global head on TEST (M0) | 0.8235 ± 0.1172 | frozen reference |
| FIT→TEST ORACLE (true labels) | 0.8381 ± 0.0891 | +0.015, CI reaches +0.043 |
| IN-SAMPLE fit+score TEST | 0.8736 ± 0.0681 | optimism ceiling |
| **PURGED interleaved-block cross-fit** | **0.8030 ± 0.0928** | Δ vs same-window global **−0.0193** [−0.071, +0.042] |
| **PURGED contiguous-half cross-fit** | **0.7702 ± 0.1084** | Δ vs same-window global **−0.0817** [−0.132, −0.039] |
| REVERSE TEST→FIT cross-fit | 0.8834 ± 0.0585 | scored on FIT |

**Reading:** a head refit given *true labels* on held-out same-night windows
does **not** beat the frozen head — it is at or below it. The +0.05 in-sample
number is optimism, not transferable headroom. **Head-level personalisation has
nothing to find.** (The reverse-direction asymmetry is a night-half difficulty
effect, not usable signal.)

---

## D2. Operating point — the one place a real gain exists

Balanced accuracy on TEST (mean ± sd over 18 subjects):

| Threshold | bal acc | Δ vs 0.29 |
|---|---|---|
| shipped fixed 0.29 | 0.5439 ± 0.0566 | — |
| **shared recalibrated τ\* (one τ for all, chosen on pooled FIT; τ\*=0.700)** | **0.6798 ± 0.1197** | **+0.1359** [+0.067, +0.202] |
| per-subject τ\* chosen on FIT, applied TEST | 0.7349 ± 0.1007 | +0.1910 [+0.132, +0.246] |
| **per-subject τ\* cross-fitted within TEST** | **0.7723 ± 0.0758** | **+0.2450** [+0.207, +0.284] |
| **per-subject τ\* − shared τ\* (NET personalisation)** | — | **+0.0582** [+0.022, +0.104], 73 % of subjects up |
| control: AUROC − AUROC@0.29 | — | **+0.0000** (τ-invariant, as required) |

**Reading:** two distinct, real effects.
1. **A calibration fix of +0.136** — one better threshold for everyone. Caveat:
   the host feature pipeline shifts the score distribution relative to the board's
   int8 pipeline, so part of this is a host/board mismatch at 0.29, not a
   deployable gain.
2. **A genuine personalisation increment of +0.058** on top of the best shared
   threshold, 73 % of subjects improving. This is the robust part: it does not
   depend on the 0.29 scaling.

AUROC is **exactly unchanged** — the whole effect lives at the operating point,
which mean-of-subject AUROC cannot see. This is the reviewer's Issue 6, confirmed.

Caveat: τ\* is chosen with **true labels**, so this is an upper bound. The
on-device job is to *estimate* the operating point without labels.

---

## D3. Split-half reliability — is the target learnable?

Estimates computed independently on the two halves of TEST, correlated across
subjects (Pearson r):

| quantity | r(half A, half B) |
|---|---|
| per-subject optimal threshold τ\* | **+0.900** (n=15) |
| per-subject head coefficients (16+1) | +0.780 |
| label-free recentring offsets (3 channels) | **−0.063** |

**Reading:** the per-subject operating point is **highly stable** (r = 0.90) —
there is a real, repeatable personal target to estimate. But the **label-free
recentring heuristic does not recover it** (r ≈ 0). So the mechanism in the
firmware today is the wrong one; the target is learnable, the current recipe is
not the thing that learns it.

---

## D4. Sensor or label — where the ranking ceiling lives

| quantity | value |
|---|---|
| positives (any overlap ≥ 5 s) | 3915 |
| positives (≥ 50 % window coverage) | 223 |
| share of any-overlap positives with ≥ 3 % dip from own baseline | **0.267** |
| share of ≥50 %-coverage positives with ≥ 3 % dip | 0.506 |
| AUROC p0, strong positives (≥3 % dip) + negatives | 0.9897 ± 0.0114 |
| AUROC p0, weak positives (<3 % dip) + negatives | 0.8035 ± 0.1238 |

**Reading:** ~73 % of labelled positive windows have **no** meaningful
desaturation. When a positive *does* desaturate the model is near-perfect
(0.99); when it does not, ranking collapses to 0.80. The ranking ceiling is
mostly a **label-definition / sensor mismatch**, not a modelling gap.

---

## Verdict

- **Ranking (claim b): closed.** D1 (purged refit ≤ global), D4 (73 % of
  positives invisible to SpO2) and the ORACLE all agree. Do not chase AUROC.
- **Operating point (claim a): open.** Net personalisation +0.058 balanced
  accuracy (CI +0.022 … +0.104) on top of a shared recalibration, with AUROC
  untouched. This is the only place a defensible on-device win lives.
- **Mechanism:** must be **operating-point / prevalence estimation**, not head
  training (D1) and not the current label-free recentring (D3, r ≈ 0).

### Honest caveats
- τ\* uses true labels → D2 is an upper bound, not a demonstrated deployment gain.
- The 0.29 baseline is partly a host/board scaling mismatch; the robust number is
  the **+0.058 personalisation-on-top-of-shared-τ**.
- Same 20 subjects as before; a sealed cohort is still needed to confirm.
