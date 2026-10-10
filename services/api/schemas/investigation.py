"""Pydantic schemas for the AI investigation API.

These schemas are the contract shared by the orchestrator, the persistence
layer, and the frontend. ``allow_inf_nan=False`` guarantees NaN / Infinity can
never be serialized into a JSON response.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from services.api.schemas.hypothesis import Hypothesis

InvestigationStatus = Literal["queued", "running", "completed", "failed"]

AgentStatus = Literal["pending", "running", "completed", "failed", "skipped"]


class StageEntry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    stage: str
    message: str | None = None
    timestamp: str


class AgentActivity(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    agent: str
    label: str
    status: AgentStatus = "pending"
    summary: str | None = None
    evidence_count: int | None = None
    started_at: str | None = None
    completed_at: str | None = None


class CriticReview(BaseModel):
    """Independent verification output from the Critic Agent."""

    model_config = ConfigDict(allow_inf_nan=False)

    verification_outcome: str
    issues_found: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(default_factory=list)
    revision_required: bool = False
    deterministic_findings: list[str] = Field(
        default_factory=list,
        description="Issues found by deterministic validation, not by the model.",
    )


class RecommendedAction(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    action: str
    rationale: str = ""
    requires_human_approval: bool = True


class InvestigationReport(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    status: InvestigationStatus
    summary: str
    provider: str
    model: str
    generated_at: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    critic_review: CriticReview
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    agent_activity: list[AgentActivity] = Field(default_factory=list)
    evidence_catalog: list[str] = Field(default_factory=list)
    rejected_citations: list[str] = Field(default_factory=list)
    revision_count: int = 0
    disclaimer: str


class InvestigationJob(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    status: InvestigationStatus
    stage: str
    provider: str
    model: str
    summary: str | None = None
    error: str | None = None
    attempt_count: int = 0
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str
    stage_history: list[StageEntry] = Field(default_factory=list)
    agent_activity: list[AgentActivity] = Field(default_factory=list)
    report: InvestigationReport | None = None


class InvestigationStartResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    status: InvestigationStatus
    stage: str
    created_at: str


class InvestigationListItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    status: InvestigationStatus
    stage: str
    provider: str
    model: str
    summary: str | None = None
    created_at: str
    completed_at: str | None = None


class InvestigationListResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    incident_id: str
    total: int
    items: list[InvestigationListItem]


class InvestigationListPage(BaseModel):
    """Global, incident-agnostic investigation listing for the workspace."""

    model_config = ConfigDict(allow_inf_nan=False)

    total: int
    limit: int
    offset: int
    returned: int
    items: list[InvestigationListItem]


class InvestigationRunResponse(BaseModel):
    """Internal worker response (Cloud Tasks / local worker contract)."""

    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    status: InvestigationStatus
    stage: str
    executed: bool


#: Fixed disclaimer attached to every report. Keeps the "these are not
#: confirmed physical diagnoses" distinction explicit in stored data.
REPORT_DISCLAIMER = (
    "AI-assisted hypotheses derived from synthetic dataset observations, "
    "deterministic anomaly scores, and general/synthetic maintenance guidance. "
    "Hypotheses are not confirmed physical diagnoses and are not calibrated "
    "failure probabilities. A qualified engineer must verify every finding."
)


class InvestigationPayload(BaseModel):
    """Read-only diagnostic view of the exact input handed to the agents."""

    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    machine_type: str
    sensor_measurements: dict[str, Any]
    anomaly_findings: dict[str, Any]
    evidence_catalog: list[str]
    ground_truth_used_for_investigation: bool = False
