"""Agent 3 - Root Cause Investigation Agent.

Combines the Sensor and Knowledge findings into several plausible, clearly
evidence-linked hypotheses. Assessments are qualitative and evidence-dependent,
never calibrated failure probabilities.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from services.api.agents.base import AgentSpec
from services.api.agents.prompts import format_evidence_catalog


class HypothesisDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str = Field(description="Stable id such as H-001.")
    title: str
    description: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    assessment: Literal["plausible", "weak", "unsupported"] = "weak"


class InvestigationDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str
    hypotheses: list[HypothesisDraft] = Field(default_factory=list)


INSTRUCTION = (
    "You are the Root Cause Investigation Agent. You receive a Sensor Analysis "
    "and a Knowledge Analysis for one incident. Produce several plausible root-cause "
    "hypotheses.\n"
    "Rules:\n"
    "1. Use only evidence IDs that appear in the provided evidence catalog. "
    "Never invent an evidence ID.\n"
    "2. Separate measured observations from inferred explanations.\n"
    "3. Provide both supporting and (where applicable) contradicting evidence IDs.\n"
    "4. Include at least one alternative hypothesis and note missing evidence.\n"
    "5. Assessments are qualitative ('plausible', 'weak', 'unsupported'). Do NOT give "
    "numeric probabilities or claim a confirmed diagnosis.\n"
    "6. Do not treat every unusual measurement as a machine failure.\n"
    "7. Propose concrete, safe verification/inspection checks for a technician.\n"
    "Return only the requested structured output."
)


def build_prompt(context: dict[str, Any]) -> str:
    incident = context["incident"]
    sensor = context["sensor_analysis"]
    knowledge = context["knowledge_analysis"]
    max_hypotheses = context.get("max_hypotheses", 4)
    feedback = context.get("revision_feedback")

    prompt = (
        f"Incident {incident['incident_id']} (record {incident['record_id']}, "
        f"machine type {incident['machine_type']}), anomaly severity "
        f"{incident['severity']}.\n\n"
        f"## Sensor Analysis summary\n{sensor.get('summary', '')}\n"
        f"Sensor findings:\n"
        + "\n".join(
            f"- {finding.get('feature')}: {finding.get('observation')} "
            f"(evidence {finding.get('evidence_ids')})"
            for finding in sensor.get("findings", [])
        )
        + f"\n\n## Knowledge Analysis summary\n{knowledge.get('summary', '')}\n"
        "Knowledge guidance:\n"
        + "\n".join(
            f"- {item.get('symptom')}: {item.get('guidance')} "
            f"(evidence {item.get('evidence_ids')})"
            for item in knowledge.get("guidance", [])
        )
        + f"\n\n## Evidence catalog (cite only these IDs)\n"
        f"{format_evidence_catalog(context['evidence'])}\n\n"
        f"Produce between 2 and {max_hypotheses} hypotheses."
    )
    if feedback:
        prompt += (
            "\n\n## REQUIRED REVISION\nThe previous report was rejected. "
            f"Fix these issues and try again:\n{feedback}\n"
            "Only reference evidence IDs that exist in the catalog above."
        )
    return prompt


SPEC = AgentSpec(
    name="investigation_agent",
    label="Root Cause Investigation Agent",
    instruction=INSTRUCTION,
    output_schema=InvestigationDraft,
    build_prompt=build_prompt,
)
