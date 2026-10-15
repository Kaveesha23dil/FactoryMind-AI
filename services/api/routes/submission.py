"""Authenticated read-only submission data using the configured repositories."""
from fastapi import APIRouter
from services.api.routes.investigations import get_service
from services.api.services.anomaly_engine import get_engine
from services.api.services.submission_service import overview

router = APIRouter(prefix='/api/submission', tags=['submission'])


@router.get('/overview')
def submission_overview():
    return overview(get_service(), get_engine())
