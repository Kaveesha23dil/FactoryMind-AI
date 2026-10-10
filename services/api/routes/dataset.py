"""Dataset and telemetry endpoints (unchanged response shapes from Step 2)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services.api import data
from services.api.core import config

router = APIRouter(tags=["dataset"])


@router.get("/health")
def health():
    frame = data.get_dataset()
    return {
        "status": "healthy",
        "project": "FactoryMind AI",
        "version": "0.3.0",
        "dataset": config.DATASET_NAME,
        "records": int(len(frame)),
    }


@router.get("/api/dataset/summary")
def dataset_summary():
    frame = data.get_dataset()
    total = int(len(frame))
    failures = int((frame["Machine failure"] == 1).sum())
    normal = total - failures

    failure_categories = [
        {
            "code": code,
            "label": config.FAILURE_CATEGORY_LABELS[code],
            "count": int(frame[code].sum()),
        }
        for code in config.FAILURE_CATEGORY_COLUMNS
    ]

    machine_types = [
        {"type": machine_type, "count": int(count)}
        for machine_type, count in frame["Type"].value_counts().items()
    ]

    return {
        "dataset": config.DATASET_NAME,
        "source": config.DATASET_SOURCE,
        "record_count": total,
        "normal_count": normal,
        "failure_count": failures,
        "failure_rate": round(failures / total, 4) if total else 0.0,
        "failure_categories": failure_categories,
        "machine_types": machine_types,
    }


@router.get("/api/telemetry")
def telemetry(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    failure_only: bool = Query(False),
    normal_only: bool = Query(False),
    record_id: Optional[int] = Query(None, ge=1),
    machine_type: Optional[str] = Query(None),
):
    frame = data.get_dataset()

    if record_id is not None:
        frame = frame[frame["UDI"] == record_id]

    if failure_only:
        frame = frame[frame["Machine failure"] == 1]
    elif normal_only:
        frame = frame[frame["Machine failure"] == 0]

    if machine_type:
        frame = frame[frame["Type"] == machine_type.upper()]

    total = int(len(frame))
    window = frame.iloc[offset : offset + limit]
    records = [data.to_record(row) for _, row in window.iterrows()]

    return {
        "dataset": config.DATASET_NAME,
        "source": config.DATASET_SOURCE,
        "total": total,
        "limit": limit,
        "offset": offset,
        "returned": len(records),
        "records": records,
    }


@router.get("/api/telemetry/{record_id}")
def telemetry_record(record_id: int):
    frame = data.get_dataset()
    match = frame[frame["UDI"] == record_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="Record not found")
    return data.to_record(match.iloc[0])
