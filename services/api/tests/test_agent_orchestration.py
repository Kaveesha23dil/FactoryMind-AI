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


@pytest.fixture()
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
    runtime = AdkRuntime(provider="scripted", model_name="scripted", scripted_responses={})
    with pytest.raises(InvestigationProviderError):
        asyncio.run(runtime.run(sensor_agent.SPEC, "prompt"))


def test_orchestrator_end_to_end(isolated_incident_store, anomaly_ids):
    install_scripted_responses()
    incident = isolated_incident_store.create_incident(anomaly_ids[0])
    runtime = AdkRuntime(
        provider="scripted",
        model_name="scripted",
        scripted_responses=default_scripted_responses(),
    )
    orchestrator = Orchestrator(runtime=runtime, incident_service=isolated_incident_store)
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
    assert all(action["requires_human_approval"] for action in report["recommended_actions"])

    assert _activity_agents(report) == AGENT_NAMES
    assert {record["agent"] for record in reporter.agents} == AGENT_NAMES

    rendered = json.dumps(report).lower()
    assert "ground_truth" not in rendered
    assert "machine failure" not in rendered


def test_orchestrator_rejects_unsupported_citation(isolated_incident_store, anomaly_ids):
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
    orchestrator = Orchestrator(runtime=runtime, incident_service=isolated_incident_store)
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
    orchestrator = Orchestrator(runtime=runtime, incident_service=isolated_incident_store)
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
        runtime=_SlowRuntime(), incident_service=None, timeout_seconds=0.05, max_retries=0
    )
    with pytest.raises(InvestigationError):
        asyncio.run(orchestrator._run_agent(_dummy_spec(), {}))


def test_provider_failure_raises_investigation_error():
    orchestrator = Orchestrator(
        runtime=_FailingRuntime(), incident_service=None, timeout_seconds=1, max_retries=0
    )
    with pytest.raises(InvestigationError):
        asyncio.run(orchestrator._run_agent(_dummy_spec(), {}))


def _activity_agents(report: dict) -> set[str]:
    return {entry["agent"] for entry in report["agent_activity"]}
