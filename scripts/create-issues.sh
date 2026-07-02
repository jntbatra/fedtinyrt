#!/usr/bin/env bash
# Populate the FedTinyRT GitHub Project with HIL vertical-slice issues.
# Requires: gh CLI authenticated (gh auth status). Run once.
# Usage:  REPO=jntbatra/fedtinyrt bash scripts/create-issues.sh
set -u
REPO="${REPO:-jntbatra/fedtinyrt}"
echo "Target repo: $REPO"

# --- labels (idempotent; ignore 'already exists') -------------------------
gh label create slice     -R "$REPO" -c "#1f77b4" -d "HIL vertical slice"            2>/dev/null || true
gh label create hil       -R "$REPO" -c "#2ca02c" -d "hardware-in-the-loop demo"     2>/dev/null || true
gh label create ml        -R "$REPO" -c "#9467bd" -d "PC-side ML (off HIL board)"    2>/dev/null || true
gh label create adr-gate  -R "$REPO" -c "#d62728" -d "gates an ADR decision"         2>/dev/null || true
gh label create foundation -R "$REPO" -c "#7f7f7f" -d "bring-up foundation"          2>/dev/null || true

# --- milestones (idempotent) ---------------------------------------------
for M in "Wk1 S0-S3 plumbing" "Wk2 S4-S6 real" "Wk3 S7-S9 harden" "Wk4 S10 science+submit"; do
  gh api "repos/$REPO/milestones" -f title="$M" -f state=open >/dev/null 2>&1 || true
done

# --- helper --------------------------------------------------------------
mk () {  # mk "title" "labels" "milestone" "body"
  gh issue create -R "$REPO" --title "$1" --label "$2" --milestone "$3" --body "$4" \
  && echo "created: $1"
}

# =========================== HIL SLICES ==================================
mk "S0 — Skeleton HIL foundation" "slice,hil,foundation" "Wk1 S0-S3 plumbing" \
"Vertical path: M85 -> GPIO/UART/RTT
Proves: toolchain + flash + debug I/O + uT-Kernel task creation
Resolves: B6 (uT-Kernel API names vs BSP2)
Depends on: -
HIL acceptance: GIVEN a flashed board WHEN reset THEN LED blinks 1 Hz AND RTT prints a task heartbeat.
DoD: runs on EK-RA8P1; logged."

mk "S1 — NPU inference + telemetry egress" "slice,hil" "Wk1 S0-S3 plumbing" \
"Vertical path: MRAM -> M85 -> Ethos-U55 NPU -> Ethernet/UART -> mock PC aggregator
Slice: dummy INT8 model -> Vela -> NPU_Binary in MRAM -> one inference on canned Raw_Window -> telemetry to PC.
Proves: RFC-001 1.4 (NPU Offload), 1.2 (working set <=512KB, p99 <=100ms), egress I/O
Resolves: B7 (INT8 path), partial B6 (NPU<->core coupling)
Depends on: S0
HIL acceptance: GIVEN NPU_Binary in MRAM WHEN one inference runs THEN output == PC golden vector AND latency <=100ms AND mock PC receives telemetry frame.
DoD: on-hw demo; regression S0 passes."

mk "S2 — Local head training + delta to MRAM (gates ADR-004)" "slice,hil,adr-gate" "Wk1 S0-S3 plumbing" \
"Vertical path: SRAM/TCM -> M33 CPU -> MRAM (A/B slot)
Slice: one fwd+bwd pass of the HEAD on M33 (FP32) over canned batch -> weight delta -> write MRAM inactive slot.
Proves: RFC-001 1.3 (M33 grad RAM <=96KB TCM), F4 (A/B write), R5 gate on ADR-004
Resolves: B2 (M33 epoch time + RAM)
Depends on: S0
HIL acceptance: GIVEN a canned batch WHEN one head epoch runs on M33 THEN peak TCM <=96KB AND epoch <=5s AND delta readable from inactive MRAM slot.
IF FAIL: auto-open 'ADR-004 revision: M85 idle-slot training' card.
DoD: numbers logged to RFC-001 B2."

mk "S3 — Federated round loop" "slice,hil" "Wk1 S0-S3 plumbing" \
"Vertical path: PC(FedAvg) -> Ethernet -> M33(gate) -> MRAM(A/B swap) -> M85/NPU
Slice: mock aggregator gets 3 mock Aggregation_Payloads -> FedAvg -> push Global_Model[r] back -> A/B swap -> re-quantize -> next inference uses new weights.
Proves: RFC-001 2 (federated contract), 3.2 (round_id/stale-reject), F3 (sanity filter), F4 (atomic swap)
Resolves: partial B8, B4 path
Depends on: S1, S2
HIL acceptance: GIVEN 3 payloads (incl 1 NaN + 1 wrong round_id) WHEN a round runs THEN both bad rejected, good aggregates, device boots new slot, inference reflects update.
DoD: on-hw; regression S0-S2 pass."

mk "S4 — Real sensor real-time loop (live prediction)" "slice,hil" "Wk2 S4-S6 real" \
"Vertical path: I2C accel -> DMA ring buffer -> 2s window -> Feature_Vector -> NPU -> LED/display
Proves: RFC-001 4.2 (0 missed 100Hz deadlines), DMA path, F6 (sensor liveness), 'board does prediction'
Depends on: S1 (+ external accel chip / I2C driver — part name pending)
HIL acceptance: GIVEN live accel motion WHEN sampled 60s THEN 0 missed sampling deadlines AND live prediction updates each 1s AND unplugging sensor -> liveness=false (no false negative).
DoD: on-hw."

mk "S5 — Real model on real FoG data (device<->PC parity)" "slice,hil" "Wk2 S4-S6 real" \
"Vertical path: flash/UART replay -> M85 -> NPU -> PC compare
Slice: replace dummy with trained depthwise-separable 1D-CNN on real Kaggle FoG replay; compare device vs PC golden; measure per-window AUPRC.
Proves: 2.3 determinism, 1.1 payload size (B3), B1 metric start
Resolves: B3, B7-final (INT8 vs INT16 -> R6)
Depends on: S1, S4, ML-1, ML-2
HIL acceptance: GIVEN real FoG windows WHEN device infers THEN device-vs-PC AUPRC delta <=1% AND payload bytes recorded to RFC-001 1.1.
DoD: parity logged."

mk "S6 — End-to-end real federation (value demo)" "slice,hil" "Wk2 S4-S6 real" \
"Vertical path: board(train+infer) || >=3 PC virtual hospitals -> aggregator -> back to board
Proves: RFC-001 2.1 federation-must-not-hurt + scarce-hospital uplift
Resolves: B1 (T_auprc, N_max from this run)
Depends on: S3, S5, ML-3
HIL acceptance: GIVEN N hospitals WHEN federation converges THEN federated AUPRC >= local for board hospital AND staged freeze-poor hospital improves materially.
DoD: results table."

mk "S7 — Concurrency under real-time load (ADR-004 headline)" "slice,hil,adr-gate" "Wk3 S7-S9 harden" \
"Vertical path: M85(sample+infer) || M33(train), inter-core mailbox+HW-sem
Proves: RFC-001 4.2 headline RTOS metric under load; ADR-004 parallel split
Depends on: S2, S4
HIL acceptance: GIVEN concurrent train+infer 5 min THEN 0 missed sampling deadlines AND worst-case jitter logged AND inference latency SLA still met.
DoD: jitter/deadline report."

mk "S8 — Failure-mode drills" "slice,hil" "Wk3 S7-S9 harden" \
"Inject F1 (NPU hang), F2 (train hang), F4 (reset mid-MRAM-write), F5 (unplug Ethernet).
Proves: RFC-001 3 (F1/F2/F4/F5) + 4 fail-safe invariant
Depends on: S3, S4
HIL acceptance: each fault -> contracted fallback observed (CPU fallback / discard Personalized_Model / boot last-good slot / store-and-forward) AND sampler never stalls AND no false no-freeze.
DoD: drill log."

mk "S9 — Power characterization" "slice,hil" "Wk3 S7-S9 harden" \
"Measure deep-sleep-between-assessments, NPU-vs-CPU energy/inference, Ethernet PHY off.
Proves: RFC-001 2.1 energy SLA (measured; no battery claim)
Depends on: S4, S7
HIL acceptance: report avg active vs idle power AND NPU/CPU energy ratio from board instrumentation.
DoD: power numbers logged."

mk "S10 — Personalization + cross-site science" "slice,hil" "Wk4 S10 science+submit" \
"On-device personalization; leave-one-hospital-out + lab->home evaluation.
Proves: scientific claim (context.md Appendix C), 2.1 T_auprc
Depends on: S5, S6
Analysis: report local vs federated vs personalized, LOHO, lab->home AUPRC.
DoD: final results section."

# =========================== ML TRACK (off HIL board) ===================
mk "ML-1 — Kaggle FoG ingest + harmonize" "ml" "Wk2 S4-S6 real" \
"Pull Kaggle tlvmc FoG; harmonize units (tdcsfog m/s^2 <-> defog g, 1g=9.81); resample -> 100Hz; defog Valid/Task filter; subject-level manifest.
Proves: context.md preprocessing Trap 1 + Trap 2 handled
Blocks: S5, S6"

mk "ML-2 — Windowing + models + INT8 export" "ml" "Wk2 S4-S6 real" \
"2s/50% windowing (200 samples); FI-MLP baseline + depthwise-separable 1D-CNN; INT8 export via SavedModel->TFLite; golden vectors.
Proves: RFC-001 2.3 determinism inputs; B7 candidate
Blocks: S5"

mk "ML-3 — Partition + FedAvg sim" "ml" "Wk2 S4-S6 real" \
"Partition tdcsfog -> 4-5 hospitals (subject-level); Daphnet seed (disjoint); FedAvg sim; LOHO + lab->home; freeze-poor scenario.
Proves: RFC-001 2.1 + 2.2; B1, B5
Blocks: S6, S10"

echo "Done. Review issues at: https://github.com/$REPO/issues"
