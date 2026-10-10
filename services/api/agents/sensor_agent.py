"""Agent 1 - Sensor Analysis Agent.

Interprets deterministic numerical evidence. It never recalculates statistics,
never invents readings, and never uses ground-truth failure labels.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from services.api.agents.base import AgentSpec
from services.api.agents.prompts import (
    format_anomaly,
    format_baselines,
    format_evidence_catalog,
    format_measurements,
)


class SensorFeatureFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feature: str = Field(description="Feature key or label discussed.")
    observation: str = Field(description="Concise interpretation of the measured values.")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs (EV-SENSOR/EV-BASELINE/EV-ANOMALY) that support this.",
    )


class SensorAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(description="One-paragraph interpretation of the numerical evidence.")
    findings: list[SensorFeatureFinding] = Field(default_factory=list)
    missing_measurements: list[str] = Field(
        default_factory=list,
        description="Measurements that would help but are not available in this dataset.",
    )
    referenced_evidence_ids: list[str] = Field(default_factory=list)


INSTRUCTION = (
    "You are the Sensor Analysis Agent in an industrial investigation system. "
    "You receive validated sensor measurements and deterministic anomaly findings "
    "that were already computed in Python. Your job is to interpret them in plain "
    "engineering language. Rules you must follow:\n"
    "1. Never invent or recalculate numerical values. Use only the numbers provided.\n"
    "2. Never mention dataset failure labels; they are not available to you.\n"
    "3. Explicitly identify which features are unusual and why they contributed to the alert.\n"
    "4. Note missing measurements that are genuinely absent from this dataset "
    "(for example vibration or machine-specific time series).\n"
    "5. Cite supporting evidence using only the evidence IDs listed in the prompt. "
    "Do not create new IDs.\n"
    "6. State clearly that a high anomaly score means 'unusual relative to baseline', "
    "not 'confirmed failure'.\n"
    "Return only the requested structured output."
)


def build_prompt(context: dict[str, Any]) -> str:
    incident = context["incident"]
    return (
        f"Incident: {incident['incident_id']} (record {incident['record_id']}, "
        f"machine type {incident['machine_type']}).\n\n"
        f"## Recorded sensor measurements\n{format_measurements(context['measurements'])}\n\n"
        f"## Deterministic anomaly findings\n{format_anomaly(context['anomaly'])}\n\n"
        f"## Training baselines\n{format_baselines(context['baselines'])}\n\n"
        f"## Available evidence IDs (cite only these)\n{format_evidence_catalog(context['evidence'])}\n\n"
        "Produce the SensorAnalysis structured output."
    )


SPEC = AgentSpec(
    name="sensor_agent",
    label="Sensor Analysis Agent",
    instruction=INSTRUCTION,
    output_schema=SensorAnalysis,
    build_prompt=build_prompt,
)
