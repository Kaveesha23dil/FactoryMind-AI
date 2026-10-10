"""Deterministic evidence-exclusion logic for counterfactual investigations.

Counterfactual reasoning must be *genuine*: excluding a measurement has to
remove it (and anything that would trivially reveal it) from the revised
reasoning context, instead of asking a model to pretend. This module contains
the pure, unit-testable transformations that make that possible:

* which features an excluded evidence item implies, including the transitive
  closure over derived features (so ``mechanical_power`` cannot leak the
  torque it is computed from),
* which evidence records must be dropped,
* how to restrict the recorded measurements, baselines and deterministic
  anomaly summary to the remaining features,
* how to recompute the aggregate anomaly score from the surviving per-feature
  robust z-scores (the score is a Euclidean norm, so this is exact).
"""

from __future__ import annotations

import math
from typing import Any

from services.api.core import config

#: Feature key -> raw measurement keys in the incident's ``source_measurements``.
FEATURE_MEASUREMENT_KEYS: dict[str, list[str]] = {
    "air_temperature_c": ["air_temperature_c", "air_temperature_k"],
    "process_temperature_c": ["process_temperature_c", "process_temperature_k"],
    "temperature_difference_c": [],
    "rotational_speed_rpm": ["rotational_speed_rpm"],
    "torque_nm": ["torque_nm"],
    "mechanical_power_w": [],
    "tool_wear_min": ["tool_wear_min"],
}


def _column_to_feature_key() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for definition in config.FEATURE_DEFINITIONS:
        if len(definition["columns"]) == 1:
            mapping[definition["columns"][0]] = definition["key"]
    return mapping


def feature_dependencies() -> dict[str, list[str]]:
    """Map each derived feature to the single-column features it depends on."""
    column_key = _column_to_feature_key()
    dependencies: dict[str, list[str]] = {}
    for definition in config.FEATURE_DEFINITIONS:
        if len(definition["columns"]) <= 1:
            continue
        sources = [column_key[column] for column in definition["columns"] if column in column_key]
        if sources:
            dependencies[definition["key"]] = sources
    return dependencies


def _evidence_feature(record: dict[str, Any]) -> str | None:
    if record.get("evidence_type") not in ("sensor_measurement", "baseline_statistic"):
        return None
    payload = record.get("payload") or {}
    feature = payload.get("feature")
    return feature if isinstance(feature, str) and feature else None


def resolve_excluded_features(
    excluded_evidence_ids: set[str],
    evidence_records: list[dict[str, Any]],
) -> tuple[set[str], dict[str, int]]:
    """Return (excluded feature keys, provenance counts).

    The provenance map records how many evidence records were resolved to each
    feature so the UI can explain *why* a feature was excluded. The closure adds
    derived features whose inputs were excluded.
    """
    by_id = {record["evidence_id"]: record for record in evidence_records}
    provenance: dict[str, int] = {}
    features: set[str] = set()
    for evidence_id in excluded_evidence_ids:
        record = by_id.get(evidence_id)
        if record is None:
            continue
        feature = _evidence_feature(record)
        if feature:
            features.add(feature)
            provenance[feature] = provenance.get(feature, 0) + 1

    dependencies = feature_dependencies()
    changed = True
    while changed:
        changed = False
        for derived, sources in dependencies.items():
            if derived in features:
                continue
            if any(source in features for source in sources):
                features.add(derived)
                provenance[derived] = provenance.get(derived, 0) + 1
                changed = True
    return features, provenance


def filter_evidence_records(
    records: list[dict[str, Any]],
    excluded_evidence_ids: set[str],
    excluded_features: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split records into (kept, dropped).

    A record is dropped when it is explicitly excluded, when it is a sensor /
    baseline record for an excluded (or dependency-closed) feature, or when it
    is a visual/anomaly record that was explicitly excluded.
    """
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for record in records:
        evidence_id = record["evidence_id"]
        if evidence_id in excluded_evidence_ids:
            dropped.append({
                "evidence_id": evidence_id,
                "reason": "explicitly excluded by the engineer",
            })
            continue
        feature = _evidence_feature(record)
        if feature and feature in excluded_features:
            dropped.append({
                "evidence_id": evidence_id,
                "reason": f"depends on excluded measurement '{feature}'",
                "feature": feature,
            })
            continue
        kept.append(record)
    return kept, dropped


def _severity_for(score: float, threshold: float) -> str:
    if score < threshold:
        return "normal"
    for severity in ["low", "medium", "high"]:
        lower, upper = config.SEVERITY_MULTIPLIERS[severity]
        if threshold * lower <= score < threshold * upper:
            return severity
    return "critical"


def restrict_anomaly(anomaly: dict[str, Any], excluded_features: set[str]) -> dict[str, Any]:
    """Recompute the deterministic anomaly view without the excluded features."""
    if not excluded_features:
        return dict(anomaly)

    features = [f for f in anomaly.get("features", []) if f.get("feature") not in excluded_features]
    sum_squares = 0.0
    for feature in features:
        z = feature.get("robust_zscore")
        if isinstance(z, (int, float)) and math.isfinite(float(z)):
            sum_squares += float(z) ** 2
    score = round(math.sqrt(sum_squares), 4)
    threshold = float(anomaly.get("threshold", config.ANOMALY_SCORE_THRESHOLD))
    anomalous = sorted(
        [f for f in features if f.get("is_anomalous")],
        key=lambda item: abs(float(item.get("robust_zscore", 0.0))),
        reverse=True,
    )
    return {
        **anomaly,
        "features": features,
        "anomalous_features": anomalous,
        "anomaly_score": score,
        "severity": _severity_for(score, threshold),
        "is_anomaly": score >= threshold,
        "anomaly_score_recomputed": True,
        "original_anomaly_score": anomaly.get("anomaly_score"),
        "excluded_feature_keys": sorted(excluded_features),
    }


def sanitize_measurements(
    measurements_context: dict[str, Any], excluded_features: set[str]
) -> dict[str, Any]:
    """Remove excluded measurements (and derived values) from the context."""
    if not excluded_features:
        return measurements_context
    measurements = dict(measurements_context.get("measurements") or {})
    for feature in excluded_features:
        for key in FEATURE_MEASUREMENT_KEYS.get(feature, []):
            measurements.pop(key, None)
    derived = dict(measurements.get("derived_features") or {})
    for feature in excluded_features:
        derived.pop(feature, None)
    measurements["derived_features"] = derived
    return {
        **measurements_context,
        "measurements": measurements,
        "excluded_feature_keys": sorted(excluded_features),
    }


def restrict_baselines(baselines: dict[str, Any], excluded_features: set[str]) -> dict[str, Any]:
    """Remove excluded features from the baseline statistics context."""
    if not excluded_features:
        return baselines
    result = {
        **baselines,
        "baselines": {
            key: value
            for key, value in (baselines.get("baselines") or {}).items()
            if key not in excluded_features
        },
        "global_baselines": {
            key: value
            for key, value in (baselines.get("global_baselines") or {}).items()
            if key not in excluded_features
        },
        "feature_labels": {
            key: value
            for key, value in (baselines.get("feature_labels") or {}).items()
            if key not in excluded_features
        },
        "feature_units": {
            key: value
            for key, value in (baselines.get("feature_units") or {}).items()
            if key not in excluded_features
        },
        "excluded_feature_keys": sorted(excluded_features),
    }
    return result


def excluded_feature_labels(
    excluded_features: set[str], feature_labels: dict[str, str] | None = None
) -> list[str]:
    labels = feature_labels or config.FEATURE_LABELS
    return [labels.get(feature, feature) for feature in sorted(excluded_features)]


__all__ = [
    "FEATURE_MEASUREMENT_KEYS",
    "feature_dependencies",
    "resolve_excluded_features",
    "filter_evidence_records",
    "restrict_anomaly",
    "sanitize_measurements",
    "restrict_baselines",
    "excluded_feature_labels",
]
