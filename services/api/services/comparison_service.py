"""Deterministic comparison of an original vs. counterfactual investigation.

Counterfactuals must explain *what changed and why* without inventing
confidence numbers. This module compares two report structures qualitatively:

* which hypotheses were retained / removed / added,
* where assessments shifted (phrased, not scored),
* which contradictions appeared or disappeared,
* how recommended actions differ,
* how the deterministic anomaly severity was recomputed under the restricted
  feature set.
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_title(title: str) -> str:
    return " ".join(_TOKEN_RE.findall((title or "").lower()))


def _tokens(title: str) -> set[str]:
    return set(_TOKEN_RE.findall((title or "").lower()))


def _overlap(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _match_hypotheses(
    original: list[dict[str, Any]], revised: list[dict[str, Any]]
) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Greedy, deterministic matching of hypotheses by title similarity."""
    matches: list[tuple[dict, dict]] = []
    remaining_revised = list(revised)
    unmatched_original: list[dict] = []
    for item in original:
        normalized = _normalize_title(item.get("title", ""))
        best = None
        best_score = 0.0
        for candidate in remaining_revised:
            if _normalize_title(candidate.get("title", "")) == normalized:
                best, best_score = candidate, 1.0
                break
            score = _overlap(item.get("title", ""), candidate.get("title", ""))
            if score > best_score:
                best, best_score = candidate, score
        if best is not None and best_score >= 0.34:
            matches.append((item, best))
            remaining_revised.remove(best)
        else:
            unmatched_original.append(item)
    return matches, unmatched_original, remaining_revised


def compare_reports(
    original_report: dict[str, Any],
    revised_report: dict[str, Any],
    anomaly_original: dict[str, Any],
    anomaly_revised: dict[str, Any],
    original_evidence: list[dict[str, Any]],
    revised_evidence: list[dict[str, Any]],
    excluded_evidence_ids: list[str],
    excluded_feature_keys: list[str],
) -> dict[str, Any]:
    original_hypotheses = original_report.get("hypotheses", []) or []
    revised_hypotheses = revised_report.get("hypotheses", []) or []

    matches, removed, added = _match_hypotheses(original_hypotheses, revised_hypotheses)

    retained: list[dict[str, Any]] = []
    assessment_shifts: list[dict[str, Any]] = []
    for before, after in matches:
        original_assessment = before.get("assessment")
        revised_assessment = after.get("assessment")
        retained.append(
            {
                "title": after.get("title") or before.get("title") or "",
                "original_hypothesis_id": before.get("hypothesis_id"),
                "revised_hypothesis_id": after.get("hypothesis_id"),
                "original_assessment": original_assessment,
                "revised_assessment": revised_assessment,
                "note": (
                    "assessment unchanged"
                    if original_assessment == revised_assessment
                    else "assessment shifted under the restricted context"
                ),
            }
        )
        if original_assessment != revised_assessment:
            assessment_shifts.append(
                {
                    "title": after.get("title") or before.get("title") or "",
                    "original_hypothesis_id": before.get("hypothesis_id") or "",
                    "revised_hypothesis_id": after.get("hypothesis_id") or "",
                    "original_assessment": original_assessment or "unknown",
                    "revised_assessment": revised_assessment or "unknown",
                }
            )

    removed_changes = [
        {
            "title": item.get("title") or "",
            "original_hypothesis_id": item.get("hypothesis_id"),
            "original_assessment": item.get("assessment"),
            "note": "no matching hypothesis in the revised investigation",
        }
        for item in removed
    ]
    added_changes = [
        {
            "title": item.get("title") or "",
            "revised_hypothesis_id": item.get("hypothesis_id"),
            "revised_assessment": item.get("assessment"),
            "note": "hypothesis only present under the restricted context",
        }
        for item in added
    ]

    excluded = set(excluded_evidence_ids)

    def _contradictions(hypotheses: list[dict[str, Any]]) -> set[str]:
        ids: set[str] = set()
        for hypothesis in hypotheses:
            ids.update(hypothesis.get("contradicting_evidence_ids", []) or [])
        return ids - excluded

    def _missing(hypotheses: list[dict[str, Any]]) -> set[str]:
        items: set[str] = set()
        for hypothesis in hypotheses:
            items.update(hypothesis.get("missing_evidence", []) or [])
        return items

    original_contradictions = _contradictions(original_hypotheses)
    revised_contradictions = _contradictions(revised_hypotheses)
    new_contradictions = sorted(revised_contradictions - original_contradictions)
    removed_contradictions = sorted(original_contradictions - revised_contradictions)

    original_missing = _missing(original_hypotheses)
    revised_missing = _missing(revised_hypotheses)
    new_missing = sorted(revised_missing - original_missing)

    def _actions(report: dict[str, Any]) -> list[str]:
        return [
            action.get("action", "")
            for action in report.get("recommended_actions", []) or []
            if action.get("action")
        ]

    original_actions = set(_actions(original_report))
    revised_actions = set(_actions(revised_report))

    retained_evidence = sorted(
        {record["evidence_id"] for record in revised_evidence}
    )

    anomaly_comparison = {
        "original_score": anomaly_original.get("anomaly_score"),
        "revised_score": anomaly_revised.get("anomaly_score"),
        "original_severity": anomaly_original.get("severity"),
        "revised_severity": anomaly_revised.get("severity"),
        "threshold": float(anomaly_revised.get("threshold", anomaly_original.get("threshold", 0.0))),
        "retained_feature_count": len(anomaly_revised.get("features", []) or []),
        "excluded_feature_keys": sorted(excluded_feature_keys),
        "recomputed": bool(anomaly_revised.get("anomaly_score_recomputed")),
    }

    summary = _summary(
        excluded_count=len(excluded_evidence_ids),
        excluded_features=excluded_feature_keys,
        original_severity=anomaly_original.get("severity"),
        revised_severity=anomaly_revised.get("severity"),
        retained=len(retained),
        removed=len(removed),
        added=len(added),
        shifts=len(assessment_shifts),
    )

    notes = [
        "This is a what-if revision computed on a restricted context, not a "
        "measured change to the physical asset.",
        "Anomaly severity is the deterministically recomputed score for the "
        "remaining features; it carries no physical certainty.",
    ]

    return {
        "summary": summary,
        "retained_hypotheses": retained,
        "removed_hypotheses": removed_changes,
        "added_hypotheses": added_changes,
        "assessment_shifts": assessment_shifts,
        "new_contradictions": new_contradictions,
        "removed_contradictions": removed_contradictions,
        "new_missing_evidence": new_missing,
        "recommendation_diff": {
            "added": sorted(revised_actions - original_actions),
            "removed": sorted(original_actions - revised_actions),
        },
        "anomaly": anomaly_comparison,
        "retained_evidence_ids": retained_evidence,
        "excluded_evidence_ids": sorted(excluded_evidence_ids),
        "notes": notes,
    }


def _summary(
    excluded_count: int,
    excluded_features: list[str],
    original_severity: str | None,
    revised_severity: str | None,
    retained: int,
    removed: int,
    added: int,
    shifts: int,
) -> str:
    feature_text = (
        f" across {len(excluded_features)} feature(s)" if excluded_features else ""
    )
    severity_text = (
        f" Anomaly severity moved from {original_severity} to {revised_severity}."
        if original_severity != revised_severity
        else f" Anomaly severity stayed {revised_severity}."
    )
    return (
        f"Removed {excluded_count} evidence item(s){feature_text} and re-ran the "
        f"investigation. {retained} hypothesis(es) were retained, {removed} no "
        f"longer held, {added} new one(s) appeared, with {shifts} assessment "
        f"shift(s).{severity_text}"
    )


__all__ = ["compare_reports"]
