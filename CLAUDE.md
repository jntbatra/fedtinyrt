# FedTinyRT contributor context

Modify the existing EK-RA8P1/FSP/µT-Kernel project in place. Current target is
sleep-event screening. Bearing and FoG designs are historical.

Read `README.md` for status, `context.md` for the supplied target,
`RFC-001-systems-contract.md` for contracts and `KANBAN.md` for integration gates.
A design statement is not evidence of an implemented feature.

Preserve generated startup/kernel boot. Handwritten work belongs in `src/` and
the adapted `ml/sleep/` pipeline. Historical code/results remain in
`ml/legacy_bearing/`; bearing features are not sleep features.

Use subject-disjoint splits, training-only preprocessing, explicit modality masks
and prior stable calibration. Record float/INT8 probability metrics. Synthetic
fixtures prove software operation only. Keep recordings, generated models,
environments and caches out of Git.

Acquisition must not wait for ML/networking. Bound buffers, track drops, use
monotonic time and make missing/error outputs explicit. NPU and M33 integration
follow CPU correctness. No board timing, privacy or clinical claim without
evidence. On this workstation use `.venv/Scripts/python.exe`.
