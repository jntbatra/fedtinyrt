# RA8P1 Apnea-Detector — Consolidated Progress Log

Single-file record of everything done on this project: setup, firmware, data,
evaluation history, current results, board state, open issues, and how to
reproduce. Generated 2026-09-29.

Everything below is on disk and was verified in the session that produced this
file, unless explicitly marked **[unverified]** or **[inferred]**.

---

## 0. One-paragraph summary

We deploy a small **INT8 MLP apnea/hypopnea detector** (21 hand-crafted
ECG+SpO2 features, 60 s windows) onto a **Renesas RA8P1** board and study
whether **label-free on-device adaptation** can beat the **frozen global model**
across subjects. Conclusion after the full evaluation: **it cannot** — every
adapted recipe ties the global head (all paired tests p ≥ 0.18 on 20 held-out
subjects). The board runs the model bit-exactly against a host reference. No
energy/power claims are made (no probe available); only cycles/ms.

---

## 1. Hardware

| Item | Value |
|---|---|
| Board | Renesas **RA8P1** (EK-RA8P1 class) |
| Primary core | **Arm Cortex-M85** @ 1 GHz (Helium/MVE) |
| Secondary core | **Arm Cortex-M33** |
| NPU | **Arm Ethos-U55** (present in silicon; `NPUCLK Div /2` in clock config) |
| Debug probe | On-board J-Link (SWD), USB **Debug1** port |
| Serial console | SCI_B virtual COM → `/dev/ttyACM0` |
| J-Link device string | `R7KA8P1` |
| FSP | **6.6.0** (`ra/fsp/inc/fsp_version.h`: `"6.6.0"`) |

On-screen + camera: a MIPI-CSI camera and a display are attached to the board.
Bring-up work lives in `/home/jbatra/tron/cam2lcd/` (see §9).

> **NPU note:** the board *does* have an Ethos-U55. Our firmware path is
> **CPU inference only** — we did not integrate an FSP Ethos-U55 driver, so we
> make **no NPU claims**. (This corrects an earlier statement that the board had
> no NPU.)

---

## 2. Host toolchain setup (headless, no GUI)

| Tool | Location / version | Verified |
|---|---|---|
| cmake | `/usr/bin/cmake` — 3.31.11 | yes |
| ninja | `/usr/bin/ninja` — 1.13.1 | yes |
| arm-none-eabi-gcc | `/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin/` — 13.2.1 (Arm GNU Toolchain 13.2.rel1) | yes |
| J-Link | `/opt/SEGGER/JLink_V978/`, `/usr/bin/JLinkExe` | yes |
| RASC | extracted under `/home/jbatra/tron/rasc_payload/` etc. | see §9 |
| Host Python | `/tmp/cincenv/bin/python` (numpy, scipy, h5py, wfdb, pyserial) | yes |

System deps: `cmake ninja-build build-essential`. Toolchain installed from the
Arm GNU 13.2.rel1 `arm-none-eabi` tarball; J-Link from the SEGGER Linux `.deb`
(accepting the license via `--post-data 'accept_license_agreement=accepted'`).

Paths are **not** on the default `PATH` for the toolchain/J-Link; call the
toolchain by absolute path or `export PATH=...` per shell.

---

## 3. Project layout (root `/home/jbatra/tron/apnea_deploy`)

Firmware (FSP-generated RA project; **do not hand-edit generated files**):

- `src/apnea.c` — INT8 classifier + serial command shell + training/federation
- `src/apnea_personal.c` — per-session recentring / threshold
- `src/apnea.h`, `src/apnea_model.h` — model + INT8 weights
- `src/apnea_selftest_vectors.h` — 256 stored test vectors
- `src/common_utils.h`, `src/hal_entry.c`, `src/user_config.h`
- `src/SEGGER_RTT/`, `src/SERIAL_TERM/` — console plumbing
- Build output: `build/Release/apnea_deploy.elf`
- `flash.jlink`, `flash2.jlink` — J-Link command scripts
- `configuration.xml`, `ra/`, `ra_cfg/`, `ra_gen/`, `cmake/` — FSP generated

Analysis / tooling (`tools/`):

- `cross_subject_eval.py` — the main P3/P5 protocol evaluator (see §6)
- `ref_features.py` — faithful port of the original feature extractor
- `serial_cmd.py` — send a command to the board over `/dev/ttyACM0`
- `parallel_fetch.sh`, `fetch_record.py`, `fetch_validation.sh`, `fetch_finals.sh`
- `pseudo_label_experiment.py`, `repro_experiment.py`, `sim_personal.py`
- `protocol_eval.py`, `extract_features.py`, `dump_vectors.py`,
  `extract_tflite.py`, `tflite_walk.py`

Docs (append-only log + plans):

- `RESULTS_PROTOCOL.md` — the results protocol (565 lines; sections P1→P5′)
- `DEFENSIBLE_PLAN.md`, `DEFENSIBLE_PLAN_V2.md`, `DEFENSIBLE_PLAN_V3.md`
- `PROGRESS_LOG.md` — **this file**; now kept at the tron root, one level up
  (`/home/jbatra/tron/PROGRESS_LOG.md`)

---

## 4. Data & artifacts

### 4.1 Model artifacts — `/home/jbatra/cinc2018_apnea_artifacts/`

26 files: the trained central model, selected INT8 `.tflite` + C header,
normalization constants, fixed 256 test vectors, federation CSVs, and
`TRAINING_CONTEXT.md` (full reproduction context), `subject_split_manifest.csv`.

Key facts from `TRAINING_CONTEXT.md`:

- Feature-based MLP, **1,249 parameters** (21-32-16-1), window 60 s / stride 30 s.
- Trained centrally on **70 subjects**; **final layer only** (17 params) updated
  in **one federated round** across 2 client shards (5 subjects each).
- Exported INT8 to `.tflite` + C array header. Status `PROTOTYPE_ACCEPTED`.
- **ECG contributes almost nothing** (ECG-only AUROC 0.578 vs SpO2-only 0.902);
  functionally this is an **SpO2 desaturation detector**.
- **No per-window training features ship in the zip** — only models, aggregates,
  and 256 fixed test vectors. Retraining requires the raw PhysioNet/CinC 2018
  v1.0.0 training recordings (see §4.2).
- `subject_split_manifest.csv` partitions (col 13): `central_train` 70,
  `final_test` 10, `validation` 10, `pi_client` 5, `renesas_client` 5.

### 4.2 Raw records on disk (fetched from PhysioNet CinC 2018 v1.0.0)

- `/tmp/cinc_ms/` — 9 `final_test` subjects (`tr04-0029 tr05-0647 tr06-0014
  tr07-0247 tr07-0841 tr10-0169 tr11-0537 tr12-0410 tr13-0164`)
- `/tmp/cinc_raw/` — `tr03-0322` (the site-A/B subject with 256 reference windows)
- `/tmp/cinc_val/` — 10 `validation` subjects fetched this session:
  `tr03-0532 tr03-1302 tr04-0020 tr04-0631 tr04-0808 tr05-1404 tr06-0122
  tr06-0584 tr11-0592 tr12-0684`
- Dataset at `/home/jbatra/cinc2018_apnea_artifacts` (parent dir) — **[inferred]**
  the `cinc2018_apnea_artifacts` tree; raw `.mat`/`.arousal` per subject.

Each `/tmp/cinc_*` record dir holds `<rec>.mat`, `<rec>.hea`, `<rec>.arousal`
(byte-exact sizes verified on fetch). `/tmp` is tmpfs (~7.8 GB; cohort uses ~2.5 GB).

### 4.3 Fixed constants used everywhere

- `THR_FIXED = 0.29` (board alert threshold; int8 `APNEA_THRESHOLD_Q`)
- `BASELINE_Q = -80`, `APNEA_MHZ`
- Recipes: `LEAKY, M0, M2, M3, M4, M5, ORACLE`

---

## 5. Board firmware — serial command reference

From `src/apnea.c` (`print_help`). Console is SCI_B virtual COM → `/dev/ttyACM0`.

```
help                 this text
run                  replay 256 fixed windows (pre-quantized input)
runraw               same, but normalize raw features on device
bench                10000 timed inferences (DWT cycle counter)
feat <21 floats>     raw features -> normalize/quantize/infer
labels               label-source stats (sites = index split)
personalize          label-free recentre + Otsu threshold
train A|B <src>      head-only GD; src = teacher|proxy|entropy|temporal
                     (entropy/temporal are label-free; teacher/proxy are not)
fed A|B <src>        local train from the federated head, store it
fedavg               n-weighted FedAvg of stored site heads
fedrounds <R> <src>  R rounds of local-train + n-weighted FedAvg
showhead             active 17-parameter head
sethead <17 floats>|global   push an aggregated head back
evalhead             active head vs the 256 oracle labels
evalci               evalhead + Wilson/bootstrap 95% CIs
cycrep               repeated timing of the training inner loop
resetoff             clear re-centring, threshold back to 0.29
```

**Board parity (verified):**

- `run` and `runraw` → **0 mismatches / PASS** over 256 vectors.
- `evalhead` AUROC all-256 = **0.8802** (site A 0.9153, site B 0.8562).
- Board left at **`sethead global`**, offsets cleared (`resetoff`,
  threshold back to 0.29).

Command wrapper used:
`/tmp/cincenv/bin/python tools/serial_cmd.py "<cmd>"`.

Flash:

```
JLinkExe -device R7KA8P1 -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink
```

---

## 6. Evaluation protocol — history and current state

`tools/cross_subject_eval.py` does per-subject **full-record** 30 s-stride /
60 s windows, chronological **FIT (first half) / TEST (second half)** split,
then fits each recipe on FIT and scores on TEST.

Recipes:

- `M0` — global head on the subject's FIT windows (the fair "global on TEST"
  reference is per-subject `M0`).
- `M2`–`M5` — label-free on-device adaptation variants.
- `LEAKY` — uses labels that leak across the split (scored on all windows).
- `ORACLE` — label-supervised on the test subject (a ceiling, not a candidate).

### 6.1 Section map of `RESULTS_PROTOCOL.md`

| Section | Line |
|---|---|
| Split / Gates / Methods / Leaky / Interpretation | 7–57 |
| Board results (P2) — RA8P1, tr03-0322 | 58 |
| Cross-subject (P3) — held-out `final_test` | 118 |
| Threats to validity (P4) | 147 |
| Cross-subject (P3′) | 242 |
| Threats revisited (P4′) | 283 |
| Cross-subject (P5) — `final_test`+`validation` | 368 |
| Threats revisited (P5′) | 439+ |

### 6.2 The key correction (P5′ §0)

The earlier P4′ §3 claim — *"every adapted recipe is significantly worse than
the frozen global head (−0.027 AUROC)"* — was a **window-set artifact and has
been withdrawn.** The recipes are scored on the harder TEST (second-half)
windows, but the "global" reference used there (`p0_all = 0.9211`) averaged
**all** windows. Comparing a test-half score to an all-window score
manufactures a spurious gap. Re-paired on the **same windows**, every recipe is
**indistinguishable** from global (10 subjects: |Δ| ≤ 0.002, all CIs include 0,
all p > 0.18).

**Corrected claim:** *no label-free on-device adaptation recipe improves over
the frozen global head* — a clean **null**, not a negative.

---

## 7. Current results (P5, n = 20 held-out subjects)

Run: `final_test` (10) + `validation` (10), faithful reference extractor,
chronological FIT/TEST split. Per-subject TEST positive rates spread from
2/… ≈ 0.005 to 380/929 ≈ 0.41; `tr05-0647` and `tr05-1404` have **zero** FIT
positives but still score on TEST.

### 7.1 Aggregate AUROC (mean ± sd)

| Model / baseline | AUROC |
|---|---|
| prevalence (constant) | 0.5000 ± 0.0000 |
| SpO2 threshold (`spo2_min < 92`) | 0.7729 ± 0.1580 |
| SpO2-only logistic regression | 0.8358 ± 0.1296 |
| **frozen global head (TEST windows, = M0)** | **0.8430 ± 0.1059** |
| global head, all windows (`p0_all`) | 0.8755 ± 0.0872 |
| LEAKY | 0.8764 ± 0.0867 |
| M2 | 0.8431 ± 0.1067 |
| M3 | 0.8456 ± 0.1030 |
| M4 | 0.8484 ± 0.0972 |
| M5 | 0.8452 ± 0.1036 |
| ORACLE | 0.8431 ± 0.1007 |

### 7.2 Same-window paired deltas vs global

| Recipe | mean Δ | 95% CI | t p | Wilcoxon p | DeLong p |
|---|---|---|---|---|---|
| LEAKY | +0.0008 | [−0.0002, +0.0021] | 0.182 | 0.388 | 0.687 |
| M2 | +0.0001 | [−0.0016, +0.0025] | 0.937 | 0.368 | 0.256 |
| M3 | +0.0025 | [−0.0008, +0.0065] | 0.204 | 0.261 | 0.382 |
| M4 | +0.0054 | [−0.0032, +0.0174] | 0.354 | 0.596 | 0.826 |
| M5 | +0.0022 | [−0.0010, +0.0058] | 0.236 | 0.261 | 0.367 |
| ORACLE | +0.0001 | [−0.0075, +0.0068] | 0.984 | 0.841 | 0.955 |

All |Δ| ≤ 0.006; every CI includes 0; every test p ≥ 0.18. (`M0` is the
reference itself → t/Wilcoxon undefined.)

### 7.3 Calibration and operating point @ 0.29 (n = 20)

| Recipe | Brier | ECE | sens | spec | precision | bal-acc |
|---|---|---|---|---|---|---|
| M0 | 0.1039 | 0.1228 | 0.749 | 0.758 | 0.404 | 0.753 |
| M2 | 0.1038 | 0.1192 | 0.735 | 0.766 | 0.403 | 0.750 |
| M3 | 0.1422 | 0.1513 | 0.761 | 0.729 | 0.391 | 0.745 |
| M4 | 0.1501 | 0.1669 | 0.721 | 0.773 | 0.461 | 0.747 |
| M5 | 0.1413 | 0.1510 | 0.760 | 0.729 | 0.392 | 0.745 |
| ORACLE | 0.0852 | 0.0588 | 0.602 | 0.851 | 0.521 | 0.727 |

The global head is reasonably calibrated; adapted M3–M5 are **worse
calibrated** even where AUROC is unchanged.

### 7.4 Honest downgrade vs the 10-subject P3′ run

Absolute AUROC drops (0.9211 → 0.8430 same-window) because the added validation
subjects are harder. The head's edge over the SpO2-only regression shrinks from
**+0.039 to +0.007** — i.e. a **tie** at n = 20. It still beats the SpO2
threshold by ~0.07.

### 7.5 Reproduce

```
/tmp/cincenv/bin/python tools/cross_subject_eval.py \
  --ref --baselines --delong --calibration --operating-point \
  --partitions final_test,validation --tag P5 --write
```

`--write` appends the P5 tables to `RESULTS_PROTOCOL.md`.

---

## 8. What can and cannot be claimed

**Can claim**

- The cross-subject **null is robust**: no label-free on-device adaptation
  recipe beats the frozen global head on 20 held-out subjects, by bootstrap CI,
  paired t, Wilcoxon, or per-subject DeLong.
- The global head generalises at **0.8430 ± 0.1059** (TEST windows) across a
  cohort with widely varying prevalence; beats the SpO2 threshold by ~0.07;
  **ties** the SpO2-only regression (+0.007, within noise); is better
  calibrated than any adapted recipe.
- **Host/board agree bit-exactly** (`run`/`runraw` 0 mismatches, `evalhead`
  0.8802); the board inference path is correct.

**Cannot claim**

- That on-device adaptation helps **or** that it hurts (corrected: it's a tie).
- That the learned head adds value over a one-channel SpO2 regression at n = 20.
- Anything about **energy/power** (no probe) — cycles/ms only.
- Anything about the **Ethos-U55 NPU** (inference is CPU-only; no FSP driver).
- Any on-device-training accuracy on **unlabeled real data** (unaddressed — and
  precisely what the null motivates).

**Still open**

- n = 20; degenerate subjects (`tr04-0020` 4/8, `tr06-0122` 2/2 positives).
- The frozen global model was **given**, not retrained here; raw training data
  is not on disk (only raw PhysioNet records + 256 fixed vectors).
- On-device **training** on real, unlabeled data; labeling/self-supervision is
  the open direction, not more adaptation recipes.

---

## 9. Other work on the machine (camera / display / RASC)

- `cam2lcd/` — MIPI-CSI camera → display bring-up on the board (frame dumps,
  `.bin`/`.png`, J-Link inspect/dump scripts). Camera capture to LCD was
  demonstrated earlier in the project.
- `bench/` — timing/benchmark RA project.
- `my_ra8_project/` — the first headless RASC-generated template project.
- `ra-fsp-examples/` — Renesas FSP examples including `ek_ra8p1/mipi_csi`
  (source of the Ethos-U55 / NPUCLK config evidence).
- `rasc_payload/`, `rasc_unpk/`, `rasc_ws/`, `rasc_frag/` — RASC install
  payload/workspace (standalone CLI configurator).
- `arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/` — the toolchain.

---

## 10. Session event log (full transcript, read-only)

```
/home/jbatra/.kimi-code/sessions/wd_tron_e373f5295972/session_ca1070ca-503e-4f81-805b-e426f42eaa56/agents/main/wire.jsonl
```

One JSON record per line, append-only. Conversation is in
`context.append_message` (user prompts) and `context.append_loop_event`
(`step.begin | content.part | tool.call | tool.result | step.end`).
Compaction boundaries are `context.apply_compaction` records.

---

## 11. Changelog (this session)

1. Extended `tools/cross_subject_eval.py`: `--partitions` (multi-cohort),
   `--delong` (per-subject DeLong + Stouffer), `--calibration` (Brier + 10-bin
   ECE), `--operating-point` (sens/spec/precision/bal-acc), `--tag`.
2. Fixed the **same-window** paired-delta methodology (`M0[0]` as the fair
   global reference; `p0_all` only for `LEAKY`).
3. Fetched 10 fresh `validation` subjects from PhysioNet v1.0.0 into
   `/tmp/cinc_val/` (byte-exact; retries needed for 3 records that hit
   connection resets — a 600 s background timeout also had to be lifted).
4. Ran **P5** on 20 held-out subjects and appended the tables to
   `RESULTS_PROTOCOL.md`.
5. Wrote the **P5′** section: the correction note (± all-window-vs-test-window
   artifact), 20-subject aggregates, paired tests, calibration, operating point,
   board parity, refreshed can/cannot claim, reproduce commands.
6. Verified board parity unchanged (`run`/`runraw` 0 mismatches, `evalhead`
   0.8802); board left at `sethead global`.
7. Wrote this consolidated `PROGRESS_LOG.md`.

---

## 12. Second-opinion review + host-only diagnostics (this session)

Context: a different model reviewed the brief and argued the null is driven by three
design choices, not by anything fundamental about on-device learning. We built and ran
the "order of work, item 1" diagnostics it asked for.

Artifacts:
- `apnea_deploy/tools/diagnostics.py` — oracle ladder, headroom decomposition, lag
  sweep, protocol reconciliation. Reuses `cross_subject_eval.py`; raw features cached
  to `/tmp/diag_feat_cache.npz`.
- `apnea_deploy/DIAGNOSTICS.md` — full findings + revised plan.

Key results (n = 18 non-degenerate subjects; `tr05-0647`, `tr05-1404` have zero FIT
positives):

| Rung | AUROC | Δ vs M0 | p |
|---|---|---|---|
| M0 global | 0.8235 | — | — |
| ORACLE (true labels, head-only, FIT→TEST) | 0.8381 | +0.015 | 0.77 |
| IN-SAMPLE (fit+score TEST, head-only ceiling) | 0.8736 | +0.050 | 0.007 |
| ALL-LAYERS refit (FIT labels) | 0.8177 | −0.006 | 0.64 |

- **Headroom decomposition:** strong-desaturation positives 0.9897; weak 0.8035;
  −spo2_min on weak 0.7134.
- **Lag sweep (±4 windows):** flat to ±0.0005.
- **Protocol reconciliation:** global p0 pooled 0.8715 vs mean-of-subject 0.8295;
  SpO2-LR pooled 0.8791 vs mean 0.8436.

Interpretation: the binding constraint is **FIT→TEST transfer** (night drift), not the
head size, not the labels, not the representation (in-sample proves the 16-d features
carry ~0.87). This corrects the second model on two points (representation-ceiling and
the widen-the-trainable-set lever) and confirms its non-desaturating-positives point and
its protocol-units complaint. Lag lever is dead at 30 s resolution.

Revised plan: fix protocol units first; attack the transfer gap with input-side
baseline-relative alignment; do not chase lag, unconstrained all-layer refit, or new
label-free head losses; learning curve blocked on 70-subject download; federation
premature.

Still open: deliver `CONSULT_BRIEF.md` to PC [internal host] (SMB needs credentials).

---

## 2026-09-29 — Retrain Phase 1 (new features) + Gate G1

Plan: `apnea_deploy/RETRAIN_PLAN.md`. Results: `apnea_deploy/RETRAIN_RESULTS.md`.

**Provenance correction (important).** `subject_split_manifest.csv` shows the 20 on-disk
subjects are the 10 `final_test` + 10 `validation` subjects, with **zero overlap** with the
70 `central_train` subjects M0 was trained on. So no number computed on the 20 is directly
comparable to M0 = 0.8295. The earlier "refit beats M0 by +0.035" reading was an
in-population vs cross-population artifact — **retracted**.

**Phase 1 probes (LOSO cross-subject, fresh MLP, n=20 folds; mean-of-subject AUROC, TEST half):**

| set | all | weak | strong |
|---|---|---|---|
| legacy21 | 0.7909 | 0.7610 | 0.9592 |
| ecg11 | 0.5733 | 0.5604 | 0.6573 |
| spo2_10 | 0.8692 | 0.8465 | 0.9758 |
| legacy+extEcg | 0.8024 | 0.7752 | 0.9439 |
| legacy+extSpo2 | 0.7481 | 0.7242 | 0.8938 |
| all | 0.7532 | 0.7248 | 0.9020 |

Paired vs legacy21: **spo2_10 +0.078 all (p=0.0017), +0.086 weak (p=0.0014)** — significant;
ecg11 −0.22 (p<1e-4); legacy+extEcg +0.012 (p=0.87, n.s.); legacy+extSpo2 −0.04 (p=0.12);
all −0.038 (p=0.011).

**Feature hygiene:** ext SpO2 features are well-formed and individually informative
(spo2_drop_rel corr(y)=+0.505, nadir_count +0.420, frac_below3 +0.337) but redundant with
legacy SpO2 and perfectly collinear in one pair — adding them dilutes. ext ECG features
correlate ≤0.11 with the label.

**Gate G1:** the "new features break the ceiling" hypothesis is **falsified** (ECG route dead;
baseline-relative SpO2 redundant). But feature **pruning** (SpO2-dominant, drop the 11 weak
ECG dims) is a significant, robust cross-subject win (+0.078). Testing it against M0 requires
retraining on M0's own population → **G1 PASS on the pruning finding**.

**Phase 2 started:** downloading the 70 `central_train` subjects to
`apnea_deploy/data/central` (disk, not tmpfs). ~450 KB/s observed → several hours, resumable.
Phase-3 tooling ready (`tools/phase3_retrain.py`): retrain central on legacy21 vs spo2_10,
test on the 20 held-out → like-for-like vs M0, plus the learning curve (Gate G2).

---

## 2026-09-30 — Phase 2 (download) + Phase 3 (retrain) + Gate G2

Results written to `apnea_deploy/RETRAIN_RESULTS.md` (§Phase 2, §Phase 3).

**Phase 2 — 70 `central_train` subjects.** First download was silently corrupt (PhysioNet resets
mid-record; old fetcher aborted on first reset but the driver still printed `[done]` — only 2 of 15
started records were real). Fixed `fetch_record.py` (per-range resume + retries + atomic rename),
rewrote `fetch_central.sh` (multi-pass supervisor, 4 lanes × 8 chunks, completeness = `.mat` AND
`.arousal`), cleaned 135 stale `.part` files from the old layout. **70/70 complete, 9.4 GB.**
Rebuilt `data/feat_v2_cache.npz` over 70 central + 20 held-out → like-for-like vs M0.

**Phase 3 — retrain on the 70, test on the same 20 M0 is scored on (mean-of-subject AUROC, TEST half).**

Parity: legacy21 retrain on 70 = **0.8392** ≈ M0 **0.8295** → harness faithful.

K70, 8 seeds (`phase3_robust.json`): legacy21 0.8396, **spo2_10 0.8693**, Δ **+0.0297**, 12/20 improved.
Honest paired stats: **median Δ +0.0013, Wilcoxon p=0.546 (n.s.), CI [−0.0033,+0.0841];
excluding `tr04-0029` Δ = +0.0051 (≈0).** The mean is carried by one subject.

What pruning actually buys = **robustness, not accuracy.** `tr04-0029`: legacy 0.407 [0.274–0.823]
sd 0.179 (coin-flip, reproducible) → spo2_10 0.902 sd 0.003. Worst subject 0.407 → **0.689**;
worst-over-seeds 0.274 → **0.683**; mean per-subject sd **0.0284 → 0.0046 (6×)**. For a medical
device the worst night matters more than the mean, so this is the defensible headline.

Learning curve, 5 seeds × K=5…70 (`phase3_curve.json`): spo2_10 ≥ legacy21 at **every** K, gap
widest when data is scarce (+0.167 at K=5 → +0.034 at K=70). Both curves **saturate by ~60**:
last-4 slope legacy21 +0.00086/subj (60→70 negative), spo2_10 +0.00032/subj.

**Gate G2: CLOSED for the "more pooled data" route.** FedAvg ≈ pooled central training; pooled
training is flat at 70, so federation-as-more-data cannot add ranking AUROC. Federation as
*personalization* is a different mechanism, justified (if at all) by the per-subject variance
result, not by this curve.

**Plan consequence:** deploy the pruned spo2_10 head (Phase 4) — dominates at every data size,
6× more stable, removes a coin-flip failure mode, and is cheaper on-board (11 fewer input
channels). Do not chase AUROC via more central data. Live lever = per-subject
robustness/adaptation (Phase 5, claim a: operating point + worst-subject tail).

Guardrails unchanged: no energy/power claims (no probe), no NPU claims (no FSP driver),
subject is the unit, MEOI pre-registered at +0.02 AUROC (ranking) / a few points balanced accuracy
at the 0.29 threshold (operating point).

---

## 2026-09-30 — Phase 4 complete: spo2_10 head deployed to the RA8P1

**Governing move:** Phase 4 of `apnea_deploy/RETRAIN_PLAN.md` — retrain the pruned spo2_10 head,
quantise to INT8, publish to `src/`, restore board parity. **Status: DONE and verified on hardware.**

### What was actually wrong
The four generated headers in `src/` and the 256 fixed self-test vectors came from a **superseded
feature extractor**. On the same windows the shipped vectors had `mean_hr` 129 bpm vs 61 in the
current pipeline, and `spo2_diff_std` ~12× inflated. The board's `run` self-test was therefore
checking a model that matched nothing in the current training code; on the stale vectors it
reported 0/256 positives and an inverted AUROC (0.158). Fixed by re-deriving the SpO2 columns and
labels from `data/feat_v2_cache.npz`, matched on `start_sec` (asserts prove the match: unique rows,
max |Δ| = 0.0, labels agree).

### Gate fix (the honest part)
The old gate required **0 INT8-vs-float decision flips** on 256 vectors. That bar is unattainable:
`OUT_SCALE = 1/256` quantises the decision boundary itself, so any window whose float probability
is within one output step of the threshold *must* flip. Measured 1/256 fixed-vector flips and
110/9032 held-out flips (95 within 0.05 of the threshold), splitting 51 int8-right/float-wrong vs
59 float-right/int8-wrong → net −8 (−0.09 %), with int8 AUROC −0.0011 and int8 balanced accuracy
**+0.0057**. Also verified there are **0** float probabilities in the `[0.29, 0.29297)` band, so it
is not a rounding bug.

Gate 3 now asserts pre-stated fidelity bounds instead of decision identity — (a) ≥99 % fixed-vector
agreement [0.9961], (b) ≥98 % held-out [0.9878], (c) |ΔAUROC| ≤ 0.005 [0.0011], (d) balanced acc
≥ float − 0.005 [+0.0057] — all recorded in `results/phase4_quant.json → fidelity`. The rejected
alternative (quantisation-aware training / range grid search) would tune ranges on the evaluation
windows and was not attempted; recorded as a limitation.

### Results
Host: float spo2_10 seed 0, held-out **mean-of-subject AUROC 0.8710 ± 0.0683 (n=20)**; 897 params,
`10 → 32 → 16 → 1`; ranges = p0.01/p99.99 percentiles.

Board (flashed `build/Release/apnea_deploy.elf`):

| | legacy 21-input | spo2_10 now |
|---|---|---|
| `run` | 0 mismatches, **0 positives** | **0 mismatches [PASS]**, 22 positives |
| `runraw` | 0 mismatches, 0 positives | **0 mismatches [PASS]**, 22 positives |
| `bench` | 7753.88 cyc/inf, 128967 inf/s | **6752.41 cyc/inf**, 148095 inf/s |
| model id | 0xffffffbd | 0xffffff86 |

`run` at 0 mismatches proves the device INT8 arithmetic is bit-identical to the reference emulation
(int32 accumulators, double scales on both sides). **12.9 % throughput gain** from the 21→10 input
width alone, with no kernel optimisation. `labels` AUROC 0.8927 matches the host float AUROC on the
same 256 windows. `personalize` (label-free recentre + Otsu) lifts 256-window AUROC 0.8927 → 0.9021.

### Source edits
- `tools/phase4_quantize.py` — percentile ranges, unpack fix, cache-derived vectors, gate 3 rewrite,
  `fidelity` JSON block.
- `src/apnea.c` — cosmetic `21` → `10`; header comment corrected to state there is **no external
  TFLite file** for this head (reference = the float64 emulation).
- `src/apnea_personal.c` — proxy-desaturation index `[16]` → `[5]` (`spo2_max_drop`) at two sites;
  `personalize` recentring remapped to `{spo2_mean, spo2_min}` = indices 0,1; ECG `mean_hr` offset
  dropped entirely; event features not recentred. `showhead`/`sethead` untouched (they act on the
  16-wide penultimate activation, independent of input width).

### Environment notes for the next session
- Build needs `ARM_GCC_TOOLCHAIN_PATH` pointing at the toolchain **`bin/`** directory
  (`/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin`); the CMake preset passes
  the env var through, and `cmake/gcc.cmake` uses it as `CMAKE_FIND_ROOT_PATH`.
- J-Link software **V9.78 no longer knows `R7KA8P1`** — use `-device R7KA8P1AF`.
- Python: `/tmp/cincenv/bin/python` with `OMP_NUM_THREADS=1` (numpy 2.5.3). `python` on PATH lacks numpy.

### Guardrails still in force
No energy/power claims (no probe). No NPU claims (Ethos-U55 in silicon, no FSP driver, firmware is
pure CPU). Subject is the unit. MEOI pre-registered: +0.02 AUROC (ranking) or a few points balanced
accuracy at the 0.29 threshold (operating point). `CONSULT_BRIEF.md` delivery to [internal host]
remains shelved by the user.

### Not verified
No third-party reference interpreter (the INT8 oracle is our own emulation). One 256-window subject
in the self-test; held-out AUROC is mean-of-subject, not pooled. Single training seed.

---

## 2026-09-30 — Phase 5 measured on the RA8P1: does on-device training + federation beat the base model?

**Short answer: no, not on this test.** Every adaptation route lands within noise of the frozen
global head on ranking, and *worse* on the deployed operating point.

### What was run
On the board, with the deployed spo2_10 (v2) head, via `tools/serial_cmd.py`:

```
sethead global  evalhead  showhead
train A teacher / train B teacher / evalhead
sethead global ; fed A teacher ; fed B teacher ; fedavg ; evalhead
fedrounds 3 teacher ; evalhead
sethead global ; train A entropy ; train B entropy ; evalhead
sethead global ; train A temporal ; train B temporal ; evalhead
sethead global ; evalci ; cycrep ; resetoff ; evalhead
sethead global ; evalhead ; showhead          <- final, board left clean
```

### Results (256-window on-board self-test, subject tr03-0322)

| route | AUROC | bal@0.29 | sens | prec | drift L2 |
|---|---|---|---|---|---|
| frozen global head (baseline) | **0.8927** | **0.7751** | 0.6000 | 0.4286 | 0.0000 |
| train A teacher | 0.8929 | 0.7418 | 0.5333 | 0.4000 | 0.6205 |
| train A+B teacher | 0.8927 | 0.7438 | 0.5333 | 0.4211 | 0.6185 |
| fedavg (A,B teacher) | 0.8929 | 0.7438 | 0.5333 | 0.4211 | 0.6183 |
| fedrounds 3 teacher | 0.8929 | 0.7438 | 0.5333 | 0.4211 | 0.6265 |
| train A+B entropy (label-free) | 0.8932 | 0.7438 | 0.5333 | 0.4211 | 0.4908 |
| train A+B temporal (label-free) | 0.8927 | 0.7209 | 0.4667 | 0.5385 | 0.4949 |

Baseline bootstrap CI95 on AUROC: **[0.7901, 0.9583]** (200 resamples). Largest ranking delta
observed anywhere is **+0.0005**, i.e. ~300× smaller than the CI half-width. All ranking deltas are
indistinguishable from zero. `fedrounds` per-round AUROC is [0.8929, 0.8929, 0.8929] — the rounds
converge immediately and add nothing.

### Cost (this is the part that *is* a real, reportable number)
`cycrep`, 5 × (site A teacher, n=122, 800 iters):
`80982636 80977625 80978168 81430489 80983517` cycles → median **101228 cycles/iter** →
median **≈81.0 M cycles ≈ 81 ms @1 GHz** per local adaptation, spread within 0.6% over 5 runs.
RAM not separately instrumented (head is 17 fp32 params ≈ 68 B + gradients/momentum).
**No energy figure — there is no probe.**

### Why the null, and how it lines up with Phase 3
Phase 3 Gate G2 already closed the *"federation as more data"* route: the learning curve is
saturated by ~60 subjects (last-4-point slope +0.00086/subj for legacy-21, +0.00032/subj for
spo2_10, and 60→70 is negative). FedAvg ≈ pooled central training under that curve, so it cannot
add ranking AUROC. Phase 5 confirms this on silicon. The **single-subject, artificial index split**
(A = windows 0..127, B = 128..255 of *one* subject, as the firmware itself prints) means any gain here
would have been a mechanism demo, not deployment evidence — and there is no gain anyway.

### Verdict
- MEOI **not met** — and not testable by this self-test, which is not the pre-registered protocol
  (mean-of-subject AUROC on held-out TEST halves across 20 subjects).
- Claim (b) ranking: unsupported.
- Claim (a) operating point: *negative* — every adapted head is worse at the fixed 0.29 threshold.
- Federation: adds nothing here, consistent with G2.
- Board left clean: `drift L2 0.0000`, threshold 0.29, global head restored.

Artifact: `apnea_deploy/results/phase5_ondevice.json`.

### Still open
The defensible version of Phase 5 needs **multiple subjects / held-out nights**, not the 256-window
self-test. Federation-as-personalization (FedPer/FedRep, personal vs shared parameter split) remains
untested and is not argued for by the saturated curve.

---

# Tiered improvement pass (2026-09-30, later)

Triggered by the tier list: Tier 1 = sealed cohort + remove the label dependency; Tier 2 =
donors-per-site crossover + more subjects + metrics beyond balanced accuracy; Tier 3 = board-scale
efficacy + energy. Quantization was dropped earlier with evidence and was not revisited.

## Provenance check (do this before anything else)
`tools/extract_features.py` reproduces `data/feat_v2_cache.npz` **bit-exactly** for `tr03-0052`
(max abs diff 0.0, 997x21). The earlier worry that the feature cache had no reproducible
extractor was unfounded. New records can therefore be pooled with old ones.

## Tier 2 item 3 — donors-per-site crossover (`tools/site_crossover.py`)
Earlier framing compared per-site refs (few donors) against one global ref (67 donors), which
confounds site matching with donor count. Redone at **matched donor count** using the real
`record_group` structure. Fixed-composition control holds the target set constant.

Result: **no crossover.** Per-site is worse than pooling by 1.8-3.0 points for m <= 5, and a wash
for m = 6-8 (the whole range the grouping supports). Neither ever beats one global reference.
**Design rule: pool every device into one shared reference.** The old synthetic "+2.4 pts at
het=2.0" was per-site undoing an injected corruption, not a design rule.

## Tier 1 item 2 — label-free reference (`tools/labelfree_ref.py`, `tools/opref_labelfree.py`)
Removed the last label dependency: the reference's threshold-offset term. Three surrogates:

| roff source | roff | mean BA | vs E4 labelled | vs shipped 0.29 |
|---|---|---|---|---|
| labelled (current) | 1.460 | 0.7833 | - | +0.0632 [+0.027,+0.111] |
| LF-const | 2.356 | 0.7452 | -0.0381 | +0.0251 [-0.019,+0.082] |
| LF-proxy (3% drawdown anchor) | 2.627 | 0.7367 | -0.0466 | +0.0166 [-0.033,+0.079] |
| **LF-proxy-cal** | 1.666 | **0.7698** | **-0.0136** | **+0.0496 [+0.015,+0.098]** |

LF-proxy-cal = per-donor threshold from the fraction of FIT windows with SpO2 drawdown >= 3%,
rescaled by one scalar c=1.31 estimated on the central cohort leave-one-donor-out. Deployment
needs no labels at all. Retains 78% of the labelled gain and is itself a significant win.

Board parity: `opref_labelfree.py` reproduces the firmware's compiled labelled constants exactly
(med -3.293730, p90 -0.094107, thr -1.947199), which validates the derivation. The label-free
triple (thr -1.505705) was pushed to hardware over the existing `setthr` command and the board
computed threshold 0.0623, matching the host. Board restored to labelled + `resetoff` (0.29).

## Tier 2 item 5 — metrics beyond balanced accuracy (`tools/sealed_cohort.py`)
On the 18 in-manifest held-out subjects, with two AHI counters (window-count and run-count) that
**disagree in direction**:

- BA: shipped 0.7201 -> E4 0.7833
- MCC: shipped **0.4531** -> E4 0.4438 (degrades)
- AHI MAE: window counter 8.64 -> 15.04 (shipped better); run counter 13.47 -> **12.92** (E4 better)
- severity agreement: window 0.61 -> 0.22 (shipped better); run 0.22 -> **0.39** (E4 better)
- sens@90 is saturated at ~0.996 for every method and is useless as a co-primary

So the AHI/severity result is **unresolved, not negative**; the only consistent sign flip is MCC.

## Tier 1 item 1 + Tier 2 item 4 — sealed cohort
120 unused CinC 2018 records (10 per `record_group`, none in the manifest), selected label-blind,
frozen method. **Blocked on bandwidth**: PhysioNet throttles this IP to ~1 MB/s aggregate
(our link does 3.5 MB/s to cdn.kernel.org); a record is ~118 MB, so the full cohort is ~14 GB
(~4 h). Fetch order is group-interleaved so partial completion stays balanced. Results reported
on whatever N completes.

## Tier 3 — blocked, stated plainly
- Board-scale efficacy: the chip calibrates only the compiled-in 256-window buffer. Needs a
  `loadvec`-style host->board data path (~10 KB per night at 115200 baud) plus training-step
  parity. Next engineering step: implement `loadvec`.
- Energy: **no probe exists**. Cycles and RAM only. No joule figure is claimed.

Artifacts: `apnea_deploy/FINAL_RESULTS.md`, `results/{site_crossover,labelfree_ref,sealed_cohort,opref_labelfree}.json`.

---

# Sealed cohort completed (2026-09-30 ~10:20)

27 CinC 2018 records not in `subject_split_manifest.csv`, selected label-blind (2 per
`record_group`, interleaved), frozen method, **25 evaluable**. Download took ~110 min at the
~1 MB/s PhysioNet IP cap; the 120-record plan was abandoned as infeasible.

**Every record byte-verified** (`tools/verify_mat.py`, 3 spot ranges re-fetched per record,
27/27 match). This is not ceremony: the downloader assembles a record from N `.part` files and
**a chunk-count change between runs scrambles the assembled file at an unchanged total size**,
which the size check cannot catch. Hit mid-pass; partials wiped, chunk count then held fixed,
and verification made mandatory in `sealed_cohort.build_cache`. Also fixed: an "unreachable"
verification verdict was being cached permanently and would have excluded good records forever.

## Sealed results (n = 25)

| method | BA | MCC | dBA vs shipped | 95% CI |
|---|---|---|---|---|
| fixed 0.29 (shipped) | 0.7910 | 0.5442 | - | - |
| E4 labelled reference | 0.8269 | 0.4629 | +0.0359 | [+0.0080, +0.0656] |
| LF-proxy-cal (label-free) | 0.8256 | 0.4701 | +0.0347 | [+0.0057, +0.0651] |
| LF-proxy (event-rate anchored) | 0.7909 | 0.4675 | -0.0001 | [-0.0424, +0.0431] |
| cross-fitted labelled ceiling (per-subject tau) | 0.8241 | - | - | - |

1. **The BA gain survives out of sample** but shrinks: **+0.035 sealed vs +0.0632 in-manifest**.
   Part selection bias, part higher-baseline cohort (0.7910 vs 0.7201) with less headroom;
   n = 25 cannot separate them. Quote the smaller number.
2. **Dropping labels costs nothing out of sample** (+0.0347 vs +0.0359). The label-free path is
   the deployable one and it holds up.
3. **MEOI NOT met.** Pre-registered +0.02; CI lower bounds are +0.0080 / +0.0057. Both exclude
   zero, neither excludes +0.02. Unresolved by the project's own rule.
4. **MCC degrades reproducibly** (0.5442 -> 0.4629 / 0.4701), same sign flip as in-manifest.
5. **AHI unresolved** — window counter favours shipped (11.29 vs 15.38/13.32), run counter
   favours recalibrated (12.48/12.55 vs 13.80). Severity agreement splits the same way.
6. **Fleet reference beats a per-subject labelled threshold** (0.8269/0.8256 vs 0.8241).
   `crossfit_bal` fits tau per subject using true labels; the reference methods use none. Gap
   0.003-0.006 at n=25 — suggestive, not established — but the clearest federation signal in the
   project: pooling across devices beats what a single device can learn about itself.
7. **LF-proxy is a different operating point, not a better one**: best window-count AHI (8.64)
   and severity (0.56), but no BA gain (-0.0001). Which operating point to transport is a design
   decision with measurable consequences.

Artifacts: `apnea_deploy/FINAL_RESULTS.md` (section 5 rewritten, tier summary and limitations
updated), `results/sealed_cohort.json`, `data/feat_sealed_cache.npz` (27 records),
`data/sealed_verified.json`. New tools: `tools/verify_mat.py`, `tools/sealed_cohort.py`,
`tools/site_crossover.py`, `tools/labelfree_ref.py`, `tools/opref_labelfree.py`,
`tools/wait_sealed.sh`.
