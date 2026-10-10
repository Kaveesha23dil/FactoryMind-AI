import type { BadgeTone } from "@/components/ui/StatusBadge";
import type { IncidentStatus, Severity } from "@/types/anomaly";

export const SEVERITY_ORDER: Severity[] = [
  "normal",
  "low",
  "medium",
  "high",
  "critical",
];

export const SEVERITY_LABELS: Record<Severity, string> = {
  normal: "Normal",
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export const SEVERITY_TONE: Record<Severity, BadgeTone> = {
  normal: "success",
  low: "accent",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

export const SEVERITY_COLOR: Record<Severity, string> = {
  normal: "#10B981",
  low: "#38BDF8",
  medium: "#F59E0B",
  high: "#EF4444",
  critical: "#B91C1C",
};

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Open",
  under_review: "Under Review",
  resolved: "Resolved",
};

export const INCIDENT_STATUS_TONE: Record<IncidentStatus, BadgeTone> = {
  open: "danger",
  under_review: "warning",
  resolved: "success",
};

export const INCIDENT_ALLOWED_TRANSITIONS: Record<
  IncidentStatus,
  IncidentStatus[]
> = {
  open: ["under_review", "resolved"],
  under_review: ["resolved", "open"],
  resolved: ["under_review"],
};

export function featureLabel(key: string | null): string {
  if (!key) return "—";
  return key
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
