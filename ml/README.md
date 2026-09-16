# FedTinyRT ML

The existing feature -> small MLP -> INT8 -> golden-vector workflow now has a
[sleep pipeline](sleep/README.md). Run it as modules from the repository root.

The original bearing experiments and checked-in artifacts are preserved in
[legacy_bearing](legacy_bearing/README.md). Their recorded results are historical,
not sleep-screening results. Existing raw downloads remain under `ml/data/`.

Legacy commands have moved, for example `py ml/legacy_bearing/train_tflite.py`.
Sleep commands use `py -m ml.sleep.train_tflite --help`.
