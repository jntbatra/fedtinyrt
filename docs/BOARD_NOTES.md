# HANDOFF — apnea / on-device adaptation project (tron)

Directions for a new agent picking up this folder. Read this first, then
`apnea_deploy/FINAL_RESULTS.md` (the authoritative results) and
`PROGRESS_LOG.md` (chronological history, newest entries at the bottom).

---

## 1. What this is

A Renesas RA8P1 (Cortex-M85) port of an apnoea-detection model from CinC 2018
(ECG + SpO2, 60 s windows, 30 s stride). The board ships a **10-feature SpO2-only
INT8 MLP** (`10 -> 32 -> 16 -> 1`, 897 params) and a **label-free per-session
recalibration** mechanism. The research question is whether on-device adaptation
and federation improve it. Answer so far: a modest operating-point gain, plus a
set of honest negatives.

## 2. Layout

| path | what |
|---|---|
| `apnea_deploy/` | the firmware project and all analysis tooling |
| `apnea_deploy/src/` | hand-written C (`apnea.c`, `apnea_personal.c`) + FSP-generated |
| `apnea_deploy/tools/` | Python analysis pipeline (see below) |
| `apnea_deploy/results/*.json` | every number quoted in the docs |
| `apnea_deploy/data/feat_v2_cache.npz` | 90 subjects, `X (n,21)`, `y`, `starts` |
| `apnea_deploy/data/central/` | 70 central_train raw records |
| `apnea_deploy/data/sealed/` + `feat_sealed_cache.npz` | the 27-record sealed cohort |
| `cinc2018_apnea_artifacts/` (parent dir) | original keras models, manifest, `TRAINING_CONTEXT.md` |
| `PROGRESS_LOG.md`, `FINAL_RESULTS.md`, `CONSULT_BRIEF_V2.md` | read these |

Key tools: `final_results.py` (authoritative calibration+federation numbers),
`sealed_cohort.py` (sealed-cohort evaluation + extended metrics),
`labelfree_ref.py`, `site_crossover.py`, `opref_board.py` / `opref_labelfree.py`
(board-space reference constants), `verify_mat.py` (download integrity),
`serial_cmd.py` (talk to the board), `phase4_quantize.py` (trains + emits the
INT8 headers).

## 3. Environment (verified — do not rediscover)

- Python: **`/tmp/cincenv/bin/python`** (numpy 2.5.3, scipy 1.18.1, wfdb 4.3.1,
  pyserial). Plain `python` on PATH has no numpy. Always prefix
  `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.
- Board serial: `/dev/ttyACM0`, SCI_B virtual COM at **115200 8N1**.
- Toolchain: `/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi`.

## 4. Commands that work

```bash
cd /home/jbatra/tron/apnea_deploy

# build (~7 s, exit 0, benign newlib linker warnings only)
export ARM_GCC_TOOLCHAIN_PATH=/home/jbatra/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
cmake --build --preset ReleaseCI
# full clean: rm -rf build/Release && cmake --preset ReleaseCI && cmake --build --preset ReleaseCI

# flash (~2 s, prints O.K.). JLink V9.78 REJECTS -device R7KA8P1 -- use R7KA8P1AF
timeout 180 JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink

# talk to the board (quote multi-word commands as ONE shell arg)
timeout 150 /tmp/cincenv/bin/python tools/serial_cmd.py qstat
timeout 150 /tmp/cincenv/bin/python tools/serial_cmd.py "setthr -3.293730 -0.094107 -1.505705" qstat
```

`flash.jlink` currently contains `h / loadfile build/Release/apnea_deploy.elf / r / g / q`.

## 5. Hard rules — these are not stylistic

1. **Never claim an energy or power number.** There is no current probe. Report
   **cycles and RAM only**.
2. **Never claim the NPU works.** An Ethos-U55 is in silicon but there is no FSP
   driver; the firmware is pure CPU.
3. **Claims (a) and (b) must stay separate.** (a) = the deployed operating point.
   (b) = ranking (AUROC). Never sell a calibration gain as an AUROC gain —
   AUROC is unchanged by everything in this project.
4. **The pre-registered MEOI was +0.02 balanced accuracy. It is NOT met** (sealed
   CI lower bounds +0.0080 / +0.0057). Do not state otherwise.
5. **Do not hand-edit FSP-generated files**: `ra/`, `ra_gen/`, `ra_cfg/`,
   `script/`, `configuration.xml`, `apnea_model.h`, `apnea_selftest_vectors.h`,
   `feature_normalization_{mean,inverse_std}.h`. `src/apnea.c` and
   `src/apnea_personal.c` are hand-written and editable.
6. **Leave the board clean when you finish**: `setthr -3.293730 -0.094107
   -1.947199` then `resetoff` (threshold back to 0.29).
7. Heredocs (`<<'EOF'`) are unreliable for writing files here — use your file-write
   tool.

## 6. Established results (quote these, not older ones)

**On-device calibration, sealed cohort n = 25 (unseen subjects, frozen method):**

| method | BA | MCC | Δ vs shipped | 95% CI |
|---|---|---|---|---|
| fixed 0.29 (shipped) | 0.7910 | 0.5442 | — | — |
| E4 labelled reference | 0.8269 | 0.4629 | +0.0359 | [+0.0080, +0.0656] |
| LF-proxy-cal (label-free) | 0.8256 | 0.4701 | +0.0347 | [+0.0057, +0.0651] |
| cross-fitted labelled ceiling | 0.8241 | — | — | — |

- The in-manifest cohort (n=18) gave **+0.0632**; that number is **~2x inflated**.
  Quote +0.035.
- The label-free version costs nothing out of sample.
- MCC **degrades** reproducibly (0.5442 -> 0.4629/0.4701).
- AHI is **unresolved** — window-count and run-count counters disagree in direction.
- The fleet reference **beats a per-subject threshold fitted with that subject's
  own labels** (0.8269/0.8256 vs 0.8241) — the clearest federation signal, and
  only suggestive at n=25.

**Federation:** pooling donors 1 -> 70 gives +0.0479 BA [CI +0.036,+0.060],
saturating ~20-40 devices. Per-site splitting **never** beats pooling at matched
donor count (`site_crossover.py`). This is pooled *calibration*, not federated
learning — FedAvg of head weights was **null**.

**On-device cost:** 77,429 cycles (~77 µs @1 GHz) and ~2 KB RAM per session;
6,718 cycles (~6.71 µs) per inference. Host<->board parity verified.

**Nulls to keep:** on-device *training* of the model does nothing (purged refit
with true labels doesn't beat frozen). Quantization changes nothing (±0.0002).

## 7. Gotchas that cost real time

- **The shipped model has no ECG.** It is SpO2-only (10 features, columns 11:20).
  `deployment_metadata.json` still says `input_sensors = ["ECG","SaO2"]` — that is
  **stale metadata** for the older 21-feature model. The board header is authoritative.
- **Feature selection used the evaluation subjects.** `results/phase1_loso.json`'s
  `per_subject` list is exactly the 20 held-out subjects that score the final
  number. The in-manifest cohort is not sealed; that is what the sealed cohort fixes.
- **Download integrity:** `fetch_record.py` assembles a record from N `.part`
  files, and **changing the chunk count between runs silently scrambles the file
  at an unchanged total size**. If you ever change `CHUNKS`, wipe `.part*` first,
  and run `tools/verify_mat.py` before using a record.
- **PhysioNet is rate-limited to ~1 MB/s per IP** regardless of connection count
  (our link does 3.5 MB/s elsewhere). A record is 118-152 MB. Budget accordingly;
  27 records took ~110 min.

## 8. Open work

1. **Tier 3 item 6 (blocked, needs firmware).** The chip can only calibrate the
   256 windows compiled into `apnea_selftest_vectors.h`. Implement a `loadvec`
   command to stream a night (~960x10 features; ~10 KB as int8, ~0.9 s at 115200),
   plus a training-step parity check, then re-flash. Note this is host->board
   *replay*; the firmware has no sensor acquisition path.
2. **Tier 3 item 7 (blocked, needs hardware).** No current probe exists. Add an
   inline measurement (Joulescope/Otii, or an INA219-class shunt) and re-run
   `cycrep` under it.
3. **Widen the sealed cohort** (100-200 was the ask; 25 was a bandwidth ceiling).
4. **Settle the AHI question** with real event durations and a clinical scoring
   convention, rather than the window/run proxy.
5. **Try the AHI-anchored operating point** (`LF-proxy`) as the deployment choice:
   it has the best window-count AHI error (8.64) and severity agreement (0.56),
   at the cost of the BA gain.

## 9. How to report

Plain English, answer-first, no emoji. Name every unverified or blocked item
explicitly and never present a partial result as complete. Cite file paths and
key numbers. Report results as-is, including when they come back negative.
