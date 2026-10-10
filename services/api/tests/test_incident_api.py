"""API tests for incident endpoints (isolated database per test)."""

from __future__ import annotations

import pytest

import services.api.routes.incidents as incident_routes
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.incident_service import (
    IncidentService,
    SqliteIncidentRepository,
)
from services.api.tests.conftest import anomalous_record_ids, normal_record_id


@pytest.fixture()
def isolated_incident_store(tmp_path):
    service = IncidentService(SqliteIncidentRepository(Database(tmp_path / "api.db")))
    service.initialize()
    original = incident_routes._service
    incident_routes._service = service
    yield service
    incident_routes._service = original


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine())


def test_create_get_and_list(client, isolated_incident_store, anomaly_ids):
    created = client.post("/api/incidents", json={"record_id": anomaly_ids[0], "note": "n"})
    assert created.status_code == 201
    incident_id = created.json()["incident_id"]

    fetched = client.get(f"/api/incidents/{incident_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "open"

    listing = client.get("/api/incidents").json()
    assert listing["total"] == 1
    assert listing["items"][0]["incident_id"] == incident_id


def test_duplicate_returns_409(client, isolated_incident_store, anomaly_ids):
    first = client.post("/api/incidents", json={"record_id": anomaly_ids[1]})
    assert first.status_code == 201
    second = client.post("/api/incidents", json={"record_id": anomaly_ids[1]})
    assert second.status_code == 409
    assert second.json()["detail"]["existing_incident_id"] == first.json()["incident_id"]


def test_create_unknown_record_404(client, isolated_incident_store):
    assert client.post("/api/incidents", json={"record_id": 999999999}).status_code == 404


def test_create_non_anomalous_422(client, isolated_incident_store):
    response = client.post("/api/incidents", json={"record_id": normal_record_id(get_engine())})
    assert response.status_code == 422


def test_status_transitions_and_invalid(client, isolated_incident_store, anomaly_ids):
    incident_id = client.post("/api/incidents", json={"record_id": anomaly_ids[2]}).json()["incident_id"]

    under_review = client.patch(f"/api/incidents/{incident_id}/status", json={"status": "under_review"})
    assert under_review.status_code == 200
    assert under_review.json()["status"] == "under_review"

    invalid = client.patch(f"/api/incidents/{incident_id}/status", json={"status": "open"})
    assert invalid.status_code == 200  # under_review -> open is permitted

    bad = client.patch(f"/api/incidents/{incident_id}/status", json={"status": "resolved"})
    assert bad.status_code == 200

    # resolved -> open is not permitted
    assert client.patch(f"/api/incidents/{incident_id}/status", json={"status": "open"}).status_code == 409


def test_unknown_status_value_422(client, isolated_incident_store, anomaly_ids):
    incident_id = client.post("/api/incidents", json={"record_id": anomaly_ids[3]}).json()["incident_id"]
    response = client.patch(f"/api/incidents/{incident_id}/status", json={"status": "banana"})
    assert response.status_code == 422


def test_incident_not_found(client, isolated_incident_store):
    assert client.get("/api/incidents/INC-NOPE").status_code == 404
    assert client.patch("/api/incidents/INC-NOPE/status", json={"status": "resolved"}).status_code == 404


def test_incident_list_filters(client, isolated_incident_store, anomaly_ids):
    for record_id in anomaly_ids[:3]:
        client.post("/api/incidents", json={"record_id": record_id})
    assert client.get("/api/incidents", params={"status": "open"}).json()["total"] == 3
    assert client.get("/api/incidents", params={"status": "bogus"}).status_code == 422
    assert client.get("/api/incidents", params={"severity": "bogus"}).status_code == 422


def test_scan_dry_run(client, isolated_incident_store):
    response = client.post(
        "/api/incidents/scan",
        json={"min_severity": "critical", "max_incidents": 3, "dry_run": True},
    )
    assert response.status_code == 200
    assert response.json()["incidents_created"] == 0


def test_investigation_payload_endpoint(client, isolated_incident_store, anomaly_ids):
    incident_id = client.post("/api/incidents", json={"record_id": anomaly_ids[4]}).json()["incident_id"]
    response = client.get(f"/api/incidents/{incident_id}/investigation-payload")
    assert response.status_code == 200
    body = response.json()
    assert body["ground_truth_used_for_detection"] is False
    assert "ground_truth_failure" not in str(body).lower()


def test_anomaly_results_reflect_incident_status(client, isolated_incident_store, anomaly_ids):
    record_id = anomaly_ids[0]
    created = client.post("/api/incidents", json={"record_id": record_id})
    assert created.status_code == 201

    detail = client.get(f"/api/anomalies/{record_id}").json()
    assert detail["incident_status"] == "open"
    assert detail["incident_id"] == created.json()["incident_id"]

    listing = client.get("/api/anomalies", params={"limit": 200}).json()
    match = next(r for r in listing["records"] if r["record_id"] == record_id)
    assert match["incident_status"] == "open"
    assert match["incident_id"] == created.json()["incident_id"]
