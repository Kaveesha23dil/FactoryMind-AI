"""Visual inspection service.

Handles upload, storage, deterministic metadata parsing, and vision-agent
analysis of inspection images. Images are stored on a local filesystem backend
(the storage layer is isolated so it can be swapped for object storage later).
Analysis is a *supporting* signal: observations are always hedged and limitations
are always recorded.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from google.genai import types

from services.api.agents import vision_agent
from services.api.agents.orchestrator import Orchestrator
from services.api.agents.runtime import build_runtime
from services.api.core import config
from services.api.services import image_utils
from services.api.services.visual_repository import (
    SqliteVisualEvidenceRepository,
    VisualEvidenceNotFoundError,
    VisualEvidenceRepository,
)
from services.api.tools.anomaly_tools import get_anomaly_analysis
from services.api.tools.evidence_tools import format_evidence_id
from services.api.tools.incident_tools import get_incident_context

logger = logging.getLogger(__name__)

STORAGE_BACKEND = "local_filesystem"

_VISUAL_PROVENANCE = (
    "Engineer-supplied inspection image; visible observations only, not a "
    "confirmed physical diagnosis."
)


class VisualEvidenceError(Exception):
    """Base visual-evidence domain error."""


class InvalidImageError(VisualEvidenceError):
    pass


class ImageTooLargeError(VisualEvidenceError):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VisualEvidenceService:
    def __init__(
        self,
        incident_service=None,
        investigation_service=None,
        repository: VisualEvidenceRepository | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        if incident_service is None:
            from services.api.routes.incidents import get_service

            incident_service = get_service()
        if investigation_service is None:
            from services.api.routes.investigations import get_service

            investigation_service = get_service()
        self.incident_service = incident_service
        self.investigations = investigation_service
        from services.api.services.firestore_repository import repository as select_repository
        self.repository = repository or select_repository('images', SqliteVisualEvidenceRepository)
        self.repository.initialize()
        self.storage_dir = Path(storage_dir or config.settings.visual_storage_dir)

    # -- commands --------------------------------------------------------

    def store(
        self, incident_id: str, filename: str, mime_type: str | None, data: bytes
    ) -> dict:
        self.incident_service.get_incident(incident_id)
        if not filename:
            raise InvalidImageError("A filename is required.")
        if not data:
            raise InvalidImageError("The uploaded image is empty.")
        if len(data) > config.VISUAL_MAX_IMAGE_BYTES:
            raise ImageTooLargeError(
                f"Image exceeds the {config.VISUAL_MAX_IMAGE_BYTES} byte limit."
            )
        detected = image_utils.detect_mime_type(data)
        if detected is None or detected not in config.VISUAL_ALLOWED_MIME_TYPES:
            raise InvalidImageError(
                "Unsupported image type; upload PNG, JPEG, GIF, or WEBP."
            )
        if mime_type and mime_type not in config.VISUAL_ALLOWED_MIME_TYPES:
            raise InvalidImageError(f"Unsupported declared type '{mime_type}'.")
        # Trust the sniffed type over the client-supplied content type.
        resolved_mime = detected
        if config.settings.app_env == 'production':
            try:
                image_utils.verify_image(data)
            except Exception as exc:
                raise InvalidImageError('Image encoding is invalid or unsafe') from exc

        width, height = image_utils.image_dimensions(data)
        image_id = f"{config.VISUAL_IMAGE_ID_PREFIX}{uuid.uuid4().hex[:10].upper()}"
        storage_ref = f"{image_id}{image_utils.extension_for(resolved_mime)}"
        if config.settings.upload_backend == 'gcs':
            from services.api.services.object_storage import object_store
            object_store().write(storage_ref, data, resolved_mime)
        else:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self._path(storage_ref).write_bytes(data)

        now = _utcnow_iso()
        self.repository.insert(
            {
                "image_id": image_id,
                "incident_id": incident_id,
                "investigation_id": None,
                "storage_ref": storage_ref,
                "filename": filename,
                "mime_type": resolved_mime,
                "size_bytes": len(data),
                "width": width,
                "height": height,
                "provenance": _VISUAL_PROVENANCE,
                "storage_backend": 'google_cloud_storage' if config.settings.upload_backend == 'gcs' else STORAGE_BACKEND,
                "status": "stored",
                "summary": None,
                "observations": [],
                "limitations": [],
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return self.to_public(self.get(image_id))

    def analyze(
        self,
        image_id: str,
        investigation_id: str | None = None,
        runtime_factory=build_runtime,
    ) -> dict:
        record = self.get(image_id)
        if record['storage_backend'] == 'google_cloud_storage':
            from services.api.services.object_storage import object_store
            if not object_store().exists(record['storage_ref']):
                raise VisualEvidenceError('Stored image object is missing')
        else:
            path = self._path(record["storage_ref"])
            if not path.exists():
                raise VisualEvidenceError("Stored image file is missing.")

        if investigation_id:
            # Validate the investigation exists before we attach anything.
            self.investigations.get(investigation_id)

        self.repository.update(
            image_id, status="analyzing", error=None, investigation_id=investigation_id
        )
        try:
            retry_at = self.investigations._provider_cooldown()
            if retry_at:
                raise VisualEvidenceError(f'Gemini quota cooldown is active until {retry_at}.')
            data = object_store().read(record['storage_ref']) if record['storage_backend'] == 'google_cloud_storage' else path.read_bytes()
            context = {
                "incident": get_incident_context(record["incident_id"]),
                "anomaly": get_anomaly_analysis(record["incident_id"]),
                "image": record,
            }
            prompt = vision_agent.SPEC.build_prompt(context)
            image_part = types.Part.from_bytes(data=data, mime_type=record["mime_type"])
            runtime = runtime_factory()
            raw = asyncio.run(
                Orchestrator(runtime, self.incident_service)._run_agent(vision_agent.SPEC, context, image_parts=[image_part])
            )
            analysis = vision_agent.VisualAnalysis.model_validate(raw)
            self.repository.update(
                image_id,
                status="analyzed",
                summary=analysis.summary,
                observations=[item.model_dump() for item in analysis.observations],
                limitations=list(analysis.limitations),
                investigation_id=investigation_id,
            )
            if investigation_id:
                self._attach_evidence(image_id, investigation_id, analysis)
        except Exception as exc:  # noqa: BLE001 - persist failure for the UI
            logger.error("Visual analysis failed (%s)", type(exc).__name__)
            self.repository.update(
                image_id,
                status="failed",
                error=str(exc),
                investigation_id=investigation_id,
            )
        return self.to_public(self.get(image_id))

    # -- queries ---------------------------------------------------------

    def get(self, image_id: str) -> dict:
        record = self.repository.get(image_id)
        if record is None:
            raise VisualEvidenceNotFoundError(image_id)
        return record

    def to_public(self, record: dict) -> dict:
        return {
            **record,
            "content_url": f"/api/images/{record['image_id']}/content",
        }

    def list_for_incident(self, incident_id: str) -> dict:
        self.incident_service.get_incident(incident_id)
        items = [
            self.to_public(record)
            for record in self.repository.list_for_incident(incident_id)
        ]
        return {"incident_id": incident_id, "total": len(items), "items": items}

    def content_path(self, image_id: str) -> Path:
        record = self.get(image_id)
        path = self._path(record["storage_ref"])
        if not path.exists():
            raise VisualEvidenceNotFoundError(image_id)
        return path

    def content_bytes(self, image_id):
        record = self.get(image_id)
        from services.api.services.object_storage import object_store
        return object_store().read(record['storage_ref'])

    def content_type(self, image_id: str) -> str:
        return self.get(image_id)["mime_type"]

    # -- helpers ---------------------------------------------------------

    def _path(self, storage_ref: str) -> Path:
        root = self.storage_dir.resolve()
        candidate = (root / storage_ref).resolve()
        if candidate == root or not candidate.is_relative_to(root):
            raise VisualEvidenceError(
                "Image storage reference must stay inside the storage directory."
            )
        return candidate

    def _attach_evidence(self, image_id: str, investigation_id: str, analysis) -> None:
        repository = self.investigations.repository
        existing = repository.get_evidence(investigation_id)
        used_ids = {record["evidence_id"] for record in existing}
        index = (
            sum(
                1
                for record in existing
                if record["evidence_type"] == "visual_observation"
            )
            + 1
        )
        evidence_id = format_evidence_id("visual_observation", index)
        while evidence_id in used_ids:
            index += 1
            evidence_id = format_evidence_id("visual_observation", index)

        record = self.get(image_id)
        repository.save_evidence(
            [
                {
                    "evidence_id": evidence_id,
                    "investigation_id": investigation_id,
                    "incident_id": record["incident_id"],
                    "evidence_type": "visual_observation",
                    "source": f"Visual inspection image {record['filename']} ({image_id})",
                    "observation": analysis.summary,
                    "value": None,
                    "units": None,
                    "provenance": _VISUAL_PROVENANCE,
                    "payload": {
                        "image_id": image_id,
                        "storage_reference": record["storage_ref"],
                        "observations": [
                            item.model_dump() for item in analysis.observations
                        ],
                        "limitations": list(analysis.limitations),
                    },
                    "created_at": _utcnow_iso(),
                }
            ]
        )


__all__ = [
    "VisualEvidenceService",
    "VisualEvidenceError",
    "InvalidImageError",
    "ImageTooLargeError",
    "VisualEvidenceNotFoundError",
]
