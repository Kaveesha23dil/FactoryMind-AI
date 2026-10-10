"""Shared pytest fixtures and helpers.

The incident database path is redirected to a temporary directory *before*
the application is imported so tests never touch the development database.
"""

from __future__ import annotations

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="factorymind-tests-")
os.environ["FACTORYMIND_DB_PATH"] = os.path.join(_TMP_DIR, "incidents.db")
os.environ.setdefault("FACTORYMIND_LOG_LEVEL", "WARNING")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.api.main import app  # noqa: E402
from services.api.services.anomaly_engine import get_engine  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def engine():
    return get_engine()


def make_feature_frame(
    torque: list[float],
    wear: list[float],
    air_k: float = 300.0,
    process_k: float = 310.0,
    rpm: float = 1500.0,
    machine_type: str = "L",
) -> pd.DataFrame:
    """Build a minimal raw AI4I-shaped frame for detector unit tests."""
    n = len(torque)
    return pd.DataFrame(
        {
            "UDI": list(range(1, n + 1)),
            "Product ID": [f"{machine_type}{i}" for i in range(n)],
            "Type": [machine_type] * n,
            "Air temperature [K]": [air_k] * n,
            "Process temperature [K]": [process_k] * n,
            "Rotational speed [rpm]": [rpm] * n,
            "Torque [Nm]": torque,
            "Tool wear [min]": wear,
        }
    )


def anomalous_record_ids(engine, limit: int = 5) -> list[int]:
    return [item["record_id"] for item in engine._anomalies[:limit]]


def normal_record_id(engine) -> int:
    for record_id, result in engine._results.items():
        if not result["is_anomaly"]:
            return record_id
    raise AssertionError("expected at least one non-anomalous record")


def assert_finite(value) -> None:
    assert isinstance(value, (int, float))
    assert np.isfinite(value)
