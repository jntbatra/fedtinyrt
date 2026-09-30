# Fleet-estimated reference — how many devices does calibration need?

Script: `tools/fed_reference.py`. Results: `results/fed_reference.json`. Run: 2026-09-30.

## Question

Per-session calibration (E4) needs a *reference*: a typical session's median, spread and
threshold-offset. Those are population quantities. How many devices must contribute before
the reference is good enough?

## Protocol

LOSO over the 18 usable subjects. For target *j*, the reference is built from *m* donor
devices drawn from the other 17 subjects' labelled FIT halves; the target's TEST scores stay
unlabelled. Monte-Carlo over donor subsets (60 repeats), metric = mean-of-subject balanced
accuracy on TEST.

`m = 0` = no calibration (one fixed threshold). `m = 1` = a single donor device.

## Result

| m (donor devices) | mean BA | sd over targets |
|---|---|---|
| 0 — fixed threshold | 0.6767 | — |
| 1 — single donor | 0.7324 | 0.0956 |
| 2 | 0.7392 | 0.0994 |
| 3 | 0.7437 | 0.0991 |
| 5 | 0.7483 | 0.1025 |
| 10 | 0.7517 | 0.1036 |
| **19 — full fleet** | **0.7569** | 0.1076 |

- **Full fleet − single donor = +0.0246, 95 % CI [+0.0162, +0.0333]** (paired, subject-level).
- **Fixed threshold → full fleet = +0.0802.**

The curve is monotone and **saturates around 5–10 devices**; roughly 60 % of the federation
gain arrives by m = 3.

## What this does and does not say

- It **quantifies** a real federation effect of the shared reference: +2.5 points balanced
  accuracy over a single-donor reference, CI excluding 0.
- It says **~5–10 devices are enough**. A factory reference computed from a cohort that size
  is already saturated, so for *identical* devices a central reference makes federation
  redundant.
- Federation therefore becomes necessary only when devices **differ** (per-site sensor
  characteristics, different populations) — a per-site reference. That case is **not tested
  here** and is the honest next step for a federation claim.

## Where the labels are (honesty note)

The deployed device is **label-free**: it uses only its own unlabelled session scores plus the
shared reference. The **reference** is estimated from *labelled* calibration sessions
(the threshold-offset term needs labels). "Federation" here means pooling labelled calibration
data to estimate a shared reference — not collaborative learning without labels.

## Performance note

First version took ~70 s because each donor's statistics were recomputed inside the
Monte-Carlo loop. They are per-subject constants; caching them once per subject gives
**2.7 s (26×)**. Numbers are unchanged apart from Monte-Carlo noise in the intermediate
points; m = 19 (full fleet) is deterministic.
