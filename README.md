<h1 align="center">On-device sleep apnea screening</h1>
<p align="center"><b>Adaptive · Privacy-preserving · Runs on a microcontroller</b></p>
<p align="center">
A sleep apnea / hypopnea screener that runs entirely on a Renesas EK-RA8P1
(Arm Cortex-M85 + Ethos-U55 NPU), recalibrates itself to each patient overnight
with no labels, and improves across a fleet while patient data never leaves the device.
</p>

<p align="center">
  <img src="assets/demo.gif" alt="Live apnea dashboard running on the EK-RA8P1 board" width="70%">
</p>

### What you are looking at

The clip above is the model running **live on the real board's 1024×600 LCD**, no PC in the loop.
A full night of physiological data is streamed through the on-device INT8 network in real time, and the dashboard shows:

- **The verdict** — a large **APNEA** (red) / **NORMAL** (green) tile that flips as each window is scored.
- **The live input features** — the 10 SpO₂-derived values (green) feeding the model, refreshed every 0.5 s.
- **Balanced accuracy — 82.6 %** — the measured sealed-cohort score, shown on-device.
- **Real-time INT8 inference on the Cortex-M85**, every window, on real silicon.

> **Research prototype, not a clinical device.** No medical claims. Every headline number below is measured, and the open questions are stated plainly.

---

## Highlights

| | Result |
|---|---|
| **On-device adaptation** | **+0.035** balanced accuracy on unseen patients (0.791 → 0.826), 95% CI [+0.006, +0.065], **label-free** |
| **Federation** | **+0.048** balanced accuracy pooling 1→70 devices; only calibration statistics leave the device, never data |
| **Speed (measured)** | CPU **6.75 µs** / inference · **NPU (Ethos-U55) 3.87 µs**, **1.74× faster**, decisions identical |
| **Footprint** | 10→32→16→1 INT8 MLP, **897 params**, **~2 KB** RAM, bit-exact vs host |

Authoritative results and methodology: [`docs/RESULTS.md`](docs/RESULTS.md) · NPU on hardware: [`final_npu_results.md`](final_npu_results.md).

---

## Quickstart — run it yourself (no hardware needed)

The full training → INT8 export → verification → federation pipeline runs end to end on a
**synthetic fixture**, on any OS, CPU-only. This exercises the real software; it does **not**
reproduce the clinical numbers (those need the CinC 2018 dataset — see *Reproducing the results* below).

```bash
# 1. clone
git clone https://github.com/jntbatra/fedtinyrt.git
cd fedtinyrt

# 2. create an environment and install deps
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -r ml/sleep/requirements.txt

# 3. generate the synthetic fixture
python -m ml.sleep.synthesize

# 4. train + export the INT8 model
python -m ml.sleep.train_tflite --data ml/sleep/data/synthetic.npz --epochs 2 --allow-synthetic

# 5. verify the INT8 golden vectors match
python -m ml.sleep.verify

# 6. run a federation round
python -m ml.sleep.federate --data ml/sleep/data/synthetic.npz --rounds 1 --allow-synthetic

# 7. (optional) run the test suite
python -m pytest -q tests/test_sleep_ml.py
```

Artifacts (model, scaler, INT8 arrays, golden vectors, metrics, federation weights) land in
`ml/sleep/artifacts/`. Every model records whether it was trained on synthetic data.

> The synthetic labels and waveforms are invented — their metrics are a software check only,
> never a sleep-apnea performance claim.

---

## Run on the board (needs the hardware)

The live dashboard in the GIF is firmware for the **Renesas EK-RA8P1**. Sources, build and flash
steps are in [`firmware/apnea_dashboard/`](firmware/apnea_dashboard/README.md). In short:

```bash
export ARM_GCC_TOOLCHAIN_PATH=/path/to/arm-gnu-toolchain/bin
cmake --preset ReleaseCI && cmake --build --preset ReleaseCI
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash_dash.jlink
```

On reset the board free-runs the dashboard on its own. To stream a recorded night over serial:

```bash
python3 firmware/apnea_dashboard/live_demo.py --board --loop --subject tr03-0413
```

---

## How it works

```
 SpO2 signal ─▶ 60 s window features ─▶ INT8 MLP (Cortex-M85 / Ethos-U55) ─▶ APNEA / NORMAL
                                              │
                 ┌────────────────────────────┴───────────────────────────┐
                 ▼                                                          ▼
   per-session recalibration (on device, label-free)     fleet federation (calibration stats only)
```

- **On-device inference** — the INT8 model runs on the Cortex-M85; the same network also runs on the Ethos-U55 NPU (1.74× faster, measured).
- **Label-free recalibration** — each session recentres its own decision threshold from its unlabelled data. This is the +0.035 gain.
- **Federation** — devices pool calibration statistics into a shared reference; no patient data leaves any device.

---

## Reproducing the clinical results

The headline numbers (+0.035, +0.048, and the NPU measurement) come from the CinC 2018 SpO₂ pipeline
and the on-board Ethos-U55 integration, documented step by step in:

- [`docs/RESULTS.md`](docs/RESULTS.md) — sealed-cohort calibration + federation, with confidence intervals.
- [`final_npu_results.md`](final_npu_results.md) — the measured NPU results and full reproduction recipe.
- [`docs/NPU_VELA.md`](docs/NPU_VELA.md) — the Vela compilation report.
- [`docs/ENGINEERING_LOG.md`](docs/ENGINEERING_LOG.md) — chronological record.

These require the PhysioNet CinC 2018 data (not committed — patient data never lives in this repo).

---

## Repository layout

| path | what |
|---|---|
| `firmware/apnea_dashboard/` | on-board LCD dashboard firmware + build/flash + host driver |
| `ml/sleep/` | runnable training / INT8 export / federation pipeline (synthetic-fixture reproducible) |
| `docs/` | results, NPU report, engineering log, board notes |
| `final_npu_results.md` | measured Ethos-U55 NPU results |
| `assets/` | demo GIF / MP4 |
| `src/`, `ra/`, `ra_gen/`, `ra_cfg/`, `script/` | RA8P1 / FSP firmware project |
| `tests/` | host C + Python checks |

---

## Honest scope

- Validated on **25 sealed patients** (target 100–200). The gain's CI lower bound (+0.0057) does not yet clear the pre-registered +0.02 minimum effect — promising, needs a wider cohort.
- **AUROC (ranking) is unchanged** — the gain is at the decision threshold.
- The apnea-hour index is a **window-count proxy**; event-scored AHI is future work.
- **No energy figure** — there is no current probe; only cycles and RAM are reported.
- The NPU currently runs a **re-quantised twin** of the deployed model (same weights, different INT8 scheme); parity is checked against the TFLite reference.
- The **sensor front-end is not wired** — the board runs recorded data; live capture is future work.

These are the roadmap, not failures. Each one builds on something already demonstrated.
