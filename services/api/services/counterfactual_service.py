"""Counterfactual investigation service.

Given a completed investigation, this service builds a *restricted* reasoning
context with selected evidence removed (including the dependency closure over
derived features), re-runs the multi-agent pipeline against that context, and
stores the revised investigation plus a deterministic comparison. The original
investigation and its evidence are never modified.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from services.api.agents.orchestrator import PreparedContext
from services.api.core import config
from services.api.services.comparison_service import compare_reports
from services.api.services.counterfactual_repository import (
    CounterfactualNotFoundError,
    CounterfactualRepository,
    SqliteCounterfactualRepository,
)
from services.api.services.exclusion import (
    filter_evidence_records,
    resolve_excluded_features,
    restrict_anomaly,
    restrict_baselines,
    sanitize_measurements,
)
from services.api.services.investigation_service import InvestigationService
from services.api.tools.anomaly_tools import (
    get_anomaly_analysis,
    get_baseline_statistics,
)
from services.api.tools.incident_tools import (
    get_incident_context,
    get_incident_measurements,
)

logger = logging.getLogger(__name__)


class CounterfactualError(Exception):
    """Base counterfactual domain error."""


class InvalidExclusionError(CounterfactualError):
    """Raised when the requested exclusions are unknown or not permitted."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CounterfactualService:
    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
        repository: CounterfactualRepository | None = None,
    ) -> None:
        if investigation_service is None:
            from services.api.routes.investigations import get_service

            investigation_service = get_service()
        self.investigations = investigation_service
        self.incident_service = investigation_service.incident_service
        self.repository = repository or SqliteCounterfactualRepository()
        self.repository.initialize()

    @staticmethod
    def _new_id() -> str:
        return f"{config.COUNTERFACTUAL_ID_PREFIX}{uuid.uuid4().hex[:10].upper()}"

    # -- commands --------------------------------------------------------

    def create_scenario(
        self,
        original_investigation_id: str,
        excluded_evidence_ids: list[str],
        rationale: str | None = None,
    ) -> dict:
        original = self.investigations.get(original_investigation_id)
        if original["status"] != "completed" or not original.get("report"):
            raise CounterfactualError(
                "Counterfactual revisions require a completed investigation."
            )

        evidence = self.investigations.repository.get_evidence(
            original_investigation_id
        )
        by_id = {record["evidence_id"]: record for record in evidence}

        cleaned = self._validate_exclusions(excluded_evidence_ids, by_id, evidence)

        excluded_features, provenance = resolve_excluded_features(set(cleaned), evidence)
        kept_records, dropped_records = filter_evidence_records(
            evidence, set(cleaned), excluded_features
        )
        if not kept_records:
            raise InvalidExclusionError(
                "At least one evidence record must remain in the revised context."
            )

        incident_id = original["incident_id"]
        incident = self.incident_service.get_incident(incident_id)

        anomaly_original = get_anomaly_analysis(incident_id)
        anomaly_revised = restrict_anomaly(anomaly_original, excluded_features)
        measurements = sanitize_measurements(
            get_incident_measurements(incident_id), excluded_features
        )
        baselines = restrict_baselines(
            get_baseline_statistics(incident["machine_type"]), excluded_features
        )
        passages = self._passages_from_evidence(kept_records)

        incident_context = get_incident_context(incident_id)
        incident_context["severity"] = anomaly_revised["severity"]
        incident_context["anomaly_score"] = anomaly_revised["anomaly_score"]
        incident_context["counterfactual_revision"] = True

        scenario_id = self._new_id()
        revised_job = self.investigations.create_queued_investigation(incident_id)
        revised_investigation_id = revised_job["investigation_id"]

        revised_evidence = [
            {**record, "investigation_id": revised_investigation_id}
            for record in kept_records
        ]

        counterfactual_meta = {
            "scenario_id": scenario_id,
            "original_investigation_id": original_investigation_id,
            "excluded_evidence_ids": cleaned,
            "excluded_feature_keys": sorted(excluded_features),
            "rationale": rationale,
        }

        prepared = PreparedContext(
            incident_context=incident_context,
            measurements=measurements,
            anomaly=anomaly_revised,
            baselines=baselines,
            passages=passages,
            evidence_records=revised_evidence,
            counterfactual=counterfactual_meta,
        )

        dependency_trace = self._dependency_trace(
            excluded_features, provenance, cleaned, by_id
        )

        now = _utcnow_iso()
        self.repository.insert(
            {
                "scenario_id": scenario_id,
                "original_investigation_id": original_investigation_id,
                "incident_id": incident_id,
                "revised_investigation_id": revised_investigation_id,
                "excluded_evidence_ids": cleaned,
                "excluded_feature_keys": sorted(excluded_features),
                "rationale": rationale,
                "status": "running",
                "error": None,
                "comparison": None,
                "dependency_trace": dependency_trace,
                "created_at": now,
                "updated_at": now,
            }
        )

        try:
            self.investigations.run_job(revised_investigation_id, prepared=prepared)
            revised = self.investigations.get(revised_investigation_id)
            if revised["status"] != "completed" or not revised.get("report"):
                raise CounterfactualError(
                    revised.get("error") or "The revised investigation did not complete."
                )
            comparison = compare_reports(
                original_report=original["report"],
                revised_report=revised["report"],
                anomaly_original=anomaly_original,
                anomaly_revised=anomaly_revised,
                original_evidence=evidence,
                revised_evidence=revised_evidence,
                excluded_evidence_ids=cleaned,
                excluded_feature_keys=sorted(excluded_features),
            )
            self.repository.update(
                scenario_id,
                status="completed",
                comparison=comparison,
                excluded_feature_keys=sorted(excluded_features),
            )
        except Exception as exc:  # noqa: BLE001 - persist failure for the UI
            logger.exception("Counterfactual scenario %s failed", scenario_id)
            self.repository.update(
                scenario_id,
                status="failed",
                error=str(exc),
                excluded_feature_keys=sorted(excluded_features),
            )
        return self.get(scenario_id)

    # -- queries ---------------------------------------------------------

    def get(self, scenario_id: str) -> dict:
        scenario = self.repository.get(scenario_id)
        if scenario is None:
            raise CounterfactualNotFoundError(scenario_id)
        return scenario

    def list_for_investigation(self, investigation_id: str) -> dict:
        items = self.repository.list_for_investigation(investigation_id)
        return {
            "original_investigation_id": investigation_id,
            "total": len(items),
            "items": items,
        }

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _validate_exclusions(
        excluded_evidence_ids: list[str],
        by_id: dict[str, dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> list[str]:
        cleaned = sorted(
            {item.strip() for item in excluded_evidence_ids if item and item.strip()}
        )
        if not cleaned:
            raise InvalidExclusionError("At least one evidence ID must be excluded.")
        if len(cleaned) > config.MAX_COUNTERFACTUAL_EXCLUSIONS:
            raise InvalidExclusionError(
                f"At most {config.MAX_COUNTERFACTUAL_EXCLUSIONS} evidence items "
                "can be excluded."
            )
        unknown = [item for item in cleaned if item not in by_id]
        if unknown:
            raise InvalidExclusionError(
                "Unknown evidence ID(s): " + ", ".join(unknown)
            )
        disallowed = [
            item
            for item in cleaned
            if by_id[item]["evidence_type"] not in config.EXCLUDABLE_EVIDENCE_TYPES
        ]
        if disallowed:
            raise InvalidExclusionError(
                "Evidence cannot be excluded: " + ", ".join(disallowed)
            )
        if len(cleaned) >= len(evidence):
            raise InvalidExclusionError(
                "The entire evidence base cannot be excluded."
            )
        return cleaned

    @staticmethod
    def _passages_from_evidence(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        passages: list[dict[str, Any]] = []
        for record in records:
            if record["evidence_type"] != "manual_passage":
                continue
            payload = record.get("payload") or {}
            passages.append(
                {
                    "document_id": payload.get("document_id"),
                    "document_title": payload.get("document_title"),
                    "section_id": payload.get("section_id"),
                    "heading": payload.get("heading", ""),
                    "text": record["observation"],
                }
            )
        return passages

    @staticmethod
    def _dependency_trace(
        excluded_features: set[str],
        provenance: dict[str, int],
        excluded_evidence_ids: list[str],
        by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        from services.api.services.exclusion import feature_dependencies

        dependencies = feature_dependencies()
        direct_ids: dict[str, list[str]] = {}
        for evidence_id in excluded_evidence_ids:
            record = by_id.get(evidence_id)
            payload = (record or {}).get("payload") or {}
            feature = payload.get("feature")
            if feature:
                direct_ids.setdefault(feature, []).append(evidence_id)

        trace: list[dict[str, Any]] = []
        for feature in sorted(excluded_features):
            is_derived = feature in dependencies
            ids = list(direct_ids.get(feature, []))
            if is_derived:
                for source in dependencies[feature]:
                    ids.extend(direct_ids.get(source, []))
            trace.append(
                {
                    "feature": feature,
                    "label": config.FEATURE_LABELS.get(feature, feature),
                    "reason": "derived" if is_derived else "direct",
                    "evidence_ids": sorted(set(ids)),
                }
            )
        return trace


__all__ = [
    "CounterfactualService",
    "CounterfactualError",
    "InvalidExclusionError",
    "CounterfactualNotFoundError",
]
