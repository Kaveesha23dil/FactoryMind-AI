"""Opt-in smoke test that performs one real Gemini call through ADK.

Skipped unless ``GOOGLE_API_KEY`` is set in the environment. This test never
runs as part of the deterministic suite because it costs tokens and requires
network access.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from services.api.agents import sensor_agent
from services.api.agents.runtime import AdkRuntime
from services.api.core import config

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY is not set; live Gemini smoke test skipped",
)


def test_live_gemini_sensor_agent_returns_structured_output():
    runtime = AdkRuntime(
        provider="google",
        model_name=config.settings.gemini_model,
    )
    prompt = (
        "Incident smoke test. Recorded torque is 68 Nm versus a baseline median "
        "of 40 Nm (robust z-score 5.6). Interpret this measurement without "
        "inventing numbers and produce the SensorAnalysis structured output."
    )
    output = asyncio.run(runtime.run(sensor_agent.SPEC, prompt))
    assert isinstance(output, dict)
    assert output.get("summary")
