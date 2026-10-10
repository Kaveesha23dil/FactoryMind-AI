"""Pydantic schemas for investigation evidence.

Evidence records are immutable, independently persisted, and carry their own
deterministic ID. They are stored separately from AI-generated conclusions so a
report can always be traced back to the source it cites.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceType = Literal[
    "sensor_measurement",
    "baseline_statistic",
    "anomaly_finding",
    "source_metadata",
    "manual_passage",
    "visual_observation",
]


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    evidence_id: str = Field(description="Immutable evidence identifier, e.g. EV-SENSOR-001.")
    investigation_id: str
    incident_id: str
    evidence_type: EvidenceType
    source: str = Field(description="Human-readable origin of the evidence.")
    observation: str = Field(description="Exact observation or retrieved passage.")
    value: float | None = None
    units: str | None = None
    provenance: str = Field(description="How and from where the evidence was collected.")
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class EvidenceListResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    total: int
    items: list[EvidenceRecord]
