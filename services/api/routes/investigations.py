"""AI investigation endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query

from services.api.core import config
from services.api.schemas.evidence import EvidenceListResponse
from services.api.schemas.investigation import (
    InvestigationJob,
    InvestigationListPage,
    InvestigationListResponse,
    InvestigationRunResponse,
    InvestigationStartResponse,
)
from services.api.services.incident_service import IncidentNotFoundError
from services.api.services.investigation_repository import (
    InvestigationNotFoundError,
)
from services.api.services.investigation_service import (
    DuplicateInvestigationError,
    InvestigationDisabledError,
    InvestigationService,
)

router = APIRouter(tags=["investigations"])

_service: InvestigationService | None = None


def get_service() -> InvestigationService:
    global _service
    if _service is None:
        _service = InvestigationService()
        _service.initialize()
    return _service


@router.post(
    "/api/incidents/{incident_id}/investigate",
    response_model=InvestigationStartResponse,
    status_code=202,
)
def start_investigation(incident_id: str):
    try:
        job = get_service().start_investigation(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvestigationDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DuplicateInvestigationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "existing_investigation_id": exc.existing_investigation_id,
            },
        ) from exc
    return InvestigationStartResponse(
        investigation_id=job["investigation_id"],
        incident_id=job["incident_id"],
        status=job["status"],
        stage=job["stage"],
        created_at=job["created_at"],
    )


@router.get(
    "/api/investigations",
    response_model=InvestigationListPage,
)
def list_all_investigations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Literal["queued", "running", "completed", "failed"] | None = Query(
        None
    ),
):
    return get_service().list_investigations(
        limit=limit, offset=offset, status=status
    )


@router.get(
    "/api/investigations/{investigation_id}",
    response_model=InvestigationJob,
)
def get_investigation(investigation_id: str):
    try:
        return get_service().get(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/api/incidents/{incident_id}/investigations",
    response_model=InvestigationListResponse,
)
def list_investigations(
    incident_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return get_service().list_for_incident(incident_id, limit=limit, offset=offset)


@router.get(
    "/api/investigations/{investigation_id}/evidence",
    response_model=EvidenceListResponse,
)
def get_evidence(investigation_id: str):
    try:
        return get_service().get_evidence(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/api/investigations/{investigation_id}/process",
    response_model=InvestigationRunResponse,
)
def process_investigation(
    investigation_id: str,
    x_worker_secret: str | None = Header(default=None, alias="X-Worker-Secret"),
):
    """Bounded worker entry point (Cloud Tasks compatible, idempotent)."""
    configured = config.settings.worker_secret
    if not configured:
        raise HTTPException(
            status_code=403,
            detail="Worker endpoint is disabled (FACTORYMIND_WORKER_SECRET not set)",
        )
    if x_worker_secret != configured:
        raise HTTPException(status_code=401, detail="Invalid worker secret")
    try:
        job = get_service().run_job(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InvestigationRunResponse(
        investigation_id=investigation_id,
        status=job["status"],
        stage=job["stage"],
        executed=job["status"] in ("completed", "failed"),
    )
