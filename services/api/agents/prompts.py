"""Prompt-formatting helpers shared by the logical agents.

All numbers formatted here were computed by deterministic Python tools. The
model is only ever asked to interpret, not to calculate.
"""

from __future__ import annotations

import json
from typing import Any, Iterable


def format_evidence_catalog(records: Iterable[dict[str, Any]]) -> str:
    lines = []
    for record in records:
        lines.append(
            f"- {record['evidence_id']} [{record['evidence_type']}] "
            f"source={record['source']} :: {record['observation']}"
        )
    return "\n".join(lines) if lines else "(no evidence)"


def format_measurements(measurements: dict[str, Any]) -> str:
    return json.dumps(measurements, indent=2, default=str)


def format_anomaly(anomaly: dict[str, Any]) -> str:
    features = anomaly.get("features", [])
    lines = [
        f"algorithm: {anomaly.get('algorithm')}",
        f"anomaly_score: {anomaly.get('anomaly_score')} ({anomaly.get('severity')})",
        f"threshold: {anomaly.get('threshold')}",
        f"feature_z_threshold: {anomaly.get('feature_z_threshold')}",
        "feature contributions (already computed, do not recalculate):",
    ]
    for feature in features:
        lines.append(
            f"- {feature.get('label')} ({feature.get('feature')}): observed="
            f"{feature.get('observed_value')}{feature.get('unit')} "
            f"z={feature.get('robust_zscore')} direction={feature.get('direction')} "
            f"anomalous={feature.get('is_anomalous')} baseline_median="
            f"{feature.get('baseline_median')} scope={feature.get('baseline_scope')}"
        )
    return "\n".join(lines)


def format_baselines(baselines: dict[str, Any]) -> str:
    lines = [f"scope: {baselines.get('scope')} (machine type {baselines.get('machine_type')})"]
    for key, stats in baselines.get("baselines", {}).items():
        lines.append(
            f"- {key}: median={stats.get('median')} scale={stats.get('scale')} "
            f"mad={stats.get('mad')} count={stats.get('count')} "
            f"degenerate={stats.get('degenerate')}"
        )
    return "\n".join(lines)


def format_knowledge(passages: Iterable[dict[str, Any]]) -> str:
    lines = []
    for passage in passages:
        lines.append(
            f"- {passage['document_id']} / {passage['section_id']} "
            f"({passage['document_title']} - {passage.get('heading', '')}):\n"
            f"  \"{passage['text']}\""
        )
    return "\n".join(lines) if lines else "(no passages retrieved)"
