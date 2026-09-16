# FedTinyRT Sleep — system overview

Target: local multimodal sleep-event screening, adaptive processing, personal
baselines, event summaries and simulated site federation. This is a research
prototype. `context.md` contains the supplied target; `README.md` reports status.

Current firmware: FSP startup -> existing hal_entry -> µT-Kernel -> usermain ->
acquisition task -> bounded frame queue -> processing/controller task ->
labelled synthetic status/event/session telemetry.

Current PC workflow: synthetic or reviewed local summary NPZ -> sleep features ->
subject splits -> binary MLP -> SavedModel -> full INT8 TFLite -> golden vectors
and C arrays. Federation reuses small-network training with disjoint subject sites,
validated weight aggregation and local adaptation.

The PC model and board controller are still separate. The board uses scripted
fixture probabilities. Exported arrays do not imply a linked inference runtime.
Real DSP, trained CPU inference and golden parity are the next integration gate.

M85 remains the primary core. NPU and background M33 work follow CPU correctness.
No network or hardware privacy mechanism is implemented. Federation is an
in-process PC experiment, not deployed secure transport.

The old FoG architecture is archived in `docs/legacy/SYSTEM_OVERVIEW.md`.
