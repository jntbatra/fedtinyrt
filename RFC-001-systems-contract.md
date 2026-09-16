# RFC-001 — sleep migration contract

Status: implemented host contracts; board validation pending. Full target:
`context.md`. Old FoG budgets are archived and do not constrain sleep epochs or
make M33 a prerequisite.

## Current contracts

- Original FSP/kernel boot remains intact; changes are handwritten application code.
- Frames contain monotonic millisecond timestamps and four synchronized scalar
  summaries, each with presence, liveness, timestamp and quality. This is not a
  raw sensor/DMA interface.
- SpO2 and respiration are critical. Missing, stale, nonfinite or poor quality
  produces SENSOR_FAULT. Unavailable/invalid inference produces UNCERTAIN.
  Optional motion/audio can be absent.
- Static queue capacity is 16; full queues drop/count incoming frames. Caller
  serializes operations. Current task-only protection is not ISR/multicore-safe.
- Replay acquisition runs at 1 Hz, priority 8; processing at priority 12. Absolute
  releases avoid accumulated processing drift. Whole missed releases and drops
  are counted. Priorities and stack sizes require hardware measurement.
- Thirty stable valid frames establish a frozen baseline in session RAM.
  Stability is a signal check, not proof of absence of disease. No persistence yet.
- SpO2 drop >=3 points, respiratory amplitude <=50% of baseline, or a valid
  event score >=0.7 triggers HIGH. Borderline scores remain UNCERTAIN.
  Three scores >=0.7 debounce onset. Three scores <0.3 close an event at the first
  low timestamp. Accepted events last >=10 s. HIGH timeout is 15 s; recovery 5 s.
  Persistent unresolved triggers must clear before retriggering.
- Gaps >2000 ms invalidate the unobserved interval and discard active events.
  Other intervals use the preceding sample as a zero-order hold. Monitoring and
  valid monitoring time remain distinct; repeated session end is rejected.
- Research triage is INSUFFICIENT_DATA without valid calibration/data, with <80%
  coverage, or with any model errors. Demonstration frequency thresholds are 5
  and 15 events per valid monitoring hour. This unvalidated frequency-only rule
  is not AHI, diagnosis or sleep time. Richer triage awaits real data.
- Subject groups never cross data partitions. Baselines come from prior stable
  calibration; scaling and quantization calibration use training data only.
- Federation validates round/version, unique client IDs, sample counts, tensor
  shapes, finite weights and bounded norms. Payloads contain weights, not signals.

## Pending hardware acceptance

Full Debug link, boot, stack high-water marks, linker/RAM use, task jitter,
buffer pressure, CPU model inference and PC/board golden parity remain to measure.
Sensor acquisition must remain independent of inference. Host C tests prove
logic only; no board deadline or NPU speedup claim is made.
