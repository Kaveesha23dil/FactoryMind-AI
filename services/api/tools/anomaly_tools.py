"""Anomaly analysis and baseline statistics tools.

All numerical values come from the precomputed deterministic anomaly engine,
never from the language model.
"""

from __future__ import annotations

from typing import Any

from services.api.core import config
from services.api.services.anomaly_engine import get_engine


def get_anomaly_analysis(incident_id: str) -> dict[str, Any]:
    """Return the deterministic anomaly findings for an incident's record.

    Combines the persisted incident snapshot with the engine's feature-level
    robust z-score contributions.
    """
    from services.api.tools.incident_tools import _service

    incident = _service().get_incident(incident_id)
    stored = get_engine().get(incident["record_id"])
    if stored is None:
        raise ValueError(f"No anomaly result for record {incident['record_id']}")

    return {
        "incident_id": incident_id,
        "record_id": incident["record_id"],
        "algorithm": stored["algorithm"],
        "anomaly_score": stored["anomaly_score"],
        "severity": stored["severity"],
        "is_anomaly": stored["is_anomaly"],
        "threshold": stored["threshold"],
        "feature_z_threshold": stored["feature_z_threshold"],
        "features": stored["features"],
        "anomalous_features": stored["anomalous_features"],
        "ground_truth_used_for_investigation": False,
    }


def get_baseline_statistics(machine_type: str) -> dict[str, Any]:
    """Return the trained feature baselines used to score observations."""
    detector = get_engine().detector
    global_baselines = {
        key: stats.to_dict() for key, stats in detector.global_baselines.items()
    }
    group_baselines = {
        group: {key: stats.to_dict() for key, stats in values.items()}
        for group, values in detector.group_baselines.items()
    }
    scope = "machine_type" if machine_type in group_baselines else "global"
    baselines = group_baselines.get(machine_type, global_baselines)
    return {
        "machine_type": machine_type,
        "scope": scope,
        "feature_labels": config.FEATURE_LABELS,
        "feature_units": config.FEATURE_UNITS,
        "baselines": baselines,
        "global_baselines": global_baselines,
    }


__all__ = ["get_anomaly_analysis", "get_baseline_statistics"]
