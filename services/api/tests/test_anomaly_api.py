"""API tests for anomaly endpoints."""

from __future__ import annotations

import math

from services.api.core import config


def test_summary_shape(client):
    response = client.get("/api/anomalies/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm"] == config.ALGORITHM_VERSION
    assert body["analyzed_sample_count"] == 10_000
    assert body["detected_anomaly_count"] >= 1
    assert body["ground_truth_used_for_detection"] is False
    assert set(body["severity_distribution"]) == set(config.SEVERITY_ORDER)
    assert math.isfinite(body["threshold"])
    assert len(body["score_histogram"]) == 20
    assert sum(bucket["count"] for bucket in body["score_histogram"]) == 10_000
    assert any(bucket["bin_start"] == body["threshold"] for bucket in body["score_histogram"])
    assert body["score_stats"]["max"] > 0


def test_list_pagination(client):
    first = client.get("/api/anomalies", params={"limit": 5, "offset": 0}).json()
    second = client.get("/api/anomalies", params={"limit": 5, "offset": 5}).json()
    assert first["returned"] == 5
    assert first["total"] == second["total"]
    assert first["records"][0]["record_id"] != second["records"][0]["record_id"]
    assert first["records"][0]["algorithm"] == config.ALGORITHM_VERSION


def test_list_severity_filter(client):
    body = client.get("/api/anomalies", params={"severity": "critical"}).json()
    assert all(record["severity"] == "critical" for record in body["records"])


def test_list_machine_type_filter(client):
    body = client.get("/api/anomalies", params={"machine_type": "L"}).json()
    assert all(record["machine_type"] == "L" for record in body["records"])


def test_list_invalid_filters_rejected(client):
    assert client.get("/api/anomalies", params={"severity": "bogus"}).status_code == 422
    assert client.get("/api/anomalies", params={"min_severity": "bogus"}).status_code == 422
    assert client.get("/api/anomalies", params={"machine_type": "Z"}).status_code == 422


def test_detail_and_not_found(client):
    listing = client.get("/api/anomalies", params={"limit": 1}).json()
    record_id = listing["records"][0]["record_id"]
    detail = client.get(f"/api/anomalies/{record_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["record_id"] == record_id
    assert body["ground_truth_used_for_detection"] is False
    assert body["anomalous_features"]
    assert "incident_status" in body
    assert client.get("/api/anomalies/999999999").status_code == 404


def test_evaluation_report(client):
    response = client.get("/api/anomalies/evaluation")
    assert response.status_code == 200
    body = response.json()
    assert body["split"]["baseline_fit_on"] == "train"
    assert body["split"]["threshold_selected_on"] == "validation"
    assert body["split"]["train_count"] + body["split"]["validation_count"] + body["split"]["test_count"] == 10_000
    metrics = body["test_metrics_at_configured_threshold"]
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["f1_score"] <= 1.0
    cm = metrics["confusion_matrix"]
    assert cm["true_positive"] + cm["true_negative"] + cm["false_positive"] + cm["false_negative"] == body["split"]["test_count"]
