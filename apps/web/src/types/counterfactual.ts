export type CounterfactualStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export interface DependencyTraceEntry {
  feature: string;
  label: string;
  reason: "direct" | "derived";
  evidence_ids: string[];
}

export interface AnomalyComparison {
  original_score: number | null;
  revised_score: number | null;
  original_severity: string | null;
  revised_severity: string | null;
  threshold: number;
  retained_feature_count: number;
  excluded_feature_keys: string[];
  recomputed: boolean;
}

export interface HypothesisChange {
  title: string;
  original_hypothesis_id: string | null;
  revised_hypothesis_id: string | null;
  original_assessment: string | null;
  revised_assessment: string | null;
  note: string | null;
}

export interface AssessmentShift {
  title: string;
  original_hypothesis_id: string;
  revised_hypothesis_id: string;
  original_assessment: string;
  revised_assessment: string;
}

export interface RecommendationDiff {
  added: string[];
  removed: string[];
}

export interface CounterfactualComparison {
  summary: string;
  retained_hypotheses: HypothesisChange[];
  removed_hypotheses: HypothesisChange[];
  added_hypotheses: HypothesisChange[];
  assessment_shifts: AssessmentShift[];
  new_contradictions: string[];
  removed_contradictions: string[];
  new_missing_evidence: string[];
  recommendation_diff: RecommendationDiff;
  anomaly: AnomalyComparison;
  retained_evidence_ids: string[];
  excluded_evidence_ids: string[];
  notes: string[];
}

export interface CounterfactualScenario {
  scenario_id: string;
  original_investigation_id: string;
  incident_id: string;
  revised_investigation_id: string | null;
  excluded_evidence_ids: string[];
  excluded_feature_keys: string[];
  rationale: string | null;
  status: CounterfactualStatus;
  error: string | null;
  comparison: CounterfactualComparison | null;
  dependency_trace: DependencyTraceEntry[];
  created_at: string;
  updated_at: string;
}

export interface CounterfactualListResponse {
  original_investigation_id: string;
  total: number;
  items: CounterfactualScenario[];
}
