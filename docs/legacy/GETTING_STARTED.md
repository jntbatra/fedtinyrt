# Getting Started — FedTinyRT (team onboarding)

Welcome. This tells a new team member exactly how to go from zero → productive.
Read it fully once; it takes ~20 minutes.

---

## 0. What we're building (30 seconds)
A per-hospital µT-Kernel board that detects Parkinson's **Freezing of Gait** from an accelerometer,
learns on-device, and **federates model weights (never patient data)** across hospitals.
Full picture: **read `SYSTEM_OVERVIEW.md` first.**

---

## 1. Read in this order (do not skip)
1. **`SYSTEM_OVERVIEW.md`** — the whole system in plain language (methodology, assumptions, tools,
   uncertainty). *Everyone reads this.*
2. **`context.md`** — the strict glossary + every design decision + ADRs. *Learn the exact words we
   use* (e.g. `Float32_Master`, `NPU_Binary`, `Aggregation_Payload`). Using loose terms causes bugs.
3. **`RFC-001-systems-contract.md`** — the engineering contract: budgets, SLAs, failure modes.
   *Read the section your work touches.*
4. **`KANBAN.md`** — how work is sliced and how the board runs. *Read before picking a task.*

**Rule:** never say "the model" or "the data." Say which **state** (`context.md §0`).

---

## 2. Get access & clone
- Ask the owner (`jntbatra`) for **repo access** (it's private) + **GitHub Project** access.
- Clone:
  ```
  git clone https://github.com/jntbatra/fedtinyrt.git
  cd fedtinyrt
  ```
- Never commit datasets or large binaries (see `.gitignore`). Patient/raw data **never** goes in git.

---

## 3. Pick your track — we have two

### Track A — Firmware / Embedded (the board)
You work on µT-Kernel tasks, drivers, NPU inference, on-device training, inter-core comms.
**Setup:**
- **e2 studio** IDE + Renesas **FSP** + **µT-Kernel 3.0 BSP2** for EK-RA8P1.
- **J-Link / SEGGER RTT** for flashing + on-target logs.
- **Arm Vela** compiler for NPU: `pip install ethos-u-vela` (turns a `.tflite` into an `NPU_Binary`).
- The **EK-RA8P1 board** (we have one — HIL is serial, coordinate on Slack before you flash).
- Verify: build + flash **issue #1 (S0)** — LED blinks + RTT heartbeat. If that works, your toolchain is good.

### Track B — ML / Data (PC-side)
You work on datasets, features, model training, INT8 export, the FedAvg simulator.
**Setup:**
```
python -m venv .venv
# Windows:  .venv\Scripts\activate    |  macOS/Linux:  source .venv/bin/activate
pip install tensorflow scikit-learn numpy scipy lazypredict
pip install kaggle            # for dataset download (needs a Kaggle API token)
```
- Datasets live in `ml/data/` (git-ignored). Start with **issue #12 (ML-1)**: pull Kaggle FoG,
  harmonize units (m/s² ↔ g), resample → 100 Hz.
- Verify: run the existing `ml/*.py` pipeline on a small slice; check it produces features + a metric.

*(Some people do both tracks — fine. But pick one card at a time.)*

---

## 4. How the board (kanban) works
- Work is **HIL vertical slices** S0→S10 + an ML track (ML-1..3). See `KANBAN.md`.
- Columns: `Backlog → Ready → In Progress → HIL-Verify → Done`.
- **WIP limit = 1** slice `In Progress` (one physical board, HIL is serial).
- A card is only `Done` when its **on-hardware pass/fail test passes** *and* all lower slices still pass.
- **Dependency order matters** — don't start S4 before S1 is Done. `Ready` = all deps Done.

### The non-negotiable rules (why our cards look different)
1. **Vertical, not horizontal.** Never "write all the drivers." A task must touch ≥2 layers and end in
   an observable output. (Enforced in `KANBAN.md`.)
2. **Ends in an HIL demo**, not "it compiles."
3. **Cite the contract** — every task names the `RFC-001` clause / B-item it proves.
4. **Honesty (REALITY FILTER)** — label claims `[Verified]` / `[Target]` / `[Unresolved]`. Never dress a
   goal as an achievement. If a number isn't measured, say so.
5. **No data leakage** — split by *subject*, never by window. (This faked a 99.5 % once; don't repeat it.)

---

## 5. Your daily workflow
1. On the Project board, move a `Ready` card → `In Progress` (respect WIP=1 for HIL cards).
2. Branch: `git checkout -b s2-m33-training` (never commit straight to `main`).
3. Do the slice. Keep changes scoped to that card.
4. Run the card's **HIL acceptance test** (or the ML verification). Record the measured numbers into
   `RFC-001 §5` (the B-items).
5. Open a **PR** referencing the issue (`Closes #3`). In the PR body, paste the HIL result + numbers.
6. Move card → `HIL-Verify`; a reviewer re-runs the test; on pass → `Done` + merge.
7. Regression: confirm lower slices still pass.

**Commit style:** small, focused, message says *what + why*. End with the co-author trailer we use.

---

## 6. Suggested first task by role
| You are… | Start with | Proves |
|----------|-----------|--------|
| Firmware, new to the board | **#1 S0** skeleton (boot + RTT) | your toolchain works |
| Firmware, NPU-curious | **#2 S1** dummy INT8 → Vela → NPU → telemetry | the NPU pipeline |
| Firmware, systems | **#3 S2** M33 head training (⚠️ gates ADR-004) | the riskiest unknown — do early |
| ML / data | **#12 ML-1** Kaggle ingest + unit harmonize | clean data foundation |
| ML / modeling | **#13 ML-2** windowing + 1D-CNN + INT8 export | the device model |
| ML / federation | **#14 ML-3** partition + FedAvg sim | the federation numbers |

**Highest-leverage overall: #3 (S2).** It tells us whether on-device training even fits the M33 — if
not, we change the architecture (fall back to M85 training). Learn it in Week 1, not Week 3.

---

## 7. Milestones (1-month plan)
- **Wk1:** S0–S3 (plumbing, dummy-first).
- **Wk2:** S4–S6 (real sensor, real model, real federation) + ML-1..3 land.
- **Wk3:** S7–S9 (concurrency, failure drills, power).
- **Wk4:** S10 (personalization + cross-site science) + hardening + submission.

---

## 8. Where to ask / coordinate
- **Board flashing** — coordinate in the team chat (single board, don't collide).
- **A design decision seems wrong** — don't silently code around it. Raise it against `context.md`;
  if we change a definition there, the `RFC-001` clause must change too.
- **Stuck > 30 min on setup** — ask; setup pain is common and someone likely solved it.

---

## 9. TL;DR
1. Read `SYSTEM_OVERVIEW.md` → `context.md`.
2. Get repo + board access.
3. Set up your track (A firmware / B ML).
4. Take a `Ready` card (start: #1 firmware, #12 ML).
5. Branch → build → **prove it on hardware** → PR → regression.
6. Be honest with numbers. Split by subject. Slice vertically.
