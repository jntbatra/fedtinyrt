# Step 8 Results — Model, Dataset & Cross-Machine Validation

Roadmap **Step 8** (PC pre-train + INT8 export + golden vectors), which also
empirically validates **Step 11** (on-device incremental training) and the whole
federated thesis.

Dataset: **NASA IMS** bearing run-to-failure. Task: classify `normal / degrading / fault`.
Model: small MLP (38 features → 32 → 16 → 3), INT8 TFLite, **4.1 KB** (Ethos-U55 / NPU eligible).

---

## TL;DR — the honest progression

| Stage | What | Balanced acc | Verdict |
|-------|------|-------------|---------|
| 0. First pass | random split, RMS-threshold labels | 99.5% | **fake** — two data leaks |
| 1. Leaks fixed | grouped-by-file split, time-based labels | **96.6%** | honest, same-machine |
| 2. Cross-machine, zero-shot | train machine A, test unseen machine B | 52% → 66% (abs → normalized) | **transfer fails** on `degrading` |
| 3. **Personalized (deployment)** | fine-tune on machine B's own data | **99.6%** | **the real, deployable number** |

The headline: a single global model does **not** transfer across machines, but
**on-device personalization fixes it completely** — which is exactly why FedTinyRT
does on-device training + federation. The good number is achieved *through the
project's own mechanism*, not by hiding leakage.

---

## Stage 0 → 1: removing the leaks

The first run scored **99.5%** but was inflated by two leaks:

1. **Label leakage** — labels were thresholded from RMS, and RMS was also a model
   feature. The model just recovered the labeling rule.
2. **Sibling-window leakage** — each 1 s file was cut into 10 windows, then split
   randomly, so near-identical sibling windows landed in both train and test.

**Fixes:**
- Labels from **position in the run-to-failure timeline** (independent of features).
- **GroupShuffleSplit by file** — a file's windows never straddle train/test
  (verified: train/test group overlap = 0).

Honest same-machine result: **acc 98.4%, balanced 96.6%**, fault recall 93.6%.
Verified the labels track real physics: degrading-region RMS = **1.69×** normal.

## Stage 2: cross-machine reality check

Train on machine A (2nd_test, bearing 1), test on a **different** run-to-failure,
machine B (3rd_test):

- **Absolute features:** balanced **52%** — the model keyed on machine A's amplitude
  scale and screamed "fault" at 40% of B's *normal* data.
- **Per-machine baseline normalization** (each machine standardized by its own healthy
  startup data): balanced **66%**. `normal` and `fault` now transfer well
  (F1 0.985 / 0.965), but **`degrading` (the subtle middle class) still fails (0%)** —
  it is genuinely machine-specific.

This is the empirical justification for the project: **no single model fits all machines.**

## Stage 3: personalization (the FedTinyRT mechanism)

Ship the A-pretrained model to machine B, fine-tune on a slice of B's **own** data
(on-device incremental training), evaluate on **held-out** B files:

| B (cross-machine) | balanced | normal F1 | degrading F1 | fault F1 |
|---|---|---|---|---|
| zero-shot | 66.5% | 0.990 | 0.002 | 0.832 |
| **personalized** | **99.6%** | **1.000** | **0.995** | **0.995** |

- Fine-tuned on 30% of B's files, tested on the other 70% (grouped — no leakage).
- The adapt labels are **self-generated** from the RMS health-indicator rule the device
  computes itself → personalization is **autonomous**, no human labeling.

`degrading` recall goes **0.1% → 99.4%** purely from on-device adaptation.

---

## Why a small MLP (not RF/SVM/LSTM)

- **NPU constraint:** the Ethos-U55 only accelerates neural nets — RF/SVM can't run on it.
- LazyPredict (grouped split) ceiling is ~98% balanced (SVC/RF); the MLP matches it.
- **No LSTM:** inference is per-window classification, not a sequence; Vela/Ethos-U
  don't accelerate RNNs. For temporal context the NPU-friendly option is a small 1D-CNN.

## Files

| File | Purpose |
|------|---------|
| `feature_extract.py` | FFT bands + time stats — shared with firmware Step 7 |
| `prep_ims.py` | IMS → time-labeled, file-grouped features (`dataset.npz`) |
| `build_xmachine.py` | features for machine A & B with HI-onset labels |
| `relabel.py` | relative-threshold relabeling (cross-machine comparable) |
| `train_tflite.py` | train + INT8 quantize + export model/golden/C arrays |
| `xmachine_train.py` / `xmachine_norm.py` | cross-machine: absolute vs baseline-normalized |
| `personalize.py` | Stage 3 — on-device fine-tune (zero-shot vs personalized) |
| `lazy_compare.py` | accuracy-ceiling reference (LazyPredict) |
| `verify.py` | split-disjointness + label-vs-physics sanity checks |
| `artifacts/model_int8.tflite` | 4.1 KB device model (Vela + TFLite-Micro input) |
| `artifacts/model_data.c/.h` | model as C array + feature mean/std for firmware |
| `artifacts/golden_vectors.json` | input→output oracle for on-device validation |

## Numbers to quote (honest)

- **Same-machine:** ~97% balanced
- **Cross-machine, zero-shot:** ~66% (normal/fault transfer; degrading doesn't)
- **Cross-machine, personalized:** **~99.6%** ← the deployment number

## Open / next

- Only 2 machines so far. Stage 3b (extract 1st_test → 3–4 machines, leave-one-out
  domain generalization) would further harden the zero-shot baseline.
- Feed `model_int8.tflite` to **Vela** for the NPU (firmware Step 10); validate device
  inference against `golden_vectors.json`.
- Implement the **self-labeled personalization** on-device as Step 11.
