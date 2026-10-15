"""Explicit allowlisted settings responses. Never serialize the environment dataclass."""
from pydantic import BaseModel, ConfigDict


class SafeModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class WorkspaceInfo(SafeModel):
    workspace: str
    application: str
    team: str
    environment: str


class UsageInfo(SafeModel):
    requests: int | None
    input_tokens: int | None
    output_tokens: int | None
    scope: str


class AIInfo(SafeModel):
    provider: str
    model: str
    enabled: bool
    credentials_configured: bool
    timeout_seconds: float
    max_retries: int
    max_concurrent_requests: int
    max_concurrent_investigations: int | None
    max_model_calls_per_agent: int
    cache_enabled: bool
    cooldown_until: str | None
    latest_error_category: str | None
    last_success_at: str | None
    usage: UsageInfo


class AnomalyInfo(SafeModel):
    algorithm: str
    threshold: float
    feature_z_threshold: float
    severity_bands: dict[str, list[float | None]]
    train_count: int
    validation_count: int
    test_count: int
    split_seed: int
    last_evaluation_at: str | None


class DataInfo(SafeModel):
    name: str
    origin: str
    classification: str
    records: int
    version: str
    last_refresh_at: str | None
    database_provider: str
    image_provider: str
    document_count: int
    passage_count: int
    document_status: str
    storage_usage_bytes: int | None


class SecurityInfo(SafeModel):
    authentication: str
    role: str | None
    session: str
    access_management: str
    operational_settings: str


class SettingsResponse(SafeModel):
    workspace: WorkspaceInfo
    ai: AIInfo
    anomaly: AnomalyInfo
    data: DataInfo
    security: SecurityInfo


class SystemResponse(SafeModel):
    application_version: str
    api_status: str
    database_status: str
    image_storage_status: str
    gemini_status: str
    environment: str
    checked_at: str
