"""Tests for the evaluation service."""

from __future__ import annotations

from services.api.core import config
from services.api.services.evaluation_service import EvaluationService


def test_report_is_reproducible():
    first = EvaluationService().report()
    second = EvaluationService().report()
    assert first == second


def test_threshold_tuned_only_on_validation(engine):
    service = EvaluationService()
    tuned = service.select_threshold_on_validation()
    assert tuned > 0

    # Recomputing on the validation frame is deterministic.
    assert service.select_threshold_on_validation() == tuned

    report = service.report()
    assert report["split"]["threshold_selected_on"] == "validation"
    assert report["split"]["baseline_fit_on"] == "train"
    assert report["thresholds"]["configured"] == config.ANOMALY_SCORE_THRESHOLD


def test_metrics_are_bounded(engine):
    report = EvaluationService().report()
    for key in (
        "test_metrics_at_configured_threshold",
        "test_metrics_at_validation_tuned_threshold",
    ):
        metrics = report[key]
        for field in ("precision", "recall", "f1_score", "false_positive_rate", "accuracy"):
            assert 0.0 <= metrics[field] <= 1.0
