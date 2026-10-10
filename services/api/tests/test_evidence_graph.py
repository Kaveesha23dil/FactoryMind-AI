"""API tests for the evidence graph projection."""

from __future__ import annotations

import pytest

import services.api.routes.evidence_graph as graph_routes
import services.api.routes.incidents as incident_routes
import services.api.routes.investigations as investigation_routes
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.evidence_graph_service import EvidenceGraphService
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
def graph_env(tmp_path):
    incident_service = IncidentService(
        SqliteIncidentRepository(Database(tmp_path / "api.db"))
    )
    incident_service.initialize()
    investigation_service = InvestigationService(
        repository=SqliteInvestigationRepository(Database(tmp_path / "inv.db")),
        incident_service=incident_service,
    )
    graph_service = EvidenceGraphService(investigation_service)

    originals = (
        incident_routes._service,
        investigation_routes._service,
        graph_routes._service,
    )
    incident_routes._service = incident_service
    investigation_routes._service = investigation_service
    graph_routes._service = graph_service
    install_scripted_responses()
    try:
        yield investigation_service
    finally:
        (
            incident_routes._service,
            investigation_routes._service,
            graph_routes._service,
        ) = originals
        clear_scripted_responses()


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine())


def _investigation_id(client, record_id: int) -> str:
    incident_id = client.post(
        "/api/incidents", json={"record_id": record_id}
    ).json()["incident_id"]
    return client.post(f"/api/incidents/{incident_id}/investigate").json()[
        "investigation_id"
    ]


def test_graph_contains_incident_evidence_hypotheses_and_actions(
    client, graph_env, anomaly_ids
):
    investigation_id = _investigation_id(client, anomaly_ids[0])
    response = client.get(f"/api/investigations/{investigation_id}/graph")
    assert response.status_code == 200, response.text
    graph = response.json()

    node_ids = {node["id"] for node in graph["nodes"]}
    node_types = {node["type"] for node in graph["nodes"]}
    assert {"incident", "sensor_evidence", "hypothesis", "recommended_action"} <= node_types
    assert graph["node_count"] == len(graph["nodes"])
    assert graph["edge_count"] == len(graph["edges"])

    # Every edge references existing nodes.
    for edge in graph["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids

    relationships = {edge["relationship"] for edge in graph["edges"]}
    assert "RELATES_TO" in relationships
    assert "SUPPORTS" in relationships
    assert "RECOMMENDS" in relationships

    # Actions are linked back to the hypotheses that produced them.
    recommends = [
        edge for edge in graph["edges"] if edge["relationship"] == "RECOMMENDS"
    ]
    assert recommends


def test_graph_is_deterministic(client, graph_env, anomaly_ids):
    investigation_id = _investigation_id(client, anomaly_ids[1])
    first = client.get(f"/api/investigations/{investigation_id}/graph").json()
    second = client.get(f"/api/investigations/{investigation_id}/graph").json()
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_graph_unknown_investigation_404(client, graph_env):
    assert (
        client.get("/api/investigations/INV-NOPE/graph").status_code == 404
    )
