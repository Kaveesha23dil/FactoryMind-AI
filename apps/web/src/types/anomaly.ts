export type Severity = "normal" | "low" | "medium" | "high" | "critical";

export type IncidentStatus = "open" | "under_review" | "resolved";

export interface FeatureContribution {
  feature: string;
  label: string;
  unit: string;
  observed_value: number;
  baseline_median: number;
  baseline_scale: number;
  baseline_mad: number;
  robust_zscore: number;
  abs_zscore: number;
  direction: "high" | "low";
  is_anomalous: boolean;
  baseline_scope: "global" | "machine_type";
  explanation: string;
}

export interface BaselineStats {
  count: number;
  median: number;
  mad: number;
  scale: number;
  mean: number;
  std: number;
  degenerate: boolean;
}

export interface ScoreBin {
  bin_start: number;
  bin_end: number;
  count: number;
}

export interface ScoreStats {
  min: number;
  median: number;
  mean: number;
  max: number;
  p95: number;
}

export interface AnomalyListItem {
  record_id: number;
  machine_type: string;
  product_id: string;
  algorithm: string;
  anomaly_score: number;
  severity: Severity;
  is_anomaly: boolean;
  main_anomalous_feature: string | null;
  anomalous_feature_count: number;
  incident_status: IncidentStatus | null;
  incident_id: string | null;
  ground_truth_failure: boolean;
  ground_truth_failure_types: string[];
  ground_truth_used_for_detection: boolean;
}

export interface AnomalyDetail {
  record_id: number;
  product_id: string;
  machine_type: string;
  algorithm: string;
  anomaly_score: number;
  severity: Severity;
  is_anomaly: boolean;
  threshold: number;
  feature_z_threshold: number;
  anomalous_features: FeatureContribution[];
  features: FeatureContribution[];
  incident_status: IncidentStatus | null;
  incident_id: string | null;
  ground_truth_failure: boolean;
  ground_truth_failure_types: string[];
  ground_truth_used_for_detection: boolean;
}

export interface AnomalyListResponse {
  algorithm: string;
  threshold: number;
  total: number;
  limit: number;
  offset: number;
  returned: number;
  records: AnomalyListItem[];
}

export interface AnomalySummary {
  algorithm: string;
  analyzed_sample_count: number;
  detected_anomaly_count: number;
  anomaly_rate: number;
  severity_distribution: Record<Severity, number>;
  threshold: number;
  feature_z_threshold: number;
  baseline_fit_sample_count: number;
  feature_baselines: Record<string, BaselineStats>;
  score_histogram: ScoreBin[];
  score_stats: ScoreStats;
  ground_truth_used_for_detection: boolean;
}

export interface EvaluationMetrics {
  confusion_matrix: {
    true_positive: number;
    true_negative: number;
    false_positive: number;
    false_negative: number;
  };
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate: number;
  accuracy: number;
  support: number;
}

export interface EvaluationReport {
  algorithm: string;
  split: {
    seed: number;
    train_count: number;
    validation_count: number;
    test_count: number;
    baseline_fit_on: string;
    threshold_selected_on: string;
  };
  thresholds: { configured: number; validation_tuned: number };
  test_metrics_at_configured_threshold: EvaluationMetrics;
  test_metrics_at_validation_tuned_threshold: EvaluationMetrics;
  test_class_balance: {
    positive_failures: number;
    negative_failures: number;
    failure_rate: number;
  };
  notes: string[];
  ground_truth_used_for_detection: boolean;
}
