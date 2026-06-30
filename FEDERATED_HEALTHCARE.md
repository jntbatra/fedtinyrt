# FedTinyRT — Cross-Silo Federated Healthcare (research direction)

**Status: proposed application pivot, for team evaluation.**
Architecture and contest thesis unchanged; only the use-case sharpens so that
**privacy is essential, not decorative.**

---

## 1. The idea in one line

Each **hospital** owns one µT-Kernel board (a node). The board screens patients
with its onboard sensor, trains a model **on that hospital's own patients**, and
shares **only model weights** with other hospitals. A global, better model emerges
**without any patient data ever leaving any hospital.**

This is **cross-silo federated learning** — the flagship real-world use of FL,
used precisely because patient data legally *cannot* be pooled (HIPAA / GDPR).

## 2. Why we pivoted from "industrial monitoring"

The original proposal scenario was industrial machine monitoring (normal/degrading/
fault). It works, but its **privacy story is weak** — vibration data of a motor isn't
secret, so federation there is mostly *accuracy aggregation*, and privacy is a
nice-to-have.

In healthcare, privacy is **the whole point**:
- Patient data is legally protected and **cannot be centralized**.
- Federation becomes the **only lawful way** to build a shared model.
- So "federated" is **required, not a buzzword.**

The PDF already names *"privacy-sensitive industrial and healthcare deployments"*,
so this is within the proposal's stated scope.

## 3. What cross-silo federated learning is (plain)

Normal ML: gather everyone's data on a server, train once. Impossible with patient
data. Federated learning flips it — the **data stays put, the model travels**:

1. Each hospital trains the model on its **local** patient data.
2. Each hospital sends only the learned **weights** (not records) to an aggregator.
3. The aggregator **averages** the weights (FedAvg) into a better global model.
4. The global model is sent back. Repeat.

**Cross-silo** = each client is an *institution* (hospital) with many patients —
as opposed to cross-device (each client is one phone/wearable).

**Analogy:** several hospitals each treat their own patients privately. Each week
they share "what we learned" (model updates), never the patient files. Everyone's
model improves; no records are exposed.

## 4. The killer benefit this proves

A **small or rural hospital with few patients** cannot train a good diagnostic
model alone. By federating with larger hospitals it obtains a strong model —
**without anyone sharing patient data.**

We already demonstrated exactly this effect (CWRU sim): data-scarce nodes jumped
from **0.72–0.88 alone → 0.92–0.96 federated**, weights-only. The same mechanism
gives a small clinic big-hospital-quality screening, privately.

## 5. Candidate sensing tasks (research options)

The board has an accelerometer and a microphone. The medical signal must be
readable by one of them. Options to evaluate:

| Task | Sensor | Signal / why | Public dataset(s) | Reuses our pipeline? |
|------|--------|--------------|-------------------|----------------------|
| **Parkinson's gait / tremor** | accelerometer | resting tremor ~4–6 Hz → clear FFT signature | PhysioNet "Gait in Parkinson's Disease"; Daphnet Freezing-of-Gait | ✅ exactly (accel→FFT/stats→MLP) |
| Respiratory / cough screening | microphone | crackle / wheeze / cough → MFCC | ICBHI Respiratory Sound DB (multi-site); COUGHVID | ⚠️ needs MFCC audio features |
| Heart sounds / murmur | microphone | abnormal PCG → spectral | PhysioNet PCG / CirCor murmur | ⚠️ needs MFCC features |
| Fall-risk / mobility | accelerometer | gait instability / mobility | Daphnet, mobility datasets | ✅ reuses pipeline |

**Leading candidate: Parkinson's gait/tremor (accelerometer).** Tremor's narrow
frequency band is tailor-made for our existing FFT features, it reuses the entire
accel→FFT→MLP→FedAvg→personalization stack, and multi-patient datasets exist that
we can partition into "hospitals" (the federation clients).

## 6. Architecture on the board

Each hospital, in production, owns one board:

```
  Hospital board:  patient does a short sensor test (e.g. 30 s gait via accel)
                   -> raw signal stays on THIS board -> local training
        |
        +-- Ethernet / UART carries ONLY model weights  <->  aggregator (FedAvg)
            (raw patient data NEVER crosses the network)
```

**Critical rule:** the network (Ethernet) transports **weights, not raw data**.
Sending raw patient signals to a central board would be *centralized* and would
break the privacy guarantee. Sensor → its own board's MCU is fine (inside one node).

### Demo on one physical board
We have one board, so we simulate the federation exactly like the working sim:

| Role | Mapped to |
|------|-----------|
| Hospital A (live) | **Cortex-M85** + onboard accel (a live patient/volunteer test) |
| Hospital B | **Cortex-M33** replaying another hospital's patients from flash |
| Hospitals C, D… | **PC** virtual nodes (more dataset patients) |
| Aggregator | PC (FedAvg) |
| Network | Ethernet / UART — **weights only** |

Two cores = two genuinely separate processors = two real nodes; PC adds scale.
This is honest: "2 real on-chip hospital-nodes + PC for additional silos."

## 7. What is already proven and transfers

From `ml/RESULTS.md` (industrial datasets, but the mechanism is domain-agnostic):
- Single model doesn't fit all sites (cross-machine 66%) → per-site learning needed.
- On-device personalization fixes a node to its own data (99.6%).
- Federation rescues data-scarce nodes (0.72 → 0.95), weights-only.

The whole stack — feature extraction, INT8 MLP, FedAvg, personalization — is
**domain-agnostic**. Switching to a medical accel dataset changes only the data and
labels, not the architecture.

## 8. Mapping to the build roadmap

- Steps 1–12 (RTOS, sampling, features, INT8 inference, on-device training): unchanged.
- Step 8 (PC pre-train + export): retrain on the chosen medical dataset.
- Steps 13–15 (federation, dual-core, two-core federation): the hospital nodes
  exchanging weights over Ethernet/UART — same as planned, new framing.

## 9. Open research questions (to investigate)

1. Which sensing task (gait/tremor vs respiratory vs heart) gives the best
   accuracy-vs-privacy-vs-board-fit trade-off? (Start with accel gait/tremor.)
2. Cross-hospital generalization: does a model trained at hospitals A,B work at an
   unseen hospital C? (Leave-one-hospital-out test.)
3. Does federation actually beat each hospital's local model, and by how much, as a
   function of hospital size? (We expect biggest gains for small hospitals.)
4. Privacy hardening beyond "raw data stays local": secure aggregation,
   differential-privacy noise on the shared weights — feasible on the MCU?
5. Real-time guarantee: does on-device training keep sensor-sampling deadlines
   (the RTOS thesis) during patient assessment?

## 10. Honest limitations

- **Simulation, not clinical.** We partition a public dataset's patients into
  "hospitals." This demonstrates the *method*, not a validated clinical device.
- **One physical board.** Two cores are two real nodes; additional hospitals are
  simulated on PC. No raw data crosses the network in either real or demo setup.
- **Not a medical claim.** Accuracy figures show the federated-learning mechanism;
  clinical validity would require proper trials and regulatory work.

## 11. Next steps

1. Pick the sensing task (recommended: Parkinson's gait/tremor, accelerometer).
2. Pull the dataset, partition patients into hospital-nodes.
3. Rebuild features (reuse `feature_extract.py`), retrain INT8 model (Step 8).
4. Re-run `federate_*.py` with **hospital = node**; report local vs federated vs
   personalized, plus a leave-one-hospital-out generalization test.
5. Fold the chosen scenario into `ROADMAP.md` Steps 8 and 13–15.
