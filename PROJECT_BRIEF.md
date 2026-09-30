# FedTinyRT — Project Brief (Sleep Apnea)

> **REALITY FILTER.** Tags: `[Verified]` = checked against a source (Renesas EK-RA8P1 product page,
> the FSP-generated board pin config in this repo, or a cited paper/dataset page) · `[Inference]` =
> reasoned from verified facts · `[Unverified]` = not confirmed · `[Decision]` = chosen by us, not a
> fact about the world. Nothing here is a clinical claim.
>
> **Scope note:** this brief describes the **sleep-apnea direction**. `SYSTEM_OVERVIEW.md`,
> `context.md`, and `RFC-001-systems-contract.md` still describe the earlier **Parkinson's
> Freezing-of-Gait** target and have **not** been rewritten yet — where they conflict with this file,
> treat them as the old target. `[Verified — read in this repo]`

---

## What we are building

FedTinyRT is a privacy-preserving, on-device screening system for **obstructive sleep apnea (OSA)**
built on the **Renesas EK-RA8P1** (Cortex-M85 @ 1 GHz + Cortex-M33 @ 250 MHz + Ethos-U55 NPU) running
**µT-Kernel 3.0**. One board sits at the bedside of a sleep clinic or ward as a base station. Through
the night it ingests several cheap, low-burden signals at once — breathing and snoring **audio** from
the board's onboard **PDM MEMS microphones**, **SpO₂/PPG** from an I²C pulse-oximeter module, and
**body-position / respiratory-effort motion** from an accelerometer — windows them into fixed epochs,
and runs an **INT8 multimodal neural network on the Ethos-U55 NPU** to flag apnea/hypopnea events in
real time and accumulate an apnea–hypopnea index (AHI) estimate. Raw waveforms, features, and labels
never leave the board. `[Decision]`

The second half of the system is **federated learning**. Each clinic's board fine-tunes the model's
head **on its own patients, on-device, on the M33 core** while the M85 keeps screening in real time on
physically separate silicon — then sends **only FP32 weights** over wired Ethernet to an aggregator
that averages them (**FedAvg**) into a new global model and sends it back. No recording, no
oximetry trace, and no clinician label ever crosses the network; the M33 is the egress gate that
enforces this. `[Decision]` The intended contribution is the **embedded systems realization** —
multimodal apnea screening + on-device training + cross-site federation on an RTOS-driven dual-core
MCU with a measured real-time guarantee — not a new ML algorithm, and not a validated medical device.
We do **not** claim federation "fixes," "guarantees," or "ensures" cross-site performance; it is an
experiment, reported with uncertainty. `[Inference — positioning, based on our own literature read]`

---

## Which part of the board does what `[Decision]`

Hardware facts are `[Verified]` (Renesas EK-RA8P1 kit page + this repo's `bsp_pin_cfg.h`); the *use* we
put each part to is our plan, not a measured result.

| Part | What it is | What we use it for |
|---|---|---|
| **Cortex-M85 @ 1 GHz + Helium** | fast core, SIMD DSP | Hard-real-time sensor ingest (audio, SpO₂, accel), DMA ring buffers, CMSIS-DSP front end (log-mel / FFT), epoch alignment across modalities, issues NPU inference, drives the display. |
| **Ethos-U55 NPU @ 500 MHz, 256 GOPS** | INT8/INT16 NN accelerator, **inference only** | Forward pass of the multimodal apnea model, per epoch. **Never backprop.** Ops Vela can't take fall back to M85 CMSIS-NN. |
| **Cortex-M33 @ 250 MHz** | slower second core, no NPU/Helium | Background **on-device training of the classifier head** (FP32), federation client (store-and-forward), and the **egress gate**: weights may leave, raw data may not. |
| **M85 TCM (256 KB)** | tightest-latency RAM | Audio/PPG/accel DMA ring buffers + hottest DSP working set. |
| **M33 TCM (128 KB)** | second-core scratch | Trainable head weights, gradients, Adam state, one micro-batch. Budget ≤ 96 KB — **not yet benchmarked**. `[Unresolved]` |
| **2 MB SRAM (ECC)** | on-chip data | NN activations the NPU streams + per-modality feature buffers. |
| **1 MB MRAM** | on-chip non-volatile | Firmware + **A/B model slots** — new global model written to the inactive slot, checksummed, then atomically switched. |
| **64 MB SDRAM** | external bulk RAM | Multi-minute epoch buffers and overnight event/feature history for the AHI tally. |
| **64 MB Octo-SPI Flash** | external bulk non-volatile | **Dataset replay** for the demo (PSG recordings fed into the live pipeline), event logs, calibration. |
| **Onboard PDM MEMS mic** | `MIC_CLK` / `MIC_DAT` | Modality 1: snoring / breathing sound, gasp and arousal onsets. |
| **I²C (Pmod / Grove / Qwiic / I3C)** | sensor bus | Modality 2: **SpO₂ + PPG** pulse-oximeter module — desaturation and pulse-rate surge. Part not chosen. `[Unverified]` |
| **I²C or SPI Pmod** | sensor bus | Modality 3: accelerometer — body position + chest/abdomen respiratory effort (obstructive vs central). |
| **Arduino analog pins (ADC)** | `ARDUINO_AN0..AN5` | Reserved for an optional ECG / nasal-airflow analog front end. Not designed. `[Speculation]` |
| **Ethernet RGMII (RJ45)** | only network link on the board | Federation **only**: FP32 weights out, `Global_Model[r]` in, during sync windows. PHY off otherwise. |
| **MIPI display (7" 1024×600 touch)** | kit expansion board | Clinician view: live respiration/SpO₂ trace, flagged events, running AHI, session start/stop. |
| **Camera connector (OV5640)** | kit expansion board | Contactless chest-motion idea. **Out of v1 scope** — privacy cost, and it fights the parallel-LCD pins on SW4. `[Speculation]` |
| **USB High-Speed** | USB-C | Bulk export of anonymized session summaries and benchmark dumps to the dev PC. |
| **Onboard J-Link + VCOM UART** | debug | Telemetry, deadline-miss counters, on-target debug (SEGGER RTT). |
| **User LEDs / buttons** | 3 LEDs, 2 buttons | LED = recording / liveness / fault state; buttons = start and stop a night session. |
| **TrustZone** | M85 security extension | Deferred: optional hardware-backed egress gate, only if v1 lands early. |

**Why the split matters:** inference (M85 + NPU) and training (M33) run on **physically separate
cores at the same time**, so on-device learning can never delay real-time screening. That is the
RTOS thesis of the project. `[Decision — the 0-missed-deadline claim must still be measured]`
