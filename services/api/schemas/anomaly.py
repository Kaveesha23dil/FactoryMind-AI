"""Pydantic schemas for anomaly endpoints.

``allow_inf_nan=False`` guarantees that NaN / Infinity can never be serialized
into a JSON response.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FeatureContribution(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    feature: str
    label: str
    unit: str
    observed_value: float
    baseline_median: float
    baseline_scale: float
    baseline_mad: float
    robust_zscore: float
    abs_zscore: float
    direction: str
    is_anomalous: bool
    baseline_scope: str
    explanation: str


class BaselineStatsSchema(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    count: int
    median: float
    mad: float
    scale: float
    mean: float
    std: float
    degenerate: bool


class AnomalyDetail(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    record_id: int
    product_id: str
    machine_type: str
    algorithm: str
    anomaly_score: float
    severity: str
    is_anomaly: bool
    threshold: float
    feature_z_threshold: float
    anomalous_features: list[FeatureContribution]
    features: list[FeatureContribution]
    ground_truth_failure: bool = Field(
        description="Dataset ground-truth label, shown for historical comparison only."
    )
    ground_truth_failure_types: list[str]
    ground_truth_used_for_detection: bool = False


class AnomalyListItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    record_id: int
    machine_type: str
    product_id: str
    algorithm: str
    anomaly_score: float
    severity: str
    is_anomaly: bool
    main_anomalous_feature: str | None
    anomalous_feature_count: int
    ground_truth_failure: bool
    ground_truth_failure_types: list[str]
    ground_truth_used_for_detection: bool = False


class AnomalyListResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    algorithm: str
    threshold: float
    total: int
    limit: int
    offset: int
    returned: int
    records: list[AnomalyListItem]


class AnomalySummary(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    algorithm: str
    analyzed_sample_count: int
    detected_anomaly_count: int
    anomaly_rate: float
    severity_distribution: dict[str, int]
    threshold: float
    feature_z_threshold: float
    baseline_fit_sample_count: int
    feature_baselines: dict[str, BaselineStatsSchema]
    ground_truth_used_for_detection: bool = False
