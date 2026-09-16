# RFC-001 — FedTinyRT Systems Contract (PRD)

**Status:** Draft for sign-off · **Version:** 0.1 · **Depends on:** `context.md` (Ubiquitous Language, strict)
**Audience:** embedded firmware engineer ∧ ML researcher (both must agree)
**Scope:** Engineering SLAs, Hardware Contracts, Failure-Mode mitigations. **No UI/user stories.**

> **Notation:** `[Verified]` checked vs source · `[Target]` proposed budget, must be validated by a
> benchmark/measurement before sign-off · `[Unresolved]` value not yet determined (blocks sign-off) ·
> `[Invariant]` hard rule the system must never violate.
> **State names** (`Float32_Master`, `Frozen_Graph`, `Quantized_TFLite`, `NPU_Binary`,
> `Global_Model[r]`, `Personalized_Model`, `Aggregation_Payload`, `Raw_Window`) are defined in
> `context.md §0` and used verbatim here.

---

## 0. Two contract corrections (binding)

1. **The NPU never performs backpropagation.** Per `context.md §1.4`, Ethos-U55 offload is
   **inference-only**. All gradient computation (`Local Epoch`) runs **FP32 on the M33 CPU**. Therefore
   "NPU SRAM during backprop" = **N/A**; the relevant budget is **M33 gradient RAM** (§1.3 below).
2. **On-chip non-volatile store is MRAM, not Flash.** `NPU_Binary` / `Global_Model` persist in the
   **1 MB on-chip MRAM**. The **64 MB OSPI Flash** is external bulk (datasets/logs). "OTA payload
   footprint" is budgeted against **MRAM** (§1.1).

---

## 1. Hardware Contracts — Resource Budgets

### Platform limits (fixed silicon) `[Verified — Renesas RA8P1]`
| Resource | Hard limit |
|---|---|
| On-chip MRAM (code + models, non-volatile) | **1 MB** |
| SRAM (NN activations / framebuffer) | **2 MB** |
| TCM — M85 / M33 | **256 KB / 128 KB** |
| Data SRAM (ECC) | **1.6 MB** |
| External OSPI Flash / SDRAM | 64 MB / 64 MB |
| NPU | Ethos-U55 @ 500 MHz, 256 GOPS, INT8/INT16, **no private weight SRAM** (streams from SRAM) |

### 1.1 OTA payload footprint (MRAM)
- **Definition:** OTA payload = `Global_Model[r]` shared weights (FP32) written to an MRAM **model
  slot**. A/B slots per `context.md` R4.
- **Budget `[Target]`:** each model slot ≤ **128 KB** → **A+B = 256 KB** of MRAM; remaining ≥ 768 KB
  reserved for code + `NPU_Binary`. Rationale: depthwise-separable 1D-CNN (frozen body + small head)
  is KB-scale; 128 KB gives ~30× headroom for R1 up-sizing.
- `[Invariant]` An OTA write targets the **inactive** slot only; the active slot is never mutated in place.

### 1.2 Inference working set (SRAM)
- **Definition:** activation memory for one `NPU_Binary` forward pass over one `Raw_Window` (200×3).
- **Budget `[Target]`:** ≤ **512 KB** of the 2 MB SRAM (leaves room for M85 ring buffer + M33 use).
- `[Invariant]` Inference must complete within the **1 s** inter-window budget (2 s window, 50% overlap).
  **Latency SLA `[Target]`:** p99 inference ≤ **100 ms** (soft real-time; literature edge FoG < 350 ms).

### 1.3 Gradient RAM during a Local Epoch (M33 TCM)
- **Definition:** memory for last-layer FP32 fine-tune on M33 = {trainable weights, gradients,
  optimizer state (Adam m,v), one micro-batch of activations}.
- **Budget `[Target]`:** ≤ **96 KB** of M33's 128 KB TCM (≥ 32 KB reserved for stack/RTOS).
- `[Unresolved / R5 gate]` Actual footprint + epoch time on M33 @250 MHz **must be benchmarked**. If it
  exceeds 96 KB or a background epoch > **5 s**, ADR-004 falls back to **M85 idle-slot training**.
- `[Invariant]` Only the **head** trains on-device; the frozen conv body is never in the trainable set.

---

## 2. Federated SLAs

### 2.1 Convergence vs energy (device = mains clinic tool, per `context.md §1.5`)
> Contract note: device is **mains-powered**, not battery — "battery drain" is reframed to **energy per
> Global Round** and **average active power**. No battery-life SLA (honesty guard, Q21c).

| Metric | SLA |
|---|---|
| Convergence target | `[Unresolved]` reach **AUPRC ≥ T_auprc** on the held-out per-hospital test within **N_max Global Rounds**. `T_auprc`, `N_max` set after the first offline federation run (data-dependent; do not fabricate). |
| Federation-must-not-hurt | `[Invariant]` `federated` AUPRC ≥ `local-only` AUPRC for each **data-rich** hospital (regression gate). |
| Scarce-hospital uplift | `[Target]` a freeze-poor hospital's `federated` AUPRC materially exceeds its `local-only` (value demo; magnitude data-dependent). |
| Energy per round | `[Target]` measured Joules for {last-layer epoch on M33 + one sync}; report, no fixed cap in v1. |
| Compute-bound, not network-bound | `[Verified — Note E]` on gigabit RGMII, round latency is dominated by M33 training, not transport. |

### 2.2 Straggler tolerance (synchronous rounds, `context.md §3.2`)
- **Straggler:** a node that has not submitted a valid `Aggregation_Payload` for the current
  `round_id` by the round deadline.
- **SLA `[Proposed — resolves Unresolved #12]`:**
  - Round deadline `T_round` `[Target]` = 24 h (nightly cadence; offline-first tolerates it).
  - **Quorum** = min(**all data-rich nodes**, **≥ 60%** of registered nodes, **≥ 3** nodes). Round
    aggregates on quorum; missing nodes are skipped **for that round only**.
  - Stragglers **rejoin next round** via store-and-forward (pull latest `Global_Model[r]`, resume).
  - **Stale payloads rejected:** a payload whose echoed `round_id ≠ r-1` is **dropped, not merged**
    (§3.2 stale-gradient rule) → stragglers cannot inject stale updates.
- `[Invariant]` A single unreachable node never blocks the federation beyond `T_round`.

### 2.3 NPU silicon variation / INT8 quantization drift
- `[Verified — integer determinism]` Ethos-U55 INT8 inference is **fixed-point integer math**; a given
  `NPU_Binary` produces **bit-identical** outputs across silicon units/batches. **The NPU is not a
  quantization-drift source** — no per-silicon model divergence.
- **Real variation source = the accelerometer sensor** (offset/gain/mounting), not the NPU.
  - **Mitigation `[Decision — reuses IMS lesson]`:** per-device **baseline normalization** — calibrate
    on the device's own healthy/quiet startup data; feed normalized `Feature_Vector` to the model.
    This is also what makes cross-site (lab↔home unit conversion, Trap 1) valid.
- `[Invariant]` `Quantized_TFLite`→`NPU_Binary` conversion (Vela) is pinned to a fixed toolchain
  version; the same `Float32_Master` must yield a reproducible `NPU_Binary` (build determinism).

---

## 3. Failure Modes & Fallbacks

| # | Failure | Detection | Fallback (contract) | Real-time impact |
|---|---|---|---|---|
| F1 | **NPU hangs during inference** | Ethos-U55 op watchdog / M85 completion timeout | Reset NPU; run that window on **M85 CPU (CMSIS-NN)** or skip one window; log fault-count. Sampler (P1) is independent → sampling continues. | none (P1 sampler unaffected) |
| F2 | **M33 training hang during a Local Epoch** (not NPU — CPU) | M33 **task watchdog** timeout | Abort epoch; **discard in-progress `Personalized_Model`**; retain last-good `Personalized_Model` + current `Global_Model[r]`. No submission this round. | none |
| F3 | **Aggregator receives poisoned/malicious `Aggregation_Payload`** | Sanity filter: reject if NaN/Inf, ‖w‖ > `norm_max`, wrong `round_id`, or shape mismatch | Drop that payload; **exclude node from round**; log + alert. `[Future]` Byzantine-robust aggregation (trimmed-mean/Krum) if threat escalates. | none (server-side) |
| F4 | **Power loss mid-MRAM write (OTA apply)** | Boot-time **checksum/CRC** on active + inactive slots | A/B slots (R4): incomplete slot B fails checksum → **discarded**; device boots **last-good slot A**. Slot-pointer commit is the **final atomic step**, so a torn write never activates a partial model. | none after reboot |
| F5 | **Network partition / dropped payload** | Missed ACK within `T_round` | Store-and-forward: retransmit on next link-up; round proceeds on quorum (§2.2). | none (offline-first) |
| F6 | **Sensor drift / disconnect (I2C accel)** | I2C NAK / out-of-range / flat signal | Flag `liveness=false`; suppress prediction (no false `no-freeze`); require re-calibration. | screening paused, safe |
| F7 | **Inter-core desync (stale shared SRAM)** | sequence/version tag on mailbox message | Per `context.md`: M85 **cache-clean before handoff**, M33 **invalidate before read**; mismatched version → re-request. | none |
| F8 | **Wearable link drop (ESP32 → LAN → base station)** | missed/late accel packets vs expected 100 Hz | Base station flags `liveness=false`, suppresses prediction (no false `no-freeze`); wearable buffers + retransmits; resume on reconnect. Soft deadline tolerates buffered catch-up. `[context.md #24]` | screening paused, safe |

`[Invariant — safety]` On any inference-path fault, the system **withholds a prediction** rather than
emit a possibly-wrong `no-freeze` (a missed-freeze is the costly error). Fail safe, not silent.

---

## 4. Global Invariants (never violated)
1. **Data locality:** a **Node = wearable sensor + base station** (one hospital). Only
   `Aggregation_Payload` (FP32 shared weights) crosses the **inter-Node federation network**.
   `Raw_Window`, `Feature_Vector`, `Label` never leave the **Node**. The intra-Node link
   (wearable → base station over the hospital LAN) may carry raw accel — local, encrypted, allowed.
   Enforced by the M33 egress gate. `[context.md #24]`
2. **Real-time primacy:** the P1 `AccelSampler` (100 Hz) preempts everything; **0 missed sampling
   deadlines**, including during F1/F2 faults and on-device training.
3. **No in-place model mutation:** models update via A/B slot swap only.
4. **Determinism:** fixed Vela toolchain → reproducible `NPU_Binary`; INT8 inference bit-identical
   across silicon.
5. **Fail-safe inference:** withhold prediction on fault; never emit an unverified negative.

---

## 5. Open budget items — MUST fill before sign-off (from `context.md §4`)
| ID | Item | Blocks |
|---|---|---|
| B1 | `T_auprc`, `N_max` convergence targets — set after first offline federation | §2.1 |
| B2 | M33 last-layer epoch time + RAM (R5 benchmark) — validates §1.3 budget & ADR-004 | §1.3, §2.1 |
| B3 | Final CNN dims → exact `Aggregation_Payload` bytes (R8 bookkeeping) | §1.1 |
| B4 | `norm_max` poison threshold — set from healthy weight-norm distribution | §3/F3 |
| B5 | tdcsfog subject count → hospital partition sizes | §2.2 |
| B6 | NPU↔core coupling, boot order, low-power mode names, µT-Kernel API names (datasheet) | §1, F1, F7 |
| B7 | INT8 vs INT16 decision by AUPRC (R6) | §1.2 |
| B8 | Quorum `T_round`, %, min-nodes final values | §2.2 |

---

## 6. Sign-off
| Role | Agrees to | Name | Date |
|---|---|---|---|
| Embedded firmware | §1 budgets, §3 F1/F2/F4/F7 mitigations, §4 invariants 2–4 | | |
| ML researcher | §1.3 head-only training, §2.1 convergence, §2.3 quant/calibration, §3 F3 | | |
| Systems/integration | §2.2 straggler SLA, §3 F5, §5 open items | | |

**Sign-off is blocked until all §5 (B1–B8) are resolved.** Draft is internally consistent with
`context.md` v-current; any change to a strict definition there requires a matching revision here.
