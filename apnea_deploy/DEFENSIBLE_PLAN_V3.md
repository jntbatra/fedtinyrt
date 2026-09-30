# Defensible Evaluation Plan — v3 (P5)

Goal: make the central claim — **on-device, label-free personalisation does not beat the
frozen global head on held-out subjects** — harder to attack, by (a) doubling the held-out
cohort with previously unused subjects and (b) replacing soft claims with formal statistics.

## What was already done (v1 → v2, summarised)

- **v1** — one-subject protocol proof (`tools/protocol_eval.py`) + `RESULTS_PROTOCOL.md`.
- **v2 (P3/P4)** — 10 `final_test` subjects, faithful feature extractor gated to exact match
  against the stored reference vectors (`tools/ref_features.py`, max MAE 0.0, 256/256 labels),
  baselines (prevalence / SpO2-threshold / SpO2-only LR), ECG ablation, board parity.
  Result: global head 0.9211 ± 0.0341; every adaptation recipe is **worse** (paired Δ vs global
  all < 0, bootstrap 95% CI excludes 0); LEAKY (the dishonest upper-bound) ties global by
  construction. Written up as sections **P3′** and **P4′** in `RESULTS_PROTOCOL.md`.

## What v3 adds

### P5-A — double the held-out cohort (20 subjects)

Use the **10 untouched `validation` subjects** (never used for training or tuning) on top of the
10 `final_test` subjects:

    tr03-0532 tr03-1302 tr04-0020 tr04-0631 tr04-0808 tr05-1404 tr06-0122 tr06-0584 tr11-0592 tr12-0684

Fetched to `/tmp/cinc_val` by `tools/fetch_validation.sh` (raw `.mat` + `.arousal`, native 200 Hz).
The validation cohort has a much wider positive-rate spread (≈ 0.005 – 0.71) than `final_test`,
which stresses the negative result across prevalence instead of hiding it.

### P5-B — harden the statistics

1. **Formal paired tests** on the per-subject AUROC differences (n = 20): a paired **t-test** and a
   **Wilcoxon signed-rank** test, plus a **per-subject DeLong** test (Sun & Xu fast algorithm,
   exact correlated-AUC covariance) combined across subjects with **Stouffer's method**. This
   replaces "CI excludes 0" hand-waving with exact p-values (no sklearn dependency).
2. **Calibration** — Brier score + 10-bin expected calibration error (ECE) on TEST, per recipe.
   A recipe that "adapts" by shifting scores can be miscalibrated even at equal AUROC.
3. **Operating point** — sens / spec / precision / balanced-accuracy at the **deployed threshold
   0.29**, aggregated across subjects, so the clinical-readout consequence of the negative result
   is visible, not just the ranking metric.

### P5-C — board parity

Re-confirm `run` / `runraw` = 0 mismatches and `evalhead` on the firmware after the analysis
(model unchanged from Phase F, expected AUROC ≈ 0.88 on all 256 stored vectors).

## Exact commands

```bash
export PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin:$PATH
cd /home/jbatra/tron/apnea_deploy

# (once) fetch the validation cohort — resumable, skips complete records
bash tools/fetch_validation.sh

# P5 run: 20 held-out subjects, faithful features, baselines, DeLong, calibration, operating point
/tmp/cincenv/bin/python tools/cross_subject_eval.py \
    --ref --baselines --delong --calibration --operating-point \
    --partitions final_test,validation --tag P5 --write
```

## Deliverable

A new append-only section **P5** in `RESULTS_PROTOCOL.md` with the 20-subject per-subject table,
aggregate AUROC, paired-Δ bootstrap table **and** DeLong p-values, calibration rows, and the
operating-point table — plus a `## Threats to validity, revisited (P5′)` summary restating the
verdict against both cohorts.
