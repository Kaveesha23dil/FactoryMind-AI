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
from services.api.agents.orchestrator import Orchestrator
from services.api.tests.test_agent_orchestration import RecordingReporter, isolated_incident_store, anomaly_ids  # noqa: F401

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
    output = asyncio.run(asyncio.wait_for(runtime.run(sensor_agent.SPEC, prompt), timeout=60))
    assert isinstance(output, dict)
    assert output.get("summary")


def test_live_gemini_investigation_evidence_pipeline(isolated_incident_store, anomaly_ids):
    """Separate, isolated live pipeline: no development records are modified."""
    incident = isolated_incident_store.create_incident(anomaly_ids[0])
    runtime = AdkRuntime(provider='google', model_name=config.settings.gemini_model)
    reporter = RecordingReporter()
    result = asyncio.run(Orchestrator(runtime, isolated_incident_store,
        timeout_seconds=120, max_retries=0).run('INV-LIVE-VERIFY', incident['incident_id'], reporter))
    catalog = {r['evidence_id']: r for r in result.evidence}
    manual = {i for i, r in catalog.items() if r['evidence_type'] == 'manual_passage'}
    assert manual
    activity = next(a for a in reversed(reporter.agents) if a['agent'] == 'knowledge_agent' and a['status'] == 'completed')
    assert activity['evidence_count'] > 0
    for hypothesis in result.report['hypotheses']:
        assert set(hypothesis['supporting_evidence_ids'] + hypothesis['contradicting_evidence_ids']) <= set(catalog)
        assert hypothesis['supporting_evidence_ids'] or hypothesis['assessment'] == 'unsupported'
