# FedTinyRT — Development Context

> **Purpose of this file**
>
> This file is the authoritative development context for the next phase of **FedTinyRT**. It is written for developers, AI coding agents, reviewers, and contributors who need to understand what already exists, what is obsolete, what the new sleep-apnea direction is, how the embedded/ML/RTOS/adaptive-sensing/personalization/triage/federated-learning pieces fit together, what must change in the existing codebase, and what counts as a successful TRON Programming Contest 2026 prototype.
>
> **If another project document conflicts with this file, this file describes the current target unless the executable code proves otherwise.**

---

# 1. Project Identity

**Project name:** FedTinyRT
**Current target:** Adaptive, personalized, federated edge-AI sleep-apnea screening and triage
**Target board:** Renesas EK-RA8P1
**RTOS:** µT-Kernel 3.0
**Primary contest:** TRON Programming Contest 2026
**Project type:** Research / contest prototype, not a medical device

FedTinyRT is evolving from an earlier proof-of-concept that combined:

- µT-Kernel boot on the EK-RA8P1,
- PC-side vibration feature extraction,
- a small INT8 bearing-fault model,
- personalization experiments,
- and PC-side federated averaging.

The new project keeps the valuable systems ideas — real-time embedded inference, personalization, privacy, federation, and heterogeneous compute — but replaces the bearing-fault / Parkinson's-FoG direction with a more complete **sleep-apnea edge-health platform**.

The new system must not be implemented as "just another classifier." Its value is the **embedded systems architecture**:

1. multimodal biosignal acquisition,
2. real-time scheduling with µT-Kernel,
3. adaptive sensing,
4. signal-quality awareness,
5. on-device AI inference,
6. per-user personalization,
7. overnight triage,
8. privacy-preserving local processing,
9. federated improvement across simulated sites,
10. measurable benefit from the RA8P1 hardware architecture.

---

# 2. Reality Filter

Every contributor must distinguish between the following states.

## VERIFIED
Something already exists in source code, generated configuration, hardware documentation, or a reproduced experiment.

## IMPLEMENTED
Code exists and is integrated into the current runtime path.

## PLANNED
We have decided to build it, but it is not yet complete.

## STRETCH
Useful only after the mandatory vertical slice is stable.

## HISTORICAL
Belongs to the previous bearing/FoG direction and should not be described as current functionality.

## UNRESOLVED
A design decision still needs benchmarking or hardware validation.

Do not present PLANNED, STRETCH, HISTORICAL, or UNRESOLVED items as working features.

---

# 3. Current Repository State

The repository currently has **two mostly separate halves**.

## 3.1 Embedded firmware that already exists

The EK-RA8P1 project is configured through Renesas FSP / e2 studio.

The current firmware path is approximately:

```text
Reset
  ↓
FSP startup
  ↓
generated main()
  ↓
hal_entry()
  ↓
knl_start_mtkernel()
  ↓
usermain()
  ↓
print "FedTinyRT starting..."
  ↓
sleep forever
```

What is already useful:

- EK-RA8P1 project structure exists.
- CPU0 / Cortex-M85 is configured.
- µT-Kernel boots.
- serial/T-Monitor output works historically.
- board-generated files exist.
- FSP/CMSIS support is present.
- J-Link debug configuration exists.

What is **not** yet present in the current firmware:

- real sensor acquisition tasks,
- multimodal buffers,
- audio capture pipeline,
- SpO₂/PPG driver,
- accelerometer driver,
- respiratory-effort input,
- signal alignment,
- feature extraction for sleep data,
- TFLite Micro / CMSIS-NN / Ethos-U55 runtime integration,
- apnea model inference,
- M33 application,
- on-device training,
- Ethernet federation protocol,
- adaptive sensing,
- personalization,
- triage report generation.

The current firmware is therefore a **bring-up foundation**, not the sleep-apnea product.

---

# 4. Historical ML Work That Must Not Be Confused With the New Target

The repository contains PC-side ML code for machine-bearing vibration classification.

Historical pipeline:

```text
NASA IMS / CWRU vibration files
        ↓
2048-sample windows
        ↓
38 handcrafted features
        ↓
small MLP
        ↓
normal / degrading / fault
```

Historical assets include:

- feature extraction,
- grouped train/test logic,
- INT8 export,
- golden vectors,
- C model arrays,
- cross-machine evaluation,
- personalization,
- FedAvg simulation.

These are valuable references for:

- data splitting,
- quantization,
- model export,
- golden-vector validation,
- personalization mechanics,
- federation mechanics,
- experiment organization.

However:

> **The 38 bearing features and the 3-class bearing model are not part of the new sleep-apnea model.**

Do not reuse them as if they were medically meaningful.

The old ML scripts should be kept temporarily under a clearly marked legacy/historical path until the new sleep pipeline is stable.

Recommended migration:

```text
ml/
├── legacy_bearing/
│   ├── feature_extract.py
│   ├── train_tflite.py
│   ├── federate.py
│   ├── personalize.py
│   └── ...
│
└── sleep/
    └── new implementation
```

Do not destroy historical code before the new pipeline has working replacements.

---

# 5. New Product Goal

The new contest target is:

> **A privacy-preserving bedside/home sleep screening and triage system that combines multiple physiological signals, detects suspicious sleep-disordered breathing locally on the EK-RA8P1, adapts sensing intensity when an event is suspected, personalizes to the user's baseline, and improves across simulated sites through federated learning.**

This is a **screening prototype**, not a diagnostic medical device.

The system should be able to demonstrate:

```text
Person / public PSG replay
        ↓
multimodal signals
        ↓
µT-Kernel real-time acquisition
        ↓
signal-quality validation
        ↓
adaptive sensing controller
        ↓
multimodal AI inference
        ↓
event detection
        ↓
personalized severity / triage summary
        ↓
optional federated update flow
```

---

# 6. Clinical / Problem Framing

The prototype focuses on sleep-disordered breathing, especially obstructive-sleep-apnea-like events.

The device should not merely output:

```text
APNEA = TRUE
```

It should reason from several pieces of evidence and produce a more meaningful event description.

Example output:

```text
Possible respiratory event

Confidence: 0.91
Duration: 24 s
SpO₂: 97% → 89%
Respiratory effort: continued
Airflow/breathing signal: reduced
Movement: low
Signal quality: good
```

The nightly system should summarize:

- monitoring duration,
- number of suspicious events,
- event frequency,
- longest event,
- minimum SpO₂,
- oxygen-desaturation burden,
- signal quality,
- model confidence,
- and a simple research triage category.

Recommended wording:

```text
LOW
MODERATE
HIGH
```

The output must be described as a **research triage/screening score**, not a clinical diagnosis.

---

# 7. Core Product Features

The contest system has seven core features.

## 7.1 Multimodal sensing

The device should combine multiple complementary signals.

Preferred v1 modalities:

1. SpO₂ / PPG
2. respiratory effort
3. breathing/snoring audio
4. body movement / sleep position

Optional:

5. nasal airflow
6. ECG

The system should not require every modality to be present to run.

---

## 7.2 Adaptive sensing

The system should operate in two main modes.

### LOW-DETAIL MODE

Used when signals appear normal.

Typical active work:

- low-rate SpO₂/PPG monitoring,
- respiratory-effort monitoring,
- movement monitoring,
- lightweight quality checks,
- lightweight trigger logic.

### HIGH-DETAIL MODE

Activated when a suspicious change appears.

Possible triggers:

- respiratory amplitude drops,
- SpO₂ starts trending down,
- unusual breath-sound change,
- repeated irregular breathing,
- event probability from lightweight detector,
- combination of weak signals.

High-detail mode may enable:

- higher-frequency processing,
- audio feature extraction,
- full multimodal inference,
- detailed event logging.

The important systems concept is:

> The board should not spend maximum compute and privacy budget continuously if high-detail processing is only needed around suspicious events.

Adaptive sensing must be implemented as a real state machine, not only described in slides.

Suggested states:

```text
IDLE
  ↓
MONITORING_LOW
  ↓ suspicious trigger
MONITORING_HIGH
  ↓ run inference
EVENT_ACTIVE
  ↓ event ends
RECOVERY
  ↓
MONITORING_LOW
```

Additional states:

```text
SENSOR_FAULT
SESSION_END
```

---

## 7.3 Signal-quality awareness

A medical-signal prototype must know when its input is unreliable.

The system should track quality per modality.

Examples:

### SpO₂/PPG quality problems

- finger sensor disconnected,
- no pulse waveform,
- impossible SpO₂ jump,
- excessive motion.

### Respiratory sensor quality problems

- flatline,
- clipping,
- disconnected belt,
- impossible amplitude jump.

### Audio quality problems

- microphone saturated,
- no microphone stream,
- strong environmental noise.

### Accelerometer quality problems

- stream stopped,
- constant values,
- bus fault.

Output per modality:

```text
liveness = true/false
quality_score = 0.0 ... 1.0
```

Model policy:

```text
If critical modalities are unreliable:
    do not confidently emit "normal"
```

Allowed outputs:

```text
NORMAL
SUSPICIOUS_EVENT
UNCERTAIN
SENSOR_FAULT
```

This is important.

---

# 8. Personalization

Personalization should remain simple for contest v1.

Do **not** make full on-device neural-network retraining a prerequisite.

The v1 personalization layer should learn a user's baseline from an initial stable period.

Possible baseline values:

- median SpO₂,
- SpO₂ variance,
- resting pulse,
- respiratory rate,
- respiratory amplitude,
- motion profile,
- snoring/breathing feature statistics.

Example:

```text
baseline_spo2 = 97.1
baseline_hr = 63
baseline_resp_rate = 14.5
baseline_resp_amp = 0.62
```

Features fed to the AI may use deviations from baseline:

```text
delta_spo2
normalized_resp_amp
relative_hr_change
motion_relative_to_baseline
```

This gives a meaningful personalization story:

```text
global model
     +
individual baseline
     ↓
personalized decision context
```

Stretch personalization:

- fine-tune only the classifier head,
- keep modality encoders frozen,
- maintain both global and personalized model copies.

---

# 9. Triage Layer

The device should not stop at event classification.

Each accepted event should be converted into structured event metadata.

Recommended event record:

```json
{
  "event_id": 42,
  "start_ms": 8452000,
  "end_ms": 8476000,
  "duration_s": 24.0,
  "model_score": 0.91,
  "signal_quality": 0.94,
  "spo2_before": 97,
  "spo2_min": 89,
  "spo2_drop": 8,
  "resp_effort_score": 0.73,
  "movement_score": 0.08,
  "audio_score": 0.81,
  "event_type": "suspicious_respiratory_event"
}
```

At session end compute:

```text
monitoring_duration
valid_monitoring_duration
event_count
events_per_hour
longest_event
minimum_spo2
mean_spo2_drop
time_below_selected_spo2_ranges
oxygen-burden-style metric
average signal quality
fraction of session with missing sensors
```

Triage can combine these values into:

```text
LOW
MODERATE
HIGH
```

This is not a validated clinical score.

The purpose is to demonstrate **meaningful home screening and prioritization**.

---

# 10. Multimodal Inputs and Hardware Paths

The target board is the Renesas EK-RA8P1.

## 10.1 Audio

Source:

```text
onboard PDM MEMS microphone
```

Signals:

- snoring,
- breathing sounds,
- gasps,
- pauses,
- arousal-like acoustic changes.

Processing:

```text
PDM samples
   ↓
audio frames
   ↓
filter / optional downsample
   ↓
log-mel / FFT-style features
   ↓
audio encoder
```

Audio must be processed locally.

Recommended privacy policy:

```text
raw bedroom audio is not exported
```

Contest implementation may optionally avoid persistent raw-audio storage.

---

## 10.2 SpO₂ / PPG

External pulse-oximeter module.

Exact part number is still unresolved.

Preferred interface:

```text
I²C
```

Signals:

- SpO₂,
- raw PPG if available,
- pulse rate,
- pulse waveform quality.

Use:

- oxygen desaturation,
- heart-rate response,
- event severity,
- personal baseline.

Candidate module examples may be evaluated later, but do not hard-code a part number until bench-tested.

---

## 10.3 Respiratory effort

Preferred:

- respiratory belt,
- stretch sensor,
- pressure/effort sensor,
- or another simple chest/abdomen effort sensor.

Possible interface:

```text
ADC
or
I²C/SPI module
```

Use:

- respiration waveform,
- respiratory rate,
- effort amplitude,
- event onset,
- persistence of effort during airflow reduction.

This is a high-value modality.

---

## 10.4 Accelerometer

Preferred external 3-axis accelerometer.

Interface:

```text
I²C or SPI
```

Use:

- body position,
- motion artifact detection,
- sleep posture,
- respiratory/chest motion if sensor placement allows,
- quality gating.

---

## 10.5 Optional nasal airflow

Possible hardware:

- thermistor,
- pressure sensor,
- airflow front end.

Possible interface:

```text
ADC
```

Use:

- direct airflow evidence.

This is useful but should not delay the mandatory system.

---

## 10.6 Optional ECG

Possible hardware:

- ECG analog front end,
- ADC input.

Use:

- additional cardiac context,
- future extension.

Not required for contest v1.

---

# 11. RA8P1 Compute Allocation

The new architecture should deliberately use the board rather than treating it as a generic MCU.

## 11.1 Cortex-M85 — primary real-time core

Responsibilities:

- µT-Kernel execution,
- sensor drivers,
- DMA/ring-buffer management,
- stream timestamps,
- signal preprocessing,
- audio DSP,
- modality synchronization,
- signal-quality monitoring,
- adaptive-sensing state machine,
- event manager,
- invocation of NPU inference,
- display / live telemetry,
- benchmark timers,
- deadline-miss counters.

The M85 owns **hard real-time correctness**.

Sensor acquisition must never depend on ML inference finishing in time.

---

## 11.2 Ethos-U55 NPU — inference accelerator

Responsibilities:

- forward inference for the quantized multimodal model,
- INT8/INT16 network execution where supported.

The NPU does:

```text
inference
```

The NPU does not do:

```text
backpropagation
full training
FedAvg
sensor acquisition
```

Fallback:

If some model operation is not supported by the NPU toolchain, either:

1. redesign the network,
2. allow supported CPU fallback,
3. or temporarily run the complete v1 model on M85 until the NPU version is stable.

The project must first achieve **correct M85 inference** before making the entire prototype dependent on NPU integration.

---

## 11.3 Cortex-M33 — background core

Target responsibilities:

- background classifier-head training,
- federation client,
- update packaging,
- network communication,
- model storage coordination,
- privacy/egress policy.

However:

> M33 integration is not allowed to block the first working vertical slice.

If dual-core support becomes risky, contest v1 may run federation/training externally while still documenting M33 as the intended next integration stage.

---

# 12. Memory Allocation

Target usage:

## M85 TCM

Use for:

- highest-rate ring buffers,
- audio working buffers,
- hottest DSP scratch,
- latency-critical shared state.

## M33 TCM

Future / stretch:

- trainable classifier head,
- gradients,
- optimizer state,
- micro-batch buffers.

## 2 MB on-chip SRAM

Use for:

- NPU activation arena,
- modality feature tensors,
- aligned inference windows,
- model working buffers,
- event state.

## 64 MB external SDRAM

Use for:

- longer replay windows,
- buffered demo data,
- event/feature history,
- session summary state.

## 64 MB OSPI flash

Use for:

- public-dataset replay clips,
- test vectors,
- calibration blobs,
- stored model artifacts,
- event logs if needed.

## 1 MB MRAM

Use for:

- firmware,
- model metadata,
- potentially A/B model slots.

Do not promise atomic OTA model switching until implemented and tested.

---

# 13. µT-Kernel Task Architecture

µT-Kernel must be visibly important to the project.

Suggested task model:

```text
High priority
│
├── sensor_audio_task
├── sensor_ppg_task
├── sensor_resp_task
├── sensor_accel_task
│
├── time_sync_task
├── quality_task
│
├── adaptive_controller_task
│
├── inference_task
│
├── event_manager_task
│
├── ui_task
│
└── federation_task
Low priority
```

Actual priorities must be measured and tuned.

Recommended responsibility split:

## sensor_* tasks

- initialize hardware,
- read samples,
- timestamp samples,
- write to ring buffers,
- never perform heavy model work.

## time_sync_task

Align modalities from different sampling rates onto a common analysis window.

## quality_task

Compute modality health and quality metrics.

## adaptive_controller_task

Switch between low-detail and high-detail modes.

## inference_task

Prepare the aligned tensor and invoke the ML runtime.

## event_manager_task

- debounce predictions,
- start/end events,
- calculate duration,
- calculate oxygen drop,
- persist event metadata.

## ui_task

Update:

- display,
- serial monitor,
- LEDs,
- debug telemetry.

## federation_task

Lowest priority.

Must never cause sensor deadlines to be missed.

---

# 14. Timing Model

Inputs will operate at very different rates.

Example order of magnitude:

```text
audio:         kHz range
accelerometer: tens to hundreds of Hz
resp effort:   tens of Hz
PPG:           tens/hundreds of Hz if raw
SpO₂ summary:  ~1 Hz class of output
```

Exact sampling rates are unresolved and must be selected after hardware validation.

Each signal should have:

```text
timestamp
sample/value
quality
source
```

The M85 should maintain separate ring buffers.

Example:

```text
audio_ring
ppg_ring
spo2_ring
resp_ring
accel_ring
```

Inference windows should be created from a common time interval.

Candidate window:

```text
30 s
```

or:

```text
60 s
```

Possibly with overlap.

Do not lock epoch length until dataset experiments compare latency, AUPRC, memory, and compute cost.

---

# 15. New ML Pipeline

The new ML pipeline must live separately from the historical bearing pipeline.

Recommended layout:

```text
ml/sleep/
├── datasets/
├── preprocess/
├── features/
├── models/
├── training/
├── eval/
├── quantization/
├── federation/
├── personalization/
├── export/
└── artifacts/
```

---

# 16. Dataset Strategy

Use public, labeled sleep datasets for training and replay.

Potential sources include public polysomnography / sleep-apnea datasets such as:

- Apnea-ECG,
- UCD / St. Vincent's sleep datasets,
- MESA,
- SHHS,
- other accessible public PSG datasets.

Do not mix datasets casually.

Required dataset work:

1. define which modalities are available in each dataset,
2. define subject IDs,
3. define event labels,
4. harmonize labels,
5. define common sampling rates,
6. define train/validation/test subjects,
7. prevent subject leakage,
8. define simulated hospital partitions.

Critical rule:

> **Never randomly split overlapping epochs from the same subject across train and test.**

Evaluation must be subject-grouped.

---

# 17. Label Strategy

Contest v1 should prioritize:

```text
normal
vs
suspicious apnea/hypopnea event
```

Avoid starting with a complicated multi-class sleep-disease taxonomy.

Possible future classes:

```text
normal
obstructive-like
central-like
hypopnea-like
uncertain
```

But binary event detection is the safer first target.

---

# 18. Feature / Model Strategy

Do not reuse the old 38 bearing features.

New model inputs should come from sleep modalities.

Two acceptable v1 approaches:

## Option A — feature-based fusion

For each modality derive compact features.

Examples:

### SpO₂ / PPG

- current SpO₂,
- baseline-relative SpO₂,
- slope,
- desaturation depth,
- rolling variance,
- pulse rate,
- pulse-rate change,
- PPG quality.

### respiratory effort

- amplitude,
- respiratory rate,
- zero-crossing / cycle features,
- effort reduction,
- baseline-relative effort,
- variance.

### accelerometer

- activity magnitude,
- orientation,
- motion score,
- posture category.

### audio

- log-mel features,
- spectral energy,
- snoring probability,
- breathing-sound probability.

Then concatenate:

```text
[SpO₂ features]
      +
[respiration features]
      +
[motion features]
      +
[audio features]
      ↓
small MLP / temporal head
```

This is easiest for fast embedded integration.

---

## Option B — small per-modality encoders + late fusion

Example:

```text
audio window
  ↓
tiny 1D CNN
  ↓
audio embedding
              \
SpO₂ sequence  \
  ↓             \
small temporal   \
encoder           \
                   → concatenate → dense head → event score
resp sequence     /
  ↓              /
small encoder   /
               /
accel sequence
  ↓
small encoder
```

This is more powerful, but more difficult to integrate.

Recommended development sequence:

```text
feature-based model first
        ↓
working embedded inference
        ↓
then attempt tiny late-fusion encoders
```

Do not sacrifice the working prototype for a more sophisticated architecture.

---

# 19. Missing-Modality Robustness

The system must not break if one sensor disappears.

Training should include modality dropout.

Example:

```python
during training:
    randomly zero or mask one modality
```

Model inputs should include modality-presence masks.

Example:

```text
audio_present
spo2_present
resp_present
accel_present
```

Inference should distinguish:

```text
missing sensor
```

from:

```text
true zero signal
```

If a critical stream fails:

```text
prediction_status = UNCERTAIN
```

instead of:

```text
prediction = NORMAL
```

This feature is important for real-world credibility.

---

# 20. Quantization and Embedded Export

The final contest model should target quantized inference.

Preferred first target:

```text
INT8
```

Pipeline:

```text
trained model
    ↓
representative calibration data
    ↓
full-integer quantization
    ↓
TFLite / compatible artifact
    ↓
NPU toolchain / Vela where supported
    ↓
embedded model artifact
```

Maintain:

```text
input scale
input zero point
output scale
output zero point
```

Create golden vectors.

Each golden vector should contain:

```text
input features/tensor
expected quantized input
expected output logits/probability
expected class
```

Mandatory validation:

```text
PC float model
vs
PC INT8 model
vs
board inference
```

Outputs must match within defined tolerance.

---

# 21. Golden-Vector Test Strategy

This worked well in the historical bearing pipeline and should be preserved.

Recommended artifact:

```text
ml/sleep/artifacts/golden_vectors.json
```

Include examples of:

- normal epoch,
- apnea epoch,
- borderline epoch,
- low-signal-quality epoch,
- missing-modality epoch.

Firmware test mode:

```text
load golden vector
      ↓
run preprocessing
      ↓
run inference
      ↓
compare output
      ↓
PASS / FAIL
```

This becomes the bridge between ML and firmware teams.

---

# 22. Adaptive-Sensing Logic

Adaptive sensing must be implemented separately from the heavy model.

Recommended first trigger:

```text
if respiration amplitude falls sharply
OR SpO₂ trend becomes suspicious
OR lightweight event score > threshold
    switch to HIGH_DETAIL
```

Pseudocode:

```text
MONITORING_LOW:
    sample baseline streams
    update signal quality
    update cheap trigger

    if trigger:
        enter MONITORING_HIGH

MONITORING_HIGH:
    enable extra processing
    compute full features
    run multimodal model

    if event_score high:
        enter EVENT_ACTIVE
    else if timeout:
        return MONITORING_LOW

EVENT_ACTIVE:
    keep high-detail processing
    accumulate event metadata

    if event ends:
        finalize event
        enter RECOVERY

RECOVERY:
    wait short stabilization period
    return MONITORING_LOW
```

This state machine should have unit tests.

---

# 23. Overnight Triage Logic

The final report should aggregate accepted events.

Suggested data structure:

```c
typedef struct {
    uint32_t total_valid_seconds;
    uint32_t event_count;
    float events_per_hour;
    float longest_event_seconds;
    float minimum_spo2;
    float mean_spo2_drop;
    float oxygen_burden_score;
    float mean_signal_quality;
    float valid_data_fraction;
    uint8_t triage_level;
} sleep_session_summary_t;
```

The triage level may be based on a simple research scoring function.

Example:

```text
risk_score =
    event_frequency_weight
  + oxygen_drop_weight
  + duration_weight
  + low_spo2_time_weight
  + confidence_weight
```

Do not call the resulting score clinically validated.

---

# 24. Explainable Event Output

The prototype should explain **why** it flagged an event.

This does not require SHAP on-device.

Use rule-based post-inference evidence.

Example:

```text
Possible respiratory event

Main evidence:
- breathing effort reduced 62%
- SpO₂ dropped 7%
- snoring/breathing acoustic score changed
- movement low
- signal quality high
```

This gives interpretable output without adding a second expensive model.

---

# 25. Federated Learning

Federated learning remains a core architectural feature.

Contest v1 should use a **PC-side federation simulator** first.

Each simulated hospital contains different subjects.

Example:

```text
Hospital A → subjects 01–10
Hospital B → subjects 11–20
Hospital C → subjects 21–30
Hospital D → subjects 31–40
```

Each site:

1. receives global weights,
2. trains locally,
3. keeps raw subject data local,
4. sends only the permitted model update,
5. server aggregates,
6. receives updated global model.

Basic aggregation:

```text
FedAvg
```

Metrics:

- local-only AUPRC,
- global federated AUPRC,
- sensitivity,
- specificity,
- per-site performance,
- leave-one-site-out performance,
- personalized performance after local adaptation.

Do not make claims that federation inherently improves all sites.

Measure it.

---

# 26. Federation Payload

Recommended first payload:

```json
{
  "round_id": 3,
  "client_id": "hospital_b",
  "sample_count": 1842,
  "model_version": "sleep-v1",
  "shared_weights": "...",
  "metrics": {
    "local_loss": 0.31
  }
}
```

Server validation:

- expected round,
- expected tensor shapes,
- reject NaN/Inf,
- reject corrupted payloads,
- reject impossible weight norms.

Contest v1 may serialize with a simple binary or NumPy format.

A production-grade federation protocol is out of scope.

---

# 27. What Should Federate?

Preferred architecture:

```text
modality encoders
    mostly frozen

fusion / classifier head
    trainable
```

Then federate the small shared head.

Advantages:

- smaller payload,
- easier on-device adaptation,
- less memory,
- faster local training,
- easier M33 future integration.

If the v1 model is a simple MLP, federate the entire small model first.

Do not over-engineer until measured.

---

# 28. On-Device Training

On-device training on M33 is a **stretch integration goal**, not the first milestone.

If implemented:

- only train a tiny head,
- use FP32 or a carefully supported training format,
- micro-batches only,
- strict memory budget,
- low-priority scheduling,
- never interfere with M85 sensor deadlines.

Required proof before claiming it:

```text
0 missed sensor deadlines during background training
```

If this cannot be demonstrated, move training to a host-side simulation and describe M33 training as planned future work.

---

# 29. Privacy Model

Contest privacy rule:

```text
raw biosignal waveforms stay local by default
```

Raw data that should not leave the node in the intended architecture:

- microphone audio,
- PPG waveform,
- respiration waveform,
- accelerometer waveform,
- subject labels.

Allowed outbound data:

- aggregated session summary,
- debug data during development,
- model updates during federation,
- benchmark metadata.

For the contest development environment, debugging may temporarily export raw data.

Document when debug mode differs from the intended privacy model.

---

# 30. Board I/O Usage

Target board interfaces:

## PDM microphone

```text
audio input
```

## I²C / SPI / expansion headers

```text
SpO₂ / PPG
accelerometer
other digital sensors
```

## ADC / Arduino analog pins

```text
respiratory effort
optional airflow
optional ECG
```

## Ethernet

```text
federation / model-update transport
```

## MIPI display

```text
live clinician / demo dashboard
```

## USB

```text
session export
benchmark dump
development
```

## UART / J-Link / RTT

```text
debug logs
deadline metrics
timing
```

## LEDs / buttons

```text
recording
liveness
event / error indication
start / stop session
```

---

# 31. Pin / Peripheral Constraints

Important board constraints must be respected.

Known planning issues include:

- OSPI and some expansion interfaces share pins through board switching.
- parallel display and parallel camera paths conflict.
- some headers may be unpopulated.
- the exact active pin configuration must be verified in the generated FSP pin configuration before wiring.

Do not assume a board connector is usable just because it physically exists.

Before adding a sensor:

1. inspect `bsp_pin_cfg.h`,
2. inspect `configuration.xml`,
3. verify switch/jumper configuration,
4. create driver instance in FSP if required,
5. regenerate code,
6. test the peripheral in isolation.

---

# 32. Display / Demo UI

The demo UI should show only useful information.

Recommended live view:

```text
FedTinyRT Sleep

SpO₂: 96%
Pulse: 71 bpm
Respiration: 14/min
Position: Supine

Signal quality:
SpO₂      GOOD
Resp      GOOD
Audio     GOOD
Motion    GOOD

Mode:
HIGH-DETAIL

Event probability:
0.87

Status:
POSSIBLE RESPIRATORY EVENT
```

Nightly summary:

```text
Session: 6 h 42 m
Valid data: 94%

Events: 42
Events/hour: 6.3
Longest event: 29 s
Minimum SpO₂: 87%
Oxygen burden: elevated

Research triage:
MODERATE

Recommendation:
Consider formal sleep evaluation.
```

No unsupported medical claim.

---

# 33. Metrics

Do not use ordinary accuracy as the headline metric.

Primary ML metrics:

- AUPRC / average precision,
- sensitivity / recall,
- specificity,
- AUROC as secondary,
- per-subject metrics,
- per-site metrics.

Session-level metrics:

- event-count error,
- event timing error,
- approximate events/hour error,
- oxygen-burden correlation/error where applicable.

Embedded metrics:

- feature/preprocessing latency,
- inference latency,
- full pipeline latency,
- RAM usage,
- flash/model size,
- CPU load,
- NPU load if measurable,
- sensor deadline misses,
- jitter,
- energy/power if measurable.

Key systems metric:

```text
sensor deadline misses = 0
```

during normal inference.

---

# 34. CPU vs NPU Benchmark

To prove the RA8P1 matters, run the same quantized model in two modes if possible:

```text
Mode A:
M85 CPU inference

Mode B:
Ethos-U55 inference
```

Compare:

- inference latency,
- CPU occupancy,
- sensor jitter,
- missed deadlines,
- throughput,
- energy if available.

Do not use Renesas marketing benchmark numbers as project results.

Only report measured FedTinyRT values.

---

# 35. Recommended Repository Restructure

Target structure:

```text
fedtinyrt/
│
├── src/
│   ├── app/
│   │   ├── app_main.c
│   │   ├── session_manager.c
│   │   ├── adaptive_controller.c
│   │   ├── event_manager.c
│   │   └── triage.c
│   │
│   ├── sensors/
│   │   ├── audio_pdm.c
│   │   ├── spo2_ppg.c
│   │   ├── respiration.c
│   │   ├── accelerometer.c
│   │   └── sensor_quality.c
│   │
│   ├── dsp/
│   │   ├── audio_features.c
│   │   ├── ppg_features.c
│   │   ├── respiration_features.c
│   │   ├── motion_features.c
│   │   └── window_sync.c
│   │
│   ├── ml/
│   │   ├── inference.c
│   │   ├── model_data.c
│   │   ├── model_data.h
│   │   ├── quantization.c
│   │   └── golden_test.c
│   │
│   ├── federation/
│   │   ├── federation_client.c
│   │   └── model_update.c
│   │
│   ├── ui/
│   │   ├── display.c
│   │   └── telemetry.c
│   │
│   └── usermain.c
│
├── ml/
│   ├── legacy_bearing/
│   │
│   └── sleep/
│       ├── datasets/
│       ├── preprocess/
│       ├── features/
│       ├── models/
│       ├── training/
│       ├── eval/
│       ├── quantization/
│       ├── federation/
│       ├── personalization/
│       ├── export/
│       └── artifacts/
│
├── tests/
│   ├── host/
│   └── golden/
│
├── docs/
│   ├── PROJECT_BRIEF.md
│   ├── HARDWARE.md
│   ├── MODEL_CARD.md
│   └── FEDERATION.md
│
└── context.md
```

This structure is a recommendation, not a requirement.

---

# 36. Migration Plan From Current Code

Do not rewrite everything at once.

## Phase 0 — preserve working baseline

Before modifications:

- create git tag / branch,
- verify µT-Kernel boot,
- verify serial output,
- verify current debug build.

Recommended tag:

```text
pre-sleep-pivot
```

---

## Phase 1 — rename the current application concept

Update:

- README,
- context,
- system overview,
- architecture diagrams,
- stale FoG references.

Do not delete the historical documentation immediately.

Mark it as:

```text
legacy / previous target
```

---

## Phase 2 — create new PC sleep ML pipeline

Goal:

```text
public sleep data
      ↓
preprocessing
      ↓
binary event model
      ↓
evaluation
      ↓
INT8 export
      ↓
golden vectors
```

This must work before embedded ML integration.

---

## Phase 3 — replay pipeline on board

Before real sensors:

```text
public recorded epoch
      ↓
OSPI / compiled array / USB
      ↓
M85 preprocessing
      ↓
model inference
      ↓
correct result
```

This is the first major vertical slice.

---

## Phase 4 — real sensor integration

Integrate one sensor at a time.

Recommended order:

1. SpO₂ / PPG
2. respiratory effort
3. accelerometer
4. PDM audio

Each sensor needs:

- standalone driver test,
- timestamping,
- ring buffer,
- quality metric.

---

## Phase 5 — adaptive sensing

Implement state machine.

Test using replayed events before relying on live physiology.

---

## Phase 6 — event manager and triage

Implement event records and session summary.

---

## Phase 7 — NPU integration

Only after CPU inference is stable.

---

## Phase 8 — federation and personalization

Federation can run on PC first.

Personal baseline normalization should already be integrated into model features.

---

## Phase 9 — M33 stretch work

Attempt only if all mandatory components are stable.

---

# 37. Mandatory Vertical Slice

The project is not considered integrated until this works:

```text
real/replayed sleep epoch
        ↓
M85 receives data
        ↓
µT-Kernel task scheduling
        ↓
preprocessing
        ↓
signal-quality check
        ↓
model inference
        ↓
event score
        ↓
event manager
        ↓
visible output
```

Minimum output:

```text
window_id
signal_quality
event_probability
normal/suspicious/uncertain
inference_latency
```

This is the single most important milestone.

---

# 38. Minimum Contest-V1 Feature Set

Mandatory:

- EK-RA8P1 boots µT-Kernel.
- real RTOS tasks exist.
- at least two physiological modalities are ingested or faithfully replayed.
- signal-quality logic works.
- adaptive-sensing state machine works.
- a genuine sleep-apnea model runs on board.
- output includes normal / suspicious / uncertain.
- event duration and oxygen drop are recorded.
- personalization uses user baseline normalization.
- nightly research triage is produced.
- PC-side federated learning is demonstrated.
- raw data vs model-update privacy boundary is documented.
- latency/RAM/model-size are measured.
- golden vectors pass.

Strongly desired:

- onboard PDM audio,
- accelerometer,
- NPU inference,
- real SpO₂ sensor,
- display UI.

Stretch:

- M33 training,
- Ethernet federation between physical boards,
- TrustZone privacy gate,
- contactless camera,
- multi-class apnea typing,
- ECG.

---

# 39. Acceptance Criteria

## Firmware

PASS when:

- board boots reliably,
- tasks start,
- no sensor task deadlocks,
- replay test produces correct predictions,
- sensor buffers do not overflow under target configuration,
- no missed sensor deadlines under normal inference.

## ML

PASS when:

- subject-grouped split is enforced,
- float model metrics are recorded,
- quantized model metrics are recorded,
- quantization degradation is acceptable,
- golden vectors are generated.

## Embedded inference

PASS when:

- board output matches golden reference within tolerance,
- latency is measured,
- memory use is documented.

## Adaptive sensing

PASS when:

- LOW → HIGH mode transition occurs on test events,
- HIGH → LOW recovery occurs,
- no repeated trigger loop,
- sensor-fault path works.

## Personalization

PASS when:

- a baseline is stored,
- normalized features use the baseline,
- output differs appropriately when baseline changes in a controlled test.

## Triage

PASS when:

- accepted events accumulate,
- duration and SpO₂ drop are calculated,
- session summary is generated,
- triage output is deterministic for the same session.

## Federation

PASS when:

- clients have disjoint subject groups,
- local training works,
- FedAvg runs,
- global model redistributes,
- per-client metrics are recorded.

---

# 40. Failure Policy

The system should fail safely.

Examples:

```text
SpO₂ sensor missing
→ mark modality missing
→ do not silently replace with fake values
```

```text
audio driver fails
→ run reduced-modality model if supported
→ lower confidence
```

```text
model inference fails
→ report inference error
→ continue sensor acquisition
```

```text
Ethernet unavailable
→ continue local screening
→ defer federation
```

```text
M33 unavailable
→ continue M85 screening
→ federation/training disabled
```

Local screening must not depend on network availability.

---

# 41. Non-Goals for Contest V1

Do not spend contest time building:

- a clinically validated diagnosis device,
- full polysomnography replacement,
- production HIPAA/GDPR compliance,
- cloud hospital infrastructure,
- a mobile app ecosystem,
- full secure OTA,
- full TrustZone isolation,
- sophisticated clinical sleep staging,
- on-device large-model training,
- five disease detectors,
- camera-based monitoring,
- exact obstructive vs central diagnostic classification unless the core project is already complete.

These are future extensions.

---

# 42. Security / Privacy Boundaries

Development mode and intended product mode are different.

## Development mode

May allow:

- raw serial dumps,
- dataset replay,
- USB signal export,
- debugging.

## Intended contest architecture

Should emphasize:

- local inference,
- local raw audio processing,
- local raw physiological data,
- summaries/model weights only cross network boundary.

Do not claim hardware-enforced privacy until TrustZone/egress controls are actually implemented.

---

# 43. Demo Story

Final demo should be understandable in under two minutes.

Recommended sequence:

## Step 1

Show live/replayed normal sleep.

```text
Mode: LOW-DETAIL
Status: NORMAL
```

## Step 2

Replay or trigger suspicious breathing pattern.

```text
respiration decreases
SpO₂ trend changes
```

## Step 3

Adaptive controller switches:

```text
LOW-DETAIL
    ↓
HIGH-DETAIL
```

## Step 4

Full model runs.

```text
Possible respiratory event
Confidence: 0.91
```

## Step 5

Show evidence.

```text
SpO₂ drop
respiration change
audio score
movement quality
```

## Step 6

Show event added to nightly summary.

## Step 7

Show patient baseline / personalization.

## Step 8

Show federated-learning visualization on PC.

```text
Hospital A
Hospital B
Hospital C
      ↓
FedAvg
      ↓
new global model
```

## Step 9

Show CPU vs NPU benchmark if complete.

This tells one coherent story.

---

# 44. Why RA8P1 Matters

The board must be justified with measured system behavior.

Project thesis:

```text
M85
handles deterministic real-time sensing + DSP

U55
handles neural-network inference

M33
can handle low-priority adaptation/federation

µT-Kernel
coordinates deadlines and task isolation
```

The board matters because this workload combines:

- high-rate audio,
- lower-rate physiological sensors,
- DSP,
- AI,
- UI,
- logging,
- communication,
- and potentially background adaptation.

The strongest proof is not a specification table.

The strongest proof is:

```text
sensor deadline misses with CPU-only inference
vs
sensor deadline misses / CPU occupancy with NPU inference
```

plus measured latency.

---

# 45. Coding Rules

For embedded code:

- no dynamic allocation in hard real-time paths unless justified,
- bounded loops,
- explicit buffer sizes,
- no blocking networking from sensor tasks,
- no printf spam in high-rate loops,
- no ML work inside interrupt handlers,
- ISR should signal tasks / fill buffers only,
- use monotonic timestamps,
- centralize error codes,
- track dropped samples,
- track buffer overruns.

For ML code:

- deterministic seeds where practical,
- subject-grouped splits,
- no train/test leakage,
- preprocessing parameters saved,
- model artifacts versioned,
- export metadata saved,
- float vs quantized evaluation both recorded.

---

# 46. Artifact Versioning

Every exported model should have metadata.

Example:

```json
{
  "model_name": "fedtinyrt_sleep_v1",
  "model_version": "0.3.0",
  "dataset_version": "apnea_mix_v2",
  "window_seconds": 30,
  "modalities": [
    "spo2",
    "respiration",
    "accel",
    "audio"
  ],
  "quantization": "int8",
  "input_shape": "...",
  "created_at": "...",
  "git_commit": "..."
}
```

Firmware should expose the active model version over telemetry.

---

# 47. Data Contracts

Define contracts early.

## Sensor sample

```c
typedef struct {
    uint64_t timestamp_us;
    float value;
    float quality;
    uint8_t source;
} scalar_sample_t;
```

## Modality state

```c
typedef struct {
    bool present;
    bool live;
    float quality;
    uint64_t last_sample_us;
} modality_state_t;
```

## Inference output

```c
typedef struct {
    float event_probability;
    float signal_quality;
    uint8_t prediction;
    uint32_t inference_time_us;
} inference_result_t;
```

Exact types may change, but the contracts should remain explicit.

---

# 48. Required New Documentation

The repository should eventually contain:

```text
README.md
context.md
PROJECT_BRIEF.md
HARDWARE.md
MODEL_CARD.md
DATASET.md
FEDERATION.md
DEMO.md
SETUP_NOTES.md
```

The old Parkinson/FoG documents must either:

- be rewritten,
- moved to `docs/legacy/`,
- or clearly marked obsolete.

Do not leave contradictory top-level docs.

---

# 49. Recommended Issue / Milestone Breakdown

## S0 — preserve baseline

- boot
- serial
- git tag
- clean build

## S1 — sleep ML baseline

- dataset
- preprocessing
- grouped split
- binary model
- metrics

## S2 — quantization

- INT8
- golden vectors
- C/TFLite artifact

## S3 — board replay

- sample window on board
- preprocessing
- CPU inference

## S4 — sensor framework

- ring buffers
- timestamps
- quality state

## S5 — SpO₂ + respiration

- real drivers
- live data
- quality checks

## S6 — adaptive sensing

- state machine
- triggers
- recovery

## S7 — event manager / triage

- event records
- nightly summary

## S8 — audio + accelerometer

- multimodal fusion

## S9 — NPU

- Vela/toolchain
- U55 inference
- benchmark

## S10 — federation

- multi-site simulation
- metrics
- personalization

## S11 — M33 stretch

- background training / federation

## S12 — demo hardening

- UI
- README
- benchmarks
- video
- final clean build

---

# 50. Definition of Done

FedTinyRT Sleep is contest-ready when a reviewer can see:

1. a real EK-RA8P1 running µT-Kernel,
2. real tasks, not a single blocking loop,
3. sleep-related signals entering the board,
4. quality-aware adaptive sensing,
5. a quantized sleep-apnea model running locally,
6. visible normal/suspicious/uncertain output,
7. event duration and oxygen effect being tracked,
8. per-user baseline personalization,
9. an overnight triage summary,
10. a working federated-learning experiment,
11. measured embedded latency/memory,
12. and a clear reason the RA8P1 architecture matters.

The project does **not** need to finish every future feature to be strong.

The priority order is:

```text
CORRECTNESS
   ↓
END-TO-END INTEGRATION
   ↓
REAL-TIME RELIABILITY
   ↓
MEASUREMENTS
   ↓
ADAPTIVE + PERSONALIZED BEHAVIOR
   ↓
FEDERATION
   ↓
NPU OPTIMIZATION
   ↓
M33 / SECURITY STRETCH WORK
```

---

# 51. Immediate Next Actions

The next development session should begin with the following tasks.

## Repository

- create `pre-sleep-pivot` tag/branch,
- move old bearing ML scripts under `ml/legacy_bearing/`,
- create `ml/sleep/`,
- update top-level docs to point to this context file.

## ML

- choose the first public dataset,
- define subject-level train/val/test split,
- build a minimal binary apnea-event baseline,
- export preprocessing metadata,
- quantify with AUPRC/sensitivity/specificity,
- export first INT8 model,
- generate golden vectors.

## Firmware

- preserve current µT-Kernel boot,
- replace sleep-forever `usermain()` behavior with task creation,
- create generic ring-buffer and timestamp infrastructure,
- implement board replay mode before real sensors,
- pass one golden vector end-to-end.

## Hardware

- finalize SpO₂/PPG module,
- finalize respiratory-effort sensor,
- finalize accelerometer,
- verify available pins and switch configuration,
- bring up one sensor at a time.

## Integration

The first major milestone is:

```text
public/replayed sleep epoch
        ↓
RA8P1
        ↓
µT-Kernel
        ↓
preprocessing
        ↓
INT8 inference
        ↓
correct event result
```

Everything else builds on this.

---

# 52. Final Engineering Principle

FedTinyRT should not become a collection of impressive words:

```text
multimodal
federated
personalized
NPU
adaptive
privacy
```

Every concept must solve a real system problem.

```text
Multimodal
→ one noisy sensor should not decide everything.

Adaptive sensing
→ high-detail processing is used when it is actually needed.

Signal quality
→ the device knows when data is unreliable.

Personalization
→ "normal" differs between people.

Triage
→ the output helps prioritize who needs formal evaluation.

Federation
→ sites improve a shared model without pooling raw recordings.

NPU
→ AI does not steal real-time CPU budget.

µT-Kernel
→ all of those jobs happen predictably and concurrently.
```

That is the core engineering story of the new FedTinyRT.
