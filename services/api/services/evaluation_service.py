"""Held-out evaluation of the anomaly detector.

The detector is compared against the dataset's ``Machine failure`` label on
the deterministic held-out **test** split. Thresholds are only ever tuned on
the separate **validation** split. Anomaly detection and failure prediction
are related but distinct tasks: a flagged anomaly is an unusual observation,
not a calibrated failure probability.

Metrics are computed without any third-party ML dependency so the report is
fully reproducible.
"""

from __future__ import annotations

import numpy as np

from services.api import data
from services.api.core import config
from services.api.services.anomaly_engine import get_engine


def _confusion(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    return {"true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn}


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    cm = _confusion(y_true, y_pred)
    tp, tn, fp, fn = cm["true_positive"], cm["true_negative"], cm["false_positive"], cm["false_negative"]

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    accuracy = (tp + tn) / len(y_true) if len(y_true) else 0.0

    return {
        "confusion_matrix": cm,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "accuracy": round(accuracy, 4),
        "support": int(len(y_true)),
    }


class EvaluationService:
    def __init__(self) -> None:
        self._report: dict | None = None

    def _score_frame(self, frame):
        engine = get_engine()
        scores = np.empty(len(frame), dtype=float)
        labels = np.empty(len(frame), dtype=int)
        for position, (_, row) in enumerate(frame.iterrows()):
            result = engine.detector.score(
                data.extract_features(row), data.machine_type_of(row)
            )
            scores[position] = result["anomaly_score"]
            labels[position] = int(row["Machine failure"])
        return scores, labels

    def select_threshold_on_validation(self) -> float:
        engine = get_engine()
        scores, labels = self._score_frame(engine.validation_frame)
        candidates = np.unique(
            np.concatenate(
                [
                    [engine.detector.anomaly_score_threshold],
                    np.quantile(scores, np.linspace(0.5, 0.999, 250)),
                ]
            )
        )
        best_threshold = engine.detector.anomaly_score_threshold
        best_f1 = -1.0
        for threshold in candidates:
            predicted = (scores >= threshold).astype(int)
            metrics = _metrics(labels, predicted)
            if metrics["f1_score"] > best_f1 or (
                metrics["f1_score"] == best_f1 and threshold > best_threshold
            ):
                best_f1 = metrics["f1_score"]
                best_threshold = float(threshold)
        return round(best_threshold, 4)

    def report(self) -> dict:
        if self._report is not None:
            return self._report

        engine = get_engine()
        configured = engine.detector.anomaly_score_threshold
        tuned = self.select_threshold_on_validation()

        test_scores, test_labels = self._score_frame(engine.test_frame)
        configured_metrics = _metrics(test_labels, (test_scores >= configured).astype(int))
        tuned_metrics = _metrics(test_labels, (test_scores >= tuned).astype(int))

        positives = int(test_labels.sum())
        self._report = {
            "algorithm": engine.detector.algorithm,
            "split": {
                "seed": config.RANDOM_SEED,
                "train_count": int(len(engine.train_frame)),
                "validation_count": int(len(engine.validation_frame)),
                "test_count": int(len(engine.test_frame)),
                "baseline_fit_on": "train",
                "threshold_selected_on": "validation",
            },
            "thresholds": {
                "configured": configured,
                "validation_tuned": tuned,
            },
            "test_metrics_at_configured_threshold": configured_metrics,
            "test_metrics_at_validation_tuned_threshold": tuned_metrics,
            "test_class_balance": {
                "positive_failures": positives,
                "negative_failures": int(len(test_labels) - positives),
                "failure_rate": round(positives / len(test_labels), 4) if len(test_labels) else 0.0,
            },
            "notes": [
                "Anomaly detection flags unusual observations; it is not a "
                "calibrated failure probability.",
                "The detector never consumes ground-truth failure labels; they "
                "are used only here, for evaluation.",
                "The AI4I dataset is synthetic and strongly imbalanced, so "
                "precision/recall are sensitive to the chosen threshold.",
                "Thresholds are tuned on the validation split only; the test "
                "split is used once, for reporting.",
            ],
            "ground_truth_used_for_detection": False,
        }
        return self._report


_service: EvaluationService | None = None


def get_evaluation_service() -> EvaluationService:
    global _service
    if _service is None:
        _service = EvaluationService()
    return _service
