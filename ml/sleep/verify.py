"""Replay exported golden vectors against the actual INT8 interpreter on the PC."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .feature_extract import normalize, SCHEMA
from .train_tflite import quantize


def verify(directory):
    import tensorflow as tf
    directory = Path(directory)
    golden = json.loads((directory/"golden_vectors.json").read_text())
    prep = json.loads((directory/"preprocessing.json").read_text())
    metadata = json.loads((directory/"metadata.json").read_text())
    blob = (directory/"model_int8.tflite").read_bytes()
    if metadata != golden["metadata"] or hashlib.sha256(blob).hexdigest() != metadata["sha256"]:
        raise ValueError("Model/golden metadata or model checksum mismatch")
    if prep["schema"] != SCHEMA or prep["feature_names"] != metadata["feature_names"]:
        raise ValueError("Feature schema mismatch")
    model = tf.lite.Interpreter(model_content=blob)
    model.allocate_tensors()
    inp, out = model.get_input_details()[0], model.get_output_details()[0]
    for v in golden["vectors"]:
        normalized = normalize(np.asarray([v["features"]], np.float32), np.array(prep["mean"]), np.array(prep["std"]))
        np.testing.assert_allclose(normalized[0], v["feat_norm"], rtol=1e-5, atol=1e-5)
        q = quantize(normalized, *inp["quantization"])
        np.testing.assert_array_equal(q[0], v["in_int8"])
        model.set_tensor(inp["index"], q)
        model.invoke()
        actual = model.get_tensor(out["index"])[0].astype(int)
        if np.max(np.abs(actual-np.array(v["out_int8"]))) > golden["output_tolerance_lsb"]:
            raise ValueError(f"Golden output mismatch: {v['case']}")
    return len(golden["vectors"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifacts", type=Path, default=Path("ml/sleep/artifacts"))
    a = p.parse_args()
    print(f"PASS: {verify(a.artifacts)} PC INT8 golden vectors (board verification separate)")
