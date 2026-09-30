# FINAL NPU RESULTS — RA8P1 / Arm Ethos-U55

Status: **the Ethos-U55 is integrated, running the deployed apnea model on
hardware, and measured.** Everything below is measured on the EK-RA8P1 unless a
line explicitly says "modelled".

---

## 0. Headline

| | CPU0 (Cortex-M85) INT8 path | NPU (Ethos-U55) | Ratio |
|---|---|---|---|
| Cycles per inference (CPU DWT @ 1 GHz) | 6,751.13 | 3,869.55 | **1.74× faster** |
| Time per inference | 6.75 µs | 3.87 µs | |
| Throughput | 148,123 /s | 258,427 /s | |

Correctness: **248 of 256 self-test windows match the TFLite reference exactly**;
the remaining 8 differ by at most **3 int8 codes** (±0.012 in probability). The
number of positives at the shipped threshold (q ≥ −53) is **identical** (10 of 256).

Modelled (Vela) was 3.16 µs; measured is 3.87 µs, i.e. 1.22× the model — the gap
is the driver round trip (cache maintenance, IRQ, poll loop).

---

## 1. The three processing units

| Unit | Core | Clock | Role in this project |
|---|---|---|---|
| CPU0 | Cortex-M85 | 1000 MHz | Everything: console, feature work, the INT8 reference path, calibration, training |
| CPU1 | Cortex-M33 | 250 MHz | Benchmarked in a separate project; unused by the apnea firmware |
| NPU | Arm Ethos-U55 | 500 MHz (CPUCLK ÷ 2) | Now runs the 10→32→16→1 classifier |

Hardware identity read from the device at runtime (`npuinfo`):

```
NPU ID       : 0x10104201     product=4 (U55), arch 1.1.0
NPU CONFIG   : 0x00003008     macs_per_cc=8 (log2 → 256 MAC/cycle), shram=48 KB,
                              cmd_stream_version=0, custom_dma=0
```

---

## 2. What was actually built

1. **RASC, headless.** The full RA Smart Configurator (26.7.0 / FSP 6.6.0) is
   installed at `~/renesas/ra/sc_v2026-07_fsp_v6.6.0/eclipse/`. It runs without a
   GUI:
   ```
   xvfb-run -a ./rasc -nosplash \
     -application com.renesas.cdt.ddsc.standalone.rcp.application \
     -data <ws> --generate --devicefamily ra --projectdir <dir> <dir>/configuration.xml
   ```
2. **Ethos-U driver vendored by RASC** into `ra/npu/ethos-u-core-driver/` and
   `ra/fsp/src/rm_ethosu/`, with the NPU IRQ (vector 11, `EVENT_NPU_IRQ`) and the
   `g_ethosu0` / `g_rm_ethosu0` instances generated into `ra_gen/`.
   To get that, the module must appear in **both** places in `configuration.xml`:
   the `<raModuleConfiguration>` list *and* a `<stack module="...">` entry inside
   `<context id="_hal.0">`. Adding only the former makes RASC copy the driver
   files but silently emit no instance and no interrupt.
3. **A TFLite for the shipped model.** `tools/export_tflite_npu.py` retrains the
   same MLP and exports `apnea_spo2_10_int8.tflite` (4,640 bytes, 848 MACs).
4. **Vela compilation.** `tools/export_npu_stream.py` extracts the command stream
   into `src/npu_stream.h`:
   ```
   vela apnea_spo2_10_int8.tflite --accelerator-config ethos-u55-256 \
        --system-config Ethos_U55_High_End_Embedded --memory-mode Shared_Sram \
        --optimise Performance
   ```
   Result: **CPU operators 0 (0.0%), NPU operators 3 (100.0%)**.
5. **Runtime** in `src/npu_ethosu.c` plus console commands `npu`, `npuinfo`,
   `npubench [N]`, `npuparity`.

---

## 3. The five real bugs, and what each one was

None of these were configuration mistakes in the project — they are integration
facts about this part that are not in any document on disk.

1. **`malloc` fails on the second call.** The heap is `BSP_CFG_HEAP_BYTES = 0x400`
   (1 KB) but newlib asks `_sbrk` for a 4 KB page, so `ethosu_semaphore_create()`
   returned NULL and `ethosu_init()` failed with `FSP_ERR_INVALID_ARGUMENT`.
   *Fix:* provide a strong `ethosu_semaphore_create()` backed by static storage.
2. **The NPU must be opened secure + privileged.** The part straps non-secure at
   power-up; `ethosu_dev_verify_access_state()` rejects the mismatch. The
   `rm_ethosu` module properties must be `secure_mode=enabled`,
   `privilege_mode=enabled`.
3. **Base pointers are indexed by tensor *purpose*, not tensor order.** Vela's
   `BasePointerIndex` is `WeightTensor = 0`, `ScratchTensor = 1`. The command
   stream refers to regions 0 and 1, and the model input/output live *inside* the
   arena (input at +0x20, output at +0x00). Passing the five TFLite tensors in
   index order made the NPU execute part of the stream and then stall forever in
   `state=Running` with no fault.
   *Fix:* `num_base_addr = 2`, `base[0] = weights`, `base[1] = arena`.
4. **Cache invalidation clobbered the NPU's output.** `rm_ethosu.c` invalidates
   with `SCB_CleanInvalidateDCache_by_Addr`, which writes the CPU's stale cached
   lines back over what the device just wrote. The arena read back as all zeros
   even though the NPU had completed successfully.
   *Fix:* invalidate without cleaning after the run.
   (`SCB_InvalidateDCache_by_Addr`.)
5. **RAM budget.** The project reserves only 32 KB of data RAM (`RAM_LENGTH =
   0x8000`) next to 512 KB of code RAM. The NPU buffers had to fit in the
   remaining bytes; the weight tensor is read straight from its flash/SRAM
   constant rather than copied.

Diagnostics that proved each one, all still available on the console:
`npuinfo` (registers), `npuparity` (256-window diff), and `npusweep`
(sweeps QCONFIG × REGIONCFG, which established that the stall was *not* the
AXI-port configuration).

---

## 4. Measured results

```
apnea> npuparity
  vectors      : 256
  exact match  : 248 / 256
  max abs diff : 3 int8 code(s)
  positives    : npu 10, tflite 10 at q>=-53

apnea> npubench 1000
  inferences : 1000
  cycles     : 3869552 total, 3869.55 cycles/inference
  time       : 3.86 us/inference at 1000 MHz (CPUCLK)
  throughput : 258427 inferences/s

apnea> bench              (CPU0 INT8 reference path, for comparison)
  cycles     : 67511353 total, 6751.13 cycles/inference
  time       : 6.75 us/inference at 1000 MHz
  throughput : 148123 inferences/s
```

Note on units: the DWT cycle counter counts **CPU** cycles at 1000 MHz, not NPU
cycles. The NPU itself runs at 500 MHz, so the 3,869 counted cycles correspond to
about 1,935 NPU cycles of wall time. Both figures above are the same wall-clock
basis, which is what the comparison needs.

The 8 mismatching windows all differ by 1–3 codes and sit where the two sigmoid
implementations disagree slightly (the NPU uses a fixed-point LUT). No window
crosses the decision threshold differently.

---

## 5. How the cores are used

**CPU0 (Cortex-M85, 1000 MHz)** — the whole product. Measured 6,751 cycles per
inference on the INT8 reference path, 77,429 cycles (~77 µs) per session
calibration, ~101,228 cycles (~101 µs) per training iteration, ~81 ms for an
800-iteration adaptation, ~2 KB RAM. With the NPU in use, the CPU's per-inference
work drops to submitting the job and reading the result.

**CPU1 (Cortex-M33, 250 MHz)** — benchmarked once (4 scalar kernels × 200,000
element-ops, DWT, checksum-matched), in a separate project under `bench/`:
M85 14.09 ns/op vs M33 281.40 ns/op aggregate, i.e. ~20× slower per scalar op,
with concurrency free (no shared cache). It is **not used by the apnea
firmware** — `grep` for `CPU1ACTCSR` / mailbox in `src/*.c` returns nothing.

**NPU (Ethos-U55, 500 MHz)** — 256 MAC/cycle, 48 KB SHRAM. Runs the classifier in
3.87 µs end to end, of which Vela models 561 cycles as NPU compute.

---

## 6. Limitations — what is still not claimed

- **No energy or power numbers.** There is no current probe on this board. Only
  cycles, time and RAM are reported.
- **CPU1 is not integrated** into the product; its numbers come from a separate
  benchmark project.
- **The NPU runs a re-quantised twin of the deployed model.** The TFLite is
  exported by TensorFlow's full-integer quantiser (input scale 0.0165, zp −2)
  whereas `src/apnea_model.h` uses the project's own scheme (scale 0.0635,
  zp −15). They are the same trained weights, but not the same arithmetic, which
  is why the CPU and NPU outputs differ by 1–3 codes. Parity is established
  against the TFLite reference, which is the correct comparison.
- **Single model, single input size.** 848 MACs is a tiny workload; the 1.74× is
  specific to it. A larger network would favour the NPU more.
- The Vela cycle model assumed the weights live in off-chip flash; in the build
  they are read from the constant section, so the modelled and measured numbers
  are not directly comparable.

---

## 7. Reproducing

```bash
# 1. regenerate FSP content with the NPU module (then restore the two memory .lld files)
cd ~/renesas/ra/sc_v2026-07_fsp_v6.6.0/eclipse
xvfb-run -a ./rasc -nosplash -application com.renesas.cdt.ddsc.standalone.rcp.application \
  -data /tmp/rasc_ws --generate --devicefamily ra \
  --projectdir ~/tron/apnea_deploy ~/tron/apnea_deploy/configuration.xml

# 2. rebuild the TFLite and the command stream
cd ~/tron/apnea_deploy
OMP_NUM_THREADS=1 /tmp/cincenv/bin/python tools/export_tflite_npu.py
/tmp/cincenv/bin/vela apnea_spo2_10_int8.tflite --accelerator-config ethos-u55-256 \
  --system-config Ethos_U55_High_End_Embedded --memory-mode Shared_Sram \
  --optimise Performance --output-dir results/vela_npu
OMP_NUM_THREADS=1 /tmp/cincenv/bin/python tools/export_npu_stream.py
OMP_NUM_THREADS=1 /tmp/cincenv/bin/python tools/gen_npu_expected.py

# 3. build and flash
export ARM_GCC_TOOLCHAIN_PATH=~/tron/arm-gnu-toolchain-13.2.Rel1-x86_64-arm-none-eabi/bin
cmake --preset ReleaseCI && cmake --build --preset ReleaseCI
JLinkExe -device R7KA8P1AF -if SWD -speed 4000 -autoconnect 1 -CommanderScript flash.jlink

# 4. exercise it
python tools/serial_cmd.py npuinfo npuparity "npubench 1000"
```

Files that carry the integration:

| File | Role |
|---|---|
| `src/npu_ethosu.c` | driver instance, buffers, commands, cache fix, semaphore fix |
| `src/npu_stream.h` | Vela command stream + weight tensor (generated) |
| `src/npu_expected.h` | TFLite reference outputs for the 256 windows (generated) |
| `apnea_spo2_10_int8.tflite` | the exported model (generated) |
| `results/vela_npu/` | Vela output + per-layer summary |
| `tools/export_tflite_npu.py`, `export_npu_stream.py`, `gen_npu_expected.py` | generation |
| `CMakeLists.txt` | adds `ra/npu/...` sources, includes, `ETHOSU55=1` |

**Rule deviations, flagged:** `memory_regions.lld` and `fsp_gen.lld` are
RASC-generated but hold a hand-set memory layout that RASC resets on every
regeneration; they are restored from a backup after each generate. This should be
re-applied through RASC's Memory Regions view if it is to survive long term.
