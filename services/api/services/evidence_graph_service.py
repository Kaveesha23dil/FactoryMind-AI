"""Deterministic evidence-graph builder.

The graph is derived entirely from stored investigation records:

* the incident (id, severity, status),
* the persisted evidence catalog,
* the report hypotheses and their supporting/contradicting evidence IDs,
* the recommended actions (linked back to the hypotheses that produced them).

Nothing here calls a language model. Every node maps to a real record and every
edge references two existing nodes; unresolved references are dropped rather
than invented.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from services.api.core import config
from services.api.schemas.evidence_graph import (
    EvidenceGraph,
    GraphEdge,
    GraphNode,
)
from services.api.services.investigation_service import InvestigationService

logger = logging.getLogger(__name__)

#: Horizontal / vertical spacing for the deterministic layered layout.
_X_GAP = 340.0
_Y_GAP = 130.0

_EVIDENCE_NODE_TYPE = {
    "source_metadata": "sensor_evidence",
    "anomaly_finding": "sensor_evidence",
    "sensor_measurement": "sensor_evidence",
    "baseline_statistic": "sensor_evidence",
    "manual_passage": "document_evidence",
    "visual_observation": "visual_evidence",
}

_LAYER = {
    "incident": 0,
    "sensor_evidence": 1,
    "document_evidence": 1,
    "visual_evidence": 1,
    "hypothesis": 2,
    "recommended_action": 3,
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _column_to_feature_key() -> dict[str, str]:
    """Map a raw dataset column to the single-column feature key that owns it."""
    mapping: dict[str, str] = {}
    for definition in config.FEATURE_DEFINITIONS:
        if len(definition["columns"]) == 1:
            mapping[definition["columns"][0]] = definition["key"]
    return mapping


def _derived_dependencies() -> dict[str, list[str]]:
    """feature key -> list of source feature keys it is derived from."""
    column_key = _column_to_feature_key()
    dependencies: dict[str, list[str]] = {}
    for definition in config.FEATURE_DEFINITIONS:
        if len(definition["columns"]) <= 1:
            continue
        sources = [column_key[column] for column in definition["columns"] if column in column_key]
        if sources:
            dependencies[definition["key"]] = sources
    return dependencies


class EvidenceGraphService:
    def __init__(self, investigation_service: InvestigationService | None = None) -> None:
        self.investigations = investigation_service or InvestigationService()

    def build(self, investigation_id: str) -> EvidenceGraph:
        job = self.investigations.get(investigation_id)
        incident_id = job["incident_id"]
        incident = self.investigations.incident_service.get_incident(incident_id)
        evidence = self.investigations.repository.get_evidence(investigation_id)
        report = job.get("report") or {}
        hypotheses = report.get("hypotheses", []) or []
        actions = report.get("recommended_actions", []) or []

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        node_ids: set[str] = set()

        def add_node(node: GraphNode) -> None:
            if node.id in node_ids:
                return
            node_ids.add(node.id)
            nodes.append(node)

        # --- Incident node -------------------------------------------------
        incident_node_id = incident_id
        add_node(
            GraphNode(
                id=incident_node_id,
                type="incident",
                label=incident_id,
                sublabel=f"{incident.get('severity', 'unknown')} severity",
                position={"x": 0.0, "y": 0.0},
                data={
                    "incident_id": incident_id,
                    "record_id": incident.get("record_id"),
                    "machine_type": incident.get("machine_type"),
                    "anomaly_score": incident.get("anomaly_score"),
                    "anomaly_severity": incident.get("severity"),
                    "investigation_status": job.get("status"),
                    "status": incident.get("status"),
                    "layer": 0,
                },
            )
        )

        # --- Evidence nodes ------------------------------------------------
        feature_evidence: dict[str, str] = {}
        for record in evidence:
            evidence_type = record["evidence_type"]
            node_type = _EVIDENCE_NODE_TYPE.get(evidence_type, "sensor_evidence")
            payload = record.get("payload") or {}
            data: dict[str, Any] = {
                "evidence_id": record["evidence_id"],
                "evidence_type": evidence_type,
                "source": record.get("source"),
                "observation": record.get("observation"),
                "value": record.get("value"),
                "units": record.get("units"),
                "provenance": record.get("provenance"),
                "created_at": record.get("created_at"),
                "layer": _LAYER.get(node_type, 1),
                "payload": payload,
            }
            if evidence_type in ("sensor_measurement", "baseline_statistic"):
                data["measurement"] = payload.get("label")
                data["feature"] = payload.get("feature")
                data["robust_zscore"] = payload.get("robust_zscore")
                data["direction"] = payload.get("direction")
                data["is_anomalous"] = payload.get("is_anomalous")
                data["baseline_median"] = payload.get("median", payload.get("baseline_median"))
                data["baseline_scope"] = payload.get("scope")
            if evidence_type == "manual_passage":
                data["document_id"] = payload.get("document_id")
                data["document_title"] = payload.get("document_title")
                data["section_id"] = payload.get("section_id")
                data["heading"] = payload.get("heading")
                data["passage"] = record.get("observation")
            if evidence_type == "visual_observation":
                data["image_id"] = payload.get("image_id")
                data["storage_reference"] = payload.get("storage_reference")
                data["observations"] = payload.get("observations", [])
                data["limitations"] = payload.get("limitations", [])
                data["visible_observation"] = record.get("observation")
            if evidence_type == "anomaly_finding":
                data["anomaly_score"] = record.get("value")
                data["severity"] = payload.get("severity")
                data["threshold"] = payload.get("threshold")

            add_node(
                GraphNode(
                    id=record["evidence_id"],
                    type=node_type,
                    label=record["evidence_id"],
                    sublabel=payload.get("label") or payload.get("document_title") or evidence_type,
                    position={"x": _X_GAP * _LAYER.get(node_type, 1), "y": 0.0},
                    data=data,
                )
            )
            if (
                evidence_type == "sensor_measurement"
                and payload.get("feature")
                and payload["feature"] not in feature_evidence
            ):
                feature_evidence[payload["feature"]] = record["evidence_id"]

        # --- Hypothesis nodes ---------------------------------------------
        critic = report.get("critic_review", {}) or {}
        flagged_text = list(critic.get("citation_issues", []) or []) + list(
            critic.get("unsupported_claims", []) or []
        )
        for hypothesis in hypotheses:
            hypothesis_id = hypothesis.get("hypothesis_id")
            if not hypothesis_id or hypothesis_id in node_ids:
                continue
            title = hypothesis.get("title", hypothesis_id)
            flagged = any(
                hypothesis_id in text or (title and title in text)
                for text in flagged_text
            )
            add_node(
                GraphNode(
                    id=hypothesis_id,
                    type="hypothesis",
                    label=title,
                    sublabel=hypothesis.get("assessment"),
                    position={"x": _X_GAP * _LAYER["hypothesis"], "y": 0.0},
                    data={
                        "hypothesis_id": hypothesis_id,
                        "title": title,
                        "description": hypothesis.get("description", ""),
                        "assessment": hypothesis.get("assessment"),
                        "verification_status": hypothesis.get("assessment"),
                        "critic_flagged": flagged,
                        "supporting_evidence_ids": hypothesis.get("supporting_evidence_ids", []),
                        "contradicting_evidence_ids": hypothesis.get("contradicting_evidence_ids", []),
                        "missing_evidence": hypothesis.get("missing_evidence", []),
                        "verification_steps": hypothesis.get("verification_steps", []),
                        "layer": _LAYER["hypothesis"],
                    },
                )
            )

        # --- Recommended action nodes -------------------------------------
        for index, action in enumerate(actions, start=1):
            action_id = f"ACT-{index:03d}"
            add_node(
                GraphNode(
                    id=action_id,
                    type="recommended_action",
                    label=action.get("action", action_id),
                    sublabel=(
                        "Human approval required"
                        if action.get("requires_human_approval", True)
                        else "No approval required"
                    ),
                    position={"x": _X_GAP * _LAYER["recommended_action"], "y": 0.0},
                    data={
                        "action_id": action_id,
                        "action": action.get("action", ""),
                        "rationale": action.get("rationale", ""),
                        "requires_human_approval": bool(action.get("requires_human_approval", True)),
                        "supporting_hypothesis_ids": self._action_hypotheses(action, hypotheses),
                        "layer": _LAYER["recommended_action"],
                    },
                )
            )

        # --- Edges: incident relates to every evidence node ----------------
        for node in nodes:
            if node.type in ("sensor_evidence", "document_evidence", "visual_evidence"):
                self._add_edge(
                    edges,
                    node_ids,
                    incident_node_id,
                    node.id,
                    "RELATES_TO",
                    label="incident evidence",
                )

        # --- Edges: hypothesis <-> evidence --------------------------------
        for hypothesis in hypotheses:
            hypothesis_id = hypothesis.get("hypothesis_id")
            if hypothesis_id not in node_ids:
                continue
            for evidence_id in hypothesis.get("supporting_evidence_ids", []) or []:
                self._add_edge(
                    edges, node_ids, evidence_id, hypothesis_id, "SUPPORTS",
                    label="supports",
                )
            for evidence_id in hypothesis.get("contradicting_evidence_ids", []) or []:
                self._add_edge(
                    edges, node_ids, evidence_id, hypothesis_id, "CONTRADICTS",
                    label="contradicts",
                )

        # --- Edges: derived evidence depends on source evidence ------------
        for derived_key, sources in _derived_dependencies().items():
            derived_id = feature_evidence.get(derived_key)
            if not derived_id:
                continue
            for source_key in sources:
                source_id = feature_evidence.get(source_key)
                if source_id:
                    self._add_edge(
                        edges, node_ids, derived_id, source_id, "DERIVED_FROM",
                        label="derived from",
                        data={"derived_feature": derived_key, "source_feature": source_key},
                    )

        # --- Edges: hypothesis recommends action ---------------------------
        for index, action in enumerate(actions, start=1):
            action_id = f"ACT-{index:03d}"
            if action_id not in node_ids:
                continue
            for hypothesis_id in self._action_hypotheses(action, hypotheses):
                self._add_edge(
                    edges, node_ids, hypothesis_id, action_id, "RECOMMENDS",
                    label="recommends",
                )

        self._apply_layout(nodes)
        return EvidenceGraph(
            investigation_id=investigation_id,
            incident_id=incident_id,
            generated_at=_utcnow_iso(),
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
        )

    @staticmethod
    def _action_hypotheses(
        action: dict[str, Any], hypotheses: list[dict[str, Any]]
    ) -> list[str]:
        explicit = action.get("supporting_hypothesis_ids")
        if explicit:
            return [item for item in explicit if item]
        # Fallback for reports stored before explicit linking existed: match the
        # action text against a hypothesis' verification steps (deterministic).
        text = action.get("action", "")
        matches: list[str] = []
        for hypothesis in hypotheses:
            steps = hypothesis.get("verification_steps", []) or []
            if text and text in steps:
                matches.append(hypothesis.get("hypothesis_id"))
        return [item for item in matches if item]

    @staticmethod
    def _add_edge(
        edges: list[GraphEdge],
        node_ids: set[str],
        source: str,
        target: str,
        relationship: str,
        label: str | None = None,
        data: dict | None = None,
    ) -> None:
        if source not in node_ids or target not in node_ids or source == target:
            return
        edge_id = f"{source}->{target}:{relationship}"
        if any(edge.id == edge_id for edge in edges):
            return
        edges.append(
            GraphEdge(
                id=edge_id,
                source=source,
                target=target,
                relationship=relationship,  # type: ignore[arg-type]
                label=label,
                data=data or {},
            )
        )

    @staticmethod
    def _apply_layout(nodes: list[GraphNode]) -> None:
        """Assign deterministic vertical positions within each layer."""
        by_layer: dict[int, list[GraphNode]] = {}
        for node in nodes:
            by_layer.setdefault(node.data.get("layer", 0), []).append(node)
        for layer_nodes in by_layer.values():
            count = len(layer_nodes)
            for index, node in enumerate(layer_nodes):
                node.position.y = (index - (count - 1) / 2.0) * _Y_GAP


__all__ = ["EvidenceGraphService"]
