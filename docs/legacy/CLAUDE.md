# CLAUDE.md — FedTinyRT project instructions

Read by every Claude Code session (and every human). Keep it short and high-signal.

## What this is
Per-hospital µT-Kernel board (Renesas EK-RA8P1) that detects Parkinson's **Freezing of Gait** from an
accelerometer, learns on-device, and **federates model weights only** (never patient data) across
hospitals. Full picture: `SYSTEM_OVERVIEW.md`.

## Read order (before doing anything)
1. `SYSTEM_OVERVIEW.md` — whole system, plain language
2. `context.md` — strict Ubiquitous Language + all decisions + ADRs (**use the exact state names**)
3. `RFC-001-systems-contract.md` — SLAs, budgets, failure modes
4. `KANBAN.md` — HIL vertical-slice plan; issues #1–#15 on GitHub

## Environment (Windows / PowerShell + Git-Bash)
- **`python` is NOT on PATH — use `py` or `python3`** (Windows launcher).
- **`kaggle` CLI not installed and FoG data not present.** Before ML-1:
  `py -m pip install kaggle` then set the Kaggle API token (`~/.kaggle/kaggle.json` or
  `KAGGLE_USERNAME`/`KAGGLE_KEY`). Data lives in `ml/data/` (**git-ignored — never commit data**).
- ML deps: `py -m pip install tensorflow scikit-learn numpy scipy lazypredict`.
- Firmware: e2 studio + Renesas FSP + µT-Kernel 3.0 BSP2; Arm **Vela** (`pip install ethos-u-vela`);
  J-Link/SEGGER RTT. Single physical board — coordinate before flashing.
- `ml/` already has reusable `feature_extract.py` + the IMS/CWRU pipeline; FoG code is new.

## Working agreements (non-negotiable)
1. **REALITY FILTER.** Label claims `[Verified]` / `[Inference]` / `[Target]` / `[Unresolved]`. Never
   present a goal as an achievement. If a number isn't measured, say so. Prefer verifying (web/datasheet)
   over guessing; if you can't verify, say "I cannot verify this."
2. **Strict state names** (`context.md §0`): say `Float32_Master`, `NPU_Binary`, `Aggregation_Payload`,
   `Raw_Window` — never "the model" / "the data".
3. **Vertical slices only.** Work follows `KANBAN.md` HIL slices; a task touches ≥2 layers and ends in an
   on-hardware pass/fail test. No horizontal "write all X first" tasks.
4. **No data leakage.** Split by **subject**, never by window (this faked a 99.5% once).
5. **Metric = AUPRC / Average Precision + sensitivity/specificity.** Accuracy is banned (rare-class trap).
6. **Privacy invariant.** Raw data (`Raw_Window`/`Feature_Vector`/`Label`) never leaves the **Node**
   (wearable + base station). Only `Aggregation_Payload` (FP32 weights) crosses the inter-Node network.

## Git
- Repo: `github.com/jntbatra/fedtinyrt` (private), default branch `main`.
- Commit small + focused; message = what + why. End commits with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Never commit datasets, raw signals, or large binaries.
- Working dir may be `D:\Projects\tron`; the repo is `D:\Users\jayan\e2_studio\workspace\Project` — use
  `git -C <repo>` if needed.

## Kanban / issues
- GitHub Project, columns Backlog→Ready→In Progress→HIL-Verify→Done, **WIP=1** for HIL.
- Start points: **#1 (S0)** firmware skeleton · **#12 (ML-1)** Kaggle ingest+harmonize.
- Highest-leverage unknown: **#3 (S2)** M33 on-device training — gates ADR-004; do early.

## Honesty positioning (repeat in any writeup)
FoG + federated learning is prior art; our contribution is the **RTOS/embedded realization** (µT-Kernel +
dual-core + Ethos-U55 NPU + on-device training + measured real-time). It's a **simulation**, not a
clinical device — no medical claims. Never say federation "fixes/guarantees/ensures" cross-site results.
