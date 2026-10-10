"""Central configuration for the FactoryMind AI API.

All tunable values (dataset paths, thresholds, split ratios, database
location, CORS origins) live here so they can be adjusted without touching
business logic. Values can be overridden with environment variables.
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]

# Load backend-only secrets from services/api/.env when present. Existing
# environment variables always win, so deployment configuration is not
# overwritten. Secrets are never exposed to the frontend.
try:  # pragma: no cover - environment dependent
    from dotenv import load_dotenv

    load_dotenv(API_ROOT / ".env", override=False)
except Exception:  # pragma: no cover - dotenv is optional
    pass

DEFAULT_DATASET_PATH = REPO_ROOT / "datasets" / "telemetry" / "ai4i2020.csv"
DEFAULT_DB_PATH = API_ROOT / "data" / "incidents.db"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a finite positive number") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --- Dataset metadata -------------------------------------------------------

DATASET_NAME = "AI4I 2020 Predictive Maintenance Dataset"
DATASET_SOURCE = "AI4I 2020 - Synthetic Dataset"

FAILURE_CATEGORY_COLUMNS = ["TWF", "HDF", "PWF", "OSF", "RNF"]

FAILURE_CATEGORY_LABELS = {
    "TWF": "Tool Wear Failure",
    "HDF": "Heat Dissipation Failure",
    "PWF": "Power Failure",
    "OSF": "Overstrain Failure",
    "RNF": "Random Failure",
}

# Ground-truth columns. These are ONLY used by the evaluation service and
# must never feed the anomaly detector.
GROUND_TRUTH_COLUMNS = ["Machine failure", *FAILURE_CATEGORY_COLUMNS]


# --- Anomaly detection ------------------------------------------------------

ALGORITHM_VERSION = "robust_zscore_v1"

#: Feature definitions used by the detector. ``column`` refers to the raw CSV
#: column, ``transform`` converts it into the modelling unit. Ground-truth
#: columns are deliberately absent.
FEATURE_DEFINITIONS = [
    {
        "key": "air_temperature_c",
        "columns": ["Air temperature [K]"],
        "label": "Air temperature",
        "unit": "\u00b0C",
        "transform": "kelvin_to_celsius",
        "description": "Ambient air temperature at the machine.",
    },
    {
        "key": "process_temperature_c",
        "columns": ["Process temperature [K]"],
        "label": "Process temperature",
        "unit": "\u00b0C",
        "transform": "kelvin_to_celsius",
        "description": "Temperature of the running process.",
    },
    {
        "key": "temperature_difference_c",
        "columns": ["Process temperature [K]", "Air temperature [K]"],
        "label": "Process/air temperature difference",
        "unit": "\u00b0C",
        "transform": "temperature_difference",
        "description": "Process temperature minus air temperature.",
    },
    {
        "key": "rotational_speed_rpm",
        "columns": ["Rotational speed [rpm]"],
        "label": "Rotational speed",
        "unit": "rpm",
        "transform": "identity",
        "description": "Spindle rotational speed.",
    },
    {
        "key": "torque_nm",
        "columns": ["Torque [Nm]"],
        "label": "Torque",
        "unit": "Nm",
        "transform": "identity",
        "description": "Torque applied during the process.",
    },
    {
        "key": "mechanical_power_w",
        "columns": ["Torque [Nm]", "Rotational speed [rpm]"],
        "label": "Mechanical power",
        "unit": "W",
        "transform": "mechanical_power",
        "description": "Mechanical power derived from torque and rotational speed.",
    },
    {
        "key": "tool_wear_min",
        "columns": ["Tool wear [min]"],
        "label": "Tool wear",
        "unit": "min",
        "transform": "identity",
        "description": "Accumulated tool wear.",
    },
]

FEATURE_KEYS = [feature["key"] for feature in FEATURE_DEFINITIONS]
FEATURE_LABELS = {f["key"]: f["label"] for f in FEATURE_DEFINITIONS}
FEATURE_UNITS = {f["key"]: f["unit"] for f in FEATURE_DEFINITIONS}

MACHINE_TYPES = ["L", "M", "H"]

#: Minimum number of training samples required before a per-machine-type
#: baseline is used instead of the global baseline (documented fallback).
MIN_GROUP_SIZE = 200

#: MAD is scaled by this factor to make it a consistent estimator of the
#: standard deviation under normality.
MAD_SCALE = 1.4826

#: Per-feature robust z-score above which a feature is reported as anomalous.
FEATURE_Z_THRESHOLD = _env_float("FACTORYMIND_FEATURE_Z_THRESHOLD", 3.0)

#: Overall anomaly-score threshold. Values at or above this count as an
#: anomaly. The validation-split optimum is ~4.04 (see the evaluation
#: report); it is rounded to 4.0 here so the severity bands align to clean
#: multiples. It was never tuned on the final test split.
ANOMALY_SCORE_THRESHOLD = _env_float("FACTORYMIND_ANOMALY_SCORE_THRESHOLD", 4.0)

#: Severity is derived from multiples of the overall threshold:
#:   [T, 1.25T) -> low, [1.25T, 1.5T) -> medium,
#:   [1.5T, 2T) -> high, [2T, inf) -> critical.
SEVERITY_MULTIPLIERS = {
    "low": (1.0, 1.25),
    "medium": (1.25, 1.5),
    "high": (1.5, 2.0),
    "critical": (2.0, None),
}

SEVERITY_ORDER = ["normal", "low", "medium", "high", "critical"]

#: Maximum number of feature contributions returned per record.
MAX_FEATURE_CONTRIBUTIONS = 5

#: Guard used when a feature has zero dispersion (MAD == 0).
DEGENERATE_SCALE_EPSILON = 1e-6

#: Hard clamp on the absolute robust z-score so a degenerate scale can never
#: produce an infinite JSON value.
MAX_ABS_ZSCORE = 50.0


# --- Train / validation / test split ---------------------------------------

RANDOM_SEED = _env_int("FACTORYMIND_RANDOM_SEED", 42)
TRAIN_FRACTION = 0.6
VALIDATION_FRACTION = 0.2
TEST_FRACTION = 0.2


# --- Incident management ----------------------------------------------------

INCIDENT_ID_PREFIX = "INC-"

#: Permitted incident status transitions.
INCIDENT_TRANSITIONS = {
    "open": ["under_review", "resolved"],
    "under_review": ["resolved", "open"],
    "resolved": ["under_review"],
}

INCIDENT_STATUSES = ["open", "under_review", "resolved"]

#: Statuses that count as "active" for duplicate prevention.
ACTIVE_INCIDENT_STATUSES = ["open", "under_review"]

#: Explicit scan guard so a scan never floods the store with incidents.
SCAN_DEFAULT_MAX_INCIDENTS = _env_int("FACTORYMIND_SCAN_MAX_INCIDENTS", 25)
SCAN_MAX_INCIDENTS_LIMIT = 200


# --- AI investigation (Step 4) ---------------------------------------------

INVESTIGATION_ID_PREFIX = "INV-"

#: Coarse job lifecycle used by the API and the worker queue.
INVESTIGATION_STATUSES = ["queued", "running", "completed", "failed"]

#: Fine-grained progress stages reported to the frontend. The value is the
#: stable machine key; the frontend owns the human-readable labels.
INVESTIGATION_STAGES = [
    "queued",
    "collecting_evidence",
    "analyzing_measurements",
    "retrieving_knowledge",
    "generating_hypotheses",
    "verifying_conclusions",
    "completed",
    "failed",
]

#: Logical agents executed by the orchestrator, in pipeline order.
INVESTIGATION_AGENTS = [
    "sensor_agent",
    "knowledge_agent",
    "investigation_agent",
    "critic_agent",
]

#: Evidence ID prefixes. IDs are deterministic within an investigation so they
#: are stable across revisions and can be cited safely.
EVIDENCE_TYPE_PREFIXES = {
    "sensor_measurement": "EV-SENSOR",
    "baseline_statistic": "EV-BASELINE",
    "anomaly_finding": "EV-ANOMALY",
    "source_metadata": "EV-SOURCE",
    "manual_passage": "EV-MANUAL",
}

#: Provider used by the investigation runtime: ``google`` (Gemini / ADK) or
#: ``scripted`` (deterministic responses used only by automated tests).
AI_PROVIDERS = ["google", "scripted"]

#: Number of knowledge-base passages retrieved for the Knowledge Agent.
KNOWLEDGE_TOP_K = _env_int("FACTORYMIND_KNOWLEDGE_TOP_K", 5)

#: Hard bounds so a single investigation can never run unbounded.
MAX_INVESTIGATION_ATTEMPTS = 3


@dataclass(frozen=True)
class Settings:
    dataset_path: Path = field(default_factory=lambda: Path(
        os.environ.get("FACTORYMIND_DATASET_PATH", str(DEFAULT_DATASET_PATH))
    ))
    database_path: Path = field(default_factory=lambda: Path(
        os.environ.get("FACTORYMIND_DB_PATH", str(DEFAULT_DB_PATH))
    ))
    cors_origins: list[str] = field(default_factory=lambda: _env_list(
        "FACTORYMIND_CORS_ORIGINS",
        ["http://localhost:3000", "http://127.0.0.1:3000"],
    ))
    log_level: str = field(default_factory=lambda: os.environ.get(
        "FACTORYMIND_LOG_LEVEL", "INFO"
    ))

    # -- AI investigation -------------------------------------------------
    ai_provider: str = field(default_factory=lambda: (
        os.environ.get("AI_PROVIDER", "google").strip().lower() or "google"
    ))
    gemini_model: str = field(default_factory=lambda: (
        os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
        or "gemini-2.5-flash"
    ))
    google_api_key: str | None = field(default_factory=lambda: (
        os.environ.get("GOOGLE_API_KEY") or None
    ))
    use_vertex_ai: bool = field(default_factory=lambda: _env_bool(
        "GOOGLE_GENAI_USE_VERTEXAI", False
    ))
    gcp_project: str | None = field(default_factory=lambda: (
        os.environ.get("GOOGLE_CLOUD_PROJECT") or None
    ))
    gcp_location: str | None = field(default_factory=lambda: (
        os.environ.get("GOOGLE_CLOUD_LOCATION") or None
    ))
    ai_investigation_enabled: bool = field(default_factory=lambda: _env_bool(
        "AI_INVESTIGATION_ENABLED", True
    ))
    investigation_timeout_seconds: float = field(default_factory=lambda: _env_float(
        "FACTORYMIND_INVESTIGATION_TIMEOUT_SECONDS", 90.0
    ))
    investigation_max_retries: int = field(default_factory=lambda: _env_int(
        "FACTORYMIND_INVESTIGATION_MAX_RETRIES", 1
    ))
    investigation_max_hypotheses: int = field(default_factory=lambda: _env_int(
        "FACTORYMIND_INVESTIGATION_MAX_HYPOTHESES", 4
    ))
    investigation_async: bool = field(default_factory=lambda: _env_bool(
        "FACTORYMIND_INVESTIGATION_ASYNC", True
    ))
    worker_secret: str | None = field(default_factory=lambda: (
        os.environ.get("FACTORYMIND_WORKER_SECRET") or None
    ))


settings = Settings()
