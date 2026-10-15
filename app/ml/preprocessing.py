"""
Image preprocessing pipeline — Spiral 2 deliverable ("resizes them, adjusts
colors, turns them into numbers the model can understand").

Steps: resize -> colour/format normalisation -> array conversion -> scale
to MobileNetV2's expected [-1, 1] input range. Kept as pure functions so
they're independently unit-testable with Pytest (proposal 3.6).
"""
import numpy as np
from PIL import Image, ImageOps
import cv2


def load_image(image_path: str) -> Image.Image:
    """Load an image from disk and auto-correct EXIF rotation (common on
    phone camera uploads from the field)."""
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def resize_and_adjust(image: Image.Image, target_size=(224, 224)) -> np.ndarray:
    """Resize to the model's expected input size and mildly enhance
    contrast/brightness so poorly-lit field photos are more classifiable."""
    arr = np.array(image)

    # Mild CLAHE contrast adjustment on the luminance channel only, so
    # colour information the model relies on isn't distorted.
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    arr = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)

    resized = cv2.resize(arr, target_size, interpolation=cv2.INTER_AREA)
    return resized


def to_model_input(resized_array: np.ndarray) -> np.ndarray:
    """Scale pixels to MobileNetV2's expected [-1, 1] range and add the
    batch dimension Keras expects."""
    arr = resized_array.astype("float32")
    arr = (arr / 127.5) - 1.0
    return np.expand_dims(arr, axis=0)


def preprocess_for_inference(image_path: str, target_size=(224, 224)) -> np.ndarray:
    """Full pipeline: load -> resize/adjust -> normalise -> batch."""
    image = load_image(image_path)
    resized = resize_and_adjust(image, target_size)
    return to_model_input(resized)
