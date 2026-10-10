import type {
  DatasetSummary,
  HealthStatus,
  TelemetryRecord,
  TelemetryResponse,
} from "@/types/monitoring";

const DEFAULT_API_URL = "http://127.0.0.1:8000";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL
).replace(/\/+$/, "");

export type ApiErrorKind = "network" | "http" | "invalid";

export class ApiError extends Error {
  readonly status?: number;
  readonly kind: ApiErrorKind;

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
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
    throw new ApiError(
      `The backend responded with HTTP ${response.status} ${response.statusText}.`,
      "http",
      response.status
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