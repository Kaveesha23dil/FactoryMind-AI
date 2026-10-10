export type VisualEvidenceStatus =
  | "stored"
  | "analyzing"
  | "analyzed"
  | "failed";

export type SeverityHint = "informational" | "attention" | "urgent";

export interface VisualObservation {
  observation: string;
  related_features: string[];
  severity_hint: SeverityHint;
}

export interface VisualEvidenceRecord {
  image_id: string;
  incident_id: string;
  investigation_id: string | null;
  filename: string;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  provenance: string;
  storage_backend: string;
  status: VisualEvidenceStatus;
  summary: string | null;
  observations: VisualObservation[];
  limitations: string[];
  error: string | null;
  content_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface VisualEvidenceListResponse {
  incident_id: string;
  total: number;
  items: VisualEvidenceRecord[];
}
