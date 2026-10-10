"""Incident management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.api.core import config
from services.api.schemas.incident import (
    Incident,
    IncidentCreate,
    IncidentListResponse,
    IncidentStatusUpdate,
    ScanRequest,
    ScanResponse,
)
from services.api.services.incident_service import (
    DuplicateIncidentError,
    IncidentNotFoundError,
    IncidentService,
    InvalidTransitionError,
    RecordNotAnomalousError,
    RecordNotFoundError,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

_service: IncidentService | None = None


def get_service() -> IncidentService:
    global _service
    if _service is None:
        _service = IncidentService()
        _service.initialize()
    return _service


@router.post("", response_model=Incident, status_code=201)
def create_incident(payload: IncidentCreate):
    try:
        return get_service().create_incident(payload.record_id, payload.note)
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecordNotAnomalousError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateIncidentError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "existing_incident_id": exc.existing_incident_id,
            },
        ) from exc


@router.post("/scan", response_model=ScanResponse)
def scan_incidents(payload: ScanRequest):
    if payload.max_incidents > config.SCAN_MAX_INCIDENTS_LIMIT:
        raise HTTPException(
            status_code=422,
            detail=f"max_incidents cannot exceed {config.SCAN_MAX_INCIDENTS_LIMIT}",
        )
    return get_service().scan(
        min_severity=payload.min_severity,
        max_incidents=payload.max_incidents,
        dry_run=payload.dry_run,
    )


@router.get("", response_model=IncidentListResponse)
def list_incidents(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    severity: str | None = Query(None),
):
    if status and status not in config.INCIDENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unknown status '{status}'")
    if severity and severity not in config.SEVERITY_ORDER:
        raise HTTPException(status_code=422, detail=f"Unknown severity '{severity}'")
    return get_service().list_incidents(
        limit=limit, offset=offset, status=status, severity=severity
    )


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: str):
    try:
        return get_service().get_incident(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{incident_id}/status", response_model=Incident)
def update_status(incident_id: str, payload: IncidentStatusUpdate):
    try:
        return get_service().update_status(incident_id, payload.status, payload.note)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateIncidentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{incident_id}/investigation-payload")
def investigation_payload(incident_id: str):
    """Prepare (but do not execute) the Step 4 AI investigation payload."""
    try:
        return get_service().investigation_payload(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
