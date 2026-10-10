"""Persistence for uploaded visual-inspection evidence."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from services.api.db.database import Database

_JSON_COLUMNS = {"observations", "limitations"}

_MUTABLE_COLUMNS = {
    "investigation_id",
    "mime_type",
    "width",
    "height",
    "status",
    "summary",
    "observations",
    "limitations",
    "error",
    "updated_at",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VisualEvidenceNotFoundError(Exception):
    pass


class VisualEvidenceRepository(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def insert(self, record: dict) -> None: ...

    @abstractmethod
    def get(self, image_id: str) -> dict | None: ...

    @abstractmethod
    def list_for_incident(self, incident_id: str) -> list[dict]: ...

    @abstractmethod
    def update(self, image_id: str, **fields: Any) -> None: ...


class SqliteVisualEvidenceRepository(VisualEvidenceRepository):
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def initialize(self) -> None:
        self.database.initialize()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> dict:
        return {
            "image_id": row["image_id"],
            "incident_id": row["incident_id"],
            "investigation_id": row["investigation_id"],
            "storage_ref": row["storage_ref"],
            "filename": row["filename"],
            "mime_type": row["mime_type"],
            "size_bytes": row["size_bytes"],
            "width": row["width"],
            "height": row["height"],
            "provenance": row["provenance"],
            "storage_backend": row["storage_backend"],
            "status": row["status"],
            "summary": row["summary"],
            "observations": json.loads(row["observations"] or "[]"),
            "limitations": json.loads(row["limitations"] or "[]"),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def insert(self, record: dict) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO visual_evidence (
                    image_id, incident_id, investigation_id, storage_ref, filename,
                    mime_type, size_bytes, width, height, provenance,
                    storage_backend, status, summary, observations, limitations,
                    error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["image_id"],
                    record["incident_id"],
                    record.get("investigation_id"),
                    record["storage_ref"],
                    record["filename"],
                    record["mime_type"],
                    int(record["size_bytes"]),
                    record.get("width"),
                    record.get("height"),
                    record["provenance"],
                    record["storage_backend"],
                    record["status"],
                    record.get("summary"),
                    json.dumps(record.get("observations", [])),
                    json.dumps(record.get("limitations", [])),
                    record.get("error"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )
            connection.commit()

    def get(self, image_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM visual_evidence WHERE image_id = ?", (image_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_for_incident(self, incident_id: str) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM visual_evidence WHERE incident_id = ?
                ORDER BY created_at ASC, image_id ASC
                """,
                (incident_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update(self, image_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields.setdefault("updated_at", _utcnow_iso())
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in _MUTABLE_COLUMNS:
                raise ValueError(f"Unknown visual evidence column '{key}'")
            assignments.append(f"{key} = ?")
            if key in _JSON_COLUMNS:
                values.append(json.dumps(value) if value is not None else None)
            else:
                values.append(value)
        values.append(image_id)
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE visual_evidence SET {', '.join(assignments)} "
                "WHERE image_id = ?",
                values,
            )
            connection.commit()


__all__ = [
    "VisualEvidenceRepository",
    "SqliteVisualEvidenceRepository",
    "VisualEvidenceNotFoundError",
]
