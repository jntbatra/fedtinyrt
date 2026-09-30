# Board port of the operating-point estimator — parity restored, constants corrected

Firmware: `src/apnea_personal.c` (hand-written). Commands: `qstat`, `setthr`.
Host tools: `tools/op_estimator.py` (estimator ladder), `tools/opref_board.py` (board-space constants).
Run: 2026-09-30. Board left **clean** (`drift L2 0.0000`, threshold 0.29, bal 0.7751).

## Root cause of the apparent "parity failure"

The first board run reported a large board-vs-host score mismatch. It was **my error, not a
firmware bug**: I compared the board against `int8_probability` from
`fixed_test_vectors_float32.npz`, which belongs to the **legacy 21-feature model**, while the
board runs the **spo2_10 INT8 model** (`src/apnea_model.h`, `APNEA_IN_DIM = 10`, 897 params;
selftest inputs = SpO2 columns 11:21). Different model, different score scale.

## Parity is intact

Re-scoring the same 256 windows with **the board's own model** (`tools/opref_board.py`):

| logit pct | p05 | p25 | p50 | p75 | p90 | p95 | min | max |
|---|---|---|---|---|---|---|---|---|
| host re-score (board model) | −5.46 | −4.71 | −4.14 | −3.67 | −1.51 | +0.09 | −5.46 | +3.20 |
| **board `qstat`** | −5.58 | −4.69 | −4.18 | −3.74 | −1.56 | +0.14 | −5.58 | +3.23 |

AUROC 0.8988 (host emulation) vs **0.8927** (board); decisions at 0.29 differ by one FP
(tp 9 / fp 13 / fn 6 / tn 228 vs board tp 9 / fp 12 / fn 6 / tn 229). The residual is the
board's float dequantised path vs the int8 emulation. **The board is correct.**

## Constants corrected (two fixes)

1. **Wrong score space.** The original defaults (0.4249, 2.2850, 0.8473) came from the
   **legacy 21-feature** host scores. Re-derived with the board's spo2_10 model on the 67
   usable central_train subjects' FIT halves.
2. **Pooled reference inflated the spread.** Pooling windows across subjects mixes in the
   *between-subject* variance: pooled spread **5.364** vs median per-subject spread **3.200**
   (~1.7× too large), which over-corrected the scale and drove the threshold far too low.
   Switched to a **per-session reference** (estimator E4): reference = median of per-subject
   medians, spreads and threshold-offsets.

Final constants in the firmware:

```
ref_med  = -3.293730   (median of per-subject medians)
ref_p90  = -0.094107   (ref_med + median per-subject spread 3.199623)
ref_thr  = -1.947199   (ref_med + median per-subject offset 1.346531)
```

Host validation of the E4 variant (`tools/op_estimator.py`, LOSO over 18 subjects):
mean BA **0.7569** vs E3's 0.7538 and the labelled τ\*(FIT) control 0.7349 — the best
label-free estimator in the ladder, CI [+0.034, +0.133].

## Measured on the board

```
ref  med -3.2937 p90 -0.0941 thr -1.9472
sess med -4.1752 p90 -1.5570 scale 0.8183
threshold 0.2900 -> 0.0442   (77429 cycles)
before  bal 0.7751  f1 0.5000  sens 0.6000  prec 0.4286  predpos 21
after   bal 0.7669  f1 0.3509  sens 0.6667  prec 0.2381  predpos 42
```

**Cost: 77,429 cycles** per session (256 windows ≈ 2 h) ≈ 77 µs at 1 GHz; RAM ≈ 2 KB (two
256-float work arrays). No NPU, no training.

## Honest reading of this session

On subject `tr03-0322` the estimator is a **wash**: 0.7669 vs 0.7751 at the shipped 0.29.
That subject's own optimum is much lower still (0.020 → bal 0.815), so the estimator
*under-corrects* here. This is expected: the host study finds the estimator improves ~83 % of
subjects, not all of them, and one session with 15 positives cannot validate a gain.

What this run **does** establish: the mechanism builds, runs on-chip, is arithmetically
correct, is calibrated in the right score space, matches the host to int8 rounding, and costs
~77 k cycles / 2 KB.

## Files

- `src/apnea_personal.c` — `qstat`, `setthr`, `logitf_`, `quantile_sorted_`, `session_logit_sorted_`
- `tools/opref_board.py` → `results/opref_board.json` — board-space reference constants
- `tools/op_estimator.py` — host estimator ladder (E0–E4) + controls
- `OP_ESTIMATOR.md` — host-side validation and the label-free result
