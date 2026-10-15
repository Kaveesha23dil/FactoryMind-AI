export interface SettingsInfo {
 workspace: { workspace: string; application: string; team: string; environment: string };
 ai: { provider: string; model: string; enabled: boolean; credentials_configured: boolean; timeout_seconds: number; max_retries: number; max_concurrent_requests: number; max_concurrent_investigations: number | null; max_model_calls_per_agent: number; cache_enabled: boolean; cooldown_until: string | null; latest_error_category: string | null; last_success_at: string | null; usage: { requests: number | null; input_tokens: number | null; output_tokens: number | null; scope: string } };
 anomaly: { algorithm: string; threshold: number; feature_z_threshold: number; severity_bands: Record<string, (number | null)[]>; train_count: number; validation_count: number; test_count: number; split_seed: number; last_evaluation_at: string | null };
 data: { name: string; origin: string; classification: string; records: number; version: string; last_refresh_at: string | null; database_provider: string; image_provider: string; document_count: number; passage_count: number; document_status: string; storage_usage_bytes: number | null };
 security: { authentication: string; role: string | null; session: string; access_management: string; operational_settings: string };
}
export interface SystemInfo { application_version: string; api_status: string; database_status: string; image_storage_status: string; gemini_status: string; environment: string; checked_at: string }
