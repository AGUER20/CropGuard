"""Unit tests for the image preprocessing pipeline (proposal 3.6:
'Unit Testing ... image preprocessing pipeline (resizing, normalisation,
tensor conversion)')."""
import numpy as np
from PIL import Image, ImageDraw

from app.ml.preprocessing import looks_like_leaf_photo, resize_and_adjust, to_model_input


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


def test_leaf_photo_gate_accepts_centered_leaf(tmp_path):
    image = Image.new("RGB", (224, 224), color=(35, 35, 35))
    ImageDraw.Draw(image).ellipse((25, 45, 199, 179), fill=(50, 155, 65))
    image_path = tmp_path / "leaf.png"
    image.save(image_path)

    assert looks_like_leaf_photo(str(image_path))


def test_leaf_photo_gate_rejects_car_with_green_background(tmp_path):
    image = Image.new("RGB", (224, 224), color=(30, 105, 40))
    ImageDraw.Draw(image).rectangle((35, 65, 189, 175), fill=(35, 38, 42))
    image_path = tmp_path / "car.png"
    image.save(image_path)

    assert not looks_like_leaf_photo(str(image_path))
