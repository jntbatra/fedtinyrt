# EK-RA8P1 — Board Specs & What We Use Each Part For

> **REALITY FILTER.** `[Verified]` = stated on the Renesas EK-RA8P1 kit page or present in this repo's
> FSP-generated `ra_cfg/fsp_cfg/bsp/bsp_pin_cfg.h` · `[Inference]` = reasoned, not directly confirmed ·
> `[Unverified]` = not confirmed this session · `[Decision]` = our plan, not a hardware fact ·
> `[Speculation]` = idea only, nothing committed.
> Sources: Renesas EK-RA8P1 kit page, https://www.renesas.com/en/design-resources/boards-kits/ek-ra8p1 ·
> this repo's `bsp_pin_cfg.h` (board pin names) · `context.md` (prior verified MCU facts).

---

## 1. Silicon specs (MCU: R7KA8P1KFLCAC)

| Item | Value | Status |
|---|---|---|
| Primary core | Arm Cortex-M85 @ **1 GHz**, Helium/MVE SIMD, FPU (single-precision) | `[Verified]` |
| Secondary core | Arm Cortex-M33 @ **250 MHz** (no Helium, no NPU) | `[Verified]` core+clock; `[Inference]` on no-NPU coupling |
| NPU | **Ethos-U55 @ 500 MHz, 256 GOPS**, INT8/INT16, inference only (never trains) | `[Verified]` per `context.md`; MAC count 256 `[Inference]` |
| On-chip non-volatile | **1 MB MRAM** (code + model slots) | `[Verified]` |
| On-chip SRAM | **2 MB SRAM with ECC** (activations, buffers) | `[Verified]` |
| TCM | **256 KB (M85) / 128 KB (M33)** | `[Verified — context.md]` |
| Process | 22ULL (22 nm ultra-low-leakage) | `[Verified — context.md]` |
| Security | TrustZone | `[Verified — context.md]` |
| Radio | **None.** No onboard BLE/WiFi on RA8P1 | `[Verified]` |

## 2. Board-level resources (EK-RA8P1 kit)

| Board resource | Detail | Status |
|---|---|---|
| External Octo-SPI Flash | **64 MB** (`OSPI_*` pins, shared with Arduino/Pmod1 via SW4) | `[Verified]` |
| External SDRAM | **64 MB** (32-bit bus, `SDRAM_*` pins) | `[Verified]` |
| Onboard microphones | **PDM MEMS mic** (`MIC_CLK`, `MIC_DAT`) | `[Verified]` |
| Audio codec | codec + speaker out; SSI pins `AUDIO_MCLK/BCLK/WCLK/SSITX/SSIRX` | `[Verified]` |
| Ethernet | **RGMII + RJ45** (`ETHERNET_*`, MDIO/MDC, PHY reset) | `[Verified]` |
| USB | **High-Speed** host/device (USB-C) + **Full-Speed** host/device | `[Verified]` |
| Display | **2-lane MIPI DSI connector** (`MIPI_*`, `DISP_*`) + **parallel graphics** (`PARLCD_*`); kit ships a 7" 1024×600 capacitive-touch MIPI expansion board | `[Verified]` |
| Camera | Camera expansion connector (`CAMERA_IRQ`, `CAM_XCLK`, `CAMERA_RESET`, `DCAM_D*`/`PARCAM_*`); kit ships an Arducam **OV5640** 5 MP module | `[Verified]` |
| Expansion headers | **Arduino Uno R3** (`ARDUINO_AN0..AN5`, `ARDUINO_D*`), **2× Digilent Pmod** (SPI/UART/I²C, `PMOD1_*`/`PMOD2_*`), **mikroBUS** (`*_MIKROBUS_*`, unpopulated), **Qwiic** (unpopulated), **2× Grove** I²C + analog (`GROVE2_AN0/AN1`, unpopulated) | `[Verified]` |
| Serial buses | I3C (`I3C_SCL/SDA`), system I²C (`SYS_I2C_*`), SCI UARTs via Pmod/Arduino, VCOM UART to J-Link (`VCOMM_*`) | `[Verified]` |
| Debug | onboard **SEGGER J-Link**, SWD/JTAG/ETM/SWO | `[Verified]` |
| User I/O | 3 user LEDs (red/blue/green), 2 user buttons, reset button | `[Verified]` |

> **Note on unpopulated headers `[Verified]`:** Qwiic, Grove, and mikroBUS are listed as *not
> populated* on the kit — using them means soldering the connector or going through Pmod/Arduino
> instead. Several pins are **shared** (OSPI ↔ Arduino/Pmod1, PARLCD ↔ parallel camera) and selected
> by **SW4**; two subsystems on the same SW4 group cannot both be live. Plan around this.

---

## 3. Slot allocation — what we intend to use each part for `[Decision]`

Nothing below is measured yet; these are assignments, not results.

### 3.1 Compute
| Part | Our use |
|---|---|
| **M85 @ 1 GHz + Helium** | Hard-real-time sensor ingest (audio + SpO₂ + accel), DSP front end (CMSIS-DSP FFT / log-mel), epoch windowing, issues NPU inference, drives the display. |
| **Ethos-U55 NPU** | INT8 forward pass of the multimodal apnea model only. **Never backprop.** Ops Vela can't take fall back to M85 CMSIS-NN. |
| **M33 @ 250 MHz** | Background **on-device training of the model head** (FP32), federation client, store-and-forward, and the **egress gate** (weights out, raw never). |
| **TrustZone** | Deferred: optional hardware-backed egress gate. Only if v1 finishes early. `[Decision — defer]` |

### 3.2 Memory
| Part | Our use |
|---|---|
| **M85 TCM 256 KB** | Audio/PPG/accel DMA ring buffers + hottest DSP working set. |
| **M33 TCM 128 KB** | Trainable head weights + gradients + Adam state + one micro-batch. Budget ≤ 96 KB; **must be benchmarked**. `[Unresolved]` |
| **2 MB SRAM (ECC)** | NN activations streamed by the NPU + per-modality feature buffers. |
| **1 MB MRAM** | Firmware + **A/B model slots** (atomic OTA swap of the global model; never mutate the live slot). |
| **64 MB SDRAM** | Long-horizon working memory: multi-minute multimodal epoch buffers, overnight event/feature history for the AHI tally. |
| **64 MB OSPI Flash** | Non-volatile bulk: **dataset replay** for the demo (PSG recordings played back into the pipeline), event logs, calibration. |

### 3.3 I/O — the multimodal front end
| Part | Our use | Status |
|---|---|---|
| **Onboard PDM MEMS mic** (`MIC_CLK`/`MIC_DAT`) | Primary contactless modality: snoring / breathing-sound stream, log-mel features. | `[Decision]` |
| **Audio codec / SSI** | Alternative analog audio path + any audible cue or alarm out. | `[Decision]` |
| **I²C (Pmod / Grove / Qwiic / I3C)** | **SpO₂ + PPG** pulse-oximeter module (desaturation is the classic apnea marker). Exact part not chosen. | `[Unverified — part TBD]` |
| **I²C or SPI Pmod** | Accelerometer for **body position + respiratory effort** (chest/abdomen motion). | `[Decision]`, part TBD |
| **Arduino analog pins `AN0..AN5` (ADC)** | Analog front-end path if we add **ECG or nasal-airflow/thermistor/belt** input. Not designed yet. | `[Speculation]` |
| **Ethernet RGMII** | Federation link **only**: FP32 weights out, global model in, during sync windows. PHY powered down otherwise. | `[Decision]` |
| **MIPI display (7" touch)** | Clinician view: live respiration/SpO₂ trace, flagged events, running AHI estimate, session start/stop. | `[Decision]` |
| **Camera connector / OV5640** | Contactless chest-motion or IR video modality. **Out of v1 scope** — privacy cost is high and it competes with PARLCD pins on SW4. | `[Speculation]` |
| **USB HS** | Bulk export of anonymized session summaries / benchmark dumps to the dev PC. | `[Decision]` |
| **VCOM UART + J-Link/RTT** | Telemetry, deadline-miss counters, on-target debug. | `[Decision]` |
| **User LEDs / buttons** | LED = recording/liveness/fault state; buttons = start/stop night session. | `[Decision]` |

### 3.4 Pin-sharing conflicts to resolve before wiring `[Verified from bsp_pin_cfg.h]`
1. **OSPI Flash ↔ Arduino SPI ↔ Pmod1** share pins through **SW4** — if we replay datasets from OSPI, the Arduino SPI slot and part of Pmod1 are unavailable.
2. **Parallel LCD ↔ parallel camera** share `PARLCD_D*`/`PARCAM_*` — using the parallel camera costs the parallel display path (the MIPI display connector is the way out).
3. **Audio SSI RX ↔ `DCAM_D2`** share `P406` (`J41`) — audio-in and digital camera cannot both claim it.
4. **I3C pull-ups** need `I3C_SEL_L` enabled before the I3C sensor bus works.

---

## 4. Federated learning for sleep apnea — the paragraph `[Decision]`

Sleep apnea is a good federated problem for the same two reasons FoG was, only stronger: overnight
polysomnography data is heavily protected patient data that legally cannot be pooled across hospitals
(HIPAA/GDPR), and scoring practice, patient mix, sensor placement, and hardware differ enough between
sleep labs that a model trained at one site degrades at another `[Unverified — must be measured in our
own cross-site test, not assumed]`. In FedTinyRT each clinic's board is one federation node: it
screens its own patients overnight with the current global model, fine-tunes **only the classifier
head** on its locally scored epochs on the M33 while the M85/NPU keeps screening in real time, and at
the end of a round emits a single `Aggregation_Payload` — dense **FP32 weights of the shared layers,
KB-scale** — over Ethernet. A star aggregator runs **FedAvg** across sites, sanity-filters payloads
(NaN/Inf, absurd norm, wrong round id), and redistributes `Global_Model[r]`; each board then keeps a
**personalized** copy (global + local fine-tune) that is used for local screening and **never
submitted**. Raw audio, SpO₂ traces, and clinician labels never cross the federation network. For the
contest build, "multiple hospitals" are **subject-level splits of public PSG datasets** — e.g. SHHS,
MESA, Apnea-ECG, and the St. Vincent's/UCD database on PhysioNet `[Verified — these databases exist
and are multimodal/PSG; our specific splits and preprocessing are not yet defined]` — replayed from
OSPI flash, with one held-out site for a leave-one-hospital-out test. The headline metric is
**AUPRC / average precision plus sensitivity & specificity per epoch, and AHI error per night**;
**accuracy is banned** as a headline because apneic epochs are rare. `[Decision]`

## 5. Multimodal data on this board — the paragraph `[Decision]`

The board's value over a single-signal screener is that the EK-RA8P1 gives us **three usable sensing
paths at once, natively**: the **onboard PDM MEMS microphone** (snoring, breath sounds, gasp/arousal
onsets), an **I²C SpO₂/PPG module** on the Pmod/Grove/Qwiic side (oxygen desaturation and pulse-rate
surges, the events an apnea is scored by), and an **I²C/SPI accelerometer** (body position, and chest
or abdominal respiratory effort — the signal that separates obstructive from central events). These
arrive at wildly different rates — audio at kHz, accel around 100 Hz, SpO₂ around 1 Hz `[Inference —
typical rates; our exact sampling config is not fixed]` — so the M85 timestamps each stream into its
own DMA ring buffer in TCM and resamples/aligns them onto a **common epoch grid** (30 s or 60 s
epochs, with overlap, matching how apnea is scored clinically `[Unverified — final epoch length is a
benchmark decision]`). Fusion is **per-modality encoder branches into a late-fusion head**: a small
1D-CNN over log-mel audio frames, a light temporal branch over SpO₂/PPG, and a light branch over
accel, concatenated into the shared dense layers — so the **frozen convolutional bodies stay on the
NPU in INT8** (cheap, and they can be grown for accuracy) while the **small fused head is the only
thing that trains on the M33 and the only thing that federates**. Because a sensor can fall off or
disconnect mid-night, the design requires **modality-dropout training** (train with branches randomly
zeroed) so a missing stream degrades the score instead of breaking inference; if a stream goes dead,
the system flags `liveness=false` and **withholds** a prediction rather than emit a false "no event."
`[Decision]` Longer-term/optional modalities — the camera expansion board for contactless chest
motion, or an ECG/airflow analog front end on the Arduino ADC pins — are noted in §3.3 as
`[Speculation]`, not part of v1.

---

## 6. Open items before this page can be signed off
| # | Item |
|---|---|
| 1 | SpO₂/PPG and accelerometer part numbers not chosen; no bench validation of either. `[Unverified]` |
| 2 | Epoch length, overlap, and per-modality sampling rates not fixed. `[Unresolved]` |
| 3 | M33 head-training memory + epoch time not benchmarked (fallback = M85 idle-slot training). `[Unresolved]` |
| 4 | Dataset choice, subject-level "hospital" partitions, and label harmonization across PSG databases not defined. `[Unresolved]` |
| 5 | INT8 vs INT16 for the audio branch, decided by AUPRC, not pre-committed. `[Unresolved]` |
| 6 | Fused model dimensions → exact `Aggregation_Payload` byte size unknown. `[Unresolved]` |
| 7 | `context.md` / `RFC-001` / `SYSTEM_OVERVIEW.md` still describe the FoG target and must be rewritten for apnea. `[Verified — repo state]` |
