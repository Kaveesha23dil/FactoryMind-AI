"""Interactive evidence-graph endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.api.routes.investigations import get_service as get_investigation_service
from services.api.schemas.evidence_graph import EvidenceGraph
from services.api.services.evidence_graph_service import EvidenceGraphService
from services.api.services.investigation_repository import InvestigationNotFoundError

router = APIRouter(tags=["evidence-graph"])

_service: EvidenceGraphService | None = None


def get_service() -> EvidenceGraphService:
    global _service
    if _service is None:
        _service = EvidenceGraphService(get_investigation_service())
    return _service


@router.get(
    "/api/investigations/{investigation_id}/graph",
    response_model=EvidenceGraph,
)
def get_investigation_graph(investigation_id: str):
    try:
        return get_service().build(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
