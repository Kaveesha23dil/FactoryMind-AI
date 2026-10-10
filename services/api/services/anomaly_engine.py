"""Anomaly engine: fits the detector once, precomputes scores, caches them.

The engine is the single source of truth for anomaly results used by the
API. Scores for every dataset observation are computed once (at startup) and
served from memory, satisfying the "avoid costly per-request calculation"
requirement. The detector is fit only on the training split.
"""

from __future__ import annotations

import logging
import threading

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
        self._built = False

    # -- lifecycle -------------------------------------------------------

    def build(self) -> "AnomalyEngine":
        if self._built:
            return self

        self.train_frame, self.validation_frame, self.test_frame = data.split_dataset()
        self.detector.fit(self.train_frame)

        results: dict[int, dict] = {}
        anomalies: list[dict] = []
        severity_counts = {name: 0 for name in config.SEVERITY_ORDER}

        for _, row in data.get_dataset().iterrows():
            record_id = int(row["UDI"])
            features = data.extract_features(row)
            machine_type = data.machine_type_of(row)
            result = self.detector.score(features, machine_type)
            result["record_id"] = record_id
            result["machine_type"] = machine_type
            result["product_id"] = str(row["Product ID"])
            result["severity"] = result["severity"]
            # Ground-truth labels are attached ONLY for clearly-labelled
            # historical comparison. The detector never consumes them.
            result["ground_truth_failure"] = bool(int(row["Machine failure"]))
            result["ground_truth_failure_types"] = [
                name for name in config.FAILURE_CATEGORY_COLUMNS if int(row[name]) == 1
            ]
            results[record_id] = result
            severity_counts[result["severity"]] += 1
            if result["is_anomaly"]:
                anomalies.append(result)

        anomalies.sort(key=lambda item: item["anomaly_score"], reverse=True)
        self._results = results
        self._anomalies = anomalies
        self._severity_counts = severity_counts
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
        top = item["anomalous_features"][0]["feature"] if item["anomalous_features"] else None
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
