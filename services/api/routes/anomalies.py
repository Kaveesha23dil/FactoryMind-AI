"""Anomaly detection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from services.api.core import config
from services.api.routes.incidents import get_service as get_incident_service
from services.api.schemas.anomaly import (
    AnomalyDetail,
    AnomalyListResponse,
    AnomalySummary,
)
from services.api.services.anomaly_engine import get_engine
from services.api.services.evaluation_service import get_evaluation_service

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


def _attach_incident_status(records: list[dict]) -> None:
    """Enrich anomaly records with their active incident (if any)."""
    record_ids = [record["record_id"] for record in records]
    statuses = get_incident_service().status_map(record_ids)
    for record in records:
        info = statuses.get(record["record_id"])
        record["incident_status"] = info["status"] if info else None
        record["incident_id"] = info["incident_id"] if info else None


@router.get("/summary", response_model=AnomalySummary)
def anomalies_summary():
    return get_engine().summary()


@router.get("/evaluation")
def anomalies_evaluation():
    """Reproducible held-out evaluation metrics for the detector."""
    return get_evaluation_service().report()


@router.get("", response_model=AnomalyListResponse)
def list_anomalies(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    severity: str | None = Query(None, description="Exact severity filter"),
    min_severity: str | None = Query(None, description="Minimum severity filter"),
    machine_type: str | None = Query(None),
):
    if severity and severity not in config.SEVERITY_ORDER:
        raise HTTPException(status_code=422, detail=f"Unknown severity '{severity}'")
    if min_severity and min_severity not in config.SEVERITY_ORDER:
        raise HTTPException(status_code=422, detail=f"Unknown severity '{min_severity}'")
    if machine_type and machine_type.upper() not in config.MACHINE_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown machine type '{machine_type}'")

    result = get_engine().list(
        limit=limit,
        offset=offset,
        severity=severity,
        machine_type=machine_type,
        min_severity=min_severity,
    )
    _attach_incident_status(result["records"])
    return result


@router.get("/{record_id}", response_model=AnomalyDetail)
def get_anomaly(record_id: int):
    stored = get_engine().get(record_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Record not found")
    result = dict(stored)
    info = get_incident_service().status_map([record_id]).get(record_id)
    result["incident_status"] = info["status"] if info else None
    result["incident_id"] = info["incident_id"] if info else None
    return result
