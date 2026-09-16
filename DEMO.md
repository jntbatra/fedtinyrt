# Synthetic replay demo

Current firmware runs a **100-second scripted software fixture**. Signal values
and event probabilities are invented. No trained model or physical sensor is used.

| Seconds | Expected behavior |
| --- | --- |
| 0–29 | Stable baseline calibration, uncertain output |
| 30–39 | LOW, normal fixture scores |
| 40–42 | Trigger -> HIGH -> debounced EVENT_ACTIVE |
| 43–59 | Active event |
| 60–62 | Three clear scores close the event at second 60 |
| 63–67 | Recovery then LOW |
| 80–84 | Missing SpO2 -> SENSOR_FAULT |
| 85–99 | Normal fixture resumes |
| 100 | Session end, counters and research triage |

Ideal host timeline: one 20-second event, 8-point oxygen drop, 95 valid seconds,
5 missing seconds, 20 seconds below 90%, oxygen deficit integral 160 percentage
point seconds. Short-session event frequency is not clinical severity.

Host acceptance: `tests/host/run.py`. Board acceptance is pending: build Debug,
flash CPU0 and inspect serial at 115200 8N1. Confirm the synthetic/model-NONE
banner, transitions, event, summary, drops and missed releases. Scheduling can
slightly change durations; host timing cannot replace hardware measurements.

The separate PC demo in `ml/sleep/README.md` generates synthetic data,
trains/exports a model, checks golden vectors and runs federation.
It has not yet replaced the board's scripted scores.
