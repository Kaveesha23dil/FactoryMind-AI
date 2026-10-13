"""Agent runtime and orchestrator tests (scripted model, no network)."""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import BaseModel

import services.api.routes.incidents as incident_routes
from services.api.agents import (
    critic_agent,
    investigation_agent,
    knowledge_agent,
    sensor_agent,
)
from services.api.agents.base import AgentSpec
from services.api.agents.orchestrator import (
    MAX_REVISIONS,
    InvestigationError,
    Orchestrator,
)
from services.api.agents.runtime import AdkRuntime, InvestigationProviderError
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.incident_service import (
    IncidentService,
    SqliteIncidentRepository,
)
from services.api.tests.conftest import (
    anomalous_record_ids,
    clear_scripted_responses,
    default_scripted_responses,
    install_scripted_responses,
)

AGENT_NAMES = {
    "sensor_agent",
    "knowledge_agent",
    "investigation_agent",
    "critic_agent",
}


class RecordingReporter:
    def __init__(self) -> None:
        self.stages: list[str] = []
        self.agents: list[dict] = []
        self.evidence_records: list[dict] = []

    def stage(self, stage: str, message: str | None = None) -> None:
        self.stages.append(stage)

    def agent(self, name, status, summary=None, evidence_count=None) -> None:
        self.agents.append(
            {
                "agent": name,
                "status": status,
                "summary": summary,
                "evidence_count": evidence_count,
            }
        )

    def evidence(self, records) -> None:
        self.evidence_records.extend(records)

    def activity(self) -> list[dict]:
        return self.agents


@pytest.fixture
def isolated_incident_store(tmp_path):
    service = IncidentService(SqliteIncidentRepository(Database(tmp_path / "api.db")))
    service.initialize()
    original = incident_routes._service
    incident_routes._service = service
    try:
        yield service
    finally:
        incident_routes._service = original


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine())


@pytest.fixture(autouse=True)
def _clean_scripted_registry():
    clear_scripted_responses()
    yield
    clear_scripted_responses()


def test_runtime_builds_adk_llm_agents():
    from google.adk.agents import LlmAgent

    runtime = AdkRuntime(
        provider="scripted",
        model_name="scripted",
        scripted_responses=default_scripted_responses(),
    )
    for spec in (
        sensor_agent.SPEC,
        knowledge_agent.SPEC,
        investigation_agent.SPEC,
        critic_agent.SPEC,
    ):
        agent = runtime.build_agent(spec)
        assert isinstance(agent, LlmAgent)
        assert agent.name == spec.name
        assert agent.output_schema is not None


def test_runtime_returns_schema_validated_output():
    runtime = AdkRuntime(
        provider="scripted",
        model_name="scripted",
        scripted_responses=default_scripted_responses(),
    )
    output = asyncio.run(runtime.run(sensor_agent.SPEC, "prompt"))
    assert output["summary"].startswith("Torque")
    assert output["findings"][0]["feature"] == "torque_nm"


def test_runtime_missing_scripted_response_raises():
    runtime = AdkRuntime(
        provider="scripted", model_name="scripted", scripted_responses={}
    )
    agent_run = runtime.run(sensor_agent.SPEC, "prompt")
    with pytest.raises(InvestigationProviderError):
        asyncio.run(agent_run)


def test_orchestrator_end_to_end(isolated_incident_store, anomaly_ids):
    install_scripted_responses()
    incident = isolated_incident_store.create_incident(anomaly_ids[0])
    runtime = AdkRuntime(
        provider="scripted",
        model_name="scripted",
        scripted_responses=default_scripted_responses(),
    )
    orchestrator = Orchestrator(
        runtime=runtime, incident_service=isolated_incident_store
    )
    reporter = RecordingReporter()

    result = asyncio.run(
        orchestrator.run("INV-UNIT-1", incident["incident_id"], reporter)
    )
    report = result.report

    assert report["status"] == "completed"
    assert report["provider"] == "scripted"
    assert len(report["hypotheses"]) == 2
    assert report["critic_review"]["verification_outcome"] == "supported"
    assert report["rejected_citations"] == []
    assert report["revision_count"] == 0
    assert report["evidence_catalog"]
    assert report["disclaimer"]
    assert result.evidence
    assert report["recommended_actions"]
    assert all(
        action["requires_human_approval"] for action in report["recommended_actions"]
    )

    assert _activity_agents(report) == AGENT_NAMES
    assert {record["agent"] for record in reporter.agents} == AGENT_NAMES

    rendered = json.dumps(report).lower()
    assert "ground_truth" not in rendered
    assert "machine failure" not in rendered


def test_orchestrator_rejects_unsupported_citation(
    isolated_incident_store, anomaly_ids
):
    draft = {
        "summary": "Draft citing a nonexistent evidence id.",
        "hypotheses": [
            {
                "hypothesis_id": "H-001",
                "title": "Bad citation",
                "description": "References evidence that does not exist.",
                "supporting_evidence_ids": ["EV-GHOST-999"],
                "contradicting_evidence_ids": [],
                "missing_evidence": [],
                "verification_steps": ["Inspect"],
                "assessment": "plausible",
            }
        ],
    }
    responses = default_scripted_responses()
    responses["investigation_agent"] = json.dumps(draft)

    incident = isolated_incident_store.create_incident(anomaly_ids[1])
    runtime = AdkRuntime(
        provider="scripted", model_name="scripted", scripted_responses=responses
    )
    orchestrator = Orchestrator(
        runtime=runtime, incident_service=isolated_incident_store
    )
    reporter = RecordingReporter()

    result = asyncio.run(
        orchestrator.run("INV-UNIT-2", incident["incident_id"], reporter)
    )
    report = result.report

    assert report["rejected_citations"] == ["EV-GHOST-999"]
    assert report["hypotheses"][0]["supporting_evidence_ids"] == []
    assert report["revision_count"] == MAX_REVISIONS
    assert any(
        "EV-GHOST-999" in finding
        for finding in report["critic_review"]["deterministic_findings"]
    )


def test_critic_can_force_revision(isolated_incident_store, anomaly_ids):
    dissenting = {
        "verification_outcome": "revision required",
        "issues_found": ["Hypothesis too confident"],
        "unsupported_claims": [],
        "contradictions": [],
        "alternative_explanations": ["Sensor drift"],
        "missing_evidence": ["Vibration"],
        "citation_issues": [],
        "revision_required": True,
    }
    responses = default_scripted_responses()
    responses["critic_agent"] = json.dumps(dissenting)

    incident = isolated_incident_store.create_incident(anomaly_ids[2])
    runtime = AdkRuntime(
        provider="scripted", model_name="scripted", scripted_responses=responses
    )
    orchestrator = Orchestrator(
        runtime=runtime, incident_service=isolated_incident_store
    )
    reporter = RecordingReporter()

    result = asyncio.run(
        orchestrator.run("INV-UNIT-3", incident["incident_id"], reporter)
    )
    report = result.report

    assert report["revision_count"] == MAX_REVISIONS
    assert report["critic_review"]["revision_required"] is True
    assert report["rejected_citations"] == []


class _DummyModel(BaseModel):
    ok: bool = True


class _SlowRuntime:
    provider = "scripted"
    model_name = "slow"

    async def run(self, spec, prompt):
        await asyncio.sleep(5)
        return {"ok": True}


class _FailingRuntime:
    provider = "scripted"
    model_name = "failing"

    async def run(self, spec, prompt):
        raise InvestigationProviderError("provider exploded")


def _dummy_spec() -> AgentSpec:
    return AgentSpec(
        name="dummy",
        label="Dummy",
        instruction="i",
        output_schema=_DummyModel,
        build_prompt=lambda context: "p",
    )


def test_agent_timeout_raises_investigation_error():
    orchestrator = Orchestrator(
        runtime=_SlowRuntime(),
        incident_service=None,
        timeout_seconds=0.05,
        max_retries=0,
    )
    spec = _dummy_spec()
    agent_run = orchestrator._run_agent(spec, {})
    with pytest.raises(InvestigationError):
        asyncio.run(agent_run)


def test_provider_failure_raises_investigation_error():
    orchestrator = Orchestrator(
        runtime=_FailingRuntime(),
        incident_service=None,
        timeout_seconds=1,
        max_retries=0,
    )
    spec = _dummy_spec()
    agent_run = orchestrator._run_agent(spec, {})
    with pytest.raises(InvestigationError):
        asyncio.run(agent_run)


def _activity_agents(report: dict) -> set[str]:
    return {entry["agent"] for entry in report["agent_activity"]}


@pytest.mark.parametrize('message,expected', [
    ('503 UNAVAILABLE high demand', True), ('429 RESOURCE_EXHAUSTED', True),
    ('500 INTERNAL', True), ('403 PERMISSION_DENIED', False),
    ('400 INVALID_ARGUMENT', False), ('No structured output', False),
])
def test_provider_error_retry_classification(message, expected):
    assert InvestigationProviderError(message).retryable is expected


def test_transient_provider_retry_recovers_with_backoff(monkeypatch):
    delays = []
    async def sleep(delay):
        delays.append(delay)
    monkeypatch.setattr('services.api.agents.orchestrator.asyncio.sleep', sleep)
    class Runtime:
        calls = 0
        async def run(self, spec, prompt):
            self.calls += 1
            if self.calls < 3:
                raise InvestigationProviderError('503 UNAVAILABLE')
            return {'ok': True}
    runtime = Runtime()
    orchestrator = Orchestrator(runtime, None, max_retries=3)
    assert asyncio.run(orchestrator._run_agent(_dummy_spec(), {})) == {'ok': True}
    assert runtime.calls == 3
    assert 5 <= delays[0] <= 6 and 10 <= delays[1] <= 11


def test_transient_retry_exhaustion_is_bounded(monkeypatch):
    async def sleep(delay):
        pass
    monkeypatch.setattr('services.api.agents.orchestrator.asyncio.sleep', sleep)
    class Runtime:
        calls = 0
        async def run(self, spec, prompt):
            self.calls += 1
            raise InvestigationProviderError('503 UNAVAILABLE')
    runtime = Runtime()
    orchestrator = Orchestrator(runtime, None, max_retries=3)
    with pytest.raises(InvestigationError, match='503'):
        asyncio.run(orchestrator._run_agent(_dummy_spec(), {}))
    assert runtime.calls == 4


def test_permanent_error_is_not_retried():
    class Runtime:
        calls = 0
        async def run(self, spec, prompt):
            self.calls += 1
            raise InvestigationProviderError('403 PERMISSION_DENIED')
    runtime = Runtime()
    with pytest.raises(InvestigationError, match='403'):
        asyncio.run(Orchestrator(runtime, None, max_retries=3)._run_agent(_dummy_spec(), {}))
    assert runtime.calls == 1


@pytest.mark.parametrize('message,delay,retryable', [
    ("429 RESOURCE_EXHAUSTED {'retryDelay': '42136s'}", 42136, False),
    ('429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier', None, False),
    ("429 RESOURCE_EXHAUSTED {'retryDelay': '12s'}", 12, True),
    ('503 UNAVAILABLE', None, True),
])
def test_quota_delay_classification(message, delay, retryable):
    error = InvestigationProviderError(message)
    assert error.retry_after_seconds == delay
    assert error.retryable is retryable


def test_daily_quota_is_not_retried():
    class Runtime:
        calls = 0
        async def run(self, spec, prompt):
            self.calls += 1
            raise InvestigationProviderError("429 RESOURCE_EXHAUSTED {'retryDelay': '42136s'}")
    runtime = Runtime()
    with pytest.raises(InvestigationError, match='429'):
        asyncio.run(Orchestrator(runtime, None, max_retries=3)._run_agent(_dummy_spec(), {}))
    assert runtime.calls == 1


def test_provider_error_closes_runner_stream(monkeypatch):
    from types import SimpleNamespace
    from services.api.agents import runtime as runtime_module
    closed = []
    class Runner:
        def __init__(self, **kwargs):
            pass
        async def run_async(self, **kwargs):
            try:
                yield SimpleNamespace(error_message='429 RESOURCE_EXHAUSTED')
            finally:
                closed.append(True)
    monkeypatch.setattr(runtime_module, 'Runner', Runner)
    runtime = AdkRuntime('scripted', 'scripted', default_scripted_responses())
    with pytest.raises(InvestigationProviderError, match='429'):
        asyncio.run(runtime.run(sensor_agent.SPEC, 'Test'))
    assert closed == [True]
