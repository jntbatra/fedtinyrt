# Retraining Plan — raise the ceiling, then rebuild the whole stack

Status: **active**. Owner: main agent. Mode: CLI/host only. No firmware edits until Phase 4.
Interpreter for all tooling: `/tmp/cincenv/bin/python` (numpy 2.5.3, scipy 1.18.1, wfdb).

## 0. Why retrain at all (the one-paragraph justification)

`DIAGNOSTICS.md` proved the binding constraint is **FIT→TEST transfer (night drift)**, not head
size, not labels, not the 16-d representation:

| Rung (n=18) | AUROC |
|---|---|
| M0 global head | 0.8235 |
| ORACLE — true labels, head-only, FIT→TEST | 0.8381 (n.s.) |
| **IN-SAMPLE — fit + score TEST (head-only ceiling)** | **0.8736** (p=0.007) |
| ALL-LAYERS refit, FIT→TEST | 0.8177 (worse) |

And the residual error is concentrated on **weak (non-desaturating) positives** (1,417 of 1,629),
scored 0.80, while strong positives are solved (0.99). Lag is dead (±0.0005). So the only levers
that can move the number are ones that change **the inputs the frozen head sees**:

1. **Baseline-relative SpO2** (input-side alignment) — targets the night drift directly.
2. **New ECG features aimed at the events' real ECG signature** — CVHR (cyclic variation of heart
   rate) and EDR (ECG-derived respiration) — targets the weak-positive floor.
3. **Shift-robust head fitting** (shrink toward global along the drift direction) — targets transfer.

Phase 1 tests all three **on the 20 subjects already on disk, with no download**. If none move the
ceiling, the honest deliverable is ceiling analysis + operating-point calibration + on-board cost,
and we stop chasing AUROC (that is a real, defensible outcome). If any moves it, we download and
rebuild.

## 1. Machine capacity (verified)

i5-7500T, 4 cores, 15 GB RAM, no GPU, ~54 GB free. Central-train ML fit is **3.1 s for 50 epochs
on 61,900 windows**; feature matrix 5.2 MB. Compute is *not* the constraint; the 11 GB download
and feature extraction are. Parallelise feature extraction across the 4 cores.

## 2. Phases, gates and deliverables

### Phase 0 — Lock the protocol (done criteria: one table, machine-readable)
- Freeze the reporting unit: **mean-of-subject AUROC, TEST half, extractor named explicitly**.
- Emit `results/baseline_protocol.json` with M0 / ORACLE / IN-SAMPLE on that unit and the window
  counts, so every later number is compared like-for-like.
- Retire pooled numbers (report only if labelled "pooled, inflated by between-subject offset").

### Phase 1 — Cheap kill-tests on the 20 on-disk subjects (NO DOWNLOAD)
Three probes, each with an explicit kill condition:

- **1a ECG-only kill-test.** Train an ECG-only head (11 ECG features, SpO2 channels set to their
  mean) on FIT, score AUROC on **weak positives + all negatives** in TEST.
  *Kill:* if ECG-only AUROC on weak positives ≈ 0.5 → current ECG carries nothing for those events;
  new ECG features are the only route, and they must be shown to fix it in 1b or Wall 2 stands.
- **1b New ECG features (CVHR + EDR).** Compute from raw ECG on disk, per 60 s window:
  RR-band-power in the 0.01–0.04 Hz band (CVHR index), R-peak-amplitude std/range (EDR),
  HR surge (max−min HR). Add to the feature set; re-measure weak-positive AUROC and the
  IN-SAMPLE ceiling.
  *Pass:* weak-positive AUROC rises materially (target ≥ +0.02) OR in-sample ceiling rises.
- **1c Baseline-relative SpO2.** Per-subject slow baseline (rolling ~20 min median), then
  baseline-relative features (min−baseline, drop-from-baseline, ODI-style dip count ≥3%).
  Re-measure FIT→TEST transfer gap and mean-of-subject AUROC.
  *Pass:* ORACLE / in-sample gap narrows, or M0 rises ≥ +0.02 on the frozen unit.
- **1d Shift-robust head.** Constrain the head refit to shrink toward global along the drift
  direction (already partly in `recentre`); quantify its incremental value over 1c.

**Gate G1:** if 1a kills the ECG route AND 1b/1c do not move the ceiling → stop, write the ceiling
analysis, do not download. Otherwise → Phase 2.

### Phase 2 — Data expansion (only if G1 passes)
- Background-download the 70 `central_train` subjects (`tools/fetch_record.py`, ~156 MB each,
  ~11 GB total, ~1–2 h). Monitor disk; skip 404s (e.g. `tr14-0002`) and record them.
- Rebuild the **chosen** feature set for all 90 subjects (70 central + 20 on disk), parallel across
  4 cores. Cache to `/tmp/feat_v2_cache.npz`, versioned by feature-set hash.

### Phase 3 — Retrain central
- Fit feature normalization on central only; train N→32→16→1 MLP; save float + int8.
- **Learning curve** (decisive): mean-of-subject AUROC vs number of labeled central subjects
  (5, 10, 20, 40, 70). This is the single number that says whether federation *can* help.
- Emit `results/central_v2_metrics.json`, `results/learning_curve.json`.

**Gate G2:** if the curve is flat by 70 on the new features → federation cannot help on this data;
say so and pivot the defensible claim to operating-point/AHI calibration. If it is still rising →
Phase 6 becomes worth running.

### Phase 4 — Re-quantise and restore board parity
- Regenerate int8 header + normalization headers + thresholds from the v2 model.
- Re-flash via `flash.jlink` and re-run the board `run`/`runraw` parity harness.
  *Done:* 0 mismatches float-vs-int8 on the fixed test vectors.
- **Do not hand-edit FSP-generated files.**

### Phase 5 — On-device adaptation with the new inputs
- Re-run the on-device protocol (recentre → head adaptation) with the v2 features; judge against the
  IN-SAMPLE ceiling as the achievable target and against `sethead global` as the rollback.
- Report cycles/ms per adaptation step and RAM (never energy — no probe exists).

### Phase 6 — Federation (only if G2 says the curve is rising)
- Fleet **larger than the centre** (hundreds of unlabeled subjects, one simulated device each);
  personal params (calibration/threshold/baseline) vs shared params (ECG branch/fusion) split
  FedPer/FedRep-style. Compare local-only / FedAvg / FedProx / Ditto.
- Units: unseen clients, held-out nights, bytes per round, on-board time.

## 3. What is forbidden / guardrails
- Never claim energy/power (no probe). Never claim the NPU works (no FSP driver).
- Do not hand-edit FSP output. Keep teacher frozen to avoid collapse.
- Pre-register primary metric and minimum effect of interest **before** looking:
  primary = mean-of-subject AUROC, TEST half; MEOI = +0.02 AUROC, or a few points of balanced
  accuracy at the fixed 0.29 threshold (claim (a), operating point) with claim (b), ranking, kept
  separate.
- Subject is the unit for every AUROC claim; report the per-subject minimum Δ, not just the mean.

## 4. Deliverables
- `results/*.json` per phase, `RETRAIN_RESULTS.md` summary, board parity log, and an updated
  `PROGRESS_LOG.md` section. Nothing is "done" until the deliverable runs end-to-end on the board.
