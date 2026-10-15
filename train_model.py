"""Train the CropGuard disease classifier and explicit non-leaf class."""
import argparse
import io
import json
import os
import re
import random
import shutil
from collections import defaultdict
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import numpy as np
import requests
import tensorflow as tf
from datasets import load_dataset
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import Config
from app.ml.preprocessing import load_image, resize_and_adjust, to_model_input


IMAGE_SIZE = (224, 224)
CLASS_NAMES = [
    "Healthy",
    "Maize Leaf Blight",
    "Maize Common Rust",
    "Tomato Early Blight",
    "Tomato Late Blight",
    "Bean Angular Leaf Spot",
    "Reject",
]
CLASS_INDEX = {name: index for index, name in enumerate(CLASS_NAMES)}
PLANTVILLAGE_LABELS = {
    "Corn_(maize)___Northern_Leaf_Blight": "Maize Leaf Blight",
    "Corn_(maize)___Common_rust_": "Maize Common Rust",
    "Tomato___Early_blight": "Tomato Early Blight",
    "Tomato___Late_blight": "Tomato Late Blight",
    "Corn_(maize)___healthy": "Healthy",
    "Tomato___healthy": "Healthy",
    "Apple___Apple_scab": "Reject",
    "Potato___Early_blight": "Reject",
    "Potato___Late_blight": "Reject",
    "Tomato___Leaf_Mold": "Reject",
}
PLANTVILLAGE_BASE_URL = "https://huggingface.co/datasets/mohanty/PlantVillage/resolve/main"
PLANTVILLAGE_ARCHIVE_URL = f"{PLANTVILLAGE_BASE_URL}/data.zip?download=true"


class HTTPRangeReader(io.RawIOBase):
    """Seekable, retrying reader for ZIP members on an HTTP range endpoint."""

    def __init__(self, url, block_size=256 * 1024):
        self._session = requests.Session()
        retry = Retry(
            total=8,
            connect=8,
            read=8,
            status=8,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("GET", "HEAD")),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        response = self._session.get(
            url,
            headers={"Range": "bytes=0-0"},
            stream=True,
            timeout=(30, 300),
        )
        response.raise_for_status()
        match = re.fullmatch(r"bytes 0-0/(\d+)", response.headers.get("Content-Range", ""))
        if response.status_code != 206 or not match:
            response.close()
            raise OSError("The dataset host does not support HTTP byte-range downloads.")
        self._url = response.url
        self._size = int(match.group(1))
        self._block_size = block_size
        self._position = 0
        self._cached_block_start = None
        self._cached_block = b""
        response.close()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._position

    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            position = offset
        elif whence == os.SEEK_CUR:
            position = self._position + offset
        elif whence == os.SEEK_END:
            position = self._size + offset
        else:
            raise ValueError(f"Unsupported seek mode: {whence}")
        if position < 0:
            raise ValueError("Negative seek position")
        self._position = position
        return position

    def read(self, size=-1):
        if size is None or size < 0:
            size = self._size - self._position
        size = min(size, self._size - self._position)
        result = bytearray()
        while size:
            block_start = (self._position // self._block_size) * self._block_size
            if block_start != self._cached_block_start:
                block_end = min(self._size, block_start + self._block_size) - 1
                response = self._session.get(
                    self._url,
                    headers={"Range": f"bytes={block_start}-{block_end}"},
                    timeout=(30, 300),
                )
                response.raise_for_status()
                expected_range = f"bytes {block_start}-{block_end}/{self._size}"
                if response.status_code != 206 or response.headers.get("Content-Range") != expected_range:
                    raise OSError(f"Unexpected dataset byte range response: {response.status_code}")
                self._cached_block = response.content
                self._cached_block_start = block_start

            offset = self._position - block_start
            amount = min(size, len(self._cached_block) - offset)
            if amount <= 0:
                raise OSError("Dataset server returned an incomplete byte range.")
            result.extend(self._cached_block[offset:offset + amount])
            self._position += amount
            size -= amount
        return bytes(result)

    def close(self):
        self._session.close()
        super().close()


def _download_text(url):
    response = requests.get(url, timeout=(30, 120))
    response.raise_for_status()
    return response.text.splitlines()


def _plant_target(class_name):
    target_name = PLANTVILLAGE_LABELS.get(class_name)
    return CLASS_INDEX[target_name] if target_name else None


def _leaf_group_id(file_path, leaf_map):
    parts = PurePosixPath(file_path).parts
    class_name, file_name = parts[2], parts[3]
    image_id = file_name.replace("_final_masked", "")
    if "___" in image_id:
        image_id = image_id.split("___")[-1]
    image_id = image_id.split("copy")[0]
    image_id = os.path.splitext(image_id)[0].strip()
    suggestions = leaf_map.get(image_id.lower(), [])
    if not isinstance(suggestions, list):
        suggestions = [suggestions]
    if len(suggestions) == 1:
        return str(suggestions[0])
    for suggestion in suggestions:
        if class_name in suggestion:
            return str(suggestion)
    return f"fallback_{image_id.lower()}"


def _split_plantvillage_records(seed):
    leaf_map_response = requests.get(
        f"{PLANTVILLAGE_BASE_URL}/leaf_grouping/leaf-map.json?download=true",
        timeout=(30, 120),
    )
    leaf_map_response.raise_for_status()
    leaf_map = leaf_map_response.json()

    records_by_class = defaultdict(list)
    for source_split in ("train", "test"):
        split_url = f"{PLANTVILLAGE_BASE_URL}/splits/color_{source_split}.txt?download=true"
        for file_path in _download_text(split_url):
            parts = PurePosixPath(file_path).parts
            if len(parts) != 4 or parts[:2] != ("raw", "color"):
                continue
            target = _plant_target(parts[2])
            if target is None:
                continue
            records_by_class[target].append((file_path, target, _leaf_group_id(file_path, leaf_map)))

    split_records = {name: [] for name in ("train", "validation", "test")}
    rng = random.Random(seed)
    for target, records in records_by_class.items():
        groups = list({record[2] for record in records})
        rng.shuffle(groups)
        train_end = max(1, int(len(groups) * 0.75))
        validation_end = max(train_end + 1, int(len(groups) * 0.875))
        groups_by_split = {
            "train": set(groups[:train_end]),
            "validation": set(groups[train_end:validation_end]),
            "test": set(groups[validation_end:]),
        }
        for file_path, label, group in records:
            for split_name, selected_groups in groups_by_split.items():
                if group in selected_groups:
                    split_records[split_name].append((file_path, label))
                    break

    for split_name in split_records:
        if not split_records[split_name]:
            raise ValueError(f"PlantVillage produced no {split_name} examples.")
    return split_records


def _limit_plant_records(records, max_per_class, seed):
    by_class = defaultdict(list)
    for record in records:
        by_class[record[1]].append(record)
    rng = random.Random(seed)
    limited = []
    for label, class_records in by_class.items():
        rng.shuffle(class_records)
        limited.extend(class_records[:max_per_class] if max_per_class else class_records)
    return limited


def _map_hf_labels(dataset, label_column, label_mapping, seed):
    label_feature = dataset.features[label_column]

    def add_target(example):
        label_name = label_feature.int2str(int(example[label_column]))
        target_name = label_mapping.get(label_name, "Reject")
        return {"target": CLASS_INDEX[target_name]}

    return dataset.map(add_target).shuffle(seed=seed)


def _limit_hf_dataset(dataset, max_per_class, seed):
    if not max_per_class:
        return dataset
    indices_by_label = defaultdict(list)
    for index, label in enumerate(dataset["target"]):
        indices_by_label[int(label)].append(index)

    selected_indices = []
    for label, indices in indices_by_label.items():
        random.Random(seed + label).shuffle(indices)
        selected_indices.extend(indices[:max_per_class])
    return dataset.select(selected_indices).shuffle(seed=seed)


def _load_hf_datasets(max_per_class, seed):
    beans = load_dataset("AI-Lab-Makerere/beans")
    bean_mapping = {
        "angular_leaf_spot": "Bean Angular Leaf Spot",
        "healthy": "Healthy",
        "bean_rust": "Reject",
    }
    beans = {
        split: _limit_hf_dataset(
            _map_hf_labels(dataset, "labels", bean_mapping, seed), max_per_class, seed
        )
        for split, dataset in beans.items()
    }

    cifar = load_dataset("uoft-cs/cifar10")
    cifar_training = cifar["train"].train_test_split(test_size=0.15, seed=seed)
    cifar_splits = {
        "train": cifar_training["train"],
        "validation": cifar_training["test"],
        "test": cifar["test"],
    }
    cifar_splits = {
        split: _limit_hf_dataset(
            _map_hf_labels(dataset, "label", {}, seed), max_per_class, seed
        )
        for split, dataset in cifar_splits.items()
    }
    return beans, cifar_splits


def _extract_plantvillage(records_by_split, data_dir):
    image_root = Path(data_dir) / "plantvillage-selected"
    image_root.mkdir(parents=True, exist_ok=True)
    all_records = [record for records in records_by_split.values() for record in records]
    needed_paths = {file_path for file_path, _ in all_records}
    local_paths = {}
    for file_path in needed_paths:
        parts = PurePosixPath(file_path).parts
        local_paths[file_path] = image_root.joinpath(*parts[2:])

    missing_paths = {name for name, path in local_paths.items() if not path.is_file()}
    if missing_paths:
        with HTTPRangeReader(PLANTVILLAGE_ARCHIVE_URL) as remote:
            with ZipFile(remote) as archive:
                infos = {info.filename: info for info in archive.infolist() if info.filename in missing_paths}
                missing_members = missing_paths - set(infos)
                if missing_members:
                    raise ValueError(f"PlantVillage archive is missing {len(missing_members)} selected images.")
                ordered_infos = sorted(infos.values(), key=lambda info: info.header_offset)
                for index, info in enumerate(ordered_infos, start=1):
                    destination = local_paths[info.filename]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_suffix(destination.suffix + ".part")
                    try:
                        with archive.open(info) as source, temporary.open("wb") as target:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
                        temporary.replace(destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                    if index % 1000 == 0 or index == len(ordered_infos):
                        print(f"Extracted selected PlantVillage images: {index}/{len(ordered_infos)}", flush=True)

    return {
        split: [(local_paths[file_path], label) for file_path, label in records]
        for split, records in records_by_split.items()
    }


def _plant_tf_dataset(records):
    def generate():
        for image_path, label in records:
            resized = resize_and_adjust(load_image(str(image_path)), IMAGE_SIZE)
            image = to_model_input(resized)[0]
            yield image, np.int64(label)

    return tf.data.Dataset.from_generator(
        generate,
        output_signature=(
            tf.TensorSpec((*IMAGE_SIZE, 3), tf.float32),
            tf.TensorSpec((), tf.int64),
        ),
    )


def _hf_tf_dataset(dataset, image_column):
    def generate():
        for example in dataset:
            image = example[image_column].convert("RGB")
            resized = resize_and_adjust(image, IMAGE_SIZE)
            values = to_model_input(resized)[0]
            yield values, np.int64(example["target"])

    return tf.data.Dataset.from_generator(
        generate,
        output_signature=(
            tf.TensorSpec((*IMAGE_SIZE, 3), tf.float32),
            tf.TensorSpec((), tf.int64),
        ),
    )


def _combine_datasets(datasets):
    combined = datasets[0]
    for dataset in datasets[1:]:
        combined = combined.concatenate(dataset)
    return combined


def _load_training_data(data_dir, max_per_class, seed):
    plant = _split_plantvillage_records(seed)
    plant = {
        split: _limit_plant_records(records, max_per_class, seed + index)
        for index, (split, records) in enumerate(plant.items())
    }
    plant = _extract_plantvillage(plant, data_dir)
    beans, cifar = _load_hf_datasets(max_per_class, seed)

    data_sources = {}
    train_labels = [label for _, label in plant["train"]]
    train_labels.extend(beans["train"]["target"])
    train_labels.extend(cifar["train"]["target"])
    class_counts = np.bincount(train_labels, minlength=len(CLASS_NAMES))
    if np.any(class_counts == 0):
        missing = [CLASS_NAMES[index] for index, count in enumerate(class_counts) if count == 0]
        raise ValueError(f"Training data is missing classes: {missing}")
    total = int(class_counts.sum())
    class_weights = {
        index: total / (len(CLASS_NAMES) * int(count))
        for index, count in enumerate(class_counts)
    }

    for split in ("train", "validation", "test"):
        sources = [_plant_tf_dataset(plant[split])]
        sources.append(_hf_tf_dataset(beans[split], "image"))
        cifar_image_column = "img" if "img" in cifar[split].column_names else "image"
        sources.append(_hf_tf_dataset(cifar[split], cifar_image_column))
        data_sources[split] = _combine_datasets(sources)
        print(
            f"{split}: PlantVillage={len(plant[split])}, Beans={len(beans[split])}, "
            f"CIFAR-10={len(cifar[split])}",
            flush=True,
        )
    return data_sources, class_weights


def _build_model():
    augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal"),
            tf.keras.layers.RandomRotation(0.08),
            tf.keras.layers.RandomZoom(0.1),
            tf.keras.layers.RandomContrast(0.1),
        ],
        name="data_augmentation",
    )
    base = tf.keras.applications.MobileNetV2(
        input_shape=(*IMAGE_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False

    inputs = tf.keras.Input(shape=(*IMAGE_SIZE, 3))
    values = augmentation(inputs)
    values = base(values, training=False)
    values = tf.keras.layers.GlobalAveragePooling2D()(values)
    values = tf.keras.layers.Dropout(0.25)(values)
    outputs = tf.keras.layers.Dense(len(CLASS_NAMES), activation="softmax")(values)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _print_test_metrics(model, test_dataset):
    true_labels = np.concatenate([labels.numpy() for _, labels in test_dataset])
    predictions = np.argmax(model.predict(test_dataset, verbose=0), axis=1)
    confusion = np.zeros((len(CLASS_NAMES), len(CLASS_NAMES)), dtype=np.int64)
    np.add.at(confusion, (true_labels, predictions), 1)
    accuracy = np.trace(confusion) / max(int(confusion.sum()), 1)
    print(f"Test accuracy: {accuracy:.4f}")
    print("Class                         Precision  Recall")
    for index, name in enumerate(CLASS_NAMES):
        true_positive = confusion[index, index]
        precision = true_positive / max(int(confusion[:, index].sum()), 1)
        recall = true_positive / max(int(confusion[index, :].sum()), 1)
        print(f"{name:<29} {precision:>9.4f} {recall:>7.4f}")
    print("Confusion matrix (rows=true, columns=predicted):")
    print(confusion)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-per-class", type=int, default=1500,
                        help="Maximum examples per class and split; use 0 for all available images")
    parser.add_argument("--data-dir", default=None, help="Local cache for selected PlantVillage images")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.max_per_class < 0:
        parser.error("--epochs and --batch-size must be positive; --max-per-class cannot be negative")

    tf.keras.utils.set_random_seed(42)
    for gpu in tf.config.list_physical_devices("GPU"):
        tf.config.experimental.set_memory_growth(gpu, True)

    data_dir = args.data_dir or str(Path.home() / ".cache" / "cropguard")
    os.makedirs(data_dir, exist_ok=True)
    datasets, class_weights = _load_training_data(data_dir, args.max_per_class, seed=42)
    train_dataset = (
        datasets["train"]
        .shuffle(1024, seed=42, reshuffle_each_iteration=True)
        .batch(args.batch_size)
        .prefetch(1)
    )
    validation_dataset = datasets["validation"].batch(args.batch_size).prefetch(1)
    test_dataset = datasets["test"].batch(args.batch_size).prefetch(1)

    model = _build_model()
    os.makedirs(os.path.dirname(Config.MODEL_PATH), exist_ok=True)
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=3, restore_best_weights=True
        ),
        tf.keras.callbacks.ModelCheckpoint(
            Config.MODEL_PATH, monitor="val_loss", save_best_only=True
        ),
    ]
    model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=args.epochs,
        callbacks=callbacks,
        class_weight=class_weights,
        shuffle=False,
    )
    _print_test_metrics(model, test_dataset)

    os.makedirs(os.path.dirname(Config.CLASS_INDEX_PATH), exist_ok=True)
    with open(Config.CLASS_INDEX_PATH, "w", encoding="utf-8") as class_file:
        json.dump({str(index): name for index, name in enumerate(CLASS_NAMES)}, class_file, indent=2)
    print(f"Saved model to {Config.MODEL_PATH}")
    print(f"Saved class mapping to {Config.CLASS_INDEX_PATH}")


if __name__ == "__main__":
    main()