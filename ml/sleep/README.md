# Sleep adaptation of the existing PC pipeline

Implemented source: feature extraction from aligned modality summaries, a binary
18 -> 32 -> 16 -> 1 MLP, subject-only train/validation/test splits, training-only
scaling, modality dropout, full INT8 conversion through SavedModel, C arrays,
golden vectors, and sample-weighted PC FedAvg with local adaptation.

There is no real sleep dataset in this checkout. Synthetic fixtures test software
plumbing only. Their labels and waveforms are invented and their metrics must not
be used as sleep-apnea performance claims.

## Reproduce from the repository root

```powershell
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r ml/sleep/requirements.txt
.venv/Scripts/python.exe -m ml.sleep.synthesize
.venv/Scripts/python.exe -m ml.sleep.train_tflite --data ml/sleep/data/synthetic.npz --epochs 2 --allow-synthetic
.venv/Scripts/python.exe -m ml.sleep.verify
.venv/Scripts/python.exe -m ml.sleep.federate --data ml/sleep/data/synthetic.npz --rounds 1 --allow-synthetic
.venv/Scripts/python.exe -m pytest -q tests/test_sleep_ml.py --basetemp .cache/pytest-sleep
```

On this workstation the Windows `py` launcher has no registered interpreter. A
project-local `.venv` was created using the existing Blender-bundled Python;
the commands beginning `.venv/Scripts/python.exe` are usable directly.

Artifacts remain ignored at `ml/sleep/artifacts/`: model, scaler, preprocessing
contract, model metadata/checksum, subject splits, float/INT8/per-subject metrics,
golden vectors, C model arrays, and federation results/global weights. Each model
records whether it is synthetic. Export requires explicit `--allow-synthetic` for
fixture datasets. Generated arrays are not yet linked to a firmware ML runtime.

## Real-data input contract

Supply an NPZ loaded with `allow_pickle=False`, containing:

| Key | Contract |
| --- | --- |
| `epochs` | float `[N,T,4]`: SpO2 percent, respiratory amplitude envelope, motion magnitude, audio RMS envelope |
| `quality` | float `[N,T,4]`, scores in 0..1; invalid values mask the sample |
| `baselines` | float `[N,2]`: personal SpO2 and positive respiratory-amplitude baseline |
| `labels` | integer `[N]`: 0 normal-labelled epoch, 1 event-labelled epoch |
| `subjects` | nonempty Unicode `[N]`; same person retains same ID across all recordings |
| `sample_hz` | positive scalar; common summary rate, 1 Hz for fixtures |
| `dataset_version` | scalar string identifying the reviewed source/version |
| `synthetic` | scalar boolean, `false` only for actual recordings |

All four summary streams must describe the same time interval. This contract
does **not** accept raw microphone audio, PPG or respiration waveforms as envelope
values. Dataset-specific alignment, filtering, envelope extraction, sample-rate
conversion and label harmonization must be reviewed when a real dataset is chosen.
Missing streams use NaNs and zero quality, not invented normal values.

Supply baselines derived from an independent stable initial calibration period;
exclude calibration windows from evaluation, and never select them using held-out
event labels. Causal deployment must use only prior observations. The C replay
controller demonstrates online stable-period calibration; the PC importer expects
that calibration already prepared in `baselines`.

Features are per-modality mean/std/slope, baseline-relative SpO2/respiration and
four presence masks. Each modality needs >=80% usable samples at quality >=0.5.
Scaler statistics are fitted only to present training rows. Absent modalities
remain zero after scaling. A masked critical modality means `UNCERTAIN` in the
decision layer even if the classifier probability is small.

At least five distinct subjects are required; training, validation and test must
each contain both labels. Federation defaults to three disjoint sites, each of
which also needs five subjects. It uses a frozen coordinate system fitted to
site-0 training data; this is development preprocessing configuration, not an
implemented privacy-preserving preprocessing protocol. Test subjects never train.
Leave-one-site-out evaluation is pending.

## Public candidate

[PhysioNet Apnea-ECG 1.0.0](https://physionet.org/content/apnea-ecg/1.0.0/) provides
eight recordings with SpO2 and respiratory signals. It can support early replay,
but has minute annotations, no matching audio/motion streams, and requires a
verified person-to-record mapping for subject-held-out experiments. The source
[paper](https://physionet.org/files/challenge-2000/1.0.0/papers/apnea-ecg-cinc-2000.pdf)
reports repeated recordings per subject. Do not assume record IDs are subject IDs
or infer precise event durations from minute labels. No download/import is automated
yet; the synthetic fixture remains the selected software-test input.
