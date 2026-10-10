"""Deterministic, explainable anomaly detection.

Algorithm: robust z-score (``robust_zscore_v1``).

For each physical sensor feature we compute the training-set median and the
median absolute deviation (MAD). The MAD is scaled by 1.4826 so it estimates
the standard deviation under normality, and the robust z-score is::

    z = (observed - median) / (1.4826 * MAD)

The overall anomaly score is the Euclidean norm of the per-feature robust
z-scores, which is a diagonal (independence-assuming) robust multivariate
outlier score. Larger scores mean the observation is further from the
training baseline.

Design notes
------------
* Ground-truth failure labels are never accepted as input.
* MAD == 0 is handled with a documented fallback chain.
* Non-finite or missing features raise ``ValueError`` rather than silently
  producing a score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from services.api.core import config


@dataclass
class BaselineStats:
    count: int
    median: float
    mad: float
    scale: float
    mean: float
    std: float
    degenerate: bool

    def to_dict(self) -> dict:
        return asdict(self)


class RobustZScoreDetector:
    """Robust z-score anomaly detector with per-machine-type baselines."""

    algorithm = config.ALGORITHM_VERSION

    def __init__(
        self,
        feature_keys: list[str] | None = None,
        feature_z_threshold: float | None = None,
        anomaly_score_threshold: float | None = None,
        min_group_size: int | None = None,
    ) -> None:
        self.feature_keys = list(feature_keys or config.FEATURE_KEYS)
        self.feature_z_threshold = (
            config.FEATURE_Z_THRESHOLD
            if feature_z_threshold is None
            else feature_z_threshold
        )
        self.anomaly_score_threshold = (
            config.ANOMALY_SCORE_THRESHOLD
            if anomaly_score_threshold is None
            else anomaly_score_threshold
        )
        self.min_group_size = config.MIN_GROUP_SIZE if min_group_size is None else min_group_size
        self.global_baselines: dict[str, BaselineStats] = {}
        self.group_baselines: dict[str, dict[str, BaselineStats]] = {}
        self._fitted = False

    # -- fitting ---------------------------------------------------------

    @staticmethod
    def _compute_stats(values: np.ndarray) -> BaselineStats:
        finite = values[np.isfinite(values)]
        count = int(finite.size)
        if count == 0:
            return BaselineStats(0, 0.0, 0.0, config.DEGENERATE_SCALE_EPSILON, 0.0, 0.0, True)

        median = float(np.median(finite))
        mad = float(np.median(np.abs(finite - median)))
        scale = mad * config.MAD_SCALE
        degenerate = False

        if scale <= config.DEGENERATE_SCALE_EPSILON:
            mean_abs_dev = float(np.mean(np.abs(finite - median)))
            scale = mean_abs_dev
        if scale <= config.DEGENERATE_SCALE_EPSILON:
            scale = float(np.std(finite))
        if scale <= config.DEGENERATE_SCALE_EPSILON:
            scale = config.DEGENERATE_SCALE_EPSILON
            degenerate = True

        return BaselineStats(
            count=count,
            median=median,
            mad=mad,
            scale=scale,
            mean=float(np.mean(finite)),
            std=float(np.std(finite)),
            degenerate=degenerate,
        )

    def fit(self, frame) -> "RobustZScoreDetector":
        """Fit baselines from a training frame only."""
        from services.api import data

        feature_rows = [data.extract_features(row) for _, row in frame.iterrows()]

        self.global_baselines = {}
        for key in self.feature_keys:
            values = np.asarray([row[key] for row in feature_rows], dtype=float)
            self.global_baselines[key] = self._compute_stats(values)

        # Per-machine-type baselines when enough data exists.
        self.group_baselines = {}
        if "Type" in frame.columns:
            types = np.asarray(frame["Type"].astype(str).tolist())
            for machine_type in np.unique(types):
                mask = types == machine_type
                if int(mask.sum()) < self.min_group_size:
                    continue
                baseline: dict[str, BaselineStats] = {}
                for key in self.feature_keys:
                    values = np.asarray(
                        [row[key] for row, keep in zip(feature_rows, mask) if keep],
                        dtype=float,
                    )
                    baseline[key] = self._compute_stats(values)
                self.group_baselines[str(machine_type)] = baseline

        self._fitted = True
        return self

    def _baseline_for(self, machine_type: str | None, key: str) -> BaselineStats:
        global_stats = self.global_baselines[key]
        if machine_type and machine_type in self.group_baselines:
            group_stats = self.group_baselines[machine_type][key]
            # Fall back to the global baseline if the group is degenerate.
            if not group_stats.degenerate:
                return group_stats
        return global_stats

    # -- scoring ---------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def _validate_features(self, features: dict) -> None:
        missing = [key for key in self.feature_keys if key not in features]
        if missing:
            raise ValueError(f"Missing required features: {', '.join(missing)}")
        for key in self.feature_keys:
            value = features[key]
            if value is None:
                raise ValueError(f"Feature '{key}' is null")
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Feature '{key}' is not numeric") from exc
            if not math.isfinite(numeric):
                raise ValueError(f"Feature '{key}' is not finite")

    def score(self, features: dict, machine_type: str | None = None) -> dict:
        if not self._fitted:
            raise RuntimeError("Detector must be fit before scoring")
        self._validate_features(features)

        contributions: list[dict] = []
        sum_squares = 0.0

        for key in self.feature_keys:
            observed = float(features[key])
            stats = self._baseline_for(machine_type, key)
            finite_observed = observed if math.isfinite(observed) else stats.median
            raw_z = (finite_observed - stats.median) / stats.scale
            if not math.isfinite(raw_z):
                raw_z = config.MAX_ABS_ZSCORE if finite_observed > stats.median else 0.0
            z = float(max(-config.MAX_ABS_ZSCORE, min(config.MAX_ABS_ZSCORE, raw_z)))
            abs_z = abs(z)
            sum_squares += z * z

            is_anomalous = abs_z >= self.feature_z_threshold
            direction = "high" if z >= 0 else "low"
            label = config.FEATURE_LABELS.get(key, key)
            unit = config.FEATURE_UNITS.get(key, "")
            if is_anomalous:
                explanation = (
                    f"{label} is unusually {direction} "
                    f"({observed:.2f}{unit}) versus the training baseline "
                    f"(median {stats.median:.2f}{unit})."
                )
            else:
                explanation = (
                    f"{label} is within the expected range around the "
                    f"training median ({stats.median:.2f}{unit})."
                )

            contributions.append(
                {
                    "feature": key,
                    "label": label,
                    "unit": unit,
                    "observed_value": round(observed, 4),
                    "baseline_median": round(stats.median, 4),
                    "baseline_scale": round(stats.scale, 4),
                    "baseline_mad": round(stats.mad, 4),
                    "robust_zscore": round(z, 4),
                    "abs_zscore": round(abs_z, 4),
                    "direction": direction,
                    "is_anomalous": is_anomalous,
                    "baseline_scope": (
                        "machine_type"
                        if machine_type in self.group_baselines
                        and not self.group_baselines[machine_type][key].degenerate
                        else "global"
                    ),
                    "explanation": explanation,
                }
            )

        anomaly_score = float(math.sqrt(sum_squares))
        severity = self._severity_for(anomaly_score)
        anomalous_features = sorted(
            [c for c in contributions if c["is_anomalous"]],
            key=lambda c: c["abs_zscore"],
            reverse=True,
        )[: config.MAX_FEATURE_CONTRIBUTIONS]

        return {
            "algorithm": self.algorithm,
            "anomaly_score": round(anomaly_score, 4),
            "severity": severity,
            "is_anomaly": anomaly_score >= self.anomaly_score_threshold,
            "threshold": self.anomaly_score_threshold,
            "feature_z_threshold": self.feature_z_threshold,
            "anomalous_features": anomalous_features,
            "features": sorted(contributions, key=lambda c: c["abs_zscore"], reverse=True),
            "ground_truth_used_for_detection": False,
        }

    def _severity_for(self, score: float) -> str:
        threshold = self.anomaly_score_threshold
        if score < threshold:
            return "normal"
        for severity in ["low", "medium", "high"]:
            lower, upper = config.SEVERITY_MULTIPLIERS[severity]
            if threshold * lower <= score < threshold * upper:
                return severity
        return "critical"
