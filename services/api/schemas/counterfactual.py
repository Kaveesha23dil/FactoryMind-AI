"""Pydantic schemas for counterfactual investigations.

A counterfactual scenario removes selected evidence from an incident's
investigation context and re-runs the multi-agent pipeline. The original
investigation is never mutated; the revised run is stored as its own
investigation and linked from the scenario record.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CounterfactualStatus = Literal["pending", "running", "completed", "failed"]


class CounterfactualRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    excluded_evidence_ids: list[str] = Field(
        min_length=1,
        description="Evidence IDs to remove from the reasoning context.",
    )
    rationale: str | None = Field(
        default=None,
        description="Optional engineer-provided reason for the scenario.",
    )


class DependencyTraceEntry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    feature: str
    label: str
    reason: Literal["direct", "derived"] = "direct"
    evidence_ids: list[str] = Field(default_factory=list)


class AnomalyComparison(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    original_score: float | None = None
    revised_score: float | None = None
    original_severity: str | None = None
    revised_severity: str | None = None
    threshold: float
    retained_feature_count: int
    excluded_feature_keys: list[str] = Field(default_factory=list)
    recomputed: bool = True


class HypothesisChange(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    title: str
    original_hypothesis_id: str | None = None
    revised_hypothesis_id: str | None = None
    original_assessment: str | None = None
    revised_assessment: str | None = None
    note: str | None = None


class AssessmentShift(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    title: str
    original_hypothesis_id: str
    revised_hypothesis_id: str
    original_assessment: str
    revised_assessment: str


class RecommendationDiff(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)


class CounterfactualComparison(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    summary: str
    retained_hypotheses: list[HypothesisChange] = Field(default_factory=list)
    removed_hypotheses: list[HypothesisChange] = Field(default_factory=list)
    added_hypotheses: list[HypothesisChange] = Field(default_factory=list)
    assessment_shifts: list[AssessmentShift] = Field(default_factory=list)
    new_contradictions: list[str] = Field(default_factory=list)
    removed_contradictions: list[str] = Field(default_factory=list)
    new_missing_evidence: list[str] = Field(default_factory=list)
    recommendation_diff: RecommendationDiff
    anomaly: AnomalyComparison
    retained_evidence_ids: list[str] = Field(default_factory=list)
    excluded_evidence_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CounterfactualScenario(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    scenario_id: str
    original_investigation_id: str
    incident_id: str
    revised_investigation_id: str | None = None
    excluded_evidence_ids: list[str] = Field(default_factory=list)
    excluded_feature_keys: list[str] = Field(default_factory=list)
    rationale: str | None = None
    status: CounterfactualStatus
    error: str | None = None
    comparison: CounterfactualComparison | None = None
    dependency_trace: list[DependencyTraceEntry] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CounterfactualListResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    original_investigation_id: str
    total: int
    items: list[CounterfactualScenario]
