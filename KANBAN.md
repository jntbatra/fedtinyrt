# FedTinyRT Sleep — migration backlog

The existing pipeline is being adapted in place. `context.md` defines the full
target. The old FoG backlog is preserved in `docs/legacy/`.

| Milestone | Status |
| --- | --- |
| Preserve baseline | Tag and historical code/docs retained; fresh board boot pending |
| Sleep ML | Source and synthetic smoke pass; real dataset/mapping/metrics pending |
| INT8 export | PC conversion and golden replay verified on synthetic fixtures |
| Board replay/controller | Tasks integrated; application entry compiles; full link/board run pending |
| CPU model inference | Pending runtime, preprocessing parity and board golden check |
| Sensors | Pending parts, pin review and isolated bring-up |
| Adaptive sensing | Host state logic verified; physical sensing/compute control pending |
| Personalization/triage | Host logic verified; real-data evaluation pending |
| Audio/accelerometer | Summary masks supported; physical streams/DSP pending |
| NPU | Pending after correct CPU inference |
| Federation | PC smoke pass; real-data/leave-one-site-out evaluation pending |
| M33/security | Stretch; does not block CPU integration |

Next vertical slice: reviewed real sleep epoch -> PC preprocessing/INT8 reference
-> same preprocessing/model on M85 -> checked output and measured latency/RAM.
Keep one physical board test active at a time.
