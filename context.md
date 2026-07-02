# FedTinyRT — context.md (Ubiquitous Language, strict)

Cyber-physical distributed ML system: per-hospital µT-Kernel 3.0 edge boards detecting
Parkinson's Freezing-of-Gait, learning on-device, federating **weights only** across hospitals.

**REALITY FILTER.** Claims labeled `[Verified]` (checked against a source this session),
`[Inference]` (reasoned from verified facts / general docs), `[Unverified]` (not confirmed),
`[Decision]` (chosen in the grill). Do not treat an `[Inference]` as fact.

**State-naming rule.** Never say "the model" or "the data." Use the exact state name defined in
§0. Never say "weights" without saying which *payload state*.

---

## 0. Canonical State Names (use these verbatim)

### Model states (one artifact, many states — name the state)
| State | Definition | Where it lives | Mutable? |
|-------|------------|----------------|----------|
| `Float32_Master` | Full-precision trainable model (Keras/TF). Source of truth; the only state that trains and the only state that federates. | PC (full) / M33 (last-layer copy) | yes (training) |
| `Frozen_Graph` | `Float32_Master` with training ops stripped, weights frozen; still FP32. Inference-only graph. | PC | no |
| `Quantized_TFLite` | INT8 `.tflite` produced from `Frozen_Graph` via post-training quant or QAT. | PC → MRAM | no |
| `NPU_Binary` | Vela-compiled Ethos-U55 command stream + INT8 weights (the only state the NPU executes). | MRAM/SRAM | no |
| `Seed_Model` | Round-0 `Float32_Master`, pretrained on Daphnet (disjoint). | PC/aggregator | frozen at t0 |
| `Global_Model[r]` | `Float32_Master` after Global Round `r` aggregation. Version-tagged by `r`. | aggregator → all nodes | replaced each round |
| `Personalized_Model` | `Global_Model[r]` + local last-layer fine-tune. **Never leaves the board.** Used only to make `Quantized_TFLite`→`NPU_Binary` for local screening. | M33→M85 | yes (continuous) |

### Data states (name the state; raw never leaves the board)
| State | Definition |
|-------|------------|
| `Raw_Window` | 2 s of triaxial accel @100 Hz = 200×3 samples in the DMA ring buffer. Ingested via **I2C DMA** (demo) or **LAN packets from the ESP32 wearable** (production, decision #24). Node-local only. |
| `Feature_Vector` | Derived from `Raw_Window`: FI-MLP path = Freeze-Index + band-power + stats; CNN path = normalized `Raw_Window` tensor. Board-local only. |
| `Label` | Ground truth for a window. Demo = dataset annotation (StartHesitation/Turn/Walking→collapsed per Q12b). Production = clinician diagnosis. Board-local only. |
| `Aggregation_Payload` | The ONLY state that crosses the network: full dense **FP32** weights of the shared layers (see §2). |

---

## 1. Bounded Context: Hardware & NPU

### 1.1 Memory hierarchy (strict — EK-RA8P1 / RA8P1)
`[Verified — Renesas RA8P1]` unless noted. Distinct tiers, do NOT conflate:

| Tier | Size | Role | Volatile |
|------|------|------|----------|
| **TCM (M85)** | 256 KB | tightest-latency working set for M85 real-time (ring buffer, hot activations) | yes |
| **TCM (M33)** | 128 KB | M33 training working set (last-layer grads/optimizer) | yes |
| **Data SRAM (ECC)** | 1.6 MB | general on-chip data | yes |
| **SRAM (activations)** | 2 MB | NN intermediate activations / framebuffers | yes |
| **On-chip MRAM** | 1 MB | code + `Quantized_TFLite`/`NPU_Binary` + weights (non-volatile) | **no** |
| **External OSPI flash** | 64 MB | bulk storage (datasets for replay demo, logs) | no |
| **External SDRAM** | 64 MB | bulk working memory | yes |

- **"NPU SRAM" is NOT a separate pool here.** `[Inference]` Ethos-U55 has no large private SRAM; it **streams** INT8 weights + activations from the 2 MB SRAM / TCM via DMA. So the NPU's effective working memory = the shared on-chip SRAM, not a dedicated NPU RAM. `[Unverified — confirm Ethos-U55 local SRAM/cache size on RA8P1.]`
- **Model-weight budget:** `NPU_Binary` lives in **MRAM (1 MB)**; activations in **SRAM (2 MB)**. Our model is KB-scale → no storage pressure. The real limit is **on-device training memory on M33** (last-layer FP32 + optimizer state must fit M33 TCM 128 KB / SRAM). `[Unresolved — see §4.]`

### 1.2 Compute units
`[Verified]` **M85 @ 1 GHz + Helium/MVE** · **M33 @ 250 MHz** · **Ethos-U55 @ 500 MHz, 256 GOPS** (`[Inference]` 256-MAC config).
`[Inference — verify]` NPU is coupled to **M85**; M33 has no NPU/Helium.

### 1.3 Quantization schemes (strict)
| Scheme | Used for | Notes |
|--------|----------|-------|
| **FP32** | `Float32_Master` training (M33 CPU + PC) | Ethos-U55 does NOT train; M85 FPU is single-precision (no FP64). |
| **INT8** (asymmetric, per-axis for weights) | `Quantized_TFLite` / `NPU_Binary` inference | `[Verified]` Ethos-U55 accelerates INT8 (and INT16). TFLite default int8 scheme. |
| **FP16** | **NOT USED** | `[Inference]` Ethos-U55 does not accelerate FP16; no benefit. Explicitly excluded. |

`[Decision]` Optional **QAT** (simulate INT8 rounding during FP32 training) if post-training INT8 loses too much AUPRC.

### 1.4 "NPU Offload" — strict definition
`NPU Offload` = the act where **M85** hands a **Vela-partitioned subgraph** of INT8 ops
(CONV_2D, DEPTHWISE_CONV_2D, FULLY_CONNECTED, POOL, MEAN, ADD, RELU, SOFTMAX — `[Verified]`
Vela SUPPORTED_OPS) to the **Ethos-U55 command stream**; the NPU executes it by streaming
weights/activations from SRAM via DMA; M85 blocks-or-works until the NPU raises completion.
- Ops that **violate Vela constraints fall back to M85 CPU** (CMSIS-NN), not the NPU. `[Verified]`
- Offload is **inference-only.** Training (backprop) is never offloaded — runs FP32 on CPU.
- `[Inference]` M33 cannot issue NPU offload (NPU coupled to M85); M33 training forward/backward is pure CPU. `[Unverified — confirm.]`

### 1.5 Power / thermal envelope
- `[Decision]` Device class = **clinic assessment tool**, mains-powered, deep-sleeps between patients. NOT a battery wearable → no battery-life claim.
- `[Verified]` Process = **22ULL (22 nm ultra-low-leakage)** → low static power.
- `[Decision]` Measure: avg power idle-vs-active; NPU-vs-CPU energy per inference; Ethernet PHY off except sync.
- **Thermal envelope: `[Unresolved]`** — not characterized; M85 @1 GHz + NPU sustained load thermal behavior unknown. No throttling policy defined.

### 1.6 Connectivity & physical form `[Verified — Renesas]`
- **No onboard BLE / WiFi / Bluetooth.** RA8P1 has no radio (Renesas wireless = RA6W1/W2, RA4W1 lines).
  Only wired **Gigabit Ethernet (RGMII) with TSN**.
- **Physical form (decision #24):** the board is a **desk/cart clinic BASE STATION**, never worn — it is
  large, has a display, needs mains power, and would be a fall hazard on a patient.
- **Body-worn sensor front-end (Option A, extension):** a small **ESP32-C3/S3 wearable** (accel + WiFi)
  clips to the patient's waist, timestamps samples @100 Hz, and streams accel packets over the
  **hospital LAN** to the base station's **Ethernet IP**. **No radio is added to the RA8P1.**
- **`Sensor_Ingest` has two modes:** (1) **direct I2C** accel wired to M85 (demo liveness prop / bench);
  (2) **LAN packet ingest** from the ESP32 wearable (production). Both yield `Raw_Window` on the base
  station. Long I2C cables to a walking patient are rejected (unreliable + trip hazard).

---

## 2. Bounded Context: Federated Learning

### 2.1 Core definitions (strict)
| Term | Definition |
|------|------------|
| **Local Epoch** | One full pass over a hospital's local `Label`led window set during on-device fine-tune. `[Decision]` Fine-tune **last dense layer(s) only**, few epochs, small LR, on **M33** (FP32). |
| **Global Round `r`** | One **synchronous** cycle: every participating hospital trains `Global_Model[r-1]`→ submits `Aggregation_Payload` → aggregator runs **FedAvg** → emits `Global_Model[r]` → redistributes. `[Decision]` synchronous (aggregator waits for all). |
| **Aggregation Payload** | `[Decision]` **Full dense FP32 weights** of the shared layers (~KB-scale), sent **once per Global Round**. NOT gradients, NOT sparse, NOT LoRA, NOT INT8. |
| **Aggregation rule** | `[Decision]` **FedAvg** (equal-weight or sample-count-weighted mean) + cheap sanity filter (reject NaN / absurd-norm payloads). |
| **Personalization** | Post-aggregation local fine-tune producing `Personalized_Model`; **not** submitted (would pull the global toward one site / risk catastrophic forgetting). |

### 2.2 Weight-update format
- v1 = **full weights** (dense FP32). `[Decision]`
- `[Unresolved / future]` alternatives: **delta** (`Global_Model[r] − Global_Model[r-1]`) to enable compression + DP; **LoRA adapters** (low-rank) to shrink payload; **sparse/top-k**. None in v1.

### 2.3 Privacy / security constraints
- **Hard invariant (refined for the wearable):** a **Node = wearable sensor + base station** (one
  hospital). Only `Aggregation_Payload` crosses the **federation network** (base-station ↔ base-station,
  between hospitals). `Raw_Window`/`Feature_Vector`/`Label` **never leave the Node**. Enforced by the
  **M33 egress gate**. `[Decision]`
- **Two distinct networks — do not confuse:** (1) **wearable → base station** over the *hospital LAN*
  (BLE/WiFi/Ethernet, *intra*-Node): raw accel travels here — allowed, local, should be encrypted.
  (2) **base station ↔ base station** over Ethernet (*inter*-Node): **weights only**. The privacy
  guarantee is about network (2), not (1).
- **Threat model:** `[Decision]` the network + other hospitals. On-board M85↔M33 is trusted (so M33 is a *network* gate, not a raw-data enclave — ADR-002).
- **Differential Privacy:** `[Unresolved / future]` — no DP noise on payloads in v1. If added, switch to delta payloads and calibrate a noise multiplier (ε,δ **undefined**).
- **Secure Aggregation:** `[Unresolved / future]` — not implemented. v1 trusts the aggregator to see plaintext FP32 payloads.
- **Consent withdrawal:** `[Decision]` hospital stops future submissions + secure-wipes local `Label`/data; past diffuse influence in `Global_Model` remains (machine-unlearning = future). Defensible: no raw data was ever shared.

---

## 3. Bounded Context: Network & Telemetry

### 3.1 Transport
`[Decision]` Wired **Ethernet (RGMII, gigabit-capable)**, **offline-first / store-and-forward** via M33.
Link required only during a sync window; board fully functional disconnected.

### 3.2 Stale payload / partitioning
- **Stale Gradient (defined):** an `Aggregation_Payload` computed against `Global_Model[k]` where `k < r-1` (an outdated base). `[Decision]` v1 is **synchronous**, so the aggregator only accepts payloads tagged with the **current round id `r-1`**; mismatched-version payloads are **rejected** (not merged) → stale gradients cannot corrupt the average by construction.
- **Round versioning:** every `Global_Model[r]` carries a monotonic `round_id`; payloads echo the `round_id` they trained from.
- **Dropped payload / network partition:** `[Decision — partial]` store-and-forward retransmit on next link-up. **Quorum policy `[Unresolved]`** — undecided whether a round proceeds on a subset if a hospital is unreachable, or blocks until all report. Must resolve before PRD.

### 3.3 Heartbeat
`[Unresolved]` — no heartbeat/liveness protocol designed yet. Open: interval, timeout → drop-from-round, who monitors (aggregator polls vs node pushes).

### 3.4 OTA (Over-The-Air) update
- **Model-OTA (in scope):** distribution of `Global_Model[r]` weights to M33 → applied to `Float32_Master` → re-quantized to `Quantized_TFLite`→`NPU_Binary` for the M85/NPU. This is the normal federation redistribution.
- **Firmware-OTA (out of scope v1):** `[Unresolved]` updating the µT-Kernel image / task binaries over the network is **not** designed; only model weights are pushed in v1.
- **Atomicity `[Unresolved]`:** no defined rollback if a model-OTA apply fails mid-write to MRAM (risk: bricked model). Needs A/B model slots or checksum+rollback.

---

## 4. Unresolved Constraints (resolve before PRD)

### Hardware
1. `[Unverified]` **NPU↔core coupling** — is Ethos-U55 attached only to M85? (Assumed yes.) Determines whether M33 can offload.
2. `[Unverified]` **Boot core / order** — which core boots first and releases the other? Affects init sequence + inter-core bring-up.
3. `[Unverified]` **Ethos-U55 local SRAM/cache size** — needed to size activation streaming; "NPU SRAM vs main SRAM" boundary assumed shared.
4. `[Inference, unconfirmed]` **Ethos-U55 MAC count = 256** (from 256 GOPS @ 500 MHz). Confirm from datasheet.
5. `[Unresolved]` **Low-power mode names + measured idle/active power + thermal** for RA8P1 (Software Standby / Deep Standby assumed from RA family, not confirmed). No thermal throttling policy.
6. `[Unresolved]` **M33 on-device training memory feasibility** — does last-layer FP32 weights + gradients + optimizer state fit M33 TCM (128 KB) / SRAM at acceptable speed @250 MHz? Not benchmarked.

### Mathematical / ML
7. `[Unresolved]` **Final model architecture byte size** — depthwise-separable 1D-CNN dimensions not fixed → `Aggregation_Payload` size (~KB) not pinned.
8. `[Unresolved]` **Label granularity** (Q12b) — binary `freeze`/`no-freeze` vs 4-class; to be benchmarked, affects head shape + payload.
9. `[Unresolved]` **Unit harmonization** — tdcsfog (m/s²) vs defog (g, 1g=9.81 m/s²) must be converted; canonical unit + resample-to-100 Hz procedure not yet specified/validated.
10. `[Unresolved]` **FedAvg weighting** — equal vs sample-count weighting not fixed; matters for imbalanced/scarce hospitals.
11. `[Unverified]` **tdcsfog subject count** (only 833 *files* confirmed) — needed to fix the 4–5 hospital partition sizes.

### Distributed systems / security
12. `[Unresolved]` **Quorum policy** for dropped payloads / partition (§3.2).
13. `[Unresolved]` **Heartbeat protocol** (§3.3).
14. `[Unresolved]` **Model-OTA atomicity / rollback** (A/B MRAM slots?) (§3.4).
15. `[Unresolved / future]` **DP (ε,δ) and Secure Aggregation** — deferred; if required, forces delta payloads.
16. `[Unverified]` **µT-Kernel 3.0 API names** (`tk_cre_tsk/sem/flg/mbx/cyc`) vs the actual RA8P1 BSP2 headers.

---

## 5. Revisions (post board-fact verification)

Triggered by verified RA8P1 specs (256 GOPS NPU, M85@1 GHz+Helium, M33@250 MHz no-Helium/NPU,
TCM 256 KB/128 KB, 2 MB SRAM, 1 MB MRAM, INT8/INT16 NPU, TrustZone, 22ULL).

### 5.1 COMMIT NOW (low-risk wins)
- **R1 — Right-size the model UP.** Drop the inherited 4 KB target. Use a real depthwise-separable
  1D-CNN: **grow the frozen conv body (NPU inference, cheap) freely for accuracy; keep the
  trainable head small.** Reconciles "bigger model" with "weak-M33 training" — only the small head
  trains on M33, so training cost is bounded regardless of body size. Updates §0/§1.2.
- **R2 — INT8 default, INT16 fallback.** Ship `Quantized_TFLite` INT8. If INT8 costs real freeze
  recall (AUPRC), switch to **INT16** (still NPU-accelerated, ~2× size, storage is free). Decided by
  measurement, not pre-committed. Updates §1.3.
- **R3 — Helium-accelerated Freeze-Index FFT.** FI-MLP baseline path uses **CMSIS-DSP + Helium/MVE**
  on M85. Free speed. Updates §1.2.
- **R4 — A/B model slots in MRAM for safe OTA.** Write new `NPU_Binary` to slot B → verify checksum
  → atomic switch. Corrupt/interrupted write cannot brick the live model. **Resolves Unresolved #14**
  (model-OTA atomicity). Storage is free — use it. Updates §3.4.

### 5.2 BENCHMARK GATE (measure before locking)
- **R5 — M33 training feasibility gates ADR-004.** Plan stays: M33 trains the head concurrently
  (physical core isolation = cleanest real-time guarantee + best dual-core story). **But gate on one
  micro-benchmark:** last-layer FP32 epoch time + memory on M33 @250 MHz within 128 KB TCM.
  - PASS (fits + trains in seconds) → keep ADR-004.
  - FAIL (won't fit/too slow) → fall back to **M85 idle-slot time-sliced training** (Helium, 4× faster,
    less "pure parallel" but works). Decide with a number. Ties to Unresolved #6.
- **R6 — INT8 vs INT16 chosen by AUPRC** on subtle freezes (see R2).

### 5.3 DEFER — least priority, execute only if time remains
- **R7 — TrustZone-backed egress gate.** Put the weights-only-egress check + payload buffer in M85
  **secure world** for a hardware-backed privacy story. `[Opinion]` credible bonus, but real work
  (secure/non-secure partition, veneers, secure-boot). Threat model is network-only, so this is
  *extra*, not core. **Completion-first beats a half-wired TrustZone.** Do only if v1 is done early.
- **R8 — Payload size = bookkeeping, not a decision.** `Aggregation_Payload` bytes = (shared-weight
  count) × 4 (FP32). Falls out once CNN dims are fixed; record it in §2.2 then. Trivial on gigabit
  RGMII even at tens of KB. No choice to make.

### 5.4 Confirmed role
- **The board performs PREDICTION.** M85 + Ethos-U55 executes `NPU_Binary` → `freeze/no-freeze`
  per 2 s window, live, real-time. Training/personalization is the secondary background path (M33).

---

## Appendix A — Decision log (grill Q1–Q23)

| # | Decision |
|---|----------|
| 1 | Threat model = network + other hospitals; on-board cores trust each other. |
| 2 | Parallel core split: M85 = sampling + NPU inference (real-time); M33 = last-layer training + comms + privacy gate (concurrent). |
| 3 | Aggregator = star topology; PC in demo. |
| 4 | `Aggregation_Payload` = whole FP32 weights, once/round. |
| 5 | Synchronous Global Rounds. |
| 6 | Labels: dataset (demo) + clinician (production). |
| 7 | Hospitals = one dataset split by subject now; real second site later. |
| 8 | Task = Parkinson's, external I2C accel. |
| 9 | Success artifact = live single-board loop + offline federation numbers. |
| 10 | Transport = wired Ethernet, offline-first, store-and-forward via M33. |
| 11 | Canonical 100 Hz after resampling (tdcsfog 128 / defog 100 / Daphnet 64). |
| 12 | Task = Freezing-of-Gait; **12b** granularity (binary vs 4-class) = benchmark, open. |
| 13 | Input window = 2 s, 50% overlap = 200 samples; predict every 1 s. |
| 14 | Features = hybrid: raw→1D-CNN (device) + Freeze-Index MLP (baseline). |
| 15 | Device model = depthwise-separable 1D-CNN (INT8, NPU); TCN upgrade; unidir-LSTM available. |
| 16 | Metric = AUPRC/AP (matches Kaggle mAP) + sensitivity/specificity; accuracy banned. Imbalance: class weights + focal + oversample. Stage a freeze-poor hospital. |
| 17 | Join = pull current global. Leave = stop + secure-wipe (unlearning future). Bad weights = sanity filter (Byzantine-robust future). |
| 18 | Two models: global (shared) + personalized (local, never sent). Personalize each round + continuous in production. Last-layer only. |
| 19 | 4–5 tdcsfog hospitals + defog unseen site; battery = per-hospital/LOHO/cross-site; subject-level splits. |
| 20 | RTOS tasks: AccelSampler(M85,P1,cyclic+DMA), Inference(M85,P2,NPU), Trainer(M33), FedComms+Gate(M33); inter-core mailbox+HW-sem. Headline: 0 missed sampling deadlines during training. |
| 21 | Clinic device (mains); measure sleep + NPU-vs-CPU energy + PHY-off; no unmeasured battery claim. |
| 22 | Cold-start = pretrained seed (Daphnet), disjoint from eval. |
| 23 | Dataset v1 = Kaggle-only (tdcsfog hospitals + defog unseen) + Daphnet seed; FoG-STAR = extension. |
| 24 | **Physical form = desk/cart base station (not worn).** Body-worn sensor = **ESP32-C3/S3 wearable → WiFi → hospital LAN → base-station Ethernet** (Option A; no radio added to RA8P1). Node = wearable + base station. Two networks: intra-Node LAN (raw ok) vs inter-Node federation (weights only). Wearable = documented **extension**; demo uses dataset replay + I2C liveness prop. Long I2C cables rejected (unsafe for fall-prone patients). RA8P1 has NO onboard BLE/WiFi. |

## Appendix B — ADRs
- **ADR-001** — Pivot industrial → cross-silo hospital FoG federation (privacy essential; differentiates from LGX-Shield; keeps ~75% of submitted proposal).
- **ADR-002** — M33 = network egress gate, not raw-data enclave (TrustZone is intra-core; threat is network-only; avoids enclave paradox).
- **ADR-003** — Share full model + personalize locally (validated by prior CWRU/IMS; partial-layer sharing = future).
- **ADR-004** — Parallel core split: M85 inference ∥ M33 training (stronger real-time via physical isolation; M33 slower → last-layer only; NPU coupled to M85).

## Appendix C — Honest positioning
- **Claim:** first FoG federated-learning realization on µT-Kernel + dual-core + Ethos-U55 NPU + on-device training; an experiment on whether cross-silo FedAvg + personalization closes the cross-hospital gap FOGSense left as future work, with a measured real-time guarantee.
- **Do NOT claim:** inventing FoG detection or FL; that federation "fixes/guarantees/ensures" anything; any clinical validity. Simulation, not a clinical device.
