import type { BadgeTone } from "@/components/ui/StatusBadge";
import type {
  AgentStatus,
  EvidenceType,
  HypothesisAssessment,
  InvestigationStatus,
} from "@/types/investigation";
import type { GraphNodeType, GraphRelationship } from "@/types/evidenceGraph";
import type { CounterfactualStatus } from "@/types/counterfactual";
import type { SeverityHint, VisualEvidenceStatus } from "@/types/visual";

export const INVESTIGATION_STATUS_LABELS: Record<InvestigationStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export const INVESTIGATION_STATUS_TONE: Record<InvestigationStatus, BadgeTone> = {
  queued: "neutral",
  running: "accent",
  completed: "success",
  failed: "danger",
};

export const AGENT_STATUS_LABELS: Record<AgentStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  skipped: "Skipped",
};

export const AGENT_STATUS_TONE: Record<AgentStatus, BadgeTone> = {
  pending: "neutral",
  running: "accent",
  completed: "success",
  failed: "danger",
  skipped: "neutral",
};

export const HYPOTHESIS_ASSESSMENT_LABELS: Record<
  HypothesisAssessment,
  string
> = {
  plausible: "Plausible",
  weak: "Weak",
  unsupported: "Unsupported",
};

export const HYPOTHESIS_ASSESSMENT_TONE: Record<
  HypothesisAssessment,
  BadgeTone
> = {
  plausible: "warning",
  weak: "neutral",
  unsupported: "danger",
};

export const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  source_metadata: "Source metadata",
  anomaly_finding: "Anomaly finding",
  sensor_measurement: "Sensor measurement",
  baseline_statistic: "Baseline statistic",
  manual_passage: "Retrieved passage",
  visual_observation: "Visual observation",
};

export const INVESTIGATION_STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  collecting_evidence: "Collecting evidence",
  analyzing_measurements: "Analyzing measurements",
  retrieving_knowledge: "Retrieving knowledge",
  generating_hypotheses: "Generating hypotheses",
  verifying_conclusions: "Verifying conclusions",
  completed: "Completed",
  failed: "Failed",
};

export const AGENT_ORDER = [
  "sensor_agent",
  "knowledge_agent",
  "investigation_agent",
  "critic_agent",
] as const;

export function isTerminalInvestigation(
  status: InvestigationStatus
): boolean {
  return status === "completed" || status === "failed";
}

export function labelForStage(stage: string): string {
  return INVESTIGATION_STAGE_LABELS[stage] ?? stage;
}

export const GRAPH_NODE_LABELS: Record<GraphNodeType, string> = {
  incident: "Incident",
  sensor_evidence: "Sensor evidence",
  document_evidence: "Document evidence",
  visual_evidence: "Visual evidence",
  hypothesis: "Hypothesis",
  recommended_action: "Recommended action",
};

export const GRAPH_NODE_COLORS: Record<GraphNodeType, string> = {
  incident: "#2251ff",
  sensor_evidence: "#38bdf8",
  document_evidence: "#f59e0b",
  visual_evidence: "#10b981",
  hypothesis: "#a855f7",
  recommended_action: "#f472b6",
};

export const GRAPH_RELATIONSHIP_LABELS: Record<GraphRelationship, string> = {
  SUPPORTS: "Supports",
  CONTRADICTS: "Contradicts",
  DERIVED_FROM: "Derived from",
  RELATES_TO: "Relates to",
  RECOMMENDS: "Recommends",
};

export const GRAPH_RELATIONSHIP_COLORS: Record<GraphRelationship, string> = {
  SUPPORTS: "#10b981",
  CONTRADICTS: "#ef4444",
  DERIVED_FROM: "#38bdf8",
  RELATES_TO: "#64748b",
  RECOMMENDS: "#f59e0b",
};

export const EXCLUDABLE_EVIDENCE_TYPES: EvidenceType[] = [
  "sensor_measurement",
  "baseline_statistic",
  "anomaly_finding",
  "source_metadata",
  "manual_passage",
  "visual_observation",
];

export const COUNTERFACTUAL_STATUS_LABELS: Record<CounterfactualStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export const COUNTERFACTUAL_STATUS_TONE: Record<CounterfactualStatus, BadgeTone> = {
  pending: "neutral",
  running: "accent",
  completed: "success",
  failed: "danger",
};

export const VISUAL_STATUS_LABELS: Record<VisualEvidenceStatus, string> = {
  stored: "Stored",
  analyzing: "Analyzing",
  analyzed: "Analyzed",
  failed: "Failed",
};

export const VISUAL_STATUS_TONE: Record<VisualEvidenceStatus, BadgeTone> = {
  stored: "neutral",
  analyzing: "accent",
  analyzed: "success",
  failed: "danger",
};

export const SEVERITY_HINT_LABELS: Record<SeverityHint, string> = {
  informational: "Informational",
  attention: "Attention",
  urgent: "Urgent",
};

export const SEVERITY_HINT_TONE: Record<SeverityHint, BadgeTone> = {
  informational: "neutral",
  attention: "warning",
  urgent: "danger",
};