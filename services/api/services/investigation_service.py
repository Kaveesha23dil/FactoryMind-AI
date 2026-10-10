"""Investigation service.

Owns the business rules (validation, duplicate prevention, idempotent job
execution) and the progress reporting used by the frontend. Delegates storage
to :class:`InvestigationRepository` and agent execution to the orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from services.api.agents.orchestrator import Orchestrator
from services.api.agents.runtime import build_runtime
from services.api.core import config
from services.api.services.incident_service import IncidentNotFoundError
from services.api.services.investigation_repository import (
    InvestigationNotFoundError,
    InvestigationRepository,
    SqliteInvestigationRepository,
)
from services.api.services.investigation_worker import InvestigationWorker

logger = logging.getLogger(__name__)

AGENT_LABELS = {
    "sensor_agent": "Sensor Analysis Agent",
    "knowledge_agent": "Knowledge Retrieval Agent",
    "investigation_agent": "Root Cause Investigation Agent",
    "critic_agent": "Critic / Verification Agent",
}


class InvestigationError(Exception):
    """Base investigation domain error."""


class InvestigationDisabledError(InvestigationError):
    pass


class DuplicateInvestigationError(InvestigationError):
    def __init__(self, existing_investigation_id: str) -> None:
        super().__init__("An active investigation already exists for this incident")
        self.existing_investigation_id = existing_investigation_id


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _RepositoryReporter:
    """Progress reporter that persists stage/agent progress for the frontend."""

    def __init__(self, repository: InvestigationRepository, investigation_id: str) -> None:
        self.repository = repository
        self.investigation_id = investigation_id

    def stage(self, stage: str, message: str | None = None) -> None:
        self.repository.append_stage(
            self.investigation_id,
            {"stage": stage, "message": message, "timestamp": _utcnow_iso()},
        )

    def agent(
        self,
        name: str,
        status: str,
        summary: str | None = None,
        evidence_count: int | None = None,
    ) -> None:
        activity: dict[str, Any] = {
            "agent": name,
            "label": AGENT_LABELS.get(name, name),
            "status": status,
            "summary": summary,
            "evidence_count": evidence_count,
        }
        if status == "running":
            activity["started_at"] = _utcnow_iso()
        if status in ("completed", "failed"):
            activity["completed_at"] = _utcnow_iso()
        self.repository.upsert_agent(self.investigation_id, activity)

    def evidence(self, records: list[dict[str, Any]]) -> None:
        self.repository.save_evidence(records)

    def activity(self) -> list[dict[str, Any]]:
        job = self.repository.get(self.investigation_id)
        return list(job.get("agent_activity", [])) if job else []


class InvestigationService:
    def __init__(
        self,
        repository: InvestigationRepository | None = None,
        incident_service=None,
        runtime_factory: Callable = build_runtime,
    ) -> None:
        self.repository = repository or SqliteInvestigationRepository()
        self.repository.initialize()
        if incident_service is None:
            from services.api.routes.incidents import get_service

            incident_service = get_service()
        self.incident_service = incident_service
        self._runtime_factory = runtime_factory
        self._worker: InvestigationWorker | None = None

    def initialize(self) -> None:
        self.repository.initialize()

    @staticmethod
    def _new_id() -> str:
        return f"{config.INVESTIGATION_ID_PREFIX}{uuid.uuid4().hex[:10].upper()}"

    # -- commands --------------------------------------------------------

    def start_investigation(self, incident_id: str) -> dict:
        if not config.settings.ai_investigation_enabled:
            raise InvestigationDisabledError(
                "AI investigation is disabled (set AI_INVESTIGATION_ENABLED=true)"
            )
        # Validate the incident exists (raises IncidentNotFoundError).
        self.incident_service.get_incident(incident_id)

        active = self.repository.find_active(incident_id)
        if active is not None:
            raise DuplicateInvestigationError(active["investigation_id"])

        now = _utcnow_iso()
        job = {
            "investigation_id": self._new_id(),
            "incident_id": incident_id,
            "status": "queued",
            "stage": "queued",
            "provider": config.settings.ai_provider,
            "model": config.settings.gemini_model,
            "summary": None,
            "report": None,
            "error": None,
            "stage_history": [
                {"stage": "queued", "message": "Investigation queued", "timestamp": now}
            ],
            "agent_activity": [],
            "attempt_count": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
        }
        try:
            self.repository.insert(job)
        except sqlite3.IntegrityError as exc:
            existing = self.repository.find_active(incident_id)
            raise DuplicateInvestigationError(
                existing["investigation_id"] if existing else "unknown"
            ) from exc

        investigation_id = job["investigation_id"]
        if config.settings.investigation_async:
            self.enqueue(investigation_id)
        else:
            # Synchronous mode (local/dev + tests): execute immediately so the
            # caller observes a terminal state without a background thread.
            self.run_job(investigation_id)
        return self.get(investigation_id)

    def run_job(self, investigation_id: str) -> dict:
        """Execute an investigation. Idempotent: completed/running jobs are skipped."""
        job = self.repository.get(investigation_id)
        if job is None:
            raise InvestigationNotFoundError(investigation_id)
        if job["status"] == "completed":
            return job
        if job["status"] == "running":
            return job

        self.repository.update(
            investigation_id,
            status="running",
            started_at=_utcnow_iso(),
            error=None,
            attempt_count=int(job.get("attempt_count", 0)) + 1,
        )

        try:
            runtime = self._runtime_factory()
            orchestrator = Orchestrator(
                runtime=runtime, incident_service=self.incident_service
            )
            reporter = _RepositoryReporter(self.repository, investigation_id)
            result = asyncio.run(
                orchestrator.run(investigation_id, job["incident_id"], reporter)
            )
            report = result.report
            self.repository.save_evidence(result.evidence)
            self.repository.update(
                investigation_id,
                status="completed",
                stage="completed",
                summary=report.get("summary"),
                report=report,
                completed_at=_utcnow_iso(),
            )
            logger.info("Investigation %s completed", investigation_id)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            logger.exception("Investigation %s failed", investigation_id)
            self.repository.append_stage(
                investigation_id,
                {"stage": "failed", "message": str(exc), "timestamp": _utcnow_iso()},
            )
            self.repository.update(
                investigation_id,
                status="failed",
                stage="failed",
                error=str(exc),
                completed_at=_utcnow_iso(),
            )
        return self.get(investigation_id)

    # -- queries ---------------------------------------------------------

    def get(self, investigation_id: str) -> dict:
        job = self.repository.get(investigation_id)
        if job is None:
            raise InvestigationNotFoundError(investigation_id)
        return job

    def list_for_incident(
        self, incident_id: str, limit: int = 20, offset: int = 0
    ) -> dict:
        total, rows = self.repository.list_for_incident(incident_id, limit, offset)
        return {
            "incident_id": incident_id,
            "total": total,
            "items": [
                {
                    "investigation_id": row["investigation_id"],
                    "incident_id": row["incident_id"],
                    "status": row["status"],
                    "stage": row["stage"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "summary": row["summary"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                }
                for row in rows
            ],
        }

    def list_investigations(
        self, limit: int = 20, offset: int = 0, status: str | None = None
    ) -> dict:
        total, rows = self.repository.list_all(limit, offset, status)
        items = [
            {
                "investigation_id": row["investigation_id"],
                "incident_id": row["incident_id"],
                "status": row["status"],
                "stage": row["stage"],
                "provider": row["provider"],
                "model": row["model"],
                "summary": row["summary"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
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

    def get_evidence(self, investigation_id: str) -> dict:
        job = self.get(investigation_id)
        records = self.repository.get_evidence(investigation_id)
        return {
            "investigation_id": investigation_id,
            "incident_id": job["incident_id"],
            "total": len(records),
            "items": records,
        }

    # -- worker ----------------------------------------------------------

    def enqueue(self, investigation_id: str) -> None:
        if self._worker is None:
            self._worker = InvestigationWorker(self)
            self._worker.start()
        self._worker.wake()

    def start_worker(self) -> None:
        if self._worker is None:
            self._worker = InvestigationWorker(self)
        self._worker.start()

    def stop_worker(self) -> None:
        if self._worker is not None:
            self._worker.stop()


__all__ = [
    "InvestigationService",
    "InvestigationError",
    "InvestigationDisabledError",
    "DuplicateInvestigationError",
    "InvestigationNotFoundError",
    "IncidentNotFoundError",
]
