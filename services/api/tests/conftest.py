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
# Investigations run with a deterministic scripted model and inline (no worker
# thread) so automated tests never touch the network or a background thread.
os.environ.setdefault("AI_PROVIDER", "scripted")
os.environ.setdefault("FACTORYMIND_INVESTIGATION_ASYNC", "false")

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


# --- AI investigation helpers ----------------------------------------------

_SENSOR_RESPONSE = {
    "summary": "Torque and tool wear are unusual relative to the training baseline.",
    "findings": [
        {
            "feature": "torque_nm",
            "observation": "Torque is elevated compared with the baseline median.",
            "evidence_ids": ["EV-SENSOR-001", "EV-BASELINE-001"],
        }
    ],
    "missing_measurements": ["Vibration and machine-specific time series are unavailable."],
    "referenced_evidence_ids": ["EV-SENSOR-001", "EV-ANOMALY-001", "EV-BASELINE-001"],
}

_KNOWLEDGE_RESPONSE = {
    "summary": "General guidance links high torque to overload and tool wear.",
    "guidance": [
        {
            "symptom": "Elevated torque",
            "guidance": "Check cutting parameters and tool condition before production.",
            "evidence_ids": ["EV-MANUAL-001"],
        }
    ],
    "referenced_evidence_ids": ["EV-MANUAL-001"],
}

_INVESTIGATION_RESPONSE = {
    "summary": "Anomalous operating measurements require technician inspection.",
    "hypotheses": [
        {
            "hypothesis_id": "H-001",
            "title": "Possible excessive tool wear",
            "description": "Elevated torque can accompany a worn cutting edge.",
            "supporting_evidence_ids": ["EV-SENSOR-001", "EV-MANUAL-001"],
            "contradicting_evidence_ids": [],
            "missing_evidence": ["Direct tool inspection"],
            "verification_steps": ["Inspect tool condition using approved procedures"],
            "assessment": "plausible",
        },
        {
            "hypothesis_id": "H-002",
            "title": "Alternative: transient overload condition",
            "description": "A short overload could raise torque without persistent wear.",
            "supporting_evidence_ids": ["EV-ANOMALY-001"],
            "contradicting_evidence_ids": [],
            "missing_evidence": ["Continuity of load over time"],
            "verification_steps": ["Review recent cutting parameters"],
            "assessment": "weak",
        },
    ],
}

_CRITIC_RESPONSE = {
    "verification_outcome": "supported",
    "issues_found": [],
    "unsupported_claims": [],
    "contradictions": [],
    "alternative_explanations": ["Sensor calibration drift"],
    "missing_evidence": ["Vibration data"],
    "citation_issues": [],
    "revision_required": False,
}


def _as_json(payload: dict) -> str:
    import json

    return json.dumps(payload)


def default_scripted_responses() -> dict[str, str]:
    return {
        "sensor_agent": _as_json(_SENSOR_RESPONSE),
        "knowledge_agent": _as_json(_KNOWLEDGE_RESPONSE),
        "investigation_agent": _as_json(_INVESTIGATION_RESPONSE),
        "critic_agent": _as_json(_CRITIC_RESPONSE),
    }


def install_scripted_responses(overrides: dict | None = None) -> dict[str, str]:
    """Register scripted responses (merging JSON-dict overrides) globally."""
    from services.api.agents.runtime import set_scripted_response

    responses = default_scripted_responses()
    if overrides:
        for agent_name, payload in overrides.items():
            responses[agent_name] = (
                payload if isinstance(payload, str) else _as_json(payload)
            )
    for agent_name, text in responses.items():
        set_scripted_response(agent_name, text)
    return responses


def clear_scripted_responses() -> None:
    from services.api.agents.runtime import clear_scripted_responses as _clear

    _clear()
