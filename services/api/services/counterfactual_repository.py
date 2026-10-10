"""Persistence for counterfactual scenarios.

Kept separate from the investigation repository so the scenario lifecycle
(pending -> running -> completed/failed) and the derived comparison can be
stored alongside, without touching the original investigation rows.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from services.api.db.database import Database

_JSON_COLUMNS = {
    "excluded_evidence_ids",
    "excluded_feature_keys",
    "comparison",
    "dependency_trace",
}

_MUTABLE_COLUMNS = {
    "revised_investigation_id",
    "excluded_feature_keys",
    "status",
    "error",
    "comparison",
    "dependency_trace",
    "rationale",
    "updated_at",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CounterfactualNotFoundError(Exception):
    pass


class CounterfactualRepository(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def insert(self, scenario: dict) -> None: ...

    @abstractmethod
    def get(self, scenario_id: str) -> dict | None: ...

    @abstractmethod
    def list_for_investigation(self, investigation_id: str) -> list[dict]: ...

    @abstractmethod
    def update(self, scenario_id: str, **fields: Any) -> None: ...


class SqliteCounterfactualRepository(CounterfactualRepository):
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def initialize(self) -> None:
        self.database.initialize()

    @staticmethod
    def _row_to_scenario(row: sqlite3.Row) -> dict:
        return {
            "scenario_id": row["scenario_id"],
            "original_investigation_id": row["original_investigation_id"],
            "incident_id": row["incident_id"],
            "revised_investigation_id": row["revised_investigation_id"],
            "excluded_evidence_ids": json.loads(row["excluded_evidence_ids"] or "[]"),
            "excluded_feature_keys": json.loads(row["excluded_feature_keys"] or "[]"),
            "rationale": row["rationale"],
            "status": row["status"],
            "error": row["error"],
            "comparison": json.loads(row["comparison"]) if row["comparison"] else None,
            "dependency_trace": json.loads(row["dependency_trace"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def insert(self, scenario: dict) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO counterfactual_scenarios (
                    scenario_id, original_investigation_id, incident_id,
                    revised_investigation_id, excluded_evidence_ids,
                    excluded_feature_keys, rationale, status, error, comparison,
                    dependency_trace, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario["scenario_id"],
                    scenario["original_investigation_id"],
                    scenario["incident_id"],
                    scenario.get("revised_investigation_id"),
                    json.dumps(scenario.get("excluded_evidence_ids", [])),
                    json.dumps(scenario.get("excluded_feature_keys", [])),
                    scenario.get("rationale"),
                    scenario["status"],
                    scenario.get("error"),
                    json.dumps(scenario.get("comparison"))
                    if scenario.get("comparison")
                    else None,
                    json.dumps(scenario.get("dependency_trace", [])),
                    scenario["created_at"],
                    scenario["updated_at"],
                ),
            )
            connection.commit()

    def get(self, scenario_id: str) -> dict | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM counterfactual_scenarios WHERE scenario_id = ?",
                (scenario_id,),
            ).fetchone()
        return self._row_to_scenario(row) if row else None

    def list_for_investigation(self, investigation_id: str) -> list[dict]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM counterfactual_scenarios
                WHERE original_investigation_id = ?
                ORDER BY created_at DESC, scenario_id DESC
                """,
                (investigation_id,),
            ).fetchall()
        return [self._row_to_scenario(row) for row in rows]

    def update(self, scenario_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields.setdefault("updated_at", _utcnow_iso())
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key not in _MUTABLE_COLUMNS:
                raise ValueError(f"Unknown counterfactual column '{key}'")
            assignments.append(f"{key} = ?")
            if key in _JSON_COLUMNS:
                values.append(json.dumps(value) if value is not None else None)
            else:
                values.append(value)
        values.append(scenario_id)
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE counterfactual_scenarios SET {', '.join(assignments)} "
                "WHERE scenario_id = ?",
                values,
            )
            connection.commit()


__all__ = [
    "CounterfactualRepository",
    "SqliteCounterfactualRepository",
    "CounterfactualNotFoundError",
]
