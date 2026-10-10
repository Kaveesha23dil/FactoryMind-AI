"""Pydantic schemas for incident endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from services.api.schemas.anomaly import FeatureContribution

IncidentStatus = Literal["open", "under_review", "resolved"]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    record_id: int = Field(ge=1, description="Dataset record (UDI) that triggered the incident.")
    note: str | None = Field(default=None, max_length=2000)


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    status: IncidentStatus
    note: str | None = Field(default=None, max_length=2000)


class IncidentTimelineEntry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    status: str
    timestamp: str
    note: str | None = None


class Incident(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    incident_id: str
    record_id: int
    product_id: str
    machine_type: str
    algorithm: str
    anomaly_score: float
    severity: str
    status: str
    source_measurements: dict
    evidence: list[FeatureContribution]
    explanations: list[str]
    note: str | None = None
    created_at: str
    updated_at: str
    timeline: list[IncidentTimelineEntry]
    ground_truth_used_for_detection: bool = False


class IncidentListItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    incident_id: str
    record_id: int
    machine_type: str
    algorithm: str
    anomaly_score: float
    severity: str
    status: str
    note: str | None = None
    created_at: str
    updated_at: str


class IncidentListResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    total: int
    limit: int
    offset: int
    returned: int
    items: list[IncidentListItem]


class ScanRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    min_severity: Literal["low", "medium", "high", "critical"] = "high"
    max_incidents: int = Field(default=25, ge=1, le=200)
    dry_run: bool = False


class ScanResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    min_severity: str
    max_incidents: int
    dry_run: bool
    candidates_evaluated: int
    incidents_created: int
    incidents_skipped_duplicate: int
    created_incident_ids: list[str]
