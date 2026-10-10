"""Counterfactual investigation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.api.schemas.counterfactual import (
    CounterfactualListResponse,
    CounterfactualRequest,
    CounterfactualScenario,
)
from services.api.services.counterfactual_repository import CounterfactualNotFoundError
from services.api.services.counterfactual_service import (
    CounterfactualError,
    CounterfactualService,
    InvalidExclusionError,
)
from services.api.services.investigation_repository import InvestigationNotFoundError

router = APIRouter(tags=["counterfactuals"])

_service: CounterfactualService | None = None


def get_service() -> CounterfactualService:
    global _service
    if _service is None:
        _service = CounterfactualService()
    return _service


@router.post(
    "/api/investigations/{investigation_id}/counterfactual",
    response_model=CounterfactualScenario,
)
def create_counterfactual(
    investigation_id: str, request: CounterfactualRequest
) -> dict:
    try:
        return get_service().create_scenario(
            investigation_id,
            excluded_evidence_ids=request.excluded_evidence_ids,
            rationale=request.rationale,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidExclusionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CounterfactualError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/api/investigations/{investigation_id}/counterfactuals",
    response_model=CounterfactualListResponse,
)
def list_counterfactuals(investigation_id: str) -> dict:
    try:
        return get_service().list_for_investigation(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/api/counterfactuals/{scenario_id}",
    response_model=CounterfactualScenario,
)
def get_counterfactual(scenario_id: str) -> dict:
    try:
        return get_service().get(scenario_id)
    except CounterfactualNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
