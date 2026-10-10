import type {
  DatasetSummary,
  HealthStatus,
  TelemetryRecord,
  TelemetryResponse,
} from "@/types/monitoring";
import type {
  AnomalyDetail,
  AnomalyListResponse,
  AnomalySummary,
  EvaluationReport,
  IncidentStatus,
  Severity,
} from "@/types/anomaly";
import type {
  Incident,
  IncidentListResponse,
  ScanRequest,
  ScanResponse,
} from "@/types/incident";
import type {
  EvidenceListResponse,
  InvestigationJob,
  InvestigationListPage,
  InvestigationListResponse,
  InvestigationStartResponse,
  InvestigationStatus,
} from "@/types/investigation";

const DEFAULT_API_URL = "http://127.0.0.1:8000";

function removeTrailingSlashes(url: string): string {
  let end = url.length;
  while (end > 0 && url[end - 1] === "/") end -= 1;
  return url.slice(0, end);
}

export const API_BASE_URL = removeTrailingSlashes(
  process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL
);

export type ApiErrorKind = "network" | "http" | "invalid";

export class ApiError extends Error {
  readonly status?: number;
  readonly kind: ApiErrorKind;
  readonly detail?: unknown;

  constructor(
    message: string,
    kind: ApiErrorKind,
    status?: number,
    detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

function extractMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return fallback;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the FactoryMind AI backend at ${API_BASE_URL}. Start the FastAPI server and try again.`,
      "network"
    );
  }

  if (!response.ok) {
    let detail: unknown;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = body?.detail;
    } catch {
      detail = undefined;
    }
    const fallback = `The backend responded with HTTP ${response.status} ${response.statusText}.`;
    throw new ApiError(
      extractMessage(detail, fallback),
      "http",
      response.status,
      detail
    );
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(
      "The backend returned a response that could not be parsed.",
      "invalid",
      response.status
    );
  }
}

export const getHealth = () => apiFetch<HealthStatus>("/health");

export const getDatasetSummary = () =>
  apiFetch<DatasetSummary>("/api/dataset/summary");

export interface TelemetryQuery {
  limit?: number;
  offset?: number;
  failureOnly?: boolean;
  normalOnly?: boolean;
  recordId?: number | null;
}

export function getTelemetry({
  limit = 25,
  offset = 0,
  failureOnly = false,
  normalOnly = false,
  recordId = null,
}: TelemetryQuery = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (failureOnly) params.set("failure_only", "true");
  if (normalOnly) params.set("normal_only", "true");
  if (recordId != null && recordId > 0) params.set("record_id", String(recordId));
  return apiFetch<TelemetryResponse>(`/api/telemetry?${params.toString()}`);
}

export const getTelemetryRecord = (recordId: number) =>
  apiFetch<TelemetryRecord>(`/api/telemetry/${recordId}`);

export const getAnomalySummary = () =>
  apiFetch<AnomalySummary>("/api/anomalies/summary");

export const getEvaluationReport = () =>
  apiFetch<EvaluationReport>("/api/anomalies/evaluation");

export interface AnomalyQuery {
  limit?: number;
  offset?: number;
  severity?: Severity | null;
  minSeverity?: Exclude<Severity, "normal"> | null;
  machineType?: string | null;
}

export function getAnomalies({
  limit = 20,
  offset = 0,
  severity = null,
  minSeverity = null,
  machineType = null,
}: AnomalyQuery = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (severity) params.set("severity", severity);
  if (minSeverity) params.set("min_severity", minSeverity);
  if (machineType) params.set("machine_type", machineType);
  return apiFetch<AnomalyListResponse>(`/api/anomalies?${params.toString()}`);
}

export const getAnomaly = (recordId: number) =>
  apiFetch<AnomalyDetail>(`/api/anomalies/${recordId}`);

export interface IncidentQuery {
  limit?: number;
  offset?: number;
  status?: IncidentStatus | null;
  severity?: Severity | null;
}

export function getIncidents({
  limit = 20,
  offset = 0,
  status = null,
  severity = null,
}: IncidentQuery = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (status) params.set("status", status);
  if (severity) params.set("severity", severity);
  return apiFetch<IncidentListResponse>(`/api/incidents?${params.toString()}`);
}

export const getIncident = (incidentId: string) =>
  apiFetch<Incident>(`/api/incidents/${encodeURIComponent(incidentId)}`);

export const createIncident = (recordId: number, note?: string) =>
  apiFetch<Incident>("/api/incidents", {
    method: "POST",
    body: JSON.stringify({ record_id: recordId, note: note ?? null }),
  });

export const updateIncidentStatus = (
  incidentId: string,
  status: IncidentStatus,
  note?: string
) =>
  apiFetch<Incident>(
    `/api/incidents/${encodeURIComponent(incidentId)}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status, note: note ?? null }),
    }
  );

export const scanIncidents = (payload: ScanRequest) =>
  apiFetch<ScanResponse>("/api/incidents/scan", {
    method: "POST",
    body: JSON.stringify({
      min_severity: payload.min_severity,
      max_incidents: payload.max_incidents ?? 25,
      dry_run: payload.dry_run ?? false,
    }),
  });

export interface InvestigationQuery {
  limit?: number;
  offset?: number;
  status?: InvestigationStatus | null;
}

export function getInvestigations({
  limit = 20,
  offset = 0,
  status = null,
}: InvestigationQuery = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (status) params.set("status", status);
  return apiFetch<InvestigationListPage>(`/api/investigations?${params.toString()}`);
}

export const getInvestigation = (investigationId: string) =>
  apiFetch<InvestigationJob>(
    `/api/investigations/${encodeURIComponent(investigationId)}`
  );

export const getIncidentInvestigations = (
  incidentId: string,
  { limit = 20, offset = 0 }: { limit?: number; offset?: number } = {}
) => {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return apiFetch<InvestigationListResponse>(
    `/api/incidents/${encodeURIComponent(incidentId)}/investigations?${params.toString()}`
  );
};

export const startInvestigation = (incidentId: string) =>
  apiFetch<InvestigationStartResponse>(
    `/api/incidents/${encodeURIComponent(incidentId)}/investigate`,
    { method: "POST" }
  );

export const getInvestigationEvidence = (investigationId: string) =>
  apiFetch<EvidenceListResponse>(
    `/api/investigations/${encodeURIComponent(investigationId)}/evidence`
  );
