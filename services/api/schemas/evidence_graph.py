"""Pydantic schemas for the interactive evidence graph.

The graph is a *read-only projection* of stored investigation data. Nodes map
one-to-one to persisted evidence records, hypotheses, recommended actions and
the incident itself; edges only exist when the structured records justify them.
No separate language-model call is used to draw the graph.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GraphNodeType = Literal[
    "incident",
    "sensor_evidence",
    "document_evidence",
    "visual_evidence",
    "hypothesis",
    "recommended_action",
]

GraphRelationship = Literal[
    "SUPPORTS",
    "CONTRADICTS",
    "DERIVED_FROM",
    "RELATES_TO",
    "RECOMMENDS",
]


class GraphPosition(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    x: float
    y: float


class GraphNode(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str = Field(description="Unique node id (evidence id or hypothesis id).")
    type: GraphNodeType
    label: str
    sublabel: str | None = None
    position: GraphPosition = Field(
        description="Deterministic layered layout hint computed by the backend."
    )
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str
    source: str
    target: str
    relationship: GraphRelationship
    label: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class EvidenceGraph(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    investigation_id: str
    incident_id: str
    generated_at: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
