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
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from services.api.agents.orchestrator import Orchestrator
from services.api.agents.runtime import build_runtime, InvestigationProviderError
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

    def __init__(
        self, repository: InvestigationRepository, investigation_id: str
    ) -> None:
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
        from services.api.services.firestore_repository import repository as select_repository
        self.repository = repository or select_repository('investigations', SqliteInvestigationRepository)
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

    def _provider_cooldown(self) -> str | None:
        if not config.settings.provider_cooldown_enabled:
            return None
        if config.settings.ai_provider == 'google':
            from services.api.agents.request_control import provider_cooldown
            cooldown = provider_cooldown(config.settings.gemini_model)
            if cooldown:
                return (datetime.now(timezone.utc) + timedelta(seconds=cooldown[1])).isoformat()
        # Persisted failures make the cooldown survive API/worker restarts.
        _, jobs = self.repository.list_all(100, 0, 'failed')
        now = datetime.now(timezone.utc)
        deadlines = []
        for job in jobs:
            if job['provider'] != config.settings.ai_provider or job['model'] != config.settings.gemini_model:
                continue
            failure = InvestigationProviderError(job.get('error') or '')
            delay = failure.retry_after_seconds
            if delay is None or delay <= 60 or not job.get('completed_at'):
                continue
            try:
                deadline = datetime.fromisoformat(job['completed_at']) + timedelta(seconds=delay)
                if deadline > now:
                    deadlines.append(deadline)
            except (ValueError, TypeError, OverflowError):
                continue
        return max(deadlines).isoformat() if deadlines else None

    def start_investigation(self, incident_id: str, force_rerun: bool = False) -> dict:
        started = time.perf_counter()
        if not config.settings.ai_investigation_enabled:
            raise InvestigationDisabledError(
                "AI investigation is disabled (set AI_INVESTIGATION_ENABLED=true)"
            )
        # Validate the incident exists (raises IncidentNotFoundError).
        incident = self.incident_service.get_incident(incident_id)
        from services.api.services.investigation_cache import report_key, evidence_digest, report_digest
        try:
            key = report_key(incident)
        except Exception as exc:
            # Allow the queued execution path to persist a clear failed state
            # when source preparation is unavailable, rather than an API 500.
            key = None
            logger.warning('Investigation cache preparation unavailable (%s)', type(exc).__name__)
        if key and config.settings.investigation_cache_enabled and not force_rerun:
            total, jobs = self.repository.list_for_incident(incident_id, 100, 0)
            for job in jobs:
                report = job.get('report') or {}
                if (job['status'] == 'completed' and report.get('cache_key') == key
                    and not report.get('counterfactual') and not report.get('critic_review', {}).get('revision_required')):
                    stored = self.repository.get_evidence(job['investigation_id'])
                    ids = {r['evidence_id'] for r in stored}
                    if (ids == set(report.get('evidence_catalog', []))
                        and evidence_digest(stored) == report.get('cache_evidence_digest')
                        and report_digest(report) == report.get('cache_report_digest')):
                        logger.info('investigation_cache_hit', extra={'usage': {'event': 'investigation_cache_hit',
                            'model': job['model'], 'request_count': 0, 'latency_ms': round((time.perf_counter()-started)*1000, 2),
                            'input_tokens': 0, 'output_tokens': 0, 'error_category': None}})
                        reused = self.get(job['investigation_id'])
                        reused['cache_reused'] = True
                        return reused

        retry_at = self._provider_cooldown()
        if retry_at:
            raise InvestigationDisabledError(f'Gemini quota cooldown is active until {retry_at}. Wait for quota reset or review the project quota in Google AI Studio.')

        active = self.repository.find_active(incident_id)
        if active is not None:
            raise DuplicateInvestigationError(active["investigation_id"])

        try:
            job = self.create_queued_investigation(incident_id)
        except sqlite3.IntegrityError as exc:
            active = self.repository.find_active(incident_id)
            if active:
                raise DuplicateInvestigationError(active['investigation_id']) from exc
            raise

        investigation_id = job["investigation_id"]
        if config.settings.investigation_async:
            try:
                self.enqueue(investigation_id)
            except Exception as exc:
                self.repository.update(investigation_id, status='failed', stage='failed',
                    error='Durable job dispatch failed; review Cloud Tasks configuration before retrying.', completed_at=_utcnow_iso())
                raise InvestigationDisabledError('Investigation could not be dispatched') from exc
        else:
            # Synchronous mode (local/dev + tests): execute immediately so the
            # caller observes a terminal state without a background thread.
            self.run_job(investigation_id)
        return self.get(investigation_id)

    def create_queued_investigation(self, incident_id: str) -> dict:
        """Persist a new queued investigation without duplicate prevention.

        Used for counterfactual revisions, which legitimately run while the
        original investigation already exists for the same incident.
        """
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
        self.repository.insert(job)
        return job

    def run_job(
        self, investigation_id: str, prepared=None  # PreparedContext | None
    ) -> dict:
        """Execute an investigation. Idempotent: completed/running jobs are skipped.

        ``prepared`` lets a counterfactual revision hand the orchestrator a
        restricted reasoning context instead of rebuilding it from the dataset.
        """
        job = self.repository.get(investigation_id)
        if job is None:
            raise InvestigationNotFoundError(investigation_id)
        if job["status"] == "completed":
            return job
        if job["status"] == "running" and (config.settings.persistence_backend != 'firestore' or job.get('lease_expires_at', float('inf')) > time.time()):
            return job
        if prepared is None and job.get('prepared_context'):
            from services.api.agents.orchestrator import PreparedContext
            prepared = PreparedContext(**job['prepared_context'])

        if not self.repository.claim(investigation_id):
            return self.get(investigation_id)

        try:
            retry_at = self._provider_cooldown()
            if retry_at:
                raise InvestigationDisabledError(f'Gemini quota cooldown is active until {retry_at}.')
            runtime = self._runtime_factory()
            from services.api.services.investigation_cache import report_key, evidence_digest, report_digest
            key_before = report_key(self.incident_service.get_incident(job['incident_id'])) if prepared is None else None
            orchestrator = Orchestrator(
                runtime=runtime, incident_service=self.incident_service
            )
            reporter = _RepositoryReporter(self.repository, investigation_id)
            result = asyncio.run(
                orchestrator.run(
                    investigation_id,
                    job["incident_id"],
                    reporter,
                    prepared=prepared,
                )
            )
            report = result.report
            if prepared is None:
                from services.api.services.investigation_cache import report_key
                key_after = report_key(self.incident_service.get_incident(job['incident_id']))
                report['cache_key'] = key_before if key_before == key_after else None
                report['cache_evidence_digest'] = evidence_digest(result.evidence)
            report['usage'] = list(getattr(runtime, 'request_metrics', []))
            report['cache_report_digest'] = report_digest(report)
            self.repository.save_evidence(result.evidence)
            self.repository.update(
                investigation_id,
                status="completed",
                stage="completed",
                summary=report.get("summary"),
                report=report,
                completed_at=_utcnow_iso(),
            )
            logger.info("Investigation completed")
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            logger.error("Investigation failed category=%s", InvestigationProviderError(str(exc)).category)
            current = self.repository.get(investigation_id)
            for activity in (current or {}).get('agent_activity', []):
                if activity.get('status') == 'running':
                    self.repository.upsert_agent(investigation_id, {**activity, 'status': 'failed',
                        'summary': f"Provider execution stopped ({InvestigationProviderError(str(exc)).category}); review quota or model availability before retrying.",
                        'completed_at': _utcnow_iso()})
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
        failure = InvestigationProviderError(job.get('error') or '')
        delay = failure.retry_after_seconds
        job['retry_available_at'] = self._provider_cooldown() if job['status'] == 'failed' else None
        if config.settings.provider_cooldown_enabled and delay and delay > 60 and job.get('completed_at'):
            try:
                job['retry_available_at'] = (datetime.fromisoformat(job['completed_at']) + timedelta(seconds=delay)).isoformat()
            except (ValueError, TypeError, OverflowError):
                pass
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

    def enqueue(self, investigation_id=None) -> None:
        if config.settings.job_dispatch == 'tasks':
            from services.api.services.task_dispatch import dispatch
            dispatch(investigation_id)
            return
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
