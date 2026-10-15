"""
MobileNetV2 inference wrapper.

Loads the trained, fine-tuned MobileNetV2 classifier (Spiral 3 deliverable)
lazily as a singleton so it's read into memory once per process, not once
per request. If no trained model file is present yet (e.g. fresh clone,
model still being trained), it transparently falls back to a deterministic
"demo" predictor so the rest of the system — routes, templates, database,
feedback loop — stays fully exercisable without the real weights.

Swap in the real model by training it and dropping the .h5 file + a
class_indices.json (Keras' `train_generator.class_indices`, inverted) at
the paths configured in app/config.py.
"""
import hashlib
import json
import os
import time

import numpy as np

_model = None
_class_names = None
_using_demo_model = False


def _load_class_names(class_index_path, fallback_names):
    if os.path.exists(class_index_path):
        with open(class_index_path) as f:
            index_to_name = json.load(f)
        # keys are string indices ("0", "1", ...) -> sort numerically
        ordered = [index_to_name[str(i)] for i in range(len(index_to_name))]
        return ordered
    return fallback_names


def _get_model_and_classes(app_config, fallback_names):
    """Lazily load (and cache) the Keras model + ordered class name list."""
    global _model, _class_names, _using_demo_model

    if _class_names is None:
        _class_names = _load_class_names(app_config["CLASS_INDEX_PATH"], fallback_names)

    if _model is None:
        model_path = app_config["MODEL_PATH"]
        if os.path.exists(model_path):
            # Imported lazily: TensorFlow is heavy to import and is only
            # needed once we actually have a model file to load.
            from tensorflow.keras.models import load_model
            _model = load_model(model_path)
            _using_demo_model = False
        else:
            _model = "DEMO"
            _using_demo_model = True

    return _model, _class_names


def is_using_demo_model() -> bool:
    return _using_demo_model


def _demo_predict(image_path, class_names):
    """
    Deterministic stand-in used only when no trained .h5 model is present.
    Hashes the image bytes so the same photo always yields the same demo
    result (useful for UI testing/demos), and produces a plausible
    confidence distribution rather than a flat/fake-looking number.
    """
    with open(image_path, "rb") as f:
        digest = hashlib.sha256(f.read()).digest()
    seed = int.from_bytes(digest[:4], "big")
    rng = np.random.default_rng(seed)

    logits = rng.normal(loc=0.0, scale=1.0, size=len(class_names))
    top_idx = int(np.argmax(logits))
    logits[top_idx] += 2.5  # bias toward a confident top class, like a trained model
    probs = np.exp(logits) / np.exp(logits).sum()
    return probs


def predict(image_array: np.ndarray, image_path: str, app_config: dict, fallback_class_names):
    """
    Run inference on a preprocessed image array.

    Returns: (predicted_class_name: str, confidence: float 0-1, latency_ms: int)
    """
    start = time.time()
    model, class_names = _get_model_and_classes(app_config, fallback_class_names)

    if model == "DEMO":
        probs = _demo_predict(image_path, class_names)
    else:
        preds = model.predict(image_array, verbose=0)
        probs = preds[0]

    top_idx = int(np.argmax(probs))
    confidence = float(probs[top_idx])
    latency_ms = int((time.time() - start) * 1000)
    return class_names[top_idx], confidence, latency_ms
