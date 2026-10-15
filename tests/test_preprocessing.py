"""Unit tests for the image preprocessing pipeline (proposal 3.6:
'Unit Testing ... image preprocessing pipeline (resizing, normalisation,
tensor conversion)')."""
import numpy as np
from PIL import Image

from app.ml.preprocessing import resize_and_adjust, to_model_input


def _dummy_image(size=(400, 300)):
    return Image.new("RGB", size, color=(80, 140, 90))


def test_resize_and_adjust_outputs_target_size():
    img = _dummy_image()
    out = resize_and_adjust(img, target_size=(224, 224))
    assert out.shape == (224, 224, 3)


def test_to_model_input_scales_to_expected_range_and_batches():
    img = _dummy_image()
    resized = resize_and_adjust(img, target_size=(224, 224))
    batched = to_model_input(resized)
    assert batched.shape == (1, 224, 224, 3)
    assert batched.min() >= -1.0001
    assert batched.max() <= 1.0001
