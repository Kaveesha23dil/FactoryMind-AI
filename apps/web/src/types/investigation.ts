export type InvestigationStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed";

export type AgentStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export type HypothesisAssessment = "plausible" | "weak" | "unsupported";

export type EvidenceType =
  | "source_metadata"
  | "anomaly_finding"
  | "sensor_measurement"
  | "baseline_statistic"
  | "manual_passage"
  | "visual_observation";

export interface StageEntry {
  stage: string;
  message: string | null;
  timestamp: string;
}

export interface AgentActivity {
  agent: string;
  label: string;
  status: AgentStatus;
  summary: string | null;
  evidence_count: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Hypothesis {
  hypothesis_id: string;
  title: string;
  description: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  missing_evidence: string[];
  verification_steps: string[];
  assessment: HypothesisAssessment;
}

export interface CriticReview {
  verification_outcome: string;
  issues_found: string[];
  unsupported_claims: string[];
  contradictions: string[];
  alternative_explanations: string[];
  missing_evidence: string[];
  citation_issues: string[];
  revision_required: boolean;
  deterministic_findings: string[];
  excluded_evidence_reused: string[];
}

export interface RecommendedAction {
  action: string;
  rationale: string;
  requires_human_approval: boolean;
  supporting_hypothesis_ids: string[];
}

export interface CounterfactualMeta {
  scenario_id: string;
  original_investigation_id: string;
  excluded_evidence_ids: string[];
  excluded_feature_keys: string[];
  rationale: string | null;
}

export interface InvestigationReport {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  summary: string;
  provider: string;
  model: string;
  generated_at: string;
  hypotheses: Hypothesis[];
  critic_review: CriticReview;
  recommended_actions: RecommendedAction[];
  agent_activity: AgentActivity[];
  evidence_catalog: string[];
  rejected_citations: string[];
  revision_count: number;
  counterfactual: CounterfactualMeta | null;
  disclaimer: string;
}

export interface InvestigationJob {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  stage: string;
  provider: string;
  model: string;
  summary: string | null;
  error: string | null;
  attempt_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
  stage_history: StageEntry[];
  agent_activity: AgentActivity[];
  report: InvestigationReport | null;
}

export interface EvidenceRecord {
  evidence_id: string;
  investigation_id: string;
  incident_id: string;
  evidence_type: EvidenceType;
  source: string;
  observation: string;
  value: number | null;
  units: string | null;
  provenance: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface EvidenceListResponse {
  investigation_id: string;
  incident_id: string;
  total: number;
  items: EvidenceRecord[];
}

export interface InvestigationListItem {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  stage: string;
  provider: string;
  model: string;
  summary: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface InvestigationListPage {
  total: number;
  limit: number;
  offset: number;
  returned: number;
  items: InvestigationListItem[];
}

export interface InvestigationListResponse {
  incident_id: string;
  total: number;
  items: InvestigationListItem[];
}

export interface InvestigationStartResponse {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  stage: string;
  created_at: string;
}
