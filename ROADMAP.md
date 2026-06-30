# FedTinyRT — Master Roadmap (max board utilization, test-gated)

**One-month plan. Every hardware block on the EK-RA8P1 is used. Every step is proven by a test before the next begins.**

Board: Renesas EK-RA8P1 — Cortex-M85 (+ Helium) + Cortex-M33 + **Ethos-U55 NPU** + 2MB SRAM + 64MB SDRAM + 64MB Octo-SPI flash + MIPI camera + LCDC display + onboard mic. RTOS: μT-Kernel 3.0.
Start: 2026-06-30. Target finish: 2026-07-28 (4 weeks).

Purpose: **predictive maintenance** — a node watches an industrial machine (motor/bearing) via vibration + sound, classifies **normal / degrading / fault**, learns on-device, and federates what it learns (gradients, never raw data) with peers. The RTOS guarantees sensor deadlines are never missed even mid-computation.

---

## Hardware — nothing to buy

- **Accelerometer: use the cheap one already on hand.** Its only job is to prove the *live* sensing path (I²C read → real-time sampling, hand-shake demo). Real fault classification comes from **dataset replay**, not the live sensor — so sensor quality/rate is irrelevant. Confirm the exact chip (MPU6050 / ADXL345 / LIS3DH / etc.) so Step 5 targets the right driver.
- Everything else (camera, mic, NPU, SDRAM, OSPI, both cores) is already on the board.
- **Full hardware list = EK-RA8P1 + the cheap accel you own. Zero purchases.**

---

## Demo strategy — no real machine needed

We do **not** wire a real machine/bearing to the board. You can't crack a real bearing on stage, and you don't need to. The demo runs on **labeled dataset replay** through the real pipeline, plus the cheap accel for liveness. Three layers the judges see:

1. **Live cheap accel** — shake the board by hand. Proves real I²C sensing + RTOS sampling that never misses a deadline. (Liveness, not the AI input.)
2. **NASA IMS dataset replay** — real labeled bearing data (normal → degrading → fault) plays through the *same* `sample_next()` pipeline. Proves the node actually detects real machine faults. This is the meaningful AI demo.
3. **Federation** — PC aggregator + the board's two cores exchange gradients. Proves nodes learn together while raw data never leaves the device.

Dataset gets into the board two ways, both supported (Step 5):
- **Flash-resident (primary):** IMS data pre-loaded on the 64MB OSPI flash → board replays standalone, no PC needed on stage. Nothing external to fail.
- **PC-stream (flexible):** PC streams samples over UART/USB live → swap fault cases on the fly during Q&A.

Honest framing for judges: "real sensor path is live; fault detection is validated on real labeled industrial bearing data because we can't safely destroy a bearing on stage."

## The two rules that make this plan safe

### Rule 1 — Every step is test-gated. A step is DONE only when its test prints `PASS` on real hardware.

Each step below has a **Certified Test**: an exact, objective pass/fail check with expected numbers. Not "looks right" — a printed `[PASS] step-N` over serial. If the test can't pass, the step isn't done. You do not advance.

### Rule 2 — Every build runs ALL previous tests (cumulative regression). A defect is caught at the step that caused it, never discovered later.

Step 1 builds a **regression harness**. From then on, every firmware build runs the full list of step-tests in order and prints a report:

```
[PASS] t01_harness
[PASS] t02_board
[FAIL] t06_sampling   <-- deadline counter = 3, expected 0
[----] t07_features   (skipped, prior failed)
```

This directly solves your worry. You will **never** reach Step 6 and only then discover Step 2 was wrong: Step 2's test runs on every build from Step 2 onward. The moment any later step breaks an earlier guarantee, that earlier test flips to `FAIL` and names exactly what broke. Defects are localized in time to the step that introduced them.

**Supporting technique — golden vectors / oracle pattern:** wherever math must be exact (features, inference, FedAvg), the PC produces known-correct `input → expected output` vectors. The device test asserts it reproduces them within tolerance. Correctness is numerical and certified, not eyeballed. And when we add the NPU, it must match the already-proven software path (the *oracle*) — so we never trust new hardware blindly.

---

## Why nothing gets rebuilt twice: seams first

We do **not** build single-core then tear it apart for dual-core. Instead, Week 1 builds **abstraction seams**. Later hardware plugs into a seam as a new *backend* — a config change, not a rewrite:

| Seam (built Week 1) | What plugs in later | Step it pays off |
|---------------------|---------------------|------------------|
| **Message bus** (`msg_send`/`msg_recv`, mailbox-backed) | Move a task to the M33 — same API, shared-memory backend | 14 |
| **Memory pool** (placement = SRAM or SDRAM by config) | Big replay buffers in 64MB SDRAM | 11 |
| **Inference interface** (`infer(features)`) | Swap CMSIS-NN → Ethos-U55 NPU backend | 10 |
| **Sample source** (`sample_next()`) | Real LSM6DSO **or** dataset replay from OSPI | 5 |
| **Weight store** (`weights_load`/`weights_save`) | OSPI persistence; TrustZone-secured storage | 12, 16 |

Because the seams exist from the start, dual-core, NPU, SDRAM, OSPI and secure storage are **additions**, not rewrites. Each step genuinely feeds the next.

### Tag every step

```bash
git add -A && git commit -m "Step N: <result>" && git tag step-N && git push --tags
```
Failure → `git checkout step-(N-1)` and retry. You lose at most one step.

---

## Current state — Step 0 (DONE ✅)

μT-Kernel 3.0 boots, prints `microT-Kernel Version 3.00 / FedTinyRT starting...`. Tag `step-0`.

---

# WEEK 1 — Test infrastructure, board proof, seams

*Goal: every hardware block proven alive, every abstraction seam in place, the regression harness running. After this week, all later work is additive and self-checking.*

### Step 1 — On-device test harness + regression runner

**Produces:** A tiny test framework. Each test = a function returning pass/fail; the runner prints `[PASS]/[FAIL] name` over serial and a final summary. A `RUN_ALL` entry point executes every registered test in order.
**Certified test:** Harness self-test — one deliberately-passing and one deliberately-failing dummy test produce exactly `[PASS] selftest_ok` and `[FAIL] selftest_bad`. Summary reports `1 passed, 1 failed`.
**Proves for later:** All future PASS/FAIL lines are trustworthy. This is the instrument every other step reports through.
**Rollback:** `step-0`. **Tag:** `step-1`.

### Step 2 — Board self-test (every block you will use, proven now)

**Produces:** A power-on diagnostic that checks and reports each hardware block: core clocks at target frequency, internal SRAM, **SDRAM** (write pattern → read back → compare), **OSPI flash** (read JEDEC ID + read/write/erase a sector), **Ethos-U55 NPU** present/responding, both core IDs readable, camera interface present, mic present.
**Certified test:** Each block prints its own `[PASS]/[FAIL]` (e.g. `[PASS] t02_sdram 64MB ok`, `[PASS] t02_npu detected`). All must pass.
**Proves for later:** Every block the max-plan depends on works **on day 2**. A bad SDRAM, dead NPU, or missing camera is found now — not in Week 4. If the camera/mic aren't actually populated, this is where we learn it and adjust.
**Rollback:** `step-1`. **Tag:** `step-2`.

### Step 3 — Task framework + core-agnostic message bus

**Produces:** Multi-task scheduler (priorities, `tk_dly_tsk`). All inter-task data flows through a `msg_send(channel, buf)` / `msg_recv(channel)` abstraction backed by μT-Kernel mailboxes. Single-core today, but the API is identical to what dual-core will use.
**Certified test:** Producer task sends N numbered messages; consumer asserts it receives all N in order with no loss. A high-priority task with a 10ms deadline meets it while a low-priority task busy-runs (preemption proven). Shared serial guarded by mutex → no interleaved/garbled lines over 1000 prints.
**Proves for later:** The exact messaging seam the M33 will reuse unchanged in Step 14.
**Rollback:** `step-2`. **Tag:** `step-3`.

### Step 4 — Memory pool (SRAM/SDRAM) + weight-store seam

**Produces:** A buffer pool that allocates from SRAM or SDRAM by a config flag, and a `weights_load/weights_save` interface (RAM-backed for now).
**Certified test:** Allocate a buffer in SRAM and in SDRAM; write a pattern, read back, compare — both byte-exact. A buffer used inside a 10ms task from SDRAM does not cause a missed deadline (timing check via Step 3 monitor).
**Proves for later:** SDRAM replay buffers (Step 11) and OSPI/secure weight storage (Steps 12, 16) drop in with no structural change.
**Rollback:** `step-3`. **Tag:** `step-4`.

---

# WEEK 2 — Data in, numerically validated

*Goal: real and replayed sensor data flow through a hard-real-time pipeline, with features proven correct against PC ground truth.*

### Step 5 — Sample-source seam: LSM6DSO driver + dataset replay

**Produces:** A `sample_next()` source with two backends — (a) live **LSM6DSO** over I2C/SPI, (b) **NASA IMS dataset** replay streamed from OSPI flash. Same API; switch by config.
**Certified test:** Live backend — WHO_AM_I returns the LSM6DSO ID; X/Y/Z change when shaken. Replay backend — first 100 samples streamed from flash match the known dataset values **bit-exact** (golden vector).
**Proves for later:** Every ML step can be tested against labeled ground-truth data, not just hand-shaking. This is what lets accuracy be measured objectively.
**Rollback:** `step-4`. **Tag:** `step-5`. *(Needs LSM6DSO for the live half; replay half works board-only.)*

### Step 6 — Real-time sampling task + deadline monitor

**Produces:** Highest-priority task sampling at the configured rate into a ring buffer (pool from Step 4), pushing full windows over the message bus. A deadline-miss counter exposed to the test harness.
**Certified test:** Over 10 s the sample count is within ±1% of expected; **deadline-miss counter = 0**. Windows arrive intact at the consumer (count + checksum).
**Proves for later:** The hard-real-time guarantee — instrumented. From here on, **the miss counter must stay 0 through every later step** (the regression harness enforces it).
**Rollback:** `step-5`. **Tag:** `step-6`.

### Step 7 — Feature extraction (Helium FFT) — validated vs PC

**Produces:** Feature task: sliding-window **FFT** (CMSIS-DSP, Helium-accelerated) + statistics (RMS, peak, kurtosis), packed into a fixed feature vector. Behind a `feature_extract()` interface.
**Certified test:** Feed a **known input** (synthetic sine + a labeled IMS window). Assert output FFT bins / stats match the **PC reference within tolerance** (golden vector). Helium path produces the same result as the scalar path, faster (record cycles).
**Proves for later:** Features are numerically correct — so if inference is later wrong, it isn't the features. (This is exactly how "Step 2 was wrong, found at Step 6" is prevented: each layer is certified before the next consumes it.)
**Rollback:** `step-6`. **Tag:** `step-7`.

---

# WEEK 3 — Inference (software oracle → NPU) + on-device learning

*Goal: correct INT8 classification, first on CPU as the oracle, then on the NPU validated against it; then on-device training.*

### Step 8 — PC pre-train + export weights + golden vectors

**Produces (Python):** Small net trained on **NASA IMS** for normal/degrading/fault. Frozen feature extractor + trainable head. Exported: INT8 weights as C arrays, **plus a set of `feature_vector → expected_logits` golden vectors** for on-device validation.
**Certified test:** PC reports test-set accuracy above an agreed bar (e.g. ≥85%). Golden-vector file generated and committed.
**Proves for later:** Provides the numerical oracle that Steps 9 and 10 must reproduce.
**Rollback:** Pure PC work, no firmware risk. **Tag:** `step-8`.

### Step 9 — Software inference (CMSIS-NN) — the oracle

**Produces:** Inference task implementing the `infer(features)` interface with a **CMSIS-NN** backend (frozen extractor + head).
**Certified test:** Run the Step-8 golden vectors on-device → output logits/class match the PC within tolerance for all vectors. Latency recorded. Sampling miss counter still 0.
**Proves for later:** Correct inference path that the NPU must match. **This alone (Steps 1–9) is already a valid, submittable single-node edge-AI system.**
**Rollback:** `step-8`. **Tag:** `step-9` ← *minimum viable milestone*.

### Step 10 — NPU inference (Ethos-U55) — validated against the oracle

**Produces:** A second `infer` backend running the frozen extractor on the **Ethos-U55 NPU** (model compiled via Vela; TFLite-Micro + Ethos-U driver). Same interface — selectable at config.
**Certified test:** Same Step-8 golden vectors → **NPU output matches the Step-9 software output** within tolerance (correctness vs the oracle, not blind trust). NPU latency is markedly lower than CMSIS-NN (record both). Miss counter 0.
**Proves for later:** Hardware-accelerated inference, certified correct. Frees CPU headroom for training + the M33.
**Rollback:** `step-9` (software path intact). **Tag:** `step-10`.

### Step 11 — On-device training (SGD on head) + replay buffer

**Produces:** Low-priority training task: SGD on the **head only** (extractor frozen), drawing from a **replay buffer in SDRAM** (Step 4). Shared head weights guarded by a **priority-inheritance mutex**.
**Certified test:** Train over N rounds on labeled replay data → head accuracy measurably improves (printed curve). Mutex test: a concurrent reader never observes a torn/half-updated weight set (checksum invariant). Deadline miss counter still 0 while training runs — *the core contest claim, demonstrated.*
**Proves for later:** Gradients exist to federate; learning works without breaking real-time.
**Rollback:** `step-10`. **Tag:** `step-11`.

### Step 12 — Weight persistence (OSPI)

**Produces:** `weights_save/load` backed by **OSPI flash**.
**Certified test:** Train → save → reboot → reload → weights byte-identical (checksum) and accuracy retained. Falls back to baked-in weights if flash empty.
**Proves for later:** Federation can persist merged weights; a node powers up already knowing what it learned.
**Rollback:** `step-11`. **Tag:** `step-12`.

---

# WEEK 4 — Federation, dual-core, vision, secure + power, certify

*Goal: full federated system, both cores working, NPU vision modality, hardware-secured weights — all under the regression harness.*

### Step 13 — Federation protocol (UART + sparsify + FedAvg)

**Produces:** Federation task: head gradients compressed via **top-K (10%) sparsification + 8-bit quantization** into framed UART packets (header/len/payload/CRC). **PC acts as aggregator**, simulating extra virtual nodes, runs **FedAvg**, returns merged weights; node applies them.
**Certified test:** Packet round-trip CRC-clean. FedAvg result on-device matches a **PC reference computation** for the same inputs (golden vector). Applying merged weights changes classification as predicted. Miss counter 0.
**Proves for later:** Full single-board federation works; the cross-node exchange that dual-core will mirror internally.
**Rollback:** `step-12`. **Tag:** `step-13` ← *full single-board system*.

### Step 14 — Dual-core activation (M33 takes sampling + UART) — no rewrite

**Produces:** The M33 core brought up; **sampling (Step 6) and UART federation (Step 13) tasks moved to the M33** using the *same message bus* (Step 3) and *same shared pool* (Step 4) — backend swapped to shared-memory + IPC, application code unchanged. M85 does features/NPU/training.
**Certified test:** **Full regression suite passes with work split across cores** — every prior step-test still `PASS`. Cross-core message integrity verified (numbered messages, zero loss). Miss counter 0 with sampling on M33.
**Proves for later:** Both cores carry real load with zero rework — payoff of building seams in Week 1.
**Rollback:** `step-13` (single-core, fully working). **Tag:** `step-14`.

### Step 15 — Two-core federation + camera/NPU vision + LCD dashboard

**Produces:** (a) Treat the **two cores as two federation nodes** that FedAvg with each other via shared memory (plus the PC) — a dramatic on-board federation demo. (b) **MIPI camera → Ethos-U55** image classification as a 4th modality, fused with vibration/audio. (c) **LCDC dashboard**: live class, confidence, federation status.
**Certified test:** Cross-core gradient exchange converges (accuracy rises on both core-nodes). Camera frames captured + classified on NPU (validated vs a PC reference image set). Dashboard shows correct live state. Miss counter 0.
**Proves for later:** Maximal multi-modal, multi-core, NPU-accelerated demonstration.
**Rollback:** `step-14`. **Tag:** `step-15`. *(Vision half needs the camera module confirmed alive in Step 2.)*

### Step 16 — TrustZone secure weights + power management

**Produces:** Model weights + gradient buffers moved into the **TrustZone secure partition**, accessed via non-secure-callable veneers; idle paths use **`tk_slp_tsk`** for low power; training/federation activate only when enough data accrues.
**Certified test:** System still classifies/trains/federates with weights in the secure world. A non-secure attempt to read secure weight memory **faults** (protection demonstrated, certified). Measured current drops in idle vs busy. Miss counter 0.
**Proves for later:** Hardware-enforced privacy backing the "data never leaves the device" claim; real power efficiency.
**Rollback:** `step-15` (most invasive step — flat-build tag is the safety net). **Tag:** `step-16`.

### Step 17 — Full regression, power profile, demo certification

**Produces:** Final pass: `RUN_ALL` executes every step-test end to end; power profiled; demo script + docs finalized.
**Certified test:** **All step-tests t01–t16 print `PASS` in one run.** This is the signed-off, fully-utilized system.
**Rollback:** any prior `step-N`. **Tag:** `step-17` ← *final*.

---

## Dependency map (each step feeds the next)

```
step-0 boots
 └ 1 test harness ──────────────────────────── (instruments everything below)
    └ 2 board self-test (SDRAM/OSPI/NPU/cores/cam/mic all proven)
       └ 3 task framework + message bus ─────── seam → 14 (dual-core)
          └ 4 memory pool + weight seam ─────── seam → 11 (SDRAM), 12/16 (storage)
             └ 5 sample source (LSM6DSO + IMS replay) ── seam → testable ML
                └ 6 real-time sampling (miss=0 from here on)
                   └ 7 features (Helium, validated vs PC)
                      └ 8 PC train + golden vectors
                         └ 9 software inference (ORACLE) ── valid submission
                            └ 10 NPU inference (matches oracle)
                               └ 11 on-device training (+SDRAM replay)
                                  └ 12 OSPI persistence
                                     └ 13 federation (FedAvg vs PC ref) ── full system
                                        └ 14 dual-core (M33, no rewrite, full regression)
                                           └ 15 two-core fed + camera/NPU + dashboard
                                              └ 16 TrustZone secure + power
                                                 └ 17 full regression + certify
```

## One-page timeline

| Week | Dates | Steps | Milestone |
|------|-------|-------|-----------|
| 1 | Jun 30 – Jul 6 | 1–4 | Test harness + every block proven + seams in place |
| 2 | Jul 7 – Jul 13 | 5–7 | Real-time data pipeline, features validated vs PC |
| 3 | Jul 14 – Jul 20 | 8–12 | Inference (CPU oracle → NPU) + on-device training + persistence |
| 4 | Jul 21 – Jul 28 | 13–17 | Federation + dual-core + vision + secure/power + certify |

**Safety:** Step 9 = valid submission. Step 13 = full federated system. Steps 14–16 each only *add* and each rolls back to the prior tag. No step can sink the project.

## The golden rules

1. **A step is done only when its Certified Test prints `PASS` on hardware.**
2. **Every build runs RUN_ALL.** An earlier test going `FAIL` localizes the defect to the step that caused it — you never debug blind across steps.
3. **The sampling miss counter is sacred — it stays 0 from Step 6 to Step 17.**
4. **Seams, not rewrites.** NPU, M33, SDRAM, OSPI, TrustZone, camera all plug into Week-1 seams as backends.
5. **Validate new hardware against a proven oracle** (NPU vs software, FedAvg vs PC) — never trust a new block blindly.
6. **Tag every step.** Tags are save points; rollback costs at most one step.
