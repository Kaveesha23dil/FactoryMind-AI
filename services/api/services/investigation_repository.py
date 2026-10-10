"""Persistence for AI investigations and their evidence.

Storage is SQLite via the shared :class:`Database`, mirroring the incident
repository so it can later be replaced by Firestore without touching the
service or orchestrator.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from services.api.db.database import Database
from services.api.services.incident_service import InvalidTransitionError

_JSON_COLUMNS = {"stage_history", "agent_activity", "report"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InvestigationNotFoundError(Exception):
    pass


class InvestigationRepository(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def insert(self, job: dict) -> None: ...

    @abstractmethod
    def get(self, investigation_id: str) -> dict | None: ...

    @abstractmethod
    def find_active(self, incident_id: str) -> dict | None: ...

    @abstractmethod
    def list_for_incident(
        self, incident_id: str, limit: int, offset: int
    ) -> tuple[int, list[dict]]: ...

    @abstractmethod
    def list_all(
        self, limit: int, offset: int, status: str | None
    ) -> tuple[int, list[dict]]: ...

    @abstractmethod
    def update(self, investigation_id: str, **fields: Any) -> None: ...

    @abstractmethod
    def append_stage(self, investigation_id: str, entry: dict) -> None: ...

    @abstractmethod
    def upsert_agent(self, investigation_id: str, activity: dict) -> None: ...

    @abstractmethod
    def queued_jobs(self, limit: int = 5) -> list[dict]: ...

    @abstractmethod
    def save_evidence(self, records: list[dict]) -> None: ...

    @abstractmethod
    def get_evidence(self, investigation_id: str) -> list[dict]: ...


class SqliteInvestigationRepository(InvestigationRepository):
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def initialize(self) -> None:
        self.database.initialize()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> dict:
        return {
            "investigation_id": row["investigation_id"],
            "incident_id": row["incident_id"],
            "status": row["status"],
            "stage": row["stage"],
            "provider": row["provider"],
            "model": row["model"],
            "summary": row["summary"],
            "error": row["error"],
            "attempt_count": row["attempt_count"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "updated_at": row["updated_at"],
            "stage_history": json.loads(row["stage_history"] or "[]"),
            "agent_activity": json.loads(row["agent_activity"] or "[]"),
            "report": json.loads(row["report"]) if row["report"] else None,
        }

    def insert(self, job: dict) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO investigations (
                    investigation_id, incident_id, status, stage, provider, model,
                    summary, report, error, stage_history, agent_activity,
                    attempt_count, created_at, started_at, completed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["investigation_id"],
                    job["incident_id"],
                    job["status"],
                    job["stage"],
                    job["provider"],
                    job["model"],
                    job.get("summary"),
                    json.dumps(job.get("report")) if job.get("report") else None,
                    job.get("error"),
                    json.dumps(job.get("stage_history", [])),
                    json.dumps(job.get("agent_activity", [])),
                    int(job.get("attempt_count", 0)),
                    job["created_at"],
                    job.get("started_at"),
                    job.get("completed_at"),
                    job["updated_at"],
                ),
            )
            connection.commit()

    def get(self, investigation_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM investigations WHERE investigation_id = ?",
                (investigation_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def find_active(self, incident_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM investigations
                WHERE incident_id = ? AND status IN ('queued', 'running')
                ORDER BY created_at DESC LIMIT 1
                """,
                (incident_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_for_incident(
        self, incident_id: str, limit: int, offset: int
    ) -> tuple[int, list[dict]]:
        with self.database.connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) AS c FROM investigations WHERE incident_id = ?",
                    (incident_id,),
                ).fetchone()["c"]
            )
            rows = connection.execute(
                """
                SELECT * FROM investigations WHERE incident_id = ?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (incident_id, limit, offset),
            ).fetchall()
        return total, [self._row_to_job(row) for row in rows]

    def list_all(
        self, limit: int, offset: int, status: str | None
    ) -> tuple[int, list[dict]]:
        clause = "WHERE status = ?" if status else ""
        params: list[Any] = [status] if status else []
        with self.database.connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS c FROM investigations {clause}", params
                ).fetchone()["c"]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM investigations {clause}
                ORDER BY created_at DESC, investigation_id DESC LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return total, [self._row_to_job(row) for row in rows]

    def update(self, investigation_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields.setdefault("updated_at", _utcnow_iso())
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in {
                "status", "stage", "summary", "report", "error", "attempt_count",
                "started_at", "completed_at", "updated_at", "stage_history",
                "agent_activity",
            }:
                raise InvalidTransitionError(f"Unknown investigation column '{key}'")
            assignments.append(f"{key} = ?")
            if key in _JSON_COLUMNS:
                values.append(json.dumps(value) if value is not None else None)
            else:
                values.append(value)
        values.append(investigation_id)
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE investigations SET {', '.join(assignments)} WHERE investigation_id = ?",
                values,
            )
            connection.commit()

    def append_stage(self, investigation_id: str, entry: dict) -> None:
        job = self.get(investigation_id)
        if job is None:
            raise InvestigationNotFoundError(investigation_id)
        history = list(job.get("stage_history", []))
        history.append(entry)
        self.update(
            investigation_id,
            stage=entry["stage"],
            stage_history=history,
        )

    def upsert_agent(self, investigation_id: str, activity: dict) -> None:
        job = self.get(investigation_id)
        if job is None:
            raise InvestigationNotFoundError(investigation_id)
        activities = list(job.get("agent_activity", []))
        for index, existing in enumerate(activities):
            if existing.get("agent") == activity["agent"]:
                merged = {**existing, **activity}
                activities[index] = merged
                break
        else:
            activities.append(activity)
        self.update(investigation_id, agent_activity=activities)

    def queued_jobs(self, limit: int = 5) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM investigations WHERE status = 'queued'
                ORDER BY created_at ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def save_evidence(self, records: list[dict]) -> None:
        if not records:
            return
        with self.database.connect() as connection:
            for record in records:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO investigation_evidence (
                        evidence_id, investigation_id, incident_id, evidence_type,
                        source, observation, value, units, provenance, payload, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["evidence_id"],
                        record["investigation_id"],
                        record["incident_id"],
                        record["evidence_type"],
                        record["source"],
                        record["observation"],
                        record.get("value"),
                        record.get("units"),
                        record["provenance"],
                        json.dumps(record.get("payload", {})),
                        record["created_at"],
                    ),
                )
            connection.commit()

    def get_evidence(self, investigation_id: str) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM investigation_evidence
                WHERE investigation_id = ? ORDER BY evidence_id ASC
                """,
                (investigation_id,),
            ).fetchall()
        return [
            {
                "evidence_id": row["evidence_id"],
                "investigation_id": row["investigation_id"],
                "incident_id": row["incident_id"],
                "evidence_type": row["evidence_type"],
                "source": row["source"],
                "observation": row["observation"],
                "value": row["value"],
                "units": row["units"],
                "provenance": row["provenance"],
                "payload": json.loads(row["payload"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
