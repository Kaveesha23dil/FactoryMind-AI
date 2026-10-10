"""Unit tests for the deterministic counterfactual exclusion logic."""

from __future__ import annotations

from services.api.services.exclusion import (
    feature_dependencies,
    filter_evidence_records,
    restrict_anomaly,
    restrict_baselines,
    resolve_excluded_features,
    sanitize_measurements,
)


def _anomaly() -> dict:
    return {
        "algorithm": "robust_zscore_v1",
        "threshold": 4.0,
        "feature_z_threshold": 3.0,
        "anomaly_score": 3.9,
        "severity": "low",
        "is_anomaly": False,
        "features": [
            {
                "feature": "torque_nm",
                "label": "Torque",
                "robust_zscore": 3.0,
                "is_anomalous": True,
                "observed_value": 60.0,
                "unit": "Nm",
            },
            {
                "feature": "mechanical_power_w",
                "label": "Mechanical power",
                "robust_zscore": 2.0,
                "is_anomalous": False,
                "observed_value": 5000.0,
                "unit": "W",
            },
            {
                "feature": "tool_wear_min",
                "label": "Tool wear",
                "robust_zscore": 1.0,
                "is_anomalous": False,
                "observed_value": 10.0,
                "unit": "min",
            },
            {
                "feature": "rotational_speed_rpm",
                "label": "Rotational speed",
                "robust_zscore": 1.0,
                "is_anomalous": False,
                "observed_value": 1500.0,
                "unit": "rpm",
            },
        ],
        "anomalous_features": [],
    }


def _evidence() -> list[dict]:
    return [
        {
            "evidence_id": "EV-SENSOR-001",
            "evidence_type": "sensor_measurement",
            "payload": {"feature": "torque_nm"},
        },
        {
            "evidence_id": "EV-SENSOR-002",
            "evidence_type": "sensor_measurement",
            "payload": {"feature": "mechanical_power_w"},
        },
        {
            "evidence_id": "EV-SENSOR-003",
            "evidence_type": "sensor_measurement",
            "payload": {"feature": "tool_wear_min"},
        },
        {
            "evidence_id": "EV-BASELINE-001",
            "evidence_type": "baseline_statistic",
            "payload": {"feature": "torque_nm"},
        },
        {
            "evidence_id": "EV-ANOMALY-001",
            "evidence_type": "anomaly_finding",
            "payload": {},
        },
        {
            "evidence_id": "EV-MANUAL-001",
            "evidence_type": "manual_passage",
            "payload": {"document_id": "DOC-1"},
        },
    ]


def test_feature_dependencies_include_derived_features():
    dependencies = feature_dependencies()
    assert set(dependencies["temperature_difference_c"]) == {
        "air_temperature_c",
        "process_temperature_c",
    }
    assert set(dependencies["mechanical_power_w"]) == {
        "torque_nm",
        "rotational_speed_rpm",
    }


def test_resolve_excluded_features_closes_over_dependencies():
    features, provenance = resolve_excluded_features({"EV-SENSOR-001"}, _evidence())
    assert features == {"torque_nm", "mechanical_power_w"}
    assert provenance["torque_nm"] == 1
    assert provenance["mechanical_power_w"] == 1


def test_filter_evidence_drops_direct_and_derived_features():
    features, _ = resolve_excluded_features({"EV-SENSOR-001"}, _evidence())
    kept, dropped = filter_evidence_records(_evidence(), {"EV-SENSOR-001"}, features)
    kept_ids = {record["evidence_id"] for record in kept}
    dropped_ids = {record["evidence_id"] for record in dropped}
    assert "EV-SENSOR-001" not in kept_ids  # explicitly excluded
    assert "EV-BASELINE-001" not in kept_ids  # same feature
    assert "EV-SENSOR-002" not in kept_ids  # derived feature (mechanical power)
    assert {"EV-SENSOR-001", "EV-BASELINE-001", "EV-SENSOR-002"} <= dropped_ids
    assert {"EV-SENSOR-003", "EV-ANOMALY-001", "EV-MANUAL-001"} <= kept_ids


def test_restrict_anomaly_recomputes_score_exactly():
    restricted = restrict_anomaly(_anomaly(), {"torque_nm", "mechanical_power_w"})
    assert [f["feature"] for f in restricted["features"]] == [
        "tool_wear_min",
        "rotational_speed_rpm",
    ]
    # sqrt(1^2 + 1^2)
    assert abs(restricted["anomaly_score"] - 1.4142) < 1e-3
    assert restricted["severity"] == "normal"
    assert restricted["is_anomaly"] is False
    assert restricted["anomaly_score_recomputed"] is True


def test_sanitize_measurements_removes_raw_and_derived():
    context = {
        "measurements": {
            "torque_nm": 60.0,
            "rotational_speed_rpm": 1500.0,
            "derived_features": {"torque_nm": 60.0, "mechanical_power_w": 5000.0},
        }
    }
    sanitized = sanitize_measurements(context, {"torque_nm", "mechanical_power_w"})
    assert "torque_nm" not in sanitized["measurements"]
    assert sanitized["measurements"]["rotational_speed_rpm"] == 1500.0
    assert "torque_nm" not in sanitized["measurements"]["derived_features"]
    assert "mechanical_power_w" not in sanitized["measurements"]["derived_features"]


def test_restrict_baselines_removes_excluded_features():
    baselines = {
        "baselines": {"torque_nm": {"median": 1}, "tool_wear_min": {"median": 2}},
        "global_baselines": {"torque_nm": {"median": 1}, "tool_wear_min": {"median": 2}},
        "feature_labels": {"torque_nm": "Torque", "tool_wear_min": "Tool wear"},
        "feature_units": {"torque_nm": "Nm", "tool_wear_min": "min"},
    }
    restricted = restrict_baselines(baselines, {"torque_nm"})
    assert set(restricted["baselines"]) == {"tool_wear_min"}
    assert set(restricted["feature_labels"]) == {"tool_wear_min"}
