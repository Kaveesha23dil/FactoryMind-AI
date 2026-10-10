"""Anomaly engine: fits the detector once, precomputes scores, caches them.

The engine is the single source of truth for anomaly results used by the
API. Scores for every dataset observation are computed once (at startup) and
served from memory, satisfying the "avoid costly per-request calculation"
requirement. The detector is fit only on the training split.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from services.api import data
from services.api.core import config
from services.api.services.anomaly_detector import RobustZScoreDetector

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {name: index for index, name in enumerate(config.SEVERITY_ORDER)}


def severity_at_least(severity: str, minimum: str) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(minimum, 0)


class AnomalyEngine:
    def __init__(self) -> None:
        self.detector = RobustZScoreDetector()
        self.train_frame = None
        self.validation_frame = None
        self.test_frame = None
        self._results: dict[int, dict] = {}
        self._anomalies: list[dict] = []
        self._severity_counts: dict[str, int] = {}
        self._score_histogram: list[dict] = []
        self._score_stats: dict = {}
        self._built = False

    # -- lifecycle -------------------------------------------------------

    def build(self) -> "AnomalyEngine":
        if self._built:
            return self

        self.train_frame, self.validation_frame, self.test_frame = data.split_dataset()
        self.detector.fit(self.train_frame)

        results: dict[int, dict] = {}
        anomalies: list[dict] = []
        severity_counts = dict.fromkeys(config.SEVERITY_ORDER, 0)
        all_scores: list[float] = []

        for _, row in data.get_dataset().iterrows():
            record_id = int(row["UDI"])
            features = data.extract_features(row)
            machine_type = data.machine_type_of(row)
            result = self.detector.score(features, machine_type)
            result["record_id"] = record_id
            result["machine_type"] = machine_type
            result["product_id"] = str(row["Product ID"])
            # Ground-truth labels are attached ONLY for clearly-labelled
            # historical comparison. The detector never consumes them.
            result["ground_truth_failure"] = bool(int(row["Machine failure"]))
            result["ground_truth_failure_types"] = [
                name for name in config.FAILURE_CATEGORY_COLUMNS if int(row[name]) == 1
            ]
            results[record_id] = result
            severity_counts[result["severity"]] += 1
            all_scores.append(result["anomaly_score"])
            if result["is_anomaly"]:
                anomalies.append(result)

        anomalies.sort(key=lambda item: item["anomaly_score"], reverse=True)
        self._results = results
        self._anomalies = anomalies
        self._severity_counts = severity_counts
        self._score_histogram, self._score_stats = self._build_score_distribution(
            np.asarray(all_scores, dtype=float), threshold=self.detector.anomaly_score_threshold
        )
        self._built = True
        logger.info(
            "Anomaly engine built: %d observations, %d anomalies, threshold=%.3f",
            len(results),
            len(anomalies),
            self.detector.anomaly_score_threshold,
        )
        return self

    @property
    def is_built(self) -> bool:
        return self._built

    @staticmethod
    def _build_score_distribution(scores: np.ndarray, bins: int = 20, threshold: float | None = None):
        if scores.size == 0:
            return [], {}
        upper = float(scores.max())
        if upper <= 0:
            upper = 1.0
        edges = np.linspace(0.0, upper, bins + 1)
        if threshold is not None and 0 < threshold < upper:
            nearest = int(np.argmin(np.abs(edges[1:-1] - threshold))) + 1
            edges[nearest] = threshold
            edges.sort()
        counts, _ = np.histogram(scores, bins=edges)
        histogram = [
            {
                "bin_start": round(float(edges[i]), 4),
                "bin_end": round(float(edges[i + 1]), 4),
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]
        stats = {
            "min": round(float(scores.min()), 4),
            "median": round(float(np.median(scores)), 4),
            "mean": round(float(scores.mean()), 4),
            "max": round(upper, 4),
            "p95": round(float(np.percentile(scores, 95)), 4),
        }
        return histogram, stats

    # -- queries ---------------------------------------------------------

    def summary(self) -> dict:
        self.build()
        return {
            "algorithm": self.detector.algorithm,
            "analyzed_sample_count": len(self._results),
            "detected_anomaly_count": len(self._anomalies),
            "anomaly_rate": round(len(self._anomalies) / len(self._results), 4)
            if self._results
            else 0.0,
            "severity_distribution": dict(self._severity_counts),
            "threshold": self.detector.anomaly_score_threshold,
            "feature_z_threshold": self.detector.feature_z_threshold,
            "baseline_fit_sample_count": int(len(self.train_frame)),
            "feature_baselines": {
                key: stats.to_dict()
                for key, stats in self.detector.global_baselines.items()
            },
            "score_histogram": self._score_histogram,
            "score_stats": self._score_stats,
            "ground_truth_used_for_detection": False,
        }

    def get(self, record_id: int) -> dict | None:
        self.build()
        return self._results.get(int(record_id))

    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        severity: str | None = None,
        machine_type: str | None = None,
        min_severity: str | None = None,
    ) -> dict:
        self.build()
        items = self._anomalies

        if severity:
            items = [item for item in items if item["severity"] == severity]
        if min_severity:
            items = [
                item for item in items if severity_at_least(item["severity"], min_severity)
            ]
        if machine_type:
            items = [item for item in items if item["machine_type"] == machine_type.upper()]

        total = len(items)
        window = items[offset : offset + limit]
        records = [self._anomaly_view(item) for item in window]
        return {
            "algorithm": self.detector.algorithm,
            "threshold": self.detector.anomaly_score_threshold,
            "total": total,
            "limit": limit,
            "offset": offset,
            "returned": len(records),
            "records": records,
        }

    def scan_candidates(
        self, min_severity: str = "high", max_incidents: int = 25
    ) -> list[dict]:
        self.build()
        candidates = [
            item
            for item in self._anomalies
            if severity_at_least(item["severity"], min_severity)
        ]
        return candidates[:max_incidents]

    @staticmethod
    def _anomaly_view(item: dict) -> dict:
        """Compact view for list endpoints."""
        top = item["features"][0]["feature"] if item["features"] else None
        return {
            "record_id": item["record_id"],
            "machine_type": item["machine_type"],
            "product_id": item["product_id"],
            "algorithm": item["algorithm"],
            "anomaly_score": item["anomaly_score"],
            "severity": item["severity"],
            "is_anomaly": item["is_anomaly"],
            "main_anomalous_feature": top,
            "anomalous_feature_count": len(item["anomalous_features"]),
            "ground_truth_failure": item["ground_truth_failure"],
            "ground_truth_failure_types": item["ground_truth_failure_types"],
            "ground_truth_used_for_detection": False,
        }


_engine: AnomalyEngine | None = None
_lock = threading.Lock()


def get_engine() -> AnomalyEngine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = AnomalyEngine().build()
    return _engine
