"""API tests for visual inspection upload and analysis."""

from __future__ import annotations

import base64

import pytest

import services.api.core.config as config
import services.api.routes.evidence_graph as graph_routes
import services.api.routes.incidents as incident_routes
import services.api.routes.investigations as investigation_routes
import services.api.routes.visual_inspection as visual_routes
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.evidence_graph_service import EvidenceGraphService
from services.api.services.incident_service import (
    IncidentService,
    SqliteIncidentRepository,
)
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.investigation_service import InvestigationService
from services.api.services.visual_evidence_service import VisualEvidenceService
from services.api.services.visual_repository import SqliteVisualEvidenceRepository
from services.api.tests.conftest import (
    anomalous_record_ids,
    clear_scripted_responses,
    install_scripted_responses,
)

#: 1x1 transparent PNG.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def visual_env(tmp_path):
    incident_service = IncidentService(
        SqliteIncidentRepository(Database(tmp_path / "api.db"))
    )
    incident_service.initialize()
    investigation_service = InvestigationService(
        repository=SqliteInvestigationRepository(Database(tmp_path / "inv.db")),
        incident_service=incident_service,
    )
    visual_service = VisualEvidenceService(
        incident_service=incident_service,
        investigation_service=investigation_service,
        repository=SqliteVisualEvidenceRepository(Database(tmp_path / "vision.db")),
        storage_dir=tmp_path / "images",
    )
    graph_service = EvidenceGraphService(investigation_service)

    originals = (
        incident_routes._service,
        investigation_routes._service,
        visual_routes._service,
        graph_routes._service,
    )
    incident_routes._service = incident_service
    investigation_routes._service = investigation_service
    visual_routes._service = visual_service
    graph_routes._service = graph_service
    install_scripted_responses()
    try:
        yield visual_service
    finally:
        (
            incident_routes._service,
            investigation_routes._service,
            visual_routes._service,
            graph_routes._service,
        ) = originals
        clear_scripted_responses()


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine())


def _create_incident(client, record_id: int) -> str:
    return client.post("/api/incidents", json={"record_id": record_id}).json()[
        "incident_id"
    ]


def _upload(client, incident_id: str, name: str = "tool.png"):
    return client.post(
        f"/api/incidents/{incident_id}/images",
        files={"file": (name, PNG_BYTES, "image/png")},
    )


def test_upload_and_fetch_image(client, visual_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[0])
    response = _upload(client, incident_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["image_id"].startswith("IMG-")
    assert body["incident_id"] == incident_id
    assert body["mime_type"] == "image/png"
    assert body["width"] == 1 and body["height"] == 1
    assert body["status"] == "stored"
    assert body["content_url"].endswith("/content")

    listing = client.get(f"/api/incidents/{incident_id}/images").json()
    assert listing["total"] == 1

    content = client.get(f"/api/images/{body['image_id']}/content")
    assert content.status_code == 200
    assert content.content == PNG_BYTES

    assert client.get("/api/images/IMG-NOPE").status_code == 404


def test_analyze_attaches_visual_evidence(client, visual_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[1])
    investigation_id = client.post(
        f"/api/incidents/{incident_id}/investigate"
    ).json()["investigation_id"]

    image_id = _upload(client, incident_id).json()["image_id"]
    analyzed = client.post(
        f"/api/images/{image_id}/analyze",
        json={"investigation_id": investigation_id},
    )
    assert analyzed.status_code == 200, analyzed.text
    record = analyzed.json()
    assert record["status"] == "analyzed"
    assert record["observations"]
    assert record["limitations"]

    evidence = client.get(
        f"/api/investigations/{investigation_id}/evidence"
    ).json()["items"]
    visual = [item for item in evidence if item["evidence_type"] == "visual_observation"]
    assert visual
    assert visual[0]["evidence_id"].startswith("EV-VISUAL-")

    graph = client.get(f"/api/investigations/{investigation_id}/graph").json()
    visual_nodes = [node for node in graph["nodes"] if node["type"] == "visual_evidence"]
    assert visual_nodes


def test_analyze_without_investigation(client, visual_env, anomaly_ids):
    incident_id = _create_incident(client, anomaly_ids[2])
    image_id = _upload(client, incident_id).json()["image_id"]
    record = client.post(f"/api/images/{image_id}/analyze").json()
    assert record["status"] == "analyzed"
    assert record["investigation_id"] is None


def test_reject_invalid_and_oversized_uploads(client, visual_env, anomaly_ids, monkeypatch):
    incident_id = _create_incident(client, anomaly_ids[3])

    invalid = client.post(
        f"/api/incidents/{incident_id}/images",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert invalid.status_code == 400

    assert _upload(client, "INC-NOPE").status_code == 404

    monkeypatch.setattr(config, "VISUAL_MAX_IMAGE_BYTES", 4)
    oversized = _upload(client, incident_id)
    assert oversized.status_code == 413
