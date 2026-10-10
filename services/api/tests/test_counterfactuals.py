"""API tests for counterfactual investigations."""

from __future__ import annotations

import pytest

import services.api.routes.counterfactuals as counterfactual_routes
import services.api.routes.incidents as incident_routes
import services.api.routes.investigations as investigation_routes
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.counterfactual_repository import (
    SqliteCounterfactualRepository,
)
from services.api.services.counterfactual_service import CounterfactualService
from services.api.services.exclusion import resolve_excluded_features
from services.api.services.incident_service import (
    IncidentService,
    SqliteIncidentRepository,
)
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.investigation_service import InvestigationService
from services.api.tests.conftest import (
    anomalous_record_ids,
    clear_scripted_responses,
    install_scripted_responses,
)


@pytest.fixture()
def counterfactual_env(tmp_path):
    incident_service = IncidentService(
        SqliteIncidentRepository(Database(tmp_path / "api.db"))
    )
    incident_service.initialize()
    investigation_service = InvestigationService(
        repository=SqliteInvestigationRepository(Database(tmp_path / "inv.db")),
        incident_service=incident_service,
    )
    cf_service = CounterfactualService(
        investigation_service=investigation_service,
        repository=SqliteCounterfactualRepository(Database(tmp_path / "cf.db")),
    )

    originals = (
        incident_routes._service,
        investigation_routes._service,
        counterfactual_routes._service,
    )
    incident_routes._service = incident_service
    investigation_routes._service = investigation_service
    counterfactual_routes._service = cf_service
    install_scripted_responses()
    try:
        yield {"investigations": investigation_service, "counterfactual": cf_service}
    finally:
        (
            incident_routes._service,
            investigation_routes._service,
            counterfactual_routes._service,
        ) = originals
        clear_scripted_responses()


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine())


def _create_incident(client, record_id: int) -> str:
    response = client.post("/api/incidents", json={"record_id": record_id})
    assert response.status_code == 201
    return response.json()["incident_id"]


def _completed_investigation(client, incident_id: str) -> str:
    response = client.post(f"/api/incidents/{incident_id}/investigate")
    assert response.status_code == 202
    return response.json()["investigation_id"]


def _evidence_items(client, investigation_id: str) -> list[dict]:
    return client.get(f"/api/investigations/{investigation_id}/evidence").json()["items"]


def test_counterfactual_creates_isolated_revision(
    client, counterfactual_env, anomaly_ids
):
    incident_id = _create_incident(client, anomaly_ids[0])
    investigation_id = _completed_investigation(client, incident_id)

    evidence = _evidence_items(client, investigation_id)
    sensor = next(
        item for item in evidence if item["evidence_type"] == "sensor_measurement"
    )
    excluded_id = sensor["evidence_id"]
    expected_features, _ = resolve_excluded_features({excluded_id}, evidence)

    response = client.post(
        f"/api/investigations/{investigation_id}/counterfactual",
        json={
            "excluded_evidence_ids": [excluded_id],
            "rationale": "What if this measurement were unavailable?",
        },
    )
    assert response.status_code == 200, response.text
    scenario = response.json()
    assert scenario["status"] == "completed"
    assert scenario["original_investigation_id"] == investigation_id
    assert scenario["revised_investigation_id"].startswith("INV-")
    assert scenario["excluded_evidence_ids"] == [excluded_id]
    assert set(scenario["excluded_feature_keys"]) == expected_features
    assert scenario["dependency_trace"]

    comparison = scenario["comparison"]
    assert comparison is not None
    assert comparison["anomaly"]["recomputed"] is True
    assert comparison["excluded_evidence_ids"] == [excluded_id]

    # Original investigation is untouched.
    original = client.get(f"/api/investigations/{investigation_id}").json()
    assert original["status"] == "completed"
    original_ids = {item["evidence_id"] for item in _evidence_items(client, investigation_id)}
    assert excluded_id in original_ids

    # Revised investigation is a separate, completed record.
    revised_id = scenario["revised_investigation_id"]
    revised = client.get(f"/api/investigations/{revised_id}").json()
    assert revised["status"] == "completed"
    assert revised["report"]["counterfactual"]["scenario_id"] == scenario["scenario_id"]
    revised_ids = {item["evidence_id"] for item in _evidence_items(client, revised_id)}
    assert excluded_id not in revised_ids
    assert not (revised_ids & set(comparison["excluded_evidence_ids"]))


def test_counterfactual_blocks_reuse_of_excluded_evidence(
    client, counterfactual_env, anomaly_ids
):
    incident_id = _create_incident(client, anomaly_ids[1])
    investigation_id = _completed_investigation(client, incident_id)

    # The scripted investigation agent always cites EV-SENSOR-001, so excluding
    # it exercises the leakage guard end-to-end.
    evidence = _evidence_items(client, investigation_id)
    if not any(item["evidence_id"] == "EV-SENSOR-001" for item in evidence):
        pytest.skip("scripted fixture did not produce EV-SENSOR-001")

    scenario = client.post(
        f"/api/investigations/{investigation_id}/counterfactual",
        json={"excluded_evidence_ids": ["EV-SENSOR-001"]},
    ).json()
    revised_id = scenario["revised_investigation_id"]
    report = client.get(f"/api/investigations/{revised_id}").json()["report"]

    assert "EV-SENSOR-001" not in report["evidence_catalog"]
    assert "EV-SENSOR-001" in report["rejected_citations"]
    assert "EV-SENSOR-001" in report["critic_review"]["excluded_evidence_reused"]


def test_counterfactual_list_and_get(client, counterfactual_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[2])
    investigation_id = _completed_investigation(client, incident_id)
    evidence = _evidence_items(client, investigation_id)
    sensor = next(item for item in evidence if item["evidence_type"] == "sensor_measurement")

    scenario = client.post(
        f"/api/investigations/{investigation_id}/counterfactual",
        json={"excluded_evidence_ids": [sensor["evidence_id"]]},
    ).json()

    listed = client.get(
        f"/api/investigations/{investigation_id}/counterfactuals"
    ).json()
    assert listed["total"] == 1
    assert listed["items"][0]["scenario_id"] == scenario["scenario_id"]

    fetched = client.get(f"/api/counterfactuals/{scenario['scenario_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["scenario_id"] == scenario["scenario_id"]

    assert client.get("/api/counterfactuals/CFT-NOPE").status_code == 404


def test_counterfactual_rejects_bad_exclusions(client, counterfactual_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[3])
    investigation_id = _completed_investigation(client, incident_id)

    unknown = client.post(
        f"/api/investigations/{investigation_id}/counterfactual",
        json={"excluded_evidence_ids": ["EV-NOPE-999"]},
    )
    assert unknown.status_code == 400

    evidence = _evidence_items(client, investigation_id)
    everything = client.post(
        f"/api/investigations/{investigation_id}/counterfactual",
        json={"excluded_evidence_ids": [item["evidence_id"] for item in evidence]},
    )
    assert everything.status_code == 400

    assert (
        client.post(
            "/api/investigations/INV-NOPE/counterfactual",
            json={"excluded_evidence_ids": ["EV-SENSOR-001"]},
        ).status_code
        == 404
    )
