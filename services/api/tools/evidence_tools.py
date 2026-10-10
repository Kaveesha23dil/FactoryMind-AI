"""Evidence construction and citation-validation tools.

Evidence records are deterministic, immutable, and independently persisted.
Hypotheses and critic output reference evidence by ID; anything that does not
resolve to a real record is rejected by :func:`validate_evidence_ids`.
"""

from __future__ import annotations

from typing import Any, Iterable

from services.api.core import config


def format_evidence_id(evidence_type: str, index: int) -> str:
    prefix = config.EVIDENCE_TYPE_PREFIXES.get(evidence_type, "EV-UNKNOWN")
    return f"{prefix}-{index:03d}"


def build_deterministic_evidence(
    investigation_id: str,
    incident: dict,
    anomaly: dict,
    passages: list[dict[str, Any]],
    created_at: str,
) -> list[dict[str, Any]]:
    """Build the full deterministic evidence catalog for one investigation.

    Ordering is stable so evidence IDs are reproducible across revisions.
    """
    records: list[dict[str, Any]] = []
    dataset = config.DATASET_NAME

    records.append(
        {
            "evidence_id": format_evidence_id("source_metadata", 1),
            "investigation_id": investigation_id,
            "incident_id": incident["incident_id"],
            "evidence_type": "source_metadata",
            "source": f"{dataset} ({config.DATASET_SOURCE})",
            "observation": (
                f"Incident {incident['incident_id']} refers to dataset record "
                f"{incident['record_id']} (machine type {incident['machine_type']})."
            ),
            "value": None,
            "units": None,
            "provenance": "Persisted incident snapshot created from the dataset observation.",
            "payload": {
                "record_id": incident["record_id"],
                "product_id": incident["product_id"],
                "machine_type": incident["machine_type"],
                "dataset": dataset,
            },
            "created_at": created_at,
        }
    )

    features = anomaly.get("features", [])
    anomalous_count = sum(1 for feature in features if feature.get("is_anomalous"))
    records.append(
        {
            "evidence_id": format_evidence_id("anomaly_finding", 1),
            "investigation_id": investigation_id,
            "incident_id": incident["incident_id"],
            "evidence_type": "anomaly_finding",
            "source": f"Deterministic detector '{anomaly['algorithm']}'",
            "observation": (
                f"Anomaly score {anomaly['anomaly_score']:.2f} ({anomaly['severity']}) "
                f"against threshold {anomaly['threshold']:.2f}; {anomalous_count} feature(s) "
                f"exceed the per-feature z-score limit {anomaly['feature_z_threshold']:.2f}."
            ),
            "value": float(anomaly["anomaly_score"]),
            "units": "score",
            "provenance": "Robust z-score detector output (precomputed, not model-generated).",
            "payload": {
                "algorithm": anomaly["algorithm"],
                "anomaly_score": anomaly["anomaly_score"],
                "severity": anomaly["severity"],
                "threshold": anomaly["threshold"],
                "feature_z_threshold": anomaly["feature_z_threshold"],
                "anomalous_feature_count": anomalous_count,
            },
            "created_at": created_at,
        }
    )

    for index, feature in enumerate(features, start=1):
        label = feature.get("label", feature.get("feature", ""))
        unit = feature.get("unit", "")
        records.append(
            {
                "evidence_id": format_evidence_id("sensor_measurement", index),
                "investigation_id": investigation_id,
                "incident_id": incident["incident_id"],
                "evidence_type": "sensor_measurement",
                "source": f"AI4I 2020 observation (record {incident['record_id']})",
                "observation": (
                    f"{label} observed at {feature['observed_value']:.2f}{unit} "
                    f"(robust z-score {feature['robust_zscore']:.2f}, "
                    f"{'anomalous' if feature.get('is_anomalous') else 'within range'})."
                ),
                "value": float(feature["observed_value"]),
                "units": unit or None,
                "provenance": "Dataset feature value recorded when the incident was created.",
                "payload": {
                    "feature": feature.get("feature"),
                    "label": label,
                    "robust_zscore": feature.get("robust_zscore"),
                    "direction": feature.get("direction"),
                    "is_anomalous": feature.get("is_anomalous"),
                },
                "created_at": created_at,
            }
        )
        records.append(
            {
                "evidence_id": format_evidence_id("baseline_statistic", index),
                "investigation_id": investigation_id,
                "incident_id": incident["incident_id"],
                "evidence_type": "baseline_statistic",
                "source": "Robust training baseline",
                "observation": (
                    f"{label} training baseline median {feature['baseline_median']:.2f}{unit} "
                    f"(MAD-based scale {feature['baseline_scale']:.4f}, scope "
                    f"{feature.get('baseline_scope', 'global')})."
                ),
                "value": float(feature["baseline_median"]),
                "units": unit or None,
                "provenance": "Computed on the training split only; never uses ground-truth labels.",
                "payload": {
                    "feature": feature.get("feature"),
                    "median": feature.get("baseline_median"),
                    "scale": feature.get("baseline_scale"),
                    "mad": feature.get("baseline_mad"),
                    "scope": feature.get("baseline_scope"),
                },
                "created_at": created_at,
            }
        )

    for index, passage in enumerate(passages, start=1):
        records.append(
            {
                "evidence_id": format_evidence_id("manual_passage", index),
                "investigation_id": investigation_id,
                "incident_id": incident["incident_id"],
                "evidence_type": "manual_passage",
                "source": (
                    f"{passage['document_title']} [{passage['document_id']} / "
                    f"{passage['section_id']}]"
                ),
                "observation": passage["text"],
                "value": None,
                "units": None,
                "provenance": (
                    "Synthetic/general maintenance corpus (FactoryMind MVP). "
                    "Reference data only, not AI4I dataset content."
                ),
                "payload": {
                    "document_id": passage["document_id"],
                    "document_title": passage["document_title"],
                    "section_id": passage["section_id"],
                    "heading": passage.get("heading", ""),
                },
                "created_at": created_at,
            }
        )

    return records


def evidence_catalog(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["evidence_id"]: record for record in records}


def validate_evidence_ids(
    ids: Iterable[str],
    catalog: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Split referenced IDs into (valid, rejected) against the catalog.

    Preserves order and already-seen de-duplication so reports stay stable.
    """
    valid: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for evidence_id in ids:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            continue
        cleaned = evidence_id.strip()
        if cleaned in seen:
            continue
        seen.add(cleaned)
        if cleaned in catalog:
            valid.append(cleaned)
        else:
            rejected.append(cleaned)
    return valid, rejected


__all__ = [
    "format_evidence_id",
    "build_deterministic_evidence",
    "evidence_catalog",
    "validate_evidence_ids",
]
