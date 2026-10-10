export type GraphNodeType =
  | "incident"
  | "sensor_evidence"
  | "document_evidence"
  | "visual_evidence"
  | "hypothesis"
  | "recommended_action";

export type GraphRelationship =
  | "SUPPORTS"
  | "CONTRADICTS"
  | "DERIVED_FROM"
  | "RELATES_TO"
  | "RECOMMENDS";

export interface GraphPosition {
  x: number;
  y: number;
}

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  sublabel: string | null;
  position: GraphPosition;
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: GraphRelationship;
  label: string | null;
  data: Record<string, unknown>;
}

export interface EvidenceGraph {
  investigation_id: string;
  incident_id: string;
  generated_at: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}
