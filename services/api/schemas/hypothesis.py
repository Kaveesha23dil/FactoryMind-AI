"""Pydantic schemas for candidate root-cause hypotheses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HypothesisAssessment = Literal["plausible", "weak", "unsupported"]


class Hypothesis(BaseModel):
    """A candidate root cause.

    ``assessment`` is a qualitative, evidence-dependent label only. It is never
    a calibrated probability of physical failure.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    hypothesis_id: str
    title: str
    description: str = ""
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    assessment: HypothesisAssessment = "weak"
    rank_rationale: str | None = None
