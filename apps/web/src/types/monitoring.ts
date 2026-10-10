export type FailureCode = "TWF" | "HDF" | "PWF" | "OSF" | "RNF";

export interface FailureCategory {
  code: FailureCode;
  label: string;
  count: number;
}

export interface MachineTypeCount {
  type: string;
  count: number;
}

export interface DatasetSummary {
  dataset: string;
  source: string;
  record_count: number;
  normal_count: number;
  failure_count: number;
  failure_rate: number;
  failure_categories: FailureCategory[];
  machine_types: MachineTypeCount[];
}

export interface FailureFlags {
  TWF: number;
  HDF: number;
  PWF: number;
  OSF: number;
  RNF: number;
}

export interface TelemetryRecord {
  record_id: number;
  product_id: string;
  machine_type: string;
  air_temperature_k: number;
  air_temperature_c: number;
  process_temperature_k: number;
  process_temperature_c: number;
  rotational_speed_rpm: number;
  torque_nm: number;
  tool_wear_min: number;
  machine_failure: boolean;
  failure_flags: FailureFlags;
  failure_types: FailureCode[];
}

export interface TelemetryResponse {
  dataset: string;
  source: string;
  total: number;
  limit: number;
  offset: number;
  returned: number;
  records: TelemetryRecord[];
}

export interface HealthStatus {
  status: string;
  project: string;
  version: string;
  dataset: string;
  records: number;
}

export type BackendStatus = "checking" | "connected" | "unavailable";