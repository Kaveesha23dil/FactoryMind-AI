"""Incident management service and repository abstraction.

The service owns business rules (validation, transitions, idempotency) and
delegates storage to a repository. The only repository implemented today is
SQLite; the :class:`IncidentRepository` interface keeps the door open to a
Google Firestore implementation without touching the service.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from services.api import data
from services.api.core import config
from services.api.db.database import Database
from services.api.services.anomaly_engine import get_engine

logger = logging.getLogger(__name__)


class IncidentError(Exception):
    """Base class for incident domain errors."""


class RecordNotFoundError(IncidentError):
    pass


class RecordNotAnomalousError(IncidentError):
    pass


class IncidentNotFoundError(IncidentError):
    pass


class DuplicateIncidentError(IncidentError):
    def __init__(self, existing_incident_id: str) -> None:
        super().__init__(
            "An active incident already exists for this record and algorithm"
        )
        self.existing_incident_id = existing_incident_id


class InvalidTransitionError(IncidentError):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentRepository(ABC):
    """Storage contract for incidents."""

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def insert(self, incident: dict, event: dict) -> None: ...

    @abstractmethod
    def get(self, incident_id: str) -> dict | None: ...

    @abstractmethod
    def find_active(self, record_id: int, algorithm: str) -> dict | None: ...

    @abstractmethod
    def list(
        self,
        limit: int,
        offset: int,
        status: str | None,
        severity: str | None,
    ) -> tuple[int, list[dict]]: ...

    @abstractmethod
    def update_status(self, incident_id: str, status: str, event: dict) -> None: ...

    @abstractmethod
    def events(self, incident_id: str) -> list[dict]: ...

    @abstractmethod
    def active_record_statuses(self, record_ids: list[int]) -> dict[int, dict]: ...


class SqliteIncidentRepository(IncidentRepository):
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def initialize(self) -> None:
        self.database.initialize()

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> dict:
        return {
            "incident_id": row["incident_id"],
            "record_id": row["record_id"],
            "product_id": row["product_id"],
            "machine_type": row["machine_type"],
            "algorithm": row["algorithm"],
            "anomaly_score": row["anomaly_score"],
            "severity": row["severity"],
            "status": row["status"],
            "source_measurements": json.loads(row["source_measurements"]),
            "evidence": json.loads(row["evidence"]),
            "explanations": json.loads(row["explanations"]),
            "note": row["note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "detection_config": json.loads(row["detection_config"]) if row["detection_config"] else None,
        }

    def insert(self, incident: dict, event: dict) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, record_id, product_id, machine_type, algorithm,
                    anomaly_score, severity, status, source_measurements,
                    evidence, explanations, note, created_at, updated_at, detection_config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident["incident_id"],
                    incident["record_id"],
                    incident["product_id"],
                    incident["machine_type"],
                    incident["algorithm"],
                    incident["anomaly_score"],
                    incident["severity"],
                    incident["status"],
                    json.dumps(incident["source_measurements"]),
                    json.dumps(incident["evidence"]),
                    json.dumps(incident["explanations"]),
                    incident["note"],
                    incident["created_at"],
                    incident["updated_at"],
                    json.dumps(incident["detection_config"], allow_nan=False),
                ),
            )
            self._insert_event(connection, event)
            connection.commit()

    @staticmethod
    def _insert_event(connection: sqlite3.Connection, event: dict) -> None:
        connection.execute(
            """
            INSERT INTO incident_events (incident_id, status, note, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (event["incident_id"], event["status"], event.get("note"), event["timestamp"]),
        )

    def get(self, incident_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def find_active(self, record_id: int, algorithm: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM incidents
                WHERE record_id = ? AND algorithm = ? AND status != 'resolved'
                ORDER BY created_at DESC LIMIT 1
                """,
                (record_id, algorithm),
            ).fetchone()
        return self._row_to_incident(row) if row else None

    def list(
        self,
        limit: int,
        offset: int,
        status: str | None,
        severity: str | None,
    ) -> tuple[int, list[dict]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self.database.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS c FROM incidents {where}", params
                ).fetchone()["c"]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM incidents {where}
                ORDER BY created_at DESC, incident_id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return total, [self._row_to_incident(row) for row in rows]

    def update_status(self, incident_id: str, status: str, event: dict) -> None:
        with self.database.connect() as connection:
            result = connection.execute(
                "UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ? AND status = ?",
                (status, event["timestamp"], incident_id, event["expected_status"]),
            )
            if result.rowcount != 1:
                raise InvalidTransitionError("Incident status changed; refresh before retrying")
            self._insert_event(connection, event)
            connection.commit()

    def events(self, incident_id: str) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT status, note, timestamp FROM incident_events
                WHERE incident_id = ? ORDER BY id ASC
                """,
                (incident_id,),
            ).fetchall()
        return [
            {"status": row["status"], "note": row["note"], "timestamp": row["timestamp"]}
            for row in rows
        ]

    def active_record_statuses(self, record_ids: list[int]) -> dict[int, dict]:
        if not record_ids:
            return {}
        placeholders = ",".join("?" for _ in record_ids)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT incident_id, record_id, status, severity FROM incidents
                WHERE status != 'resolved' AND record_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                record_ids,
            ).fetchall()
        statuses: dict[int, dict] = {}
        for row in rows:
            statuses.setdefault(
                int(row["record_id"]),
                {
                    "incident_id": row["incident_id"],
                    "status": row["status"],
                    "severity": row["severity"],
                },
            )
        return statuses


class IncidentService:
    def __init__(self, repository: IncidentRepository | None = None) -> None:
        self.repository = repository or SqliteIncidentRepository()
        # Ensure the schema exists so the service is usable immediately
        # (idempotent: uses CREATE IF NOT EXISTS).
        self.repository.initialize()

    def initialize(self) -> None:
        self.repository.initialize()

    # -- helpers ---------------------------------------------------------

    def _record_row(self, record_id: int):
        frame = data.get_dataset()
        match = frame[frame["UDI"] == record_id]
        if match.empty:
            return None
        return match.iloc[0]

    @staticmethod
    def _new_incident_id() -> str:
        return f"{config.INCIDENT_ID_PREFIX}{uuid.uuid4().hex[:10].upper()}"

    def _build_evidence(self, anomaly: dict) -> tuple[list[dict], list[str]]:
        evidence = anomaly["features"]
        flagged = anomaly["anomalous_features"]
        explanations = [feature["explanation"] for feature in flagged]
        summary = (
            f"Anomaly score {anomaly['anomaly_score']:.2f} "
            f"({anomaly['severity']}) exceeds the configured threshold "
            f"{anomaly['threshold']:.2f}; "
            f"{sum(feature['is_anomalous'] for feature in evidence)} feature(s) exceed the per-feature z-score limit "
            f"{anomaly['feature_z_threshold']:.2f}."
        )
        return evidence, [summary, *explanations]

    # -- commands --------------------------------------------------------

    def create_incident(self, record_id: int, note: str | None = None) -> dict:
        engine = get_engine()
        anomaly = engine.get(record_id)
        if anomaly is None:
            raise RecordNotFoundError(f"Record {record_id} not found")
        if not anomaly["is_anomaly"]:
            raise RecordNotAnomalousError(
                f"Record {record_id} is not a detected anomaly "
                f"(score {anomaly['anomaly_score']:.2f} < threshold "
                f"{anomaly['threshold']:.2f})"
            )

        algorithm = anomaly["algorithm"]
        existing = self.repository.find_active(record_id, algorithm)
        if existing is not None:
            raise DuplicateIncidentError(existing["incident_id"])

        row = self._record_row(record_id)
        source_measurements = data.to_measurement(row) if row is not None else {}
        evidence, explanations = self._build_evidence(anomaly)

        now = _utcnow_iso()
        incident = {
            "incident_id": self._new_incident_id(),
            "record_id": record_id,
            "product_id": anomaly.get("product_id", ""),
            "machine_type": anomaly.get("machine_type", ""),
            "algorithm": algorithm,
            "anomaly_score": float(anomaly["anomaly_score"]),
            "severity": anomaly["severity"],
            "status": "open",
            "source_measurements": source_measurements,
            "evidence": evidence,
            "explanations": explanations,
            "note": note,
            "created_at": now,
            "updated_at": now,
            "detection_config": {
                "threshold": anomaly["threshold"],
                "feature_z_threshold": anomaly["feature_z_threshold"],
                "baseline_fit_sample_count": len(engine.train_frame),
                "split_seed": config.RANDOM_SEED,
            },
        }
        event = {"incident_id": incident["incident_id"], "status": "open", "note": note, "timestamp": now}

        try:
            self.repository.insert(incident, event)
        except sqlite3.IntegrityError as exc:  # unique active-incident index
            existing = self.repository.find_active(record_id, algorithm)
            raise DuplicateIncidentError(
                existing["incident_id"] if existing else "unknown"
            ) from exc

        logger.info("Created incident %s for record %d", incident["incident_id"], record_id)
        return self.get_incident(incident["incident_id"])

    def get_incident(self, incident_id: str) -> dict:
        incident = self.repository.get(incident_id)
        if incident is None:
            raise IncidentNotFoundError(f"Incident {incident_id} not found")
        incident["timeline"] = self.repository.events(incident_id)
        incident["ground_truth_used_for_detection"] = False
        return incident

    def status_map(self, record_ids: list[int]) -> dict[int, dict]:
        """Map each record id to its active incident (status + id), if any."""
        return self.repository.active_record_statuses(record_ids)

    def list_incidents(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        severity: str | None = None,
    ) -> dict:
        total, rows = self.repository.list(limit, offset, status, severity)
        items = [
            {
                "incident_id": row["incident_id"],
                "record_id": row["record_id"],
                "machine_type": row["machine_type"],
                "algorithm": row["algorithm"],
                "anomaly_score": row["anomaly_score"],
                "severity": row["severity"],
                "status": row["status"],
                "note": row["note"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(items),
            "items": items,
        }

    def update_status(self, incident_id: str, new_status: str, note: str | None = None) -> dict:
        incident = self.repository.get(incident_id)
        if incident is None:
            raise IncidentNotFoundError(f"Incident {incident_id} not found")

        current = incident["status"]
        allowed = config.INCIDENT_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from '{current}' to '{new_status}'"
            )

        event = {
            "incident_id": incident_id,
            "status": new_status,
            "note": note,
            "timestamp": _utcnow_iso(),
            "expected_status": current,
        }
        try:
            self.repository.update_status(incident_id, new_status, event)
        except sqlite3.IntegrityError as exc:
            # e.g. reopening a resolved incident while another active one exists.
            raise DuplicateIncidentError("another active incident") from exc

        # The durable timeline holds IDs and statuses; do not log request-derived text.
        logger.info("Incident status updated")
        return self.get_incident(incident_id)

    def scan(
        self, min_severity: str = "high", max_incidents: int = 25, dry_run: bool = False
    ) -> dict:
        engine = get_engine()
        candidates = engine.scan_candidates(min_severity=min_severity, max_incidents=max_incidents)
        created: list[str] = []
        skipped = 0
        for anomaly in candidates:
            record_id = anomaly["record_id"]
            algorithm = anomaly["algorithm"]
            if self.repository.find_active(record_id, algorithm) is not None:
                skipped += 1
                continue
            if dry_run:
                continue
            try:
                incident = self.create_incident(record_id, note=f"Auto-scan ({min_severity})")
                created.append(incident["incident_id"])
            except DuplicateIncidentError:
                skipped += 1
        return {
            "min_severity": min_severity,
            "max_incidents": max_incidents,
            "dry_run": dry_run,
            "candidates_evaluated": len(candidates),
            "incidents_created": len(created),
            "incidents_skipped_duplicate": skipped,
            "created_incident_ids": created,
        }

    def investigation_payload(self, incident_id: str) -> dict:
        """Build the Step 4 AI investigation payload (no ground-truth labels)."""
        incident = self.get_incident(incident_id)
        return {
            "incident_id": incident["incident_id"],
            "dataset_sample_id": incident["record_id"],
            "machine_type": incident["machine_type"],
            "algorithm": incident["algorithm"],
            "anomaly_score": incident["anomaly_score"],
            "severity": incident["severity"],
            "sensor_measurements": incident["source_measurements"],
            "anomalous_features": [feature for feature in incident["evidence"] if feature["is_anomalous"]],
            "algorithm_findings": {
                "features": incident["evidence"],
                "detection_config": incident["detection_config"],
            },
            "detection_explanations": incident["explanations"],
            "source_metadata": {
                "dataset": config.DATASET_NAME,
                "source": config.DATASET_SOURCE,
                "created_at": incident["created_at"],
            },
            "ground_truth_used_for_detection": False,
        }


# Re-export for convenience.
__all__ = [
    "IncidentService",
    "IncidentRepository",
    "SqliteIncidentRepository",
    "IncidentError",
    "RecordNotFoundError",
    "RecordNotAnomalousError",
    "IncidentNotFoundError",
    "DuplicateIncidentError",
    "InvalidTransitionError",
]
