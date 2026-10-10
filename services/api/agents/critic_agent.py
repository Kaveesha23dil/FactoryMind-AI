"""Agent 4 - Critic / Verification Agent.

Independently reviews the draft investigation. It is explicitly designed to be
able to disagree and request a revision; it is not a rubber stamp.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.api.agents.base import AgentSpec
from services.api.agents.prompts import format_evidence_catalog


class CriticReviewOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verification_outcome: str = Field(
        description="Overall verdict, e.g. 'supported' or 'revision required'."
    )
    issues_found: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    citation_issues: list[str] = Field(
        default_factory=list,
        description="Hypotheses that cite evidence which does not support the claim.",
    )
    revision_required: bool = False


INSTRUCTION = (
    "You are the Critic and Verification Agent. Independently review a draft "
    "investigation report and challenge it.\n"
    "Rules:\n"
    "1. Verify that each cited evidence ID actually exists in the evidence catalog "
    "and actually supports the claim it is attached to.\n"
    "2. Identify unsupported conclusions, leaps of logic, and overconfidence.\n"
    "3. Look for overlooked alternative explanations and internal contradictions.\n"
    "4. Check that recommended verification steps are safe and appropriately "
    "qualified (no autonomous physical machine control).\n"
    "5. You must be willing to disagree. Set revision_required=true and list concrete "
    "issues when the draft is not adequately supported. Do not approve by default.\n"
    "6. Never invent evidence IDs or documents.\n"
    "Return only the requested structured output."
)


def build_prompt(context: dict[str, Any]) -> str:
    draft = context["draft"]
    lines = [f"Draft summary: {draft.get('summary', '')}", "Hypotheses:"]
    for hypothesis in draft.get("hypotheses", []):
        lines.append(
            f"- {hypothesis.get('hypothesis_id')} \"{hypothesis.get('title')}\" "
            f"assessment={hypothesis.get('assessment')} "
            f"supporting={hypothesis.get('supporting_evidence_ids')} "
            f"contradicting={hypothesis.get('contradicting_evidence_ids')}\n"
            f"  description: {hypothesis.get('description')}\n"
            f"  verification: {hypothesis.get('verification_steps')}"
        )
    return (
        "\n".join(lines)
        + f"\n\n## Evidence catalog (the only valid IDs)\n"
        f"{format_evidence_catalog(context['evidence'])}\n\n"
        "Produce the CriticReviewOut structured output."
    )


SPEC = AgentSpec(
    name="critic_agent",
    label="Critic / Verification Agent",
    instruction=INSTRUCTION,
    output_schema=CriticReviewOut,
    build_prompt=build_prompt,
)
