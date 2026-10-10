import type { BadgeTone } from "@/components/ui/StatusBadge";
import type {
  AgentStatus,
  EvidenceType,
  HypothesisAssessment,
  InvestigationStatus,
} from "@/types/investigation";

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