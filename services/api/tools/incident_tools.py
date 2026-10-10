"""Incident retrieval tools.

Only physical sensor measurements and incident metadata are returned. Ground
truth failure labels are never exposed through these tools.
"""

from __future__ import annotations

from typing import Any

from services.api.core import config
from services.api.services.incident_service import IncidentNotFoundError


def _service():
    # Imported lazily to avoid a circular import at module load time and to
    # respect the incident route's swappable service (used by tests).
    from services.api.routes.incidents import get_service

    return get_service()


def get_incident_measurements(incident_id: str) -> dict[str, Any]:
    """Return the recorded sensor measurements for an incident.

    Raises ``IncidentNotFoundError`` when the incident does not exist.
    """
    incident = _service().get_incident(incident_id)
    return {
        "incident_id": incident_id,
        "record_id": incident["record_id"],
        "machine_type": incident["machine_type"],
        "measurements": incident["source_measurements"],
        "ground_truth_used_for_investigation": False,
    }


def get_incident_context(incident_id: str) -> dict[str, Any]:
    """Return label-free metadata for an incident."""
    incident = _service().get_incident(incident_id)
    return {
        "incident_id": incident["incident_id"],
        "record_id": incident["record_id"],
        "product_id": incident["product_id"],
        "machine_type": incident["machine_type"],
        "algorithm": incident["algorithm"],
        "anomaly_score": incident["anomaly_score"],
        "severity": incident["severity"],
        "status": incident["status"],
        "created_at": incident["created_at"],
        "dataset": config.DATASET_NAME,
        "dataset_source": config.DATASET_SOURCE,
        "ground_truth_used_for_investigation": False,
    }


__all__ = [
    "get_incident_measurements",
    "get_incident_context",
    "IncidentNotFoundError",
]
