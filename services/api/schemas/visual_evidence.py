"""Pydantic schemas for visual inspection evidence.

Visual observations are treated as *unverified* supporting evidence. The vision
agent describes what is visible and explicitly lists limitations so the UI never
presents an image as a confirmed diagnosis.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VisualEvidenceStatus = Literal["stored", "analyzing", "analyzed", "failed"]

SeverityHint = Literal["informational", "attention", "urgent"]


class VisualObservation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    observation: str = Field(description="What is visibly present in the image.")
    related_features: list[str] = Field(
        default_factory=list,
        description="Sensor feature keys this observation may relate to.",
    )
    severity_hint: SeverityHint = "informational"


class VisualEvidenceRecord(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    image_id: str
    incident_id: str
    investigation_id: str | None = None
    filename: str
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    provenance: str
    storage_backend: str
    status: VisualEvidenceStatus
    summary: str | None = None
    observations: list[VisualObservation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    error: str | None = None
    content_url: str | None = None
    created_at: str
    updated_at: str


class VisualEvidenceListResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    incident_id: str
    total: int
    items: list[VisualEvidenceRecord]


class VisualAnalysisRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str | None = Field(
        default=None,
        description="Optional investigation to attach the resulting evidence to.",
    )
