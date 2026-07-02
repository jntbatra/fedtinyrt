# FedTinyRT — System Overview (read this first)

A plain-language guide to the whole system. For deeper detail: `context.md` (strict definitions),
`RFC-001-systems-contract.md` (engineering SLAs), `KANBAN.md` (build plan).

> **Honesty note (REALITY FILTER):** claims are tagged `[Verified]` (checked against a source),
> `[Inference]` (reasoned, not directly confirmed), `[Target]` (a goal we must still measure), or
> `[Unresolved]` (not yet decided). This doc does not present goals as achievements.

---

## 1. What this is, in one paragraph

FedTinyRT is a small medical-screening device: a **Renesas EK-RA8P1** board that watches a person's
walking motion through an **accelerometer** and detects **Freezing of Gait (FoG)** — the moments a
Parkinson's patient's feet "get stuck." Each **hospital** owns one board. The board **learns from its
own patients on-device** and then shares **only the learned model weights** (never patient data) with
other hospitals, which are combined into a better shared model. The result: hospitals collectively
build a strong FoG detector **without any patient data ever leaving any hospital** — real-time, low
power, and privacy-preserving.

**Plain analogy:** several hospitals each teach their own copy of a student privately. Once a week
they swap *lesson notes* (model weights), never the *patient files*. Every hospital's student gets
smarter; no records are exposed.

---

## 2. The problem we solve

1. **FoG detection is real-time and safety-relevant** — catching a freeze as it happens could trigger
   a cue to help the patient step. `[Verified]` it's a heavily researched wearable-sensor task.
2. **Models don't transfer between sites** — `[Verified]` published FoG work shows a model trained at
   one clinic degrades at another (documented as an open problem; FOGSense explicitly lists cross-site
   generalization as future work).
3. **Patient data legally cannot be pooled** (HIPAA/GDPR) — so you cannot just gather everyone's data
   on one server.

**Federated learning** solves 2 + 3 at once: keep data local, share only weights, average them.
A small/rural hospital with few patients gets a big-hospital-quality model **privately.**

**Our contribution `[Inference, based on contest/literature review]`:** FoG + federated learning has
been done on PCs/phones — but **not** on a **µT-Kernel RTOS + dual-core + NPU + on-device training on
a real MCU** with a measured real-time guarantee. That embedded realization is the novel part; the ML
method is prior art we build on (not claimed as new).

---

## 3. How it works, end to end

```
  [Accelerometer]  --I2C-->  [M85 core]  --features-->  [Ethos-U55 NPU]  --> freeze / no-freeze
       100 Hz               ring buffer,               (INT8 CNN                 (shown live)
                            2 s windows                inference)
                                                             |
   patient data STAYS on the board                           v
                                          [M33 core]  trains the model's head on THIS
                                          hospital's data (in parallel), and is the
                                          "privacy gate": only WEIGHTS may leave.
                                                             |
                                          --Ethernet (weights only, offline-first)-->
                                                             v
                                          [PC Aggregator]  averages weights from all
                                          hospitals (FedAvg) --> new global model --> back to boards
```

**The loop:** sense → screen (predict) → learn locally → share weights → average → receive better
model → personalize → repeat. Raw signal never leaves the board; only ~KB of weights travel.

---

## 4. The hardware, plainly (EK-RA8P1) `[Verified — Renesas]`

- **Cortex-M85 @ 1 GHz** (+ Helium/MVE SIMD) — the fast brain: samples the sensor and runs inference.
- **Cortex-M33 @ 250 MHz** — the helper: trains the model's head *in parallel* and guards the network.
- **Ethos-U55 NPU @ 500 MHz (256 GOPS)** — a dedicated neural-net accelerator; runs the detector
  **inference** far faster/cheaper than the CPU. **It cannot train** (inference only).
- **Memory tiers:** TCM 256 KB (M85) / 128 KB (M33) · 2 MB SRAM (activations) · 1.6 MB ECC SRAM ·
  **1 MB MRAM** (non-volatile: code + model) · board adds 64 MB flash + 64 MB SDRAM.
- **Ethernet (gigabit-capable, with TSN)** — carries weights only, and only during sync windows.
  **No onboard BLE/WiFi** — the RA8P1 has no radio; Ethernet is the only link.
- **TrustZone**, 22 nm ultra-low-leakage process (low power).
- **No onboard accelerometer** — one is added over I2C (Grove/Qwiic) for the bench/liveness demo.

**Physical form — the board is NOT worn.** It is a **desk/cart clinic base station** (big, has a
display, mains-powered — a fall hazard on a patient). The patient wears only a **small sensor node**:
`[Decision #24]` an **ESP32-C3/S3 + accelerometer** clipped to the waist that streams readings over the
**hospital WiFi/LAN to the base station's Ethernet** (no radio added to the RA8P1). Long wires to a
walking, fall-prone patient are rejected (unreliable + trip hazard). *The wearable is a documented
extension; the contest demo uses dataset replay + a hand-waved accel as a liveness prop.*

**Why two cores matter:** inference (M85) and training (M33) run on **physically separate cores at the
same time**, so learning can never delay the real-time screening. That is the core RTOS thesis.

---

## 5. Methodology

The scientific and engineering method, step by step. Designed to be **honest first** (we killed
inflated numbers in an earlier phase of this project and carry those lessons here).

### 5.1 Data
- **Datasets `[Verified]`:** Kaggle *tlvmc* FoG — `tdcsfog` (lab, 128 Hz, m/s²) + `defog` (home,
  100 Hz, g). Daphnet (10 patients, 64 Hz) as a disjoint pretraining "seed." FoG-STAR reserved as a
  future real extra site.
- **Harmonization (critical):** `[Verified traps]` convert units (1 g = 9.81 m/s²), **resample to a
  canonical 100 Hz**, keep only valid annotated regions (`defog` `Valid`/`Task`). Skipping this makes
  the cross-site test meaningless (a 9.81× scale jump masquerades as domain shift).

### 5.2 Windowing & features
- **2-second windows, 50 % overlap** (200 samples at 100 Hz) → one prediction every 1 s. `[Verified]`
  matches SOTA edge-FoG practice.
- **Two feature paths, benchmarked:**
  - *Interpretable baseline:* the classic **Freeze Index** (power in the 3–8 Hz "freeze" band ÷ 0.5–3 Hz
    "walk" band) + band powers + stats → a tiny MLP.
  - *Device path:* the **raw window → depthwise-separable 1D-CNN** (learned features), which uses the
    NPU. Ship whichever scores better; keep the MLP as a fallback.

### 5.3 Model & quantization
- **Device model:** depthwise-separable **1D-CNN**, INT8-quantized, NPU-accelerated (TCN or unidirectional
  LSTM held as upgrades if it underfits).
- **Precision rule:** **train in FP32** (M33 CPU / PC), **infer in INT8** (NPU). No FP16/FP64 (no
  hardware benefit).
- **On-device training is head-only** — the CNN body stays frozen (cheap NPU inference), only the last
  layer(s) fine-tune, so training fits the weak M33.

### 5.4 Federation
- **Star topology**, **synchronous rounds**: each hospital trains locally → sends **full FP32 weights**
  → PC aggregator averages (**FedAvg**) → sends the global model back.
- **Warm start:** round 0 is a Daphnet-pretrained seed (kept disjoint from test data).
- **Personalization:** after each round, a hospital lightly fine-tunes the global model on its own data
  for local screening — this copy is **never shared** (avoids "catastrophic forgetting" and keeps the
  shared model honest).

### 5.5 Evaluation (how we avoid fooling ourselves)
- **Subject-level splits** — a patient is wholly in train or test, never both (prevents the leakage that
  faked a 99.5 % in our earlier work).
- **Three tests:** per-hospital (local vs federated vs personalized), **leave-one-hospital-out**, and
  **lab→home cross-site**.
- **Metric = Average Precision / AUPRC** (matches the Kaggle competition), plus **sensitivity &
  specificity**. **Accuracy is banned** as a headline because freezes are rare (a "always no-freeze"
  model scores 95 % while catching nothing).

### 5.6 On-device verification
- A device prediction must match the PC "golden vector" within tolerance; the NPU binary is built with a
  pinned toolchain so results are reproducible. Real-time is proven by **0 missed sampling deadlines
  during training** (measured on hardware — see `KANBAN.md` slice S7).

---

## 6. Assumptions

These are the things we take as true; if one breaks, results may change.

| # | Assumption | Status / risk |
|---|------------|---------------|
| A1 | The chosen public datasets represent real hospital FoG well enough to demonstrate the *method*. | `[Assumption]` — it's a **simulation of hospitals**, not a clinical trial. |
| A2 | Partitioning one dataset's **subjects** into groups is a fair stand-in for separate hospitals. | `[Assumption]` reasonable; real multi-site (FoG-STAR) is a future upgrade. |
| A3 | The FoG signal lives in the accelerometer's frequency bands we window/feature. | `[Verified — literature]`. |
| A4 | On-device head-only training fits the M33 (128 KB TCM, 250 MHz) in acceptable time. | `[Unresolved]` — **must be benchmarked** (KANBAN S2 gates this; fallback = train on M85 idle slots). |
| A5 | INT8 quantization keeps enough accuracy on subtle freezes. | `[Target]` — measured in S5; INT16 fallback exists. |
| A6 | The NPU is coupled to the M85; the M33 trains on CPU only. | `[Inference]` — confirm from datasheet. |
| A7 | Hospitals share the *same* label space, sensor placement (lower back), and sampling after harmonization. | `[Required invariant]` — federation is invalid otherwise. |
| A8 | Network is intermittent; the device works offline and syncs weights when connected. | `[Design decision]` — offline-first. |
| A9 | Federation is *trusted* (hospitals are honest) in v1. | `[Assumption]` — malicious-node robustness is a future extension. |
| A10 | Clinical labels come from clinicians in production; dataset labels stand in for the demo. | `[Design decision]`. |
| A11 | The board is a desk base station; the patient wears only a small wireless accel node (ESP32→LAN). | `[Decision #24]` — no radio on RA8P1; wearable is a documented extension, not needed for the demo. |

---

## 7. Tools & libraries used

**Hardware / RTOS / firmware**
- Renesas **EK-RA8P1** board (Cortex-M85 + M33 + **Ethos-U55** NPU).
- **µT-Kernel 3.0** (BSP2) real-time OS · Renesas **FSP** · **e2 studio** IDE.
- **Arm Vela** compiler (TFLite → Ethos-U NPU binary) · **TFLite-Micro** runtime.
- **CMSIS-NN** (CPU NN fallback) · **CMSIS-DSP** (Helium-accelerated FFT for the Freeze-Index path).
- External **I2C accelerometer** (chip TBD) · **SEGGER RTT / J-Link** for on-target debug/telemetry.

**PC-side ML & federation (Python)**
- **TensorFlow / Keras** (model build + training) · **TFLite converter** (INT8, via SavedModel path).
- **scikit-learn** (metrics: average precision, balanced accuracy; subject-level `GroupShuffleSplit`).
- **NumPy / SciPy** (FFT, signal processing, windowing) · **LazyPredict** (accuracy-ceiling baseline).
- Custom **FedAvg** implementation (`federate_*.py`).

**Datasets**
- Kaggle **tlvmc Parkinson's FoG** (tdcsfog + defog) · **Daphnet FoG** (seed/benchmark) ·
  **FoG-STAR** (future real site).

**Dev infra**
- **git** + **GitHub** (private repo `jntbatra/fedtinyrt`), **GitHub Issues/Projects** (HIL kanban),
  **gh** CLI.

---

## 8. Uncertainty estimation

How confident we are, where the error comes from, and how we quantify it. (Often skipped — we make it
explicit.)

### 8.1 Two kinds of uncertainty
- **Deterministic parts (near-zero uncertainty):** `[Verified]` INT8 NPU inference is fixed-point
  integer math → **bit-identical across silicon**. Same input → same output, every board. The NPU is
  *not* a source of statistical variation.
- **Statistical parts (the real uncertainty):** the *data* and *model*, not the hardware.

### 8.2 Sources of statistical uncertainty
1. **Label noise** — human annotators disagree on exactly when a freeze starts/ends.
2. **Domain shift** — lab vs home, different patients, sensor placement/mounting.
3. **Class imbalance** — freezes are rare → metrics on the rare class are noisier.
4. **Small N** — few subjects per hospital → wide confidence intervals.
5. **Quantization error** — INT8 rounding vs FP32 (bounded; measured device-vs-PC ≤ 1 % AUPRC target).
6. **Sensor variation** — per-device offset/gain → mitigated by per-device baseline normalization.

### 8.3 How we quantify it
- **Report distributions, not point scores:** AUPRC as **mean ± standard deviation across hospitals**
  (leave-one-hospital-out gives one score per held-out site → a spread, not a single number).
- **Bootstrap confidence intervals** on Average Precision (resample test windows) to put error bars on
  the headline metric.
- **Sensitivity & specificity reported separately** so the rare-class performance isn't hidden by an
  aggregate.
- **Cross-site gap = an uncertainty measure itself:** the drop from same-hospital → leave-one-out →
  lab→home directly quantifies how much we should distrust the model on unseen sites.
- **Quantization uncertainty** measured explicitly: device (INT8) vs PC (FP32) AUPRC delta.
- **Personalization uplift as a distribution** — improvement per hospital, with spread, not a single
  "99 %."

### 8.4 The honesty ledger (what is NOT yet known)
`[Unresolved — from RFC-001 §5]`: convergence targets (`T_auprc`, `N_max`), M33 training feasibility
(A4), final model size, poison-rejection threshold, tdcsfog subject count, INT8-vs-INT16 decision,
straggler quorum values, several datasheet facts. **These are marked, not hidden** — the system is a
signed-off contract only once they're measured.

---

## 9. Honest limitations (what we do NOT claim)

- **Simulation, not clinical.** We partition public datasets into "hospitals" to demonstrate the
  *method*. This is **not** a validated medical device and makes **no clinical claim.**
- **ML method is prior art.** FoG + federated learning exists; our novelty is the RTOS/embedded
  realization, not the algorithm.
- **One physical board.** Two cores act as two concurrent nodes; additional hospitals are simulated on a
  PC. No raw data crosses the network in either the real or simulated setup.
- **We never claim** federation "fixes," "guarantees," or "ensures" cross-site performance — we run an
  **experiment** and report measured results with uncertainty.

---

## 10. Where to go next
- Strict definitions & every design decision → `context.md`
- Engineering SLAs, budgets, failure modes → `RFC-001-systems-contract.md`
- The build plan (HIL vertical slices, GitHub issues) → `KANBAN.md`
