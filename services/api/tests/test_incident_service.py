"""Service-level tests for incident management and persistence."""

from __future__ import annotations

import pytest

from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine
from services.api.services.incident_service import (
    DuplicateIncidentError,
    IncidentNotFoundError,
    IncidentService,
    InvalidTransitionError,
    RecordNotAnomalousError,
    RecordNotFoundError,
    SqliteIncidentRepository,
)
from services.api.tests.conftest import anomalous_record_ids, normal_record_id


def _service(tmp_path) -> IncidentService:
    database = Database(tmp_path / "incidents.db")
    return IncidentService(SqliteIncidentRepository(database))


@pytest.fixture(scope="module")
def anomaly_ids():
    return anomalous_record_ids(get_engine(), limit=10)


def test_create_incident_from_anomalous_record(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[0], note="test")
    assert incident["status"] == "open"
    assert incident["record_id"] == anomaly_ids[0]
    assert incident["incident_id"].startswith("INC-")
    assert incident["ground_truth_used_for_detection"] is False
    assert incident["evidence"]
    assert incident["explanations"]
    assert len(incident["timeline"]) == 1
    assert "machine_failure" not in incident["source_measurements"]
    assert "ground_truth_failure" not in incident["source_measurements"]


def test_duplicate_active_incident_prevented(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    service.create_incident(anomaly_ids[0])
    with pytest.raises(DuplicateIncidentError):
        service.create_incident(anomaly_ids[0])


def test_incident_not_found(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(IncidentNotFoundError):
        service.get_incident("INC-DOESNOTEXIST")


def test_record_not_found(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(RecordNotFoundError):
        service.create_incident(999_999_999)


def test_non_anomalous_record_rejected(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(RecordNotAnomalousError):
        service.create_incident(normal_record_id(get_engine()))


def test_status_transitions(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[1])
    incident_id = incident["incident_id"]

    under_review = service.update_status(incident_id, "under_review")
    assert under_review["status"] == "under_review"

    resolved = service.update_status(incident_id, "resolved")
    assert resolved["status"] == "resolved"
    assert [entry["status"] for entry in resolved["timeline"]] == [
        "open",
        "under_review",
        "resolved",
    ]


def test_invalid_transition_rejected(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[2])
    # open -> open is not a permitted transition.
    with pytest.raises(InvalidTransitionError):
        service.update_status(incident["incident_id"], "open")


def test_resolved_incident_allows_new_one(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    first = service.create_incident(anomaly_ids[3])
    service.update_status(first["incident_id"], "resolved")
    second = service.create_incident(anomaly_ids[3])
    assert second["incident_id"] != first["incident_id"]


def test_persistence_across_instances(tmp_path, anomaly_ids):
    path = tmp_path / "persist.db"
    first = IncidentService(SqliteIncidentRepository(Database(path)))
    incident = first.create_incident(anomaly_ids[4])

    reopened = IncidentService(SqliteIncidentRepository(Database(path)))
    fetched = reopened.get_incident(incident["incident_id"])
    assert fetched["incident_id"] == incident["incident_id"]
    assert fetched["record_id"] == anomaly_ids[4]


def test_list_and_pagination_and_filters(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    for record_id in anomaly_ids[:4]:
        service.create_incident(record_id)

    page = service.list_incidents(limit=2, offset=0)
    assert page["total"] == 4
    assert page["returned"] == 2

    service.update_status(service.list_incidents(limit=1)["items"][0]["incident_id"], "under_review")
    under_review = service.list_incidents(status="under_review")
    assert under_review["total"] == 1

    high = service.list_incidents(severity="critical")
    assert high["total"] <= 4


def test_scan_is_idempotent(tmp_path):
    service = _service(tmp_path)
    first = service.scan(min_severity="critical", max_incidents=3)
    second = service.scan(min_severity="critical", max_incidents=3)
    assert first["incidents_created"] >= 1
    # The second scan must skip already-created active incidents.
    assert second["incidents_skipped_duplicate"] >= 1


def test_scan_dry_run_creates_nothing(tmp_path):
    service = _service(tmp_path)
    result = service.scan(min_severity="critical", max_incidents=3, dry_run=True)
    assert result["incidents_created"] == 0
    assert service.list_incidents()["total"] == 0


def test_investigation_payload_excludes_ground_truth(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[5])
    payload = service.investigation_payload(incident["incident_id"])
    serialized = str(payload).lower()
    assert "machine failure" not in serialized
    assert "ground_truth_failure" not in serialized
    assert payload["ground_truth_used_for_detection"] is False
    assert payload["dataset_sample_id"] == anomaly_ids[5]


def test_snapshot_retains_all_contributions_and_thresholds(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[0])
    assert len(incident["evidence"]) == len(get_engine().detector.feature_keys)
    assert incident["detection_config"]["feature_z_threshold"] == get_engine().detector.feature_z_threshold
    reopened = _service(tmp_path).get_incident(incident["incident_id"])
    assert reopened["detection_config"] == incident["detection_config"]


def test_stale_status_update_does_not_append_event(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[0])
    service.update_status(incident["incident_id"], "resolved")
    with pytest.raises(InvalidTransitionError, match="changed"):
        service.repository.update_status(incident["incident_id"], "under_review", {
            "incident_id": incident["incident_id"], "expected_status": "open",
            "timestamp": incident["created_at"], "status": "under_review",
        })
    assert len(service.get_incident(incident["incident_id"])["timeline"]) == 2


def test_legacy_schema_migration_preserves_incident(tmp_path, anomaly_ids):
    service = _service(tmp_path)
    incident = service.create_incident(anomaly_ids[0])
    with service.repository.database.connect() as connection:
        connection.execute("ALTER TABLE incidents DROP COLUMN detection_config")
        connection.commit()
    reopened = _service(tmp_path).get_incident(incident["incident_id"])
    assert reopened["detection_config"] is None
    assert reopened["evidence"] == incident["evidence"]
    assert reopened["timeline"] == incident["timeline"]
