import type {
  FeatureContribution,
  IncidentStatus,
  Severity,
} from "@/types/anomaly";

export interface IncidentTimelineEntry {
  status: IncidentStatus;
  timestamp: string;
  note: string | null;
}

export interface Incident {
  incident_id: string;
  record_id: number;
  product_id: string;
  machine_type: string;
  algorithm: string;
  anomaly_score: number;
  severity: Severity;
  status: IncidentStatus;
  source_measurements: Record<string, unknown>;
  evidence: FeatureContribution[];
  explanations: string[];
  note: string | null;
  created_at: string;
  updated_at: string;
  timeline: IncidentTimelineEntry[];
  detection_config: {
    threshold: number;
    feature_z_threshold: number;
    baseline_fit_sample_count: number;
    split_seed: number;
  } | null;
  ground_truth_used_for_detection: boolean;
}

export interface IncidentListItem {
  incident_id: string;
  record_id: number;
  machine_type: string;
  algorithm: string;
  anomaly_score: number;
  severity: Severity;
  status: IncidentStatus;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentListResponse {
  total: number;
  limit: number;
  offset: number;
  returned: number;
  items: IncidentListItem[];
}

export interface ScanRequest {
  min_severity: Exclude<Severity, "normal">;
  max_incidents?: number;
  dry_run?: boolean;
}

export interface ScanResponse {
  min_severity: string;
  max_incidents: number;
  dry_run: boolean;
  candidates_evaluated: number;
  incidents_created: number;
  incidents_skipped_duplicate: number;
  created_incident_ids: string[];
}
