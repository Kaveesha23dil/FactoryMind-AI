"""Visual inspection endpoints (upload, metadata, content, analysis)."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from services.api.schemas.visual_evidence import (
    VisualAnalysisRequest,
    VisualEvidenceListResponse,
    VisualEvidenceRecord,
)
from services.api.services.incident_service import IncidentNotFoundError
from services.api.services.visual_evidence_service import (
    ImageTooLargeError,
    InvalidImageError,
    VisualEvidenceError,
    VisualEvidenceService,
)
from services.api.services.visual_repository import VisualEvidenceNotFoundError

router = APIRouter(tags=["visual-inspection"])

_service: VisualEvidenceService | None = None


def get_service() -> VisualEvidenceService:
    global _service
    if _service is None:
        _service = VisualEvidenceService()
    return _service


@router.post(
    "/api/incidents/{incident_id}/images",
    response_model=VisualEvidenceRecord,
    status_code=201,
)
async def upload_image(incident_id: str, file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        return get_service().store(
            incident_id,
            filename=file.filename or "",
            mime_type=file.content_type,
            data=data,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/api/incidents/{incident_id}/images",
    response_model=VisualEvidenceListResponse,
)
def list_images(incident_id: str) -> dict:
    try:
        return get_service().list_for_incident(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/api/images/{image_id}",
    response_model=VisualEvidenceRecord,
)
def get_image(image_id: str) -> dict:
    try:
        return get_service().to_public(get_service().get(image_id))
    except VisualEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/images/{image_id}/content")
def get_image_content(image_id: str) -> FileResponse:
    try:
        service = get_service()
        return FileResponse(
            service.content_path(image_id), media_type=service.content_type(image_id)
        )
    except VisualEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/api/images/{image_id}/analyze",
    response_model=VisualEvidenceRecord,
)
def analyze_image(image_id: str, request: VisualAnalysisRequest | None = None) -> dict:
    investigation_id = request.investigation_id if request else None
    try:
        return get_service().analyze(image_id, investigation_id=investigation_id)
    except VisualEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VisualEvidenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
