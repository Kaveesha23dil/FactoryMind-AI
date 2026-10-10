"""API tests for the AI investigation endpoints (isolated stores per test)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

import services.api.core.config as config
import services.api.routes.incidents as incident_routes
import services.api.routes.investigations as investigation_routes
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.incident_service import (
    IncidentService,
    SqliteIncidentRepository,
)
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.investigation_service import (
    DuplicateInvestigationError,
    InvestigationService,
)
from services.api.tests.conftest import (
    anomalous_record_ids,
    clear_scripted_responses,
    default_scripted_responses,
    install_scripted_responses,
)


def _queued_job(investigation_id: str, incident_id: str) -> dict:
    now = "2026-10-10T00:00:00+00:00"
    return {
        "investigation_id": investigation_id,
        "incident_id": incident_id,
        "status": "queued",
        "stage": "queued",
        "provider": "scripted",
        "model": "gemini-2.5-flash",
        "summary": None,
        "report": None,
        "error": None,
        "stage_history": [{"stage": "queued", "message": None, "timestamp": now}],
        "agent_activity": [],
        "attempt_count": 0,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "updated_at": now,
    }


@pytest.fixture()
def investigation_env(tmp_path):
    incident_service = IncidentService(
        SqliteIncidentRepository(Database(tmp_path / "api.db"))
    )
    incident_service.initialize()
    investigation_service = InvestigationService(
        repository=SqliteInvestigationRepository(Database(tmp_path / "inv.db")),
        incident_service=incident_service,
    )

    original_incident = incident_routes._service
    original_investigation = investigation_routes._service
    incident_routes._service = incident_service
    investigation_routes._service = investigation_service
    install_scripted_responses()
    try:
        yield investigation_service
    finally:
        incident_routes._service = original_incident
        investigation_routes._service = original_investigation
        clear_scripted_responses()


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine())


def _create_incident(client, record_id: int) -> str:
    response = client.post("/api/incidents", json={"record_id": record_id})
    assert response.status_code == 201
    return response.json()["incident_id"]


def test_start_investigation_completes_inline(client, investigation_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[0])

    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 202
    body = response.json()
    assert body["investigation_id"].startswith("INV-")
    assert body["incident_id"] == incident_id

    investigation_id = body["investigation_id"]
    fetched = client.get(f"/api/investigations/{investigation_id}")
    assert fetched.status_code == 200
    job = fetched.json()
    assert job["status"] == "completed"
    assert job["stage"] == "completed"
    assert job["report"] is not None
    assert job["report"]["hypotheses"]
    assert job["report"]["disclaimer"]
    assert job["report"]["rejected_citations"] == []
    assert {entry["agent"] for entry in job["agent_activity"]} == {
        "sensor_agent",
        "knowledge_agent",
        "investigation_agent",
        "critic_agent",
    }


def test_report_does_not_expose_ground_truth(client, investigation_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[1])
    investigation_id = client.post(
        f"/api/incidents/{incident_id}/investigate"
    ).json()["investigation_id"]

    report = client.get(f"/api/investigations/{investigation_id}").json()["report"]
    rendered = json.dumps(report).lower()
    assert "ground_truth" not in rendered
    assert "machine failure" not in rendered
    assert "failure probabilities" in report["disclaimer"].lower()
    assert "not confirmed physical diagnoses" in report["disclaimer"].lower()


def test_start_unknown_incident_404(client, investigation_env):
    assert client.post("/api/incidents/INC-NOPE/investigate").status_code == 404


def test_get_unknown_investigation_404(client, investigation_env):
    assert client.get("/api/investigations/INV-NOPE").status_code == 404
    assert client.get("/api/investigations/INV-NOPE/evidence").status_code == 404


def test_duplicate_active_investigation_409(client, investigation_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[2])
    investigation_env.repository.insert(_queued_job("INV-ACTIVE", incident_id))

    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 409
    assert response.json()["detail"]["existing_investigation_id"] == "INV-ACTIVE"


def test_duplicate_service_error_direct(investigation_env, anomaly_ids):
    incident_id = _create_incident_service(investigation_env, anomaly_ids[3])
    investigation_env.repository.insert(_queued_job("INV-ACTIVE-2", incident_id))
    with pytest.raises(DuplicateInvestigationError) as excinfo:
        investigation_env.start_investigation(incident_id)
    assert excinfo.value.existing_investigation_id == "INV-ACTIVE-2"


def test_list_investigations(client, investigation_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[4])
    investigation_id = client.post(
        f"/api/incidents/{incident_id}/investigate"
    ).json()["investigation_id"]

    listing = client.get(f"/api/incidents/{incident_id}/investigations").json()
    assert listing["total"] == 1
    assert listing["items"][0]["investigation_id"] == investigation_id
    assert listing["items"][0]["status"] == "completed"


def test_global_investigation_list(client, investigation_env, anomaly_ids):
    first_incident = _create_incident(client, anomaly_ids[0])
    first_id = client.post(
        f"/api/incidents/{first_incident}/investigate"
    ).json()["investigation_id"]

    page = client.get("/api/investigations").json()
    assert page["total"] == 1
    assert page["items"][0]["investigation_id"] == first_id
    assert page["items"][0]["status"] == "completed"

    completed = client.get(
        "/api/investigations", params={"status": "completed"}
    ).json()
    assert completed["total"] == 1

    queued = client.get("/api/investigations", params={"status": "queued"}).json()
    assert queued["total"] == 0

    assert (
        client.get("/api/investigations", params={"status": "bogus"}).status_code
        == 422
    )


def test_evidence_endpoint_returns_catalog(client, investigation_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[0])
    investigation_id = client.post(
        f"/api/incidents/{incident_id}/investigate"
    ).json()["investigation_id"]

    response = client.get(f"/api/investigations/{investigation_id}/evidence")
    assert response.status_code == 200
    body = response.json()
    assert body["investigation_id"] == investigation_id
    assert body["total"] == len(body["items"])
    assert body["total"] > 0
    for item in body["items"]:
        assert item["evidence_id"].startswith("EV-")
        assert item["source"]
        assert item["provenance"]
        assert "ground_truth" not in json.dumps(item).lower()


def test_disabled_investigation_returns_503(client, investigation_env, anomaly_ids, monkeypatch):
    incident_id = _create_incident(client, anomaly_ids[1])
    monkeypatch.setattr(
        config,
        "settings",
        replace(config.settings, ai_investigation_enabled=False),
    )
    assert client.post(f"/api/incidents/{incident_id}/investigate").status_code == 503


def test_worker_endpoint_requires_secret(client, investigation_env, anomaly_ids, monkeypatch):
    incident_id = _create_incident(client, anomaly_ids[2])

    monkeypatch.setattr(
        config, "settings", replace(config.settings, worker_secret=None)
    )
    # No secret configured -> endpoint disabled.
    assert (
        client.post(f"/api/investigations/INV-ANY/process").status_code == 403
    )

    monkeypatch.setattr(
        config, "settings", replace(config.settings, worker_secret="topsecret")
    )
    wrong = client.post(
        "/api/investigations/INV-ANY/process", headers={"X-Worker-Secret": "nope"}
    )
    assert wrong.status_code == 401


def test_worker_endpoint_executes_queued_job(client, investigation_env, anomaly_ids, monkeypatch):
    incident_id = _create_incident(client, anomaly_ids[3])
    investigation_env.repository.insert(_queued_job("INV-PROC", incident_id))

    monkeypatch.setattr(
        config, "settings", replace(config.settings, worker_secret="topsecret")
    )
    response = client.post(
        "/api/investigations/INV-PROC/process",
        headers={"X-Worker-Secret": "topsecret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["executed"] is True


def test_unsupported_citation_is_reported(client, investigation_env, anomaly_ids):
    from services.api.agents.runtime import set_scripted_response

    draft = {
        "summary": "Draft with a fabricated citation.",
        "hypotheses": [
            {
                "hypothesis_id": "H-001",
                "title": "Fabricated evidence",
                "description": "Cites an ID that does not exist.",
                "supporting_evidence_ids": ["EV-GHOST-999"],
                "contradicting_evidence_ids": [],
                "missing_evidence": [],
                "verification_steps": ["Inspect"],
                "assessment": "plausible",
            }
        ],
    }
    set_scripted_response("investigation_agent", json.dumps(draft))

    incident_id = _create_incident(client, anomaly_ids[4])
    investigation_id = client.post(
        f"/api/incidents/{incident_id}/investigate"
    ).json()["investigation_id"]

    job = client.get(f"/api/investigations/{investigation_id}").json()
    assert job["status"] == "completed"
    assert job["report"]["rejected_citations"] == ["EV-GHOST-999"]
    assert job["report"]["revision_count"] == 1
    assert any(
        "EV-GHOST-999" in finding
        for finding in job["report"]["critic_review"]["deterministic_findings"]
    )


def test_failed_job_is_persisted(client, investigation_env, anomaly_ids, monkeypatch):
    from services.api.agents import runtime as runtime_module

    def _boom():
        raise runtime_module.InvestigationProviderError("no provider")

    investigation_env._runtime_factory = _boom

    incident_id = _create_incident(client, anomaly_ids[0])
    investigation_id = client.post(
        f"/api/incidents/{incident_id}/investigate"
    ).json()["investigation_id"]

    job = client.get(f"/api/investigations/{investigation_id}").json()
    assert job["status"] == "failed"
    assert job["error"]
    assert job["report"] is None


def _create_incident_service(service: InvestigationService, record_id: int) -> str:
    return service.incident_service.create_incident(record_id)["incident_id"]
