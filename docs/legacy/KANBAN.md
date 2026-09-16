# FedTinyRT — HIL Vertical-Slice Kanban

Source-of-truth backlog. Each card → one GitHub Issue. Board = GitHub Project (columns below).
Grounded in `context.md` (definitions) + `RFC-001-systems-contract.md` (SLAs, B-items).

> **Corrections vs the generic template:** our transport is **Ethernet/UART** (no BLE); non-volatile
> store is **MRAM** (not Flash); the NPU is **inference-only** (backprop is M33-CPU). Cards reflect this.

---

## Board columns
`Backlog` → `Ready` (all deps Done) → `In Progress` → `HIL-Verify` (on-hardware acceptance test) → `Done`

**WIP limit = 1 slice in `In Progress`** (single board, HIL is serial).

## The Vertical-Slice Rule (enforced — a card is rejected if it fails any)
1. **Vertical, not horizontal.** A card touches **≥2 layers** of the stack
   (sensor → compute → NPU → storage → network) and ends in an **observable output**.
   ❌ Banned card shape: "Write all NPU drivers", "Implement the whole FL aggregator".
2. **Ends in an HIL demo.** Definition-of-Done = a **pass/fail test run on hardware (or HIL mock)**,
   not "code compiles" / "unit tests pass".
3. **Cites the contract.** Every card names the `RFC-001` clause or `context.md` decision it proves,
   and the **B-item(s)** it resolves.
4. **Builds on the prior slice.** A failure localizes to the newest slice (regression harness re-runs
   all prior slices' HIL tests).

## Card schema (each Issue body)
```
ID:            S<n>
Slice:         <one-line capability proven>
Vertical path: <layers touched, e.g. I2C accel → M85 → NPU → MRAM → Ethernet → PC>
Proves:        <RFC-001 §x / context.md #y>
Resolves:      <B-items, e.g. B2, B7>
Depends on:    <S<n-1>, ...>
HIL acceptance test (pass/fail):
  GIVEN <hw state> WHEN <action> THEN <measurable observable + numeric SLA>
Definition of Done:
  - demo runs on the EK-RA8P1 (or HIL mock aggregator on PC)
  - regression: all prior slices' HIL tests still pass
  - measured numbers logged into RFC-001 §5 (B-items)
Artifacts: <binary, capture, number>
```

---

## Slices (the backlog, in dependency order)

Dummy-first (S0–S3 prove the *plumbing* with fake model/data → de-risk before real ML),
then real sensor/data/model (S4–S6), then concurrency/failure/power/science (S7–S10).

### S0 — Skeleton HIL foundation
- **Slice:** µT-Kernel 3.0 boots; one task toggles LED + prints over UART/SEGGER-RTT.
- **Vertical path:** M85 → GPIO/UART.
- **Proves:** toolchain + flash + debug I/O + RTOS task creation (`context.md §0` bring-up).
- **Resolves:** B6 (µT-Kernel API names confirmed vs BSP2).
- **HIL:** GIVEN a flashed board WHEN reset THEN LED blinks at 1 Hz AND RTT prints a task heartbeat.

### S1 — NPU inference + telemetry egress  *(your Slice 1, adapted)*
- **Slice:** dummy INT8 model → **Vela** → `NPU_Binary` in MRAM → run **one inference** on a canned
  `Raw_Window` → send result as telemetry over **Ethernet/UART** to a **mock PC aggregator**.
- **Vertical path:** MRAM → M85 → **Ethos-U55 NPU** → Ethernet → PC.
- **Proves:** RFC-001 §1.4 (NPU Offload), §1.2 (inference working set ≤512 KB, p99 ≤100 ms), egress I/O.
- **Resolves:** B7 (INT8 path works), partial B6 (NPU↔core coupling observed).
- **Depends on:** S0.
- **HIL:** GIVEN `NPU_Binary` in MRAM WHEN one inference runs THEN output matches a PC golden vector
  AND measured latency ≤100 ms AND the PC mock receives the telemetry frame.

### S2 — Local head training + delta to MRAM  *(your Slice 2 — HIGH LEVERAGE, gates ADR-004)*
- **Slice:** one **forward+backward** pass of the **head** on **M33 (FP32)** over a canned batch →
  compute weight **delta** → write to an MRAM **A/B slot**.
- **Vertical path:** SRAM/TCM → M33 CPU → MRAM (A/B slot).
- **Proves:** RFC-001 §1.3 (M33 gradient RAM ≤96 KB TCM), §3/F4 (A/B slot write), R5 gate on ADR-004.
- **Resolves:** **B2** (M33 epoch time + RAM → keep ADR-004 or fall back to M85 idle-slot training).
- **Depends on:** S0 (parallel to S1 possible).
- **HIL:** GIVEN a canned batch WHEN one head epoch runs on M33 THEN peak TCM ≤96 KB AND epoch ≤5 s
  AND the delta is readable back from the inactive MRAM slot. *(If FAIL → open ADR-004-revision card.)*

### S3 — Federated round loop  *(your Slice 3, adapted)*
- **Slice:** mock PC aggregator receives **3 mock `Aggregation_Payload`s** → **FedAvg** → pushes
  `Global_Model[r]` back → device applies via **A/B swap** → re-quantize → next inference uses new weights.
- **Vertical path:** PC(FedAvg) → Ethernet → M33(gate) → MRAM(A/B swap) → M85/NPU.
- **Proves:** RFC-001 §2 (federated contract), §3.2 (`round_id` / stale-reject), F3 (sanity filter),
  F4 (atomic OTA swap).
- **Resolves:** part of B8 (round mechanics), B4 (poison threshold path).
- **Depends on:** S1, S2.
- **HIL:** GIVEN 3 payloads (incl. one NaN + one wrong `round_id`) WHEN a round runs THEN the two bad
  payloads are rejected, the good one aggregates, device boots the new slot, inference reflects it.

### S4 — Real sensor real-time loop (the live prediction)
- **Slice:** **I2C accel → DMA ring buffer → 2 s window → `Feature_Vector` → NPU inference →
  `freeze/no-freeze` on LED/display.**
- **Vertical path:** I2C accel → DMA → M85 (P1 sampler + P2 inference) → NPU → display.
- **Proves:** §4.2 (0 missed 100 Hz deadlines), DMA path, F6 (sensor liveness), "board does prediction".
- **Resolves:** confirms §1.2 latency under real sampling.
- **Depends on:** S1. Needs the external accel chip (pending part name for I2C driver).
- **Ingest mode:** demo = **direct I2C→DMA** (this slice). Production = **LAN packets from the ESP32
  wearable** (see S11); the `AccelSampler` task then becomes a `SensorIngest` task. Same `Raw_Window`.
- **HIL:** GIVEN live accel motion WHEN sampled 60 s THEN 0 missed sampling deadlines AND a live
  prediction updates each 1 s AND unplugging the sensor raises `liveness=false` (no false negative).

### S5 — Real model on real FoG data (device↔PC parity)
- **Slice:** replace dummy with the trained **depthwise-separable 1D-CNN** on **real Kaggle FoG replay**
  (over UART/flash); compare on-device output to PC golden vectors; measure per-window AUPRC.
- **Vertical path:** flash/UART replay → M85 → NPU → PC compare.
- **Proves:** quant parity (§2.3 determinism), §1.1 payload size (**B3**), baseline metric (**B1** start).
- **Resolves:** B3, B7-final (INT8 vs INT16 by AUPRC → R6).
- **Depends on:** S1, S4, + offline ML (Kaggle pull, unit-harmonize m/s²↔g, train — tracked as ML cards).
- **HIL:** GIVEN real FoG windows WHEN device infers THEN device vs PC AUPRC delta ≤1% AND payload
  bytes recorded into RFC-001 §1.1.

### S6 — End-to-end real federation (value demo)
- **Slice:** real board = one hospital + **≥3 virtual hospitals on PC**, full **Global Round over
  Ethernet** with real weights; show **federated AUPRC ≥ local-only** (regression gate).
- **Vertical path:** board(train+infer) ∥ PC virtual hospitals → aggregator → back to board.
- **Proves:** §2.1 federation-must-not-hurt invariant + scarce-hospital uplift.
- **Resolves:** B1 (`T_auprc`, `N_max` set from this run).
- **Depends on:** S3, S5.
- **HIL:** GIVEN N hospitals WHEN federation converges THEN federated ≥ local for the board hospital
  AND a staged freeze-poor hospital improves materially.

### S7 — Concurrency under real-time load (ADR-004 headline)
- **Slice:** run **NPU inference (M85) WHILE M33 trains** concurrently; measure sampling deadlines + jitter.
- **Vertical path:** M85(sample+infer) ∥ M33(train) with inter-core mailbox+HW-sem.
- **Proves:** §4.2 headline RTOS metric under load, ADR-004 parallel split.
- **Resolves:** confirms B2 conclusion in situ.
- **Depends on:** S2, S4.
- **HIL:** GIVEN concurrent train+infer for 5 min THEN **0 missed sampling deadlines** AND worst-case
  jitter logged AND inference latency SLA still met.

### S8 — Failure-mode drills
- **Slice:** inject **F1** (NPU hang), **F2** (train hang), **F4** (reset mid-MRAM-write), **F5** (unplug
  Ethernet); verify each fallback.
- **Vertical path:** whole stack, fault-injected.
- **Proves:** RFC-001 §3 (F1/F2/F4/F5) + §4 fail-safe invariant.
- **Depends on:** S3, S4.
- **HIL:** each fault → the contracted fallback observed (CPU fallback / discard `Personalized_Model` /
  boot last-good slot / store-and-forward) AND sampler never stalls AND no false `no-freeze` emitted.

### S9 — Power characterization
- **Slice:** measure deep-sleep-between-assessments, **NPU-vs-CPU energy/inference**, Ethernet PHY off.
- **Proves:** §2.1 energy SLA (measured, no battery claim — Q21c).
- **Depends on:** S4, S7.
- **HIL:** report avg active vs idle power AND NPU/CPU energy ratio from board instrumentation.

### S10 — Personalization + cross-site science
- **Slice:** on-device **personalization**, then **leave-one-hospital-out** + **lab→home** evaluation.
- **Proves:** the scientific claim (context.md Appendix C), §2.1 `T_auprc`.
- **Depends on:** S5, S6.
- **HIL/analysis:** report local vs federated vs personalized, LOHO, and lab→home AUPRC.

### S11 — Wearable sensor node (EXTENSION, do only if v1 done)
- **Slice:** **ESP32-C3/S3 + accel** clipped to the body → sample @100 Hz, timestamp → stream over
  **WiFi/LAN** → base-station **Ethernet** `SensorIngest` → same `Raw_Window` → live prediction.
- **Vertical path:** ESP32(accel+WiFi) → hospital LAN → RA8P1 Ethernet → M85 → NPU → display.
- **Proves:** decision #24 (base-station + wireless wearable), RFC-001 F8 (wearable link drop),
  two-networks privacy split (intra-Node LAN vs inter-Node federation).
- **Depends on:** S4 (ingest path), S1.
- **HIL:** GIVEN a body-worn ESP32 WHEN a patient walks THEN base station reconstructs clean 100 Hz
  windows AND predicts live AND a dropped link → `liveness=false` (no false negative) AND raw accel
  never crosses the inter-Node federation link.
- **Note:** NOT needed for the contest demo (dataset replay + I2C liveness prop suffice). Build only
  if S0–S10 are Done.

---

## Parallel non-HIL track (ML, feeds S5/S6/S10 — kept OFF the HIL board)
These are PC-side and do **not** block early HIL slices; they must land before S5.
- `ML-1` Pull Kaggle FoG; **harmonize units (m/s² ↔ g)** + resample→100 Hz; subject-level manifest. (Trap 1/2)
- `ML-2` 2 s/50% windowing; FI-MLP baseline + depthwise-separable 1D-CNN; INT8 export + golden vectors.
- `ML-3` Partition tdcsfog→4–5 hospitals; Daphnet seed (disjoint); FedAvg sim; LOHO + lab→home.

## Regression harness (Definition-of-Done gate for every slice)
A slice is `Done` only if its HIL test passes **and** all lower-numbered slices' HIL tests still pass
(re-run headless where possible). This is how a defect localizes to the newest slice.

---

## How to instantiate the board
1. Create a **GitHub Project** (board view) in the repo; columns as above; add a **WIP=1** limit on
   `In Progress`.
2. One **Issue per card** (S0–S10 + ML-1..3). Labels: `slice`, `hil`, `ml`, `blocker:Bx`, `adr-gate`.
3. Milestones map to the 1-month plan: **Wk1** S0–S3, **Wk2** S4–S6 (+ML-1..3 land), **Wk3** S7–S9,
   **Wk4** S10 + hardening + submission.
4. `gh issue create` per card (I can generate the exact commands from this file on request).
