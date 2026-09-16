import numpy as np
import pytest
from ml.sleep.dataset import load, split_subjects, partition_sites
from ml.sleep.feature_extract import extract, fit_scaler, normalize, modality_dropout
from ml.sleep.federate import fedavg
from ml.sleep.synthesize import generate
from ml.sleep.train_tflite import quantize


def test_grouping_and_determinism(tmp_path):
    path = generate(tmp_path/"fixture.npz")
    x, y, subjects, meta = load(path)
    assert x.shape[1] == 18 and meta["synthetic"]
    parts = split_subjects(y, subjects)
    groups = [set(subjects[rows]) for rows in parts.values()]
    assert all(not groups[i] & groups[j] for i in range(3) for j in range(i))
    assert all(np.array_equal(rows, split_subjects(y, subjects)[name]) for name, rows in parts.items())
    sites = [set(subjects[r]) for r in partition_sites(subjects, 3)]
    assert all(not sites[i] & sites[j] for i in range(3) for j in range(i))


def test_presence_quality_and_baseline():
    e = np.tile([97., 1., 0., .2], (30, 1)); q = np.ones_like(e)
    a = extract(e, q, [97, 1])
    b = extract(e, q, [99, 2])
    assert a[12] == 0 and b[12] == -2 and b[13] == .5
    assert a[16] == 1  # real zero motion is present
    e[:, 3] = np.nan
    q[:, 0] = .1
    c = extract(e, q, [97, 1])
    assert c[14] == c[17] == 0
    assert np.isfinite(c).all()
    assert np.all(c[[0, 1, 2, 9, 10, 11, 12]] == 0)


def test_missing_stays_masked_after_scaling():
    x = np.zeros((3, 18), np.float32)
    x[0, [0, 14]] = [97, 1]; x[1, [0, 14]] = [99, 1]
    mean, std = fit_scaler(x)
    assert mean[0] == 98 and std[0] == 1
    z = normalize(x, mean, std)
    assert z[2, 0] == 0 and z[2, 14] == 0
    dropped = modality_dropout(z, np.random.default_rng(1), probability=1)
    assert np.all(dropped == 0)


def test_int8_saturates_without_wrap():
    assert quantize([-1000, -128, 0, 127, 1000], 1, 0).tolist() == [-128, -128, 0, 127, 127]
    with pytest.raises(ValueError): quantize([1], 0, 0)
    with pytest.raises(ValueError): quantize([np.nan], 1, 0)


def payload(client, count, weights):
    return dict(client_id=client, sample_count=count, shared_weights=[np.array(weights, np.float32)],
                round_id=2, model_version="sleep-v1")


def test_fedavg_weights_and_validation():
    a, b = payload("a", 1, [1, 3]), payload("b", 3, [5, 7])
    assert np.allclose(fedavg([a, b], [(2,)], 2)[0], [4, 6])
    with pytest.raises(ValueError): fedavg([a, a], [(2,)], 2)
    with pytest.raises(ValueError): fedavg([a], [(2,)], 3)
    with pytest.raises(ValueError): fedavg([a], [(3,)], 2)
    with pytest.raises(ValueError): fedavg([payload("a", 1, [np.nan, 0])], [(2,)], 2)
    with pytest.raises(ValueError): fedavg([payload("a", 0, [1, 0])], [(2,)], 2)
    with pytest.raises(ValueError): fedavg([payload("a", 1, [1e9, 0])], [(2,)], 2)


def test_reject_unknown_labels_and_missing_subjects(tmp_path):
    path = generate(tmp_path/"fixture.npz")
    with np.load(path) as d:
        data = dict(d)
    data["labels"][0] = 2
    np.savez(path, **data)
    with pytest.raises(ValueError): load(path)
