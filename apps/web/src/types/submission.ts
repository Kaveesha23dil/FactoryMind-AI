export interface EvidenceAudit {
  stored_evidence: number;
  citation_links: number;
  resolved_citation_links: number;
  invalid_evidence_ids: string[];
  source_issues: string[];
  catalog_matches_storage: boolean;
  relationship_reviews_available: boolean;
  critic_attention_required: boolean;
  duration_seconds: number | null;
  scope: string;
}
export interface SubmissionOverview {
  dataset: string;
  anomalies: number;
  severity_distribution: Record<string, number>;
  active_incidents: number;
  investigations: Record<string, number>;
  recent: Array<{ investigation_id: string; status: string; summary: string | null }>;
  integrity: { audited_reports: number; completed_reports: number; scan_limit: number; citation_links: number; resolved_citation_links: number; reports_needing_attention: number };
  demo: null | { investigation_id: string; incident_id: string; record_id: number; generated_at: string; model: string; label: string; audit: EvidenceAudit };
}
