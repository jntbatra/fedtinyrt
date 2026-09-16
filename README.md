# FedTinyRT Sleep

FedTinyRT is being adapted in place from the bearing/FoG proof of concept to
adaptive, personalized sleep-event screening on EK-RA8P1 with µT-Kernel 3.0.
The existing FSP boot, small-network training, INT8 export, golden vectors and
PC federation workflow remain the foundation.

**Current validation uses synthetic fixtures. No real sleep performance or
hardware completion is claimed.** The supplied [development brief](context.md)
defines the target; this README describes current implementation status.

## What changed

| Area | Current state |
| --- | --- |
| Bearing experiments | Preserved in `ml/legacy_bearing/`, including original artifacts and results |
| Existing README edits | Exact pre-migration copy in `docs/legacy/README.pre-sleep.md` |
| Firmware boot | Generated startup and `hal_entry.cpp` retained |
| µT-Kernel application | Separate acquisition and processing tasks with static stacks |
| Sleep controller | Bounded queue, timestamps, quality checks, stable-period baseline, LOW/HIGH/event/recovery/fault states |
| Events and summary | Debounce, duration/oxygen drop, valid/missing monitoring time and research triage |
| PC sleep ML | 18 sleep-summary features, binary MLP, subject partitions, INT8, masks and modality dropout |
| PC federation | Checked sample-weighted FedAvg, disjoint sites/subjects, local/global/personalized evaluation |
| Tests | Host C checks, Python checks, actual PC INT8 golden-vector replay |
| Real acquisition / board ML | Pending; replay uses **scripted synthetic scores**, model version `NONE` |
| NPU / M33 / Ethernet | Pending |

The application entry point compiles for Cortex-M85 against the initialized
µT-Kernel headers. A full e2 studio link, board boot and timing measurements have
not been performed. See [validation notes](docs/VALIDATION.md).

## Run software tests

Use Python 3.13 and [ml/sleep/requirements.txt](ml/sleep/requirements.txt).
With a project-local virtual environment, run from the repository root:

```powershell
.venv/Scripts/python.exe -m ml.sleep.synthesize
.venv/Scripts/python.exe -m ml.sleep.train_tflite --data ml/sleep/data/synthetic.npz --epochs 2 --allow-synthetic
.venv/Scripts/python.exe -m ml.sleep.verify
.venv/Scripts/python.exe -m ml.sleep.federate --data ml/sleep/data/synthetic.npz --rounds 1 --allow-synthetic
.venv/Scripts/python.exe -m pytest -q tests/test_sleep_ml.py --basetemp .cache/pytest-sleep
.venv/Scripts/python.exe tests/host/run.py --cc .venv/Lib/site-packages/ziglang/zig.exe --check-arm-entry
```

Zig is an optional host compiler (`uv pip install ziglang==0.16.0`); firmware
development still uses the existing e2 studio project. All generated datasets,
models, environments and caches are ignored. Synthetic metrics establish software
execution only. [ML instructions and real-data contract](ml/sleep/README.md).

## Board replay

Initialize existing dependencies with `git submodule update --init --recursive`.
Open the existing project in e2 studio, select Debug and follow
[SETUP_NOTES.md](SETUP_NOTES.md) for FSP 6.5.0 / Arm GCC setup.
Use `Project Debug_Flat` for CPU0 and serial at 115200 baud, 8N1.

The banner states `SYNTHETIC replay, scripted scores, model=NONE`. The 100-second
fixture calibrates, triggers an event, recovers, demonstrates missing SpO2 and
prints a session summary. No trained model or physical sensor produces these
scores. [DEMO.md](DEMO.md) gives expected behavior.

Queue copies use short task-dispatch critical sections; this is not an ISR-safe
or multicore queue. Acquisition performs no ML, networking or console output.
The new tasks still require full board validation.

## Repository map

```text
src/usermain.c          existing entry point, now starts sleep replay tasks
src/sleep/             portable controller, data contracts and labelled replay
ml/sleep/              adapted PC training/export/federation pipeline
ml/legacy_bearing/     preserved historical scripts, artifacts and results
ml/data/               existing ignored bearing downloads (location retained)
tests/                 Python checks and host C acceptance harness
docs/legacy/           archived FoG plans and pre-migration README
ra/, ra_cfg/, ra_gen/  existing FSP/CMSIS/board configuration
mtk3_bsp2/             existing pinned µT-Kernel submodule
```

The `pre-sleep-pivot` tag preserves the original committed baseline. Your
uncommitted README is separately archived. Legacy commands now use
`ml/legacy_bearing/`; raw-data paths still point to `ml/data/`.

## Next integration gate

Review a real dataset's modality/subject/label mapping, replace the synthetic NPZ,
then implement matching waveform preprocessing and CPU INT8 inference on one
board window. Verify PC/board golden parity and measure latency/RAM before real
sensor, NPU and M33 integration.

[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md), [KANBAN.md](KANBAN.md) and
[RFC-001-systems-contract.md](RFC-001-systems-contract.md) describe this migration.
`scripts/create-issues.sh` remains the historical FoG issue helper; review/update
it before using its remote actions for the sleep backlog.
