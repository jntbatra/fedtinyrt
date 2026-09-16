# FedTinyRT

FedTinyRT is an experimental edge-AI and federated-learning project for the Renesas EK-RA8P1 board, built for the TRON Programming Contest 2026. The repository combines:

1. a minimal Renesas FSP firmware that boots µT-Kernel 3.0 on the board's Cortex-M85 core; and
2. a PC-side Python proof of concept for vibration feature extraction, INT8 model export, cross-machine personalization, and federated averaging.

> **Current-state warning:** this repository is not yet an end-to-end embedded product. The firmware currently starts µT-Kernel and prints `FedTinyRT starting...`; it does not yet collect sensor data, run the checked-in model, use the NPU, train on-device, or exchange weights. The Python experiments currently classify **bearing health/faults** using NASA IMS and CWRU data. The design documents describe a planned **Parkinson's Freezing-of-Gait (FoG)** system. Those are related architectural goals, but they are not the same implemented application.

This is a research/contest prototype, not a validated medical device, and it makes no clinical claim.

## Contents

- [What is implemented](#what-is-implemented)
- [System architecture](#system-architecture)
- [Firmware execution flow](#firmware-execution-flow)
- [ML pipeline](#ml-pipeline)
- [Federated-learning experiments](#federated-learning-experiments)
- [Repository layout](#repository-layout)
- [Getting started: firmware](#getting-started-firmware)
- [Getting started: ML](#getting-started-ml)
- [Generated and ignored files](#generated-and-ignored-files)
- [Known gaps and inconsistencies](#known-gaps-and-inconsistencies)
- [Additional documentation](#additional-documentation)

## What is implemented

| Area | State in this checkout | Evidence |
|---|---|---|
| EK-RA8P1/FSP project | Implemented/configured | `.project`, `.cproject`, `configuration.xml`, `ra/`, `ra_cfg/`, `ra_gen/` |
| µT-Kernel boot | Implemented; historical hardware success is recorded | `src/hal_entry.cpp`, `src/usermain.c`, `SETUP_NOTES.md` |
| Console banner | Implemented | `src/usermain.c` |
| Python feature extraction | Implemented | `ml/feature_extract.py` |
| NASA IMS dataset preparation | Implemented | `ml/prep_ims.py`, `ml/build_xmachine.py`, `ml/relabel.py` |
| MLP training and full-INT8 TFLite export | Implemented | `ml/train_tflite.py` |
| Golden inference vectors and C model array | Checked in | `ml/artifacts/` |
| Cross-machine evaluation/personalization | Implemented as PC simulation | `ml/xmachine_*.py`, `ml/personalize.py` |
| FedAvg | Implemented as PC simulation | `ml/federate.py`, `ml/federate_cwru.py` |
| Sensor driver/sampling task | Not implemented in firmware | no driver instance or task exists in `src/` |
| Firmware feature extraction | Not implemented | Python reference only |
| TFLite Micro/CMSIS-NN/Ethos-U55 inference | Not integrated | model C files are not referenced by firmware |
| M33 application/on-device training | Not implemented | the project targets `_RA_CORE=CPU0`; no core-1 application exists |
| Ethernet/UART weight transport | Not implemented | pins exist, but no driver stack or application code exists |
| Complete FoG pipeline | Design target only | described in `SYSTEM_OVERVIEW.md`, `context.md`, and the RFC |

The status table above describes the code, not merely the roadmap. Historical measurements in `ml/RESULTS.md` and bring-up claims in `SETUP_NOTES.md` were not rerun as part of a source checkout.

## System architecture

### Implemented today

```text
EK-RA8P1 firmware
Reset/FSP startup
       |
       v
generated main() -> hal_entry() -> knl_start_mtkernel()
                                      |
                                      v
                                  usermain()
                                      |
                    print "FedTinyRT starting..."
                                      |
                               sleep forever

PC-side ML (separate from firmware)
NASA IMS or CWRU vibration files
       |
       v
2048-sample windows -> 38 handcrafted features -> normalization
       |
       v
small dense neural network -> evaluation / INT8 export / FedAvg simulation
```

There is currently no code path connecting the generated model artifacts to the firmware.

### Intended final system

The design documents propose an offline-first hospital node that receives accelerometer samples, performs real-time FoG screening, learns a small model head locally, and exchanges only model weights with a PC aggregator. The intended division is:

- Cortex-M85: sampling and time-critical inference;
- Ethos-U55 NPU: INT8 neural-network inference;
- Cortex-M33: lower-priority head training and network/privacy duties;
- PC aggregator: synchronous FedAvg across simulated or physical hospital nodes.

This architecture is a target. Dual-core execution, NPU execution, acquisition, and networking are not present in the current application sources.

## Hardware and build configuration

The checked-in FSP metadata targets:

| Item | Configuration found in the repository |
|---|---|
| Board | Renesas EK-RA8P1 |
| MCU | `R7KA8P1KFLCAC`, 289-pin LFBGA |
| Selected application core | CPU0 / Cortex-M85 (`_RA_CORE=CPU0`) |
| Device-reported cores | 2 |
| ROM | 1,048,576 bytes |
| Configured RAM size | 1,916,928 bytes |
| FSP | 6.5.0 |
| CMSIS | 6.1.0 + FSP 6.5.0 |
| TrustZone build | Flat/non-TrustZone (`BSP_TZ_SECURE_BUILD=0`) |
| FSP RTOS selection | Bare metal (`BSP_CFG_RTOS=0`); µT-Kernel is integrated manually |
| CPU clock | 1 GHz from PLL1P |
| CPU1 clock | 250 MHz |
| NPU clock | 500 MHz |
| C/C++ modes | C99 and C++17 |
| Build profiles | Debug and Release |
| Debug target | `R7KA8P1KF_CPU0`, J-Link over SWD at 4 MHz |

The generated pin table contains board-level mappings for OSPI, external bus/SDRAM, LCD, RGMII Ethernet, IIC, SSI, USB, PDM, SCI, debug, and other signals. A pin mapping is not the same as an initialized application peripheral: the only generated FSP driver instance is `r_ioport`, and the interrupt table has zero allocated application IRQs.

The FSP configuration currently disables automatic SDRAM and OSPI startup (`BSP_CFG_SDRAM_ENABLED=0`, `BSP_CFG_OSPI_B_STARTUP_ENABLED=0`). The FSP heap is also configured as zero bytes. These details matter when future model buffers and runtimes are added.

## Firmware execution flow

### 1. Renesas startup and generated `main`

FSP/CMSIS startup code performs reset and runtime initialization. `R_BSP_WarmStart()` receives lifecycle events. At `BSP_WARM_START_POST_C`, it opens the I/O-port instance and applies the generated board pin configuration. SDRAM initialization would also happen there if enabled.

`ra_gen/main.c` then calls `hal_entry()`.

### 2. `hal_entry()` starts µT-Kernel

`src/hal_entry.cpp` declares the C-linkage function `knl_start_mtkernel()` and calls it immediately. The remaining branches are the FSP template logic for multicore startup and TrustZone transitions. In the current flat CPU0 configuration, those conditional branches are not active.

### 3. µT-Kernel calls `usermain()`

`src/usermain.c` is the user entry point reached after kernel startup. It:

1. writes `FedTinyRT starting...` with T-Monitor's `tm_putstring()`; and
2. sleeps forever with `tk_slp_tsk(TMO_FEVR)`.

No user tasks, queues, semaphores, sensor loops, or ML calls have been added yet.

Expected historical serial output from `SETUP_NOTES.md`:

```text
microT-Kernel Version 3.00
FedTinyRT starting...
```

The documented terminal setting is 115200 baud, 8N1. A blank LCD is expected because no LCD application/driver is initialized.

## ML pipeline

The `ml/` directory is an independent PC workflow. It provides the algorithmic proof of concept and artifacts intended for later firmware integration.

### Feature definition

`ml/feature_extract.py` is the reference implementation. Each one-dimensional vibration signal is divided into 2,048-sample windows. The default hop is also 2,048, so windows do not overlap unless a caller supplies another hop.

Each window becomes 38 `float32` features:

- 32 spectral features: Hann-windowed real FFT, DC removed, remaining magnitude bins split into 32 contiguous groups, with the mean magnitude of each group;
- 6 time-domain features: RMS, absolute peak, standard deviation, crest factor, kurtosis, and skewness.

The firmware must reproduce these operations and ordering exactly before the checked-in model can be used. Feature index 32 is RMS.

### Dataset path A: same-run NASA IMS experiment

`ml/prep_ims.py` searches below `ml/data/` for timestamp-named NASA IMS files, uses bearing channel 0, and assigns labels from chronological position in the run-to-failure sequence:

- `normal`: first 70%;
- `degrading`: 70% to 90%;
- `fault`: final 10%.

Every source file receives a group ID. The trainer uses that group to keep sibling windows from the same source file together during the train/test split. Output is ignored file `ml/artifacts/dataset.npz`, containing `X`, `y`, `groups`, and `classes`.

Important nuance: the module's opening prose still mentions RMS-derived labeling, but the implementation uses time-based labels. The implementation is authoritative.

### Dataset path B: cross-machine NASA IMS experiment

`ml/build_xmachine.py` builds two independent datasets:

- machine A: IMS `2nd_test`, fixed channel 0;
- machine B: IMS `3rd_test`, automatically selecting the channel with the largest end/start RMS ratio.

It drops non-finite or near-zero files, estimates a healthy baseline from the first 20% of files, and labels degradation/fault using RMS thresholds. Labels are forced to be monotonic because the script assumes accumulated bearing damage does not heal. Outputs are ignored files `machine_A.npz` and `machine_B.npz`.

`ml/relabel.py` rewrites those two files using relative per-machine thresholds (`max(1.2 × baseline, baseline + 3σ)` for degradation and `1.5 × baseline` for fault). This script executes immediately when run or imported; it has no `if __name__ == "__main__"` guard.

### Model training and export

`ml/train_tflite.py` expects `dataset.npz` and performs a grouped 80/20 split with seed 42. It learns mean/std normalization from training data only, then trains this Keras model:

```text
38 inputs -> Dense(32, ReLU) -> Dense(16, ReLU) -> Dense(3 logits)
```

Training uses Adam, sparse categorical cross-entropy, 60 epochs, batch size 64, the held-out test partition as Keras validation data, and inverse-frequency class weights. It reports ordinary and balanced accuracy, then exports a fully integer-quantized TFLite model using up to 300 representative training rows. Because the test partition is also observed as validation telemetry during training, use a separate validation group if future work uses those metrics for model selection or early stopping.

The converter intentionally goes through SavedModel because the comments record a TensorFlow 2.16/Keras 3 failure in the direct `from_keras_model()` INT8 path.

Generated outputs are:

| Artifact | Purpose | Tracked? |
|---|---|---|
| `dataset.npz` | same-run features, labels, and file groups | No |
| `scaler.npz` | training feature mean and standard deviation | No |
| `saved_model/` | temporary SavedModel conversion input | No |
| `model_int8.tflite` | full-INT8 model for TFLite/Vela | No |
| `golden_vectors.json` | quantization parameters plus 20 expected input/output cases | Yes |
| `model_data.c/.h` | 4,248-byte TFLite model and scaler arrays as C constants | Yes |

The tracked golden-vector metadata currently declares three classes (`normal`, `degrading`, `fault`), input scale `0.02717874012887478`, input zero point `-64`, output scale `0.19168317317962646`, and output zero point `46`.

### Baselines, checks, and cross-machine scripts

- `ml/lazy_compare.py` runs LazyPredict on the grouped same-run split and writes `lazy_ranking.csv`. Classical models are used as a performance ceiling; they are not firmware deployment candidates.
- `ml/verify.py` checks group disjointness and compares RMS behavior across the three time-based labels.
- `ml/xmachine_train.py` trains on machine A with machine-A scaling and evaluates both held-out A data and all of unseen machine B.
- `ml/xmachine_norm.py` normalizes each machine from its own first-20% healthy baseline before performing the same transfer test.
- `ml/personalize.py` pretrains on all of A, splits B by source-file groups into 30% adaptation and 70% test, then fine-tunes the same model on B at a lower learning rate.

The "on-device" wording in these Python files describes the intended deployment analogue. The scripts themselves run on a PC with TensorFlow; they do not execute training on either RA8P1 core.

## Federated-learning experiments

### IMS two-node simulation

`ml/federate.py` treats machine A and machine B as two nodes. Each round resets a local model to the current global weights, trains locally, and sends only Keras weight arrays to the in-process aggregator. It uses equal client weighting, averages corresponding tensors, and applies a damped server update with default factor 0.7. It compares:

- local-only training;
- the shared federated model; and
- the federated model followed by local fine-tuning.

It includes a deliberately difficult scenario where B has no fault examples in its local training set. This is a simulator: there is no serialization format, network protocol, authentication, privacy mechanism, or board transport implementation yet.

### CWRU four-client simulation

`ml/federate_cwru.py` treats four motor-load/RPM folders as four clients. It classifies `normal`, `inner`, `outer`, and `ball`, caps each file at 40 windows, and uses a 38→32→16→4 MLP. It runs 25 FedAvg rounds with five local epochs by default and compares data-rich clients with clients limited to 32 training windows.

Unlike the NASA scripts' group-held-out evaluation, its `per_file_split()` divides earlier and later windows within each source file. That keeps each class in both splits, but related windows from one recording exist on both sides; treat its reported numbers as a mechanism demonstration rather than a strict cross-recording generalization estimate.

### Recorded results

`ml/RESULTS.md` records prior runs, including approximately 96.6% balanced same-machine accuracy for the three-class IMS model, weak zero-shot cross-machine transfer, improvement after local personalization, and gains from CWRU federation in the data-scarce scenario. These results are historical outputs, not automated tests, and several generated datasets/models needed to reproduce them are intentionally not committed.

## Repository layout

```text
.
├── src/                         Handwritten embedded entry points
│   ├── hal_entry.cpp            Starts µT-Kernel from the FSP entry point
│   ├── usermain.c               Prints the banner and sleeps forever
│   └── hal_warmstart.c          Applies pin setup during FSP warm start
├── mtk3_bsp2/                   µT-Kernel BSP2 git submodule
├── ra/                          Vendored/generated FSP, CMSIS, and board support
├── ra_cfg/                      Generated FSP configuration headers
├── ra_gen/                      Generated initialization, pins, clocks, vectors
├── script/fsp.ld                Includes generated FSP linker fragments
├── ml/                          PC feature/training/federation experiments
│   └── artifacts/               Selected reproducibility/deployment outputs
├── scripts/create-issues.sh     One-time GitHub issue/milestone population script
├── configuration.xml            Source of truth for the e2 studio FSP configurator
├── .project / .cproject         Eclipse/e2 studio project and build settings
├── Project Debug_Flat.launch    J-Link CPU0 debug launch configuration
├── Project Debug_Flat.jlink     J-Link settings
├── SYSTEM_OVERVIEW.md           Intended FoG system, assumptions, and limitations
├── context.md                   Vocabulary, state definitions, and decisions
├── RFC-001-systems-contract.md  Proposed budgets, invariants, and failure handling
├── KANBAN.md                    Planned HIL vertical slices
├── GETTING_STARTED.md           Team workflow/onboarding document
├── SETUP_NOTES.md               Historical board bring-up steps and result
└── CLAUDE.md                    Project-specific contributor/agent conventions
```

### What the generated directories contain

- `ra/`: the subset of Renesas FSP 6.5.0 and CMSIS needed by the generated project, including RA8P1 startup, clock, BSP, IPC, security, I/O, SDRAM/OSPI support, and board definitions.
- `ra_cfg/`: compile-time device, board, TrustZone, memory, option-byte, and I/O-port configuration headers.
- `ra_gen/`: code emitted from `configuration.xml`: generated `main`, HAL/common data, clock definitions, pin table, and the currently empty interrupt mapping.
- `mtk3_bsp2/`: µT-Kernel BSP2 and its nested kernel dependency. In this checkout it is uninitialized (shown by a leading `-` in `git submodule status`), so initialize it before building.

Do not hand-edit `ra_cfg/` or `ra_gen/`; make FSP changes through `configuration.xml` in e2 studio and regenerate project content. Treat `ra/` as tool-generated/vendor code unless deliberately updating FSP.

## Getting started: firmware

### Prerequisites

- Renesas e2 studio with FSP 6.5.0 support;
- GNU Arm Embedded toolchain 13.3.1 or another compatible GCC 12+ toolchain with Cortex-M85 support;
- EK-RA8P1 board;
- onboard/external J-Link connection and USB cable;
- serial terminal such as Tera Term.

### Clone and initialize submodules

```bash
git clone --recursive https://github.com/jntbatra/fedtinyrt.git
cd fedtinyrt
git submodule update --init --recursive
```

The recursive form is important because `mtk3_bsp2` may itself depend on the µT-Kernel source as a nested submodule.

### Import, generate, and build

1. In e2 studio, choose **File → Open Projects from File System**.
2. Select the repository root. The Eclipse project name is `Project`.
3. Open `configuration.xml` and generate project content if e2 studio reports stale/missing generated files.
4. Select the **Debug** configuration.
5. Build with **Project → Build Project** or `Ctrl+B`.

The Debug build includes the µT-Kernel directories, defines `_RAFSP_EK_RA8P1_`, targets CPU0, and adds `mtk3_bsp2/etc/linker/mtkernel.ld` alongside the FSP linker script. The Release profile exists, but its checked-in settings do not mirror all µT-Kernel include/define/source configuration visible in Debug; verify Release before relying on it.

If the compiler rejects `cortex-m85`/`nopacbti`, select a newer registered Arm GNU toolchain in **Help → Renesas Toolchain Management**.

### Flash and run

1. Connect the EK-RA8P1.
2. Launch `Project Debug_Flat` from **Run → Debug Configurations**.
3. Resume after the initial halt.
4. Open the board's serial COM port at **115200 baud, 8N1**.

The launch file targets CPU0 through J-Link/SWD. No second-core debugger is enabled.

## Getting started: ML

There is currently no pinned `requirements.txt` or lock file. The scripts import:

- NumPy;
- SciPy (listed by the ML notes, although the present feature extractor uses NumPy FFT);
- scikit-learn;
- TensorFlow/Keras;
- LazyPredict for the optional baseline comparison.

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install tensorflow numpy scipy scikit-learn lazypredict
```

Place datasets below ignored `ml/data/`. The scripts expect these effective locations:

```text
ml/data/<extracted IMS tree>                         # prep_ims.py searches recursively
ml/data/extracted/2nd_test/<timestamp files>        # build_xmachine.py
ml/data/extracted/3rd_test/<timestamp files>        # build_xmachine.py
ml/data/cwru/Data/*RPM/*.npz                        # federate_cwru.py
```

### Same-run training/export workflow

```powershell
py ml/prep_ims.py
py ml/verify.py
py ml/lazy_compare.py       # optional and comparatively slow
py ml/train_tflite.py
```

### Cross-machine and personalization workflow

```powershell
py ml/build_xmachine.py
py ml/relabel.py
py ml/xmachine_train.py
py ml/xmachine_norm.py
py ml/personalize.py
py ml/federate.py
```

### CWRU federation workflow

Prepare the RPM-folder `.npz` inputs expected by `federate_cwru.py`, then run:

```powershell
py ml/federate_cwru.py
```

There is no automated downloader or dependency installer in the repository. Raw datasets are intentionally excluded from Git.

## Generated and ignored files

The `.gitignore` excludes:

- e2 studio `Debug/`, settings, launch-output, object, dependency, ELF, S-record, HEX, and map files;
- J-Link logs;
- all `ml/data/` content;
- generated ML `.npz` and `.tflite` files and SavedModel directories;
- Python bytecode caches.

Consequences for a fresh clone:

- the board firmware cannot build until the µT-Kernel submodule is initialized;
- ML experiments cannot be fully rerun until datasets are supplied;
- `model_data.c` and golden vectors are available, but the original `model_int8.tflite`, scaler `.npz`, and training arrays are not tracked;
- the C model artifact is not currently copied into or compiled by the firmware application.

Never commit raw patient/sensor data. For this repository's current public-dataset experiments, keep all downloaded data under `ml/data/`.

## Known gaps and inconsistencies

These are the most important facts for anyone continuing development:

1. **Application mismatch:** top-level design documents target FoG detection, while all executable ML scripts and artifacts target bearing-fault classification.
2. **Firmware/ML disconnect:** `ml/artifacts/model_data.c` is not referenced or built by `src/`; no inference runtime is present.
3. **Single-core firmware:** only CPU0 is configured. The intended M33 training/privacy role has no project or binary.
4. **No acquisition or transport:** pin mappings exist, but there are no configured I2C, Ethernet, or application UART driver instances and no corresponding tasks.
5. **No NPU toolchain integration:** no Vela command, compiled Ethos-U command stream, or inference invocation is checked in.
6. **Missing reproducibility lock:** Python dependency versions, dataset checksums, exact dataset conversion instructions, and random determinism beyond selected seeds are not pinned.
7. **Metric mismatch:** the FoG design requires AUPRC plus sensitivity/specificity, while the bearing scripts primarily report accuracy and balanced accuracy.
8. **Artifact mismatch:** the tracked model is a 3-class bearing model, not the intended binary FoG CNN.
9. **Configuration vs use:** many board pins are configured, but this does not mean their peripherals are initialized or used.
10. **Release-build uncertainty:** Debug visibly carries the µT-Kernel integration; Release should be audited and tested before use.
11. **No automated test suite/CI:** verification consists of runnable research scripts and historically documented hardware output.
12. **No license file:** third-party directories carry their own notices, but the repository root does not state a project-wide license.

Recommended next integration milestone: make one honest vertical slice—acquire or replay a 2,048-sample window on CPU0, reproduce the 38 Python features in firmware, run the checked-in 3-class model through a chosen runtime, and compare its quantized output against `golden_vectors.json`. That would connect the two currently separate halves before changing the application to FoG.

## Development rules encoded by the design docs

The planning documents require:

- subject/file-grouped evaluation rather than random sibling-window splits;
- explicit distinction between verified results, inferences, targets, and unresolved items;
- raw windows, derived features, and labels to remain local to a node;
- only a defined aggregation payload to cross node boundaries;
- hardware-in-the-loop acceptance tests for firmware slices;
- no claim that federation guarantees cross-site performance.

These are design constraints, not proof that the current firmware enforces them.

## GitHub project helper

`scripts/create-issues.sh` creates labels, milestones, and the planned HIL/ML issues using the GitHub CLI. It defaults to `jntbatra/fedtinyrt` and makes remote changes. Review it, authenticate `gh`, and set `REPO` if needed before running:

```bash
REPO=owner/repository bash scripts/create-issues.sh
```

Do not run it casually against an active project because it is intended as a one-time board-population tool.

## Additional documentation

Read documents according to what you are trying to do:

1. `README.md` — source-grounded repository map and current implementation status.
2. `SYSTEM_OVERVIEW.md` — intended FoG product narrative, methodology, assumptions, and limitations.
3. `context.md` — strict state names, definitions, design decisions, and ADRs.
4. `RFC-001-systems-contract.md` — proposed real-time budgets, interfaces, invariants, and failure cases.
5. `KANBAN.md` — planned S0–S11 hardware-in-the-loop slices (S11 is an extension) and ML work.
6. `GETTING_STARTED.md` — team onboarding and workflow.
7. `SETUP_NOTES.md` — historical e2 studio/board bring-up record.
8. `ml/README.md` and `ml/RESULTS.md` — bearing-model workflow and previously recorded experiment results.

When documents disagree with executable code, use the code and generated configuration to describe the present state, and use the documents only to describe intent or historical results.
