# Consultation Brief — Why On-Device Training + Federation Do Not Beat the Frozen Model on the Renesas RA8P1

**Purpose of this document:** hand off enough context for an outside model/engineer to
independently judge six structural reasons why our on-device ("label-free") adaptation and
federated learning have *not* improved over a pre-trained, frozen global model — and to
challenge or correct them.

---

## 1. Project in one paragraph

We deployed a small **INT8 MLP apnea/hypopnea detector** (21 hand-crafted ECG + SpO2 features,
60 s windows, 30 s stride) onto a **Renesas RA8P1** board (Arm Cortex-M85 @ 1 GHz, plus a
Cortex-M33 and an Ethos-U55 NPU). The research question: **can the board take the unlabeled
data it sees locally and self-adapt (and federate) to beat the frozen global model?**
The empirical answer across 20 held-out subjects is a **clean null**: every label-free
adaptation recipe **ties** the frozen global head (all paired tests p ≥ 0.18, all CIs include 0,
all |Δ AUROC| ≤ 0.006). This document is about **why**, structurally.

---

## 2. Hardware

| Part | Detail |
|---|---|
| Board | Renesas **RA8P1** (EK-RA8P1 class) |
| Main core | **Cortex-M85** @ 1 GHz (Helium/MVE) |
| Secondary core | **Cortex-M33** |
| NPU | **Arm Ethos-U55** — present in silicon, **not used**: firmware is CPU-only inference, no FSP Ethos-U55 driver |
| Debug | On-board J-Link (SWD), USB "Debug1" port; J-Link device string `R7KA8P1AF` |
| Console | SCI_B virtual COM → `/dev/ttyACM0` |
| FSP | **6.6.0** |

> Note: an earlier claim that the board has no NPU was **wrong and has been corrected** — the
> Ethos-U55 is present. We make *no* NPU performance claims because we never integrated its driver.

---

## 3. Host toolchain (headless, no GUI)

| Tool | Version / location |
|---|---|
| cmake | 3.31.11 |
| ninja | 1.13.1 |
| arm-none-eabi-gcc | Arm GNU Toolchain 13.2.rel1 (`arm-gnu-toolchain-13.2.Rel1-.../bin`, capital "R") |
| J-Link | V9.78 (`/opt/SEGGER/JLink_V978/`) |
| RASC | from FSP **6.6.0** installer (headless via `xvfb-run`) |
| Host Python | `/tmp/cincenv/bin/python` (numpy, scipy, h5py, wfdb, pyserial) |

The original "Ubuntu guide" that motivated setup was largely wrong and is documented in
`SETUP_NOTES.md`: the host is **Fedora 43** (dnf, no apt); the J-Link V796 URL is dead;
`-device R7KA8P1` fails (must be `R7KA8P1AF`); the RASC 5.3.0 GitHub link is a fabricated 404
(and FSP 5.3.0 predates the RA8P1 — unsupported); RASC has **no** command-line "create new
project" (only regenerates an existing `configuration.xml`); the toolchain dir is `Rel1`
(capital R) and a lowercase path silently fails.

---

## 4. Model and data

- Feature-based MLP, **1,249 parameters** (21 → 32 → 16 → 1), window 60 s / stride 30 s.
- Trained centrally on **70 subjects**; the **final layer (17 params) only** was refreshed in
  **one federated round** across 2 client shards (5 subjects each). Exported to INT8 `.tflite`
  + a C header. Status `PROTOTYPE_ACCEPTED`.
- **ECG contributes almost nothing** (ECG-only AUROC 0.578 vs SpO2-only 0.902) → functionally an
  **SpO2 desaturation detector**.
- **No per-window training features ship in the artifact zip** — only models, aggregates, and
  256 fixed test vectors. Retraining requires raw PhysioNet/CinC 2018 v1.0.0 recordings.
- Subject split manifest: `central_train` 70, `final_test` 10, `validation` 10, `pi_client` 5,
  `renesas_client` 5.

## 5. Evaluation protocol

Per subject, full-record 60 s windows at 30 s stride; chronological **FIT (first half) /
TEST (second half)** split; each recipe is fit on FIT and scored on TEST. The *fair* global
reference (`M0`) is the frozen head scored on the **same TEST windows** (an earlier "−0.027
worse" claim was an all-window-vs-test-window artifact and was **withdrawn**). Baselines:
prevalence (0.5), SpO2 threshold (`spo2_min < 92`), SpO2-only logistic regression. Statistics:
paired t, Wilcoxon signed-rank, per-subject DeLong (Stouffer-combined), bootstrap CIs, plus
calibration (Brier, 10-bin ECE) and operating point at the deployed threshold 0.29.

## 6. Current results (n = 20 held-out subjects)

| Model / baseline | AUROC (mean ± sd) |
|---|---|
| prevalence | 0.5000 ± 0.0000 |
| SpO2 threshold (`spo2_min < 92`) | 0.7729 ± 0.1580 |
| SpO2-only logistic regression | 0.8358 ± 0.1296 |
| **frozen global head (TEST windows, = M0)** | **0.8430 ± 0.1059** |
| M2 / M3 / M4 / M5 (label-free adaptation) | 0.8431 / 0.8456 / 0.8484 / 0.8452 |
| ORACLE (label-supervised ceiling) | 0.8431 ± 0.1007 |

Same-window paired Δ vs global: all |Δ| ≤ 0.006, every 95% CI includes 0, every test p ≥ 0.18.
Board/host parity: `run`/`runraw` = 0 mismatches; `evalhead` AUROC 0.8802. Board left at
`sethead global`.

---

## 7. The six structural reasons (the core of this brief)

### Issue 1 — AUROC is rank-invariant, so a whole class of "adaptation" *cannot* help the metric
AUROC = P(score of a positive > score of a negative). It is invariant to **any strictly
monotonic transform** of the scores. Our label-free recipes (`personalize` = recentre + Otsu
re-threshold; M2–M5 = shift/scale/recalibrate) are monotonic operations. Therefore they **cannot
change AUROC by construction** — they can only move the **operating point** (sensitivity vs
specificity). Our data shows exactly this: AUROC stays ≈ 0.843 while sens/spec trade at
threshold 0.29.

### Issue 2 — The model is already at the signal's information ceiling
The ablation is stark: ECG-only 0.578 (noise), SpO2-only 0.902. Functionally this is an SpO2
desaturation detector, and "did SpO2 drop below ~92%?" is close to a **deterministic threshold on
one signal**. The global model already extracted essentially all separable signal; the headroom
between current performance and the best achievable ranking is tiny. You cannot personalise past
a ceiling set by the *information in the signal*, not by the model.

### Issue 3 — Only the last layer (17 parameters) is trained on-device
The 21→32→16 feature stages are frozen; only the final 17-parameter layer adapts. So on-device
training can merely re-weight an already-good feature set — it cannot learn new **representations**.
Most genuine personalisation gains come from feature/representation learning, which is switched off
here.

### Issue 4 — Label-free objectives carry no new information (no ranking gradient)
Available label-free objectives (`entropy`, `temporal`) do not know the ground truth. Entropy
minimisation induces *confidence* but not *correctness*; temporal consistency assumes adjacent
windows share a label (weak, easily wrong). None provides a signal that reliably **reorders**
positives vs negatives. Without labels (or an accurate proxy), there is no gradient that points
toward better ranking; the best achievable is to match the score distribution — which, by Issue 1,
buys nothing.

### Issue 5 — Federation adds no information here
The "global" model was trained centrally on 70 subjects, and its final layer refreshed in one
federated round across 2 shards. When the board later runs federated rounds, each client head
starts from that same central model and sees data from the **same distribution the centre already
learned**. FedAvg helps when clients hold genuinely diverse, **non-IID** data the centre never saw;
here the centre saw it all, so aggregation just averages heads that already agree.

### Issue 6 — Cross-subject variation is calibration, not representation
What differs between subjects is where SpO2 sits and how desaturation looks — a per-subject
**offset/scale**, i.e. a calibration shift. Calibration shifts are monotonic-ish and therefore
AUROC-invariant (Issue 1). The disorder is real, but it lives *below* the ranking metric we score.

---

## 8. What would have to change for a legitimate win

The six issues stack into three independent ceilings: **(a)** the metric is rank-invariant,
**(b)** the signal is near-deterministic, **(c)** only 17 parameters move. Breaking any one gives
real headroom:

| Change | Why it could help |
|---|---|
| Get **real (or accurate pseudo-) labels** on-device | Converts label-free (no ranking gradient) into supervised — the only lever that reliably moves AUROC |
| Train the **whole network**, not just the head | Enables subject-specific representation learning |
| Add **information the centre never had** (new sensors, metadata, longer context) | Genuinely new signal to exploit |
| Make federation **genuinely non-IID across devices** | Only then does aggregation add information the central model lacked |
| Choose a task/cohort with **actual headroom** | Where the global model is not already at the signal's ceiling |

Our null is therefore partly a property of *this task and this metric*, not a universal law.

---

## 9. The honest position, and the one open direction

We will **not** manufacture a positive result that isn't in the data by tuning until something
rises — that is exactly what a reviewer destroys. The defensible path is to **change the
experimental conditions so a win is earnable**, then report whatever the data says.

The most promising route — and the one the null itself points to — is the **labeling problem**:
on real devices there is no ground truth, so **pseudo-label the on-device data (clustering /
self-supervised), then train supervised on those labels**. This turns a weak label-free objective
into a real ranking gradient, the one lever that can move AUROC. Whether it clears the ceiling is
empirical.

## 10. Questions for the outside model

1. Are the six reasons above correct as stated, and which is *most* load-bearing?
2. Is there any label-free objective that can genuinely change AUROC (i.e. reorder, not just
   shift) without ground truth? If so, what?
3. For pseudo-label-then-supervised-training on-device: what clustering/self-supervised signal
   would most plausibly recover the true apnea labels, given the signal is essentially SpO2?
4. Is there a defensible experimental redesign (cohort, task, metric, or architecture) under
   which on-device training + federation could legitimately beat the frozen model?
5. Any flaw in Issue 5 (federation-adds-nothing) — e.g. a non-IID construction that would
   actually make FedAvg help here?

---

## Appendix — artifacts and reproducibility

- Frozen model + INT8 `.tflite` + C header + 256 test vectors + federation CSVs:
  `/home/jbatra/cinc2018_apnea_artifacts/` (incl. `TRAINING_CONTEXT.md`,
  `subject_split_manifest.csv`).
- Raw PhysioNet/CinC 2018 v1.0.0 records used: `/tmp/cinc_ms/`, `/tmp/cinc_raw/`, `/tmp/cinc_val/`.
- Firmware + tooling: `/home/jbatra/tron/apnea_deploy/` (`src/apnea.c`, `tools/cross_subject_eval.py`).
- Results protocol (append-only, sections P1→P5′): `apnea_deploy/RESULTS_PROTOCOL.md`.
- Consolidated log: `/home/jbatra/tron/PROGRESS_LOG.md`.
- Setup/caveats: `/home/jbatra/tron/SETUP_NOTES.md`.

Reproduce the headline result:

```bash
/tmp/cincenv/bin/python tools/cross_subject_eval.py \
  --ref --baselines --delong --calibration --operating-point \
  --partitions final_test,validation --tag P5 --write
```
