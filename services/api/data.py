"""Dataset loading, splitting, and record serialization.

This module owns all access to the AI4I 2020 CSV. Ground-truth failure
columns are preserved for reporting/evaluation but are never read by the
anomaly detector (it only consumes :func:`extract_features`).
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache

import numpy as np
import pandas as pd

from services.api.core import config

logger = logging.getLogger(__name__)


def load_dataset(path=None) -> pd.DataFrame:
    dataset_path = path or config.settings.dataset_path
    if not dataset_path.exists():
        raise RuntimeError(f"AI4I dataset not found at {dataset_path}")
    frame = pd.read_csv(dataset_path)
    logger.info("Loaded dataset from %s (%d records)", dataset_path, len(frame))
    return frame


@lru_cache(maxsize=1)
def get_dataset() -> pd.DataFrame:
    """Return the process-wide dataset (loaded once, cached)."""
    return load_dataset()


def _apply_transform(values: list[float], transform: str) -> float:
    if transform == "kelvin_to_celsius":
        return values[0] - 273.15
    if transform == "temperature_difference":
        return values[0] - values[1]
    if transform == "mechanical_power":
        torque_nm, rpm = values[0], values[1]
        return torque_nm * 2.0 * math.pi * rpm / 60.0
    return values[0]


def extract_features(row) -> dict[str, float]:
    """Return the modelling features for one dataset row.

    Only physical sensor measurements (and their deterministic physical
    derivatives) are returned. No ground-truth label column is ever included.
    """
    features: dict[str, float] = {}
    for definition in config.FEATURE_DEFINITIONS:
        values = [float(row[column]) for column in definition["columns"]]
        features[definition["key"]] = _apply_transform(values, definition["transform"])
    return features


def machine_type_of(row) -> str:
    return str(row["Type"])


def to_measurement(row) -> dict:
    """Serialize only physical sensor measurements (no ground-truth labels).

    Used for incident snapshots and the future AI investigation payload so
    that failure labels can never leak into downstream reasoning.
    """
    air_k = float(row["Air temperature [K]"])
    process_k = float(row["Process temperature [K]"])
    features = extract_features(row)
    return {
        "record_id": int(row["UDI"]),
        "product_id": str(row["Product ID"]),
        "machine_type": str(row["Type"]),
        "air_temperature_k": round(air_k, 2),
        "air_temperature_c": round(air_k - 273.15, 2),
        "process_temperature_k": round(process_k, 2),
        "process_temperature_c": round(process_k - 273.15, 2),
        "rotational_speed_rpm": int(row["Rotational speed [rpm]"]),
        "torque_nm": float(row["Torque [Nm]"]),
        "tool_wear_min": int(row["Tool wear [min]"]),
        "derived_features": {key: round(float(value), 4) for key, value in features.items()},
    }


def to_record(row) -> dict:
    """Serialize a dataset row for telemetry endpoints (unchanged shape)."""
    air_k = float(row["Air temperature [K]"])
    process_k = float(row["Process temperature [K]"])
    flags = {name: int(row[name]) for name in config.FAILURE_CATEGORY_COLUMNS}
    active = [name for name in config.FAILURE_CATEGORY_COLUMNS if flags[name] == 1]

    return {
        "record_id": int(row["UDI"]),
        "product_id": str(row["Product ID"]),
        "machine_type": str(row["Type"]),
        "air_temperature_k": round(air_k, 2),
        "air_temperature_c": round(air_k - 273.15, 2),
        "process_temperature_k": round(process_k, 2),
        "process_temperature_c": round(process_k - 273.15, 2),
        "rotational_speed_rpm": int(row["Rotational speed [rpm]"]),
        "torque_nm": float(row["Torque [Nm]"]),
        "tool_wear_min": int(row["Tool wear [min]"]),
        "machine_failure": bool(int(row["Machine failure"])),
        "failure_flags": flags,
        "failure_types": active,
    }


def split_dataset(frame: pd.DataFrame | None = None):
    """Deterministically split into train / validation / test frames.

    Uses a fixed seed so every process produces identical splits.
    """
    data = get_dataset() if frame is None else frame
    indices = np.arange(len(data))
    rng = np.random.RandomState(config.RANDOM_SEED)
    rng.shuffle(indices)

    n = len(indices)
    n_train = int(n * config.TRAIN_FRACTION)
    n_val = int(n * config.VALIDATION_FRACTION)

    train_idx = indices[:n_train]
    val_idx = indices[n_train : n_train + n_val]
    test_idx = indices[n_train + n_val :]

    train = data.iloc[train_idx].reset_index(drop=True)
    validation = data.iloc[val_idx].reset_index(drop=True)
    test = data.iloc[test_idx].reset_index(drop=True)
    logger.info(
        "Split dataset -> train=%d validation=%d test=%d (seed=%d)",
        len(train),
        len(validation),
        len(test),
        config.RANDOM_SEED,
    )
    return train, validation, test
