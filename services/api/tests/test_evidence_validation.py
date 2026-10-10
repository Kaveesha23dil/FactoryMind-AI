"""Unit tests for evidence construction and citation validation."""

from __future__ import annotations

import json

from services.api.agents.base import AgentSpec
from services.api.agents.orchestrator import Orchestrator
from services.api.agents.runtime import AdkRuntime
from services.api.tools.evidence_tools import (
    build_deterministic_evidence,
    evidence_catalog,
    format_evidence_id,
    validate_evidence_ids,
)


def test_format_evidence_id():
    assert format_evidence_id("sensor_measurement", 1) == "EV-SENSOR-001"
    assert format_evidence_id("manual_passage", 12) == "EV-MANUAL-012"
    assert format_evidence_id("anomaly_finding", 1) == "EV-ANOMALY-001"
    assert format_evidence_id("unknown_type", 1) == "EV-UNKNOWN-001"


def test_validate_evidence_ids_splits_and_dedupes():
    catalog = {"EV-SENSOR-001": {}, "EV-ANOMALY-001": {}}
    valid, rejected = validate_evidence_ids(
        ["EV-SENSOR-001", "EV-GHOST-999", "EV-SENSOR-001", "", None],
        catalog,
    )
    assert valid == ["EV-SENSOR-001"]
    assert rejected == ["EV-GHOST-999"]


def _sample_inputs():
    incident = {
        "incident_id": "INC-TEST0001",
        "record_id": 42,
        "product_id": "M42",
        "machine_type": "M",
    }
    anomaly = {
        "algorithm": "robust_zscore_v1",
        "anomaly_score": 9.5,
        "severity": "critical",
        "threshold": 4.0,
        "feature_z_threshold": 3.0,
        "features": [
            {
                "feature": "torque_nm",
                "label": "Torque",
                "unit": "Nm",
                "observed_value": 68.0,
                "baseline_median": 40.0,
                "baseline_scale": 5.0,
                "baseline_mad": 3.0,
                "robust_zscore": 5.6,
                "direction": "high",
                "is_anomalous": True,
                "baseline_scope": "global",
            }
        ],
    }
    passages = [
        {
            "document_id": "DOC-TORQUE-003",
            "section_id": "SEC-TORQUE-001",
            "document_title": "Torque Overload Troubleshooting",
            "heading": "Elevated torque signature",
            "text": "An unusually high torque reading is an overstrain signature.",
        }
    ]
    return incident, anomaly, passages


def test_build_deterministic_evidence_ids_and_label_isolation():
    incident, anomaly, passages = _sample_inputs()
    records = build_deterministic_evidence(
        investigation_id="INV-TEST",
        incident=incident,
        anomaly=anomaly,
        passages=passages,
        created_at="2026-10-10T00:00:00+00:00",
    )
    ids = [record["evidence_id"] for record in records]
    assert "EV-SOURCE-001" in ids
    assert "EV-ANOMALY-001" in ids
    assert "EV-SENSOR-001" in ids
    assert "EV-BASELINE-001" in ids
    assert "EV-MANUAL-001" in ids

    blob = json.dumps(records).lower()
    assert "ground_truth" not in blob
    assert "machine failure" not in blob

    catalog = evidence_catalog(records)
    assert set(catalog) == set(ids)


def test_normalize_hypotheses_rejects_unknown_ids():
    runtime = AdkRuntime(provider="scripted", model_name="scripted", scripted_responses={})
    orchestrator = Orchestrator(runtime=runtime, incident_service=None)
    catalog = {"EV-SENSOR-001": {}, "EV-MANUAL-001": {}}
    draft = {
        "summary": "s",
        "hypotheses": [
            {
                "hypothesis_id": "H-001",
                "title": "t",
                "description": "d",
                "supporting_evidence_ids": ["EV-SENSOR-001", "EV-GHOST-777"],
                "contradicting_evidence_ids": ["EV-MANUAL-001"],
                "missing_evidence": [],
                "verification_steps": [],
                "assessment": "plausible",
            }
        ],
    }
    hypotheses, rejected = orchestrator._normalize_hypotheses(draft, catalog)
    assert rejected == ["EV-GHOST-777"]
    assert hypotheses[0].supporting_evidence_ids == ["EV-SENSOR-001"]
    assert hypotheses[0].contradicting_evidence_ids == ["EV-MANUAL-001"]


def test_agent_spec_is_defined():
    spec = AgentSpec(
        name="x",
        label="X",
        instruction="i",
        output_schema=dict,
        build_prompt=lambda context: "p",
    )
    assert spec.name == "x"
