"""Vision Agent - describes an uploaded inspection image.

The agent receives the image plus the deterministic incident/anomaly context and
returns structured, hedged observations. It never confirms a physical fault and
always lists limitations. The image itself is passed by the runtime as a
multimodal part; this module only defines the instruction, output schema, and
text prompt.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from services.api.agents.base import AgentSpec

SeverityHint = Literal["informational", "attention", "urgent"]


class VisualObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    observation: str = Field(description="A concrete thing that is visible in the image.")
    related_features: list[str] = Field(
        default_factory=list,
        description="Sensor feature keys this observation may relate to.",
    )
    severity_hint: SeverityHint = "informational"


class VisualAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(description="One-paragraph description of the image.")
    observations: list[VisualObservation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


INSTRUCTION = (
    "You are the Vision Agent in an industrial investigation system. You are "
    "given a single inspection image plus deterministic incident context. Rules "
    "you must follow:\n"
    "1. Describe only what is visibly present. Never guess part numbers, "
    "measurements, or hidden conditions.\n"
    "2. Never state that a fault is confirmed. Use hedged language and mark "
    "observations as informational, attention, or urgent.\n"
    "3. Only relate an observation to sensor feature keys that are listed in the "
    "provided context.\n"
    "4. Always record limitations (for example: lighting, resolution, single "
    "view, no scale reference).\n"
    "Return only the requested structured output."
)


def build_prompt(context: dict[str, Any]) -> str:
    incident = context.get("incident", {})
    anomaly = context.get("anomaly", {})
    image = context.get("image", {})
    features = ", ".join(
        feature.get("feature", "")
        for feature in anomaly.get("features", []) or []
        if feature.get("feature")
    )
    return (
        f"Incident {incident.get('incident_id')} (machine type "
        f"{incident.get('machine_type')}, severity {anomaly.get('severity')}).\n"
        f"Anomaly score {anomaly.get('anomaly_score')} against threshold "
        f"{anomaly.get('threshold')}.\n"
        f"Known sensor feature keys: {features or 'none'}.\n"
        f"Image: {image.get('filename')} ({image.get('width')}x{image.get('height')} "
        f"{image.get('mime_type')}).\n\n"
        "Analyse the attached image and produce the VisualAnalysis structured "
        "output. Describe visible conditions and list limitations."
    )


SPEC = AgentSpec(
    name="vision_agent",
    label="Vision Inspection Agent",
    instruction=INSTRUCTION,
    output_schema=VisualAnalysis,
    build_prompt=build_prompt,
)
