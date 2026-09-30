# Plan: defensible results for the RA8P1 apnea deployment

## Claim we want to defend
On the RA8P1, a **label-free** on-device adaptation (recentre SpO2 features +
Otsu threshold) and a **federated head** protocol improve the *operating point*
over the frozen global model, at measured cycle/energy cost — and the effect is
**not leakage**: it holds on windows the adaptation never saw, across multiple
untouched subjects.

## Threats to validity we must close
1. **Leakage** — `personalize` selects baseline windows, fits offsets, picks the
   Otsu threshold, *and* reports metrics all on the same 256 windows
   (`src/apnea_personal.c:1240`). Fix: fit on a fit-split, report on a held-out
   split with a 60 s guard between them (windows overlap 30 s).
2. **Fake sites** — "site A/B" is an index split of one subject. Fix: evaluate
   the per-subject protocol across many subjects from the untouched
   `final_test` partition.
3. **No uncertainty** — report bootstrap 95% CI on AUROC and Wilson 95% CI on
   balanced accuracy.
4. **No baselines** — ablate: global@0.29 → global+Otsu → recentre+Otsu →
   head-train(teacher) → head-train(label-free) → FedAvg over fit-sites.
5. **Feature drift** — our host extractor's ECG features do not match the
   reference (reference double-counts beats; ECG-only AUROC ~0.58). State
   explicitly; do not claim ECG contributes.
6. **n=1 subject** — the current firmware demo is one subject. Extend with the
   10 `final_test` subjects.

## Phases
- **P1 (host, now):** build `tools/protocol_eval.py` implementing the exact
  firmware semantics on the npz vectors, with the guarded split, CIs, ablations.
  Gate: reproduced float MLP matches stored `float_probability` (max diff <1e-5).
- **P2 (board, now):** flash current firmware; run the same subject's pipeline
  on hardware (`personalize`, `train`, `fedrounds`, `evalci`, `cycrep`); confirm
  host↔board agreement and capture cycle counts → energy estimate.
- **P3 (background):** download the 10 held-out `final_test` subjects, extract
  features + labels (`.arousal`), run the per-subject guarded protocol on each;
  produce the cross-subject table (mean ± sd of personalization gain).
- **P4:** write `RESULTS_PROTOCOL.md` with tables, CIs, ablations, and an
  explicit threats-to-validity section.

## What is explicitly out of scope / not claimed
- No accuracy-ceiling improvement (AUROC stays ~0.88 single-subject; the
  published 100-subject federated AUROC is 0.934, already in the artifacts).
- No Raspberry Pi measurement (no Pi reachable here) — cite the artifact's
  `federation_client_metrics.csv` instead of inventing numbers.
- NPU unchanged (inference-only, no FSP driver).
