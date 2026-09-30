# NPU (Ethos-U55) — Vela compilation report

> **Superseded by hardware measurement.** The NPU has since been integrated and
> **measured on the board**: **3.87 µs/inference, 1.74× faster than CPU**, decisions
> identical on the 256-window parity test. See [`../final_npu_results.md`](../final_npu_results.md)
> for the authoritative measured results. This document is the pre-measurement Vela
> estimate (which predicted 3.16 µs; measured was 3.87 µs — the gap is driver overhead).

**Status of this doc: Vela estimate (pre-hardware).** Arm's Vela compiler's estimate
for the model on the Ethos-U55, kept for the record.

## Method
1. Exported the deployed `spo2_10` model (10→32→16→1, 897 params) to INT8 TFLite,
   reproducing the deployed weights via `tools/phase4_quantize.py`'s `train_mlp`
   (iters=400, seed=0) and full-integer quantization with a representative dataset
   from the training windows. Script: `tools/export_tflite_npu.py`. Output:
   `apnea_spo2_10_int8.tflite` (4,640 bytes).
2. Compiled with Arm Vela: `vela --accelerator-config ethos-u55-256
   --optimise Performance`. Output: `apnea_spo2_10_int8_vela.tflite` (3,744 bytes).

## Vela estimate (Ethos-U55-256, "High_End_Embedded" system config)
| metric | value |
|---|---|
| operators mapped to NPU | **3 / 3 (100%)** — 0 fall back to CPU |
| nn MACs | 848 |
| cycles/inference (total) | **1,581** (NPU 561 + SRAM access) |
| inference time | **~3.16 µs** (at Vela's default ~500 MHz NPU model) |
| inferences/sec | ~316,000 |
| SRAM used | 0.05 KiB |
| encoded weights | ~1,056 bytes |

## Comparison to the measured CPU path
| | CPU (measured) | NPU (Vela estimate) |
|---|---|---|
| cycles/inference | 6,718 | 1,581 |
| time/inference | 6.71 µs | ~3.16 µs |

Vela estimates roughly **2× fewer cycles** on the NPU, and the whole network maps to
the accelerator.

## Honest caveats (read before quoting these numbers)
- **This is a Vela estimate, not a hardware measurement.** No inference has been run
  on the RA8P1's NPU.
- The estimate **excludes CPU-side driver, DMA-trigger, and interrupt/setup overhead**,
  which real hardware pays per inference — so the on-hardware figure will be higher.
- It assumes Vela's default system config clock (~500 MHz); the RA8P1's actual NPUCLK
  (configured ÷2) is not verified here, so the µs figure may scale.
- For a model this small, fixed per-inference overhead dominates; the real-world win
  may be smaller than 2×, or negligible once overhead counts.

## Next step (to get a real number)
Add the Ethos-U55 driver + NPU memory region to the FSP project (RA Smart
Configurator / e2 studio — a GUI step), embed `apnea_spo2_10_vela.tflite`, run it via
the Ethos-U core driver, and read the real DWT cycle count on the board.
