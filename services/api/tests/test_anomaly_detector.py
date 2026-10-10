"""Unit tests for the robust z-score anomaly detector."""

from __future__ import annotations

import math

import pytest

from services.api.core import config
from services.api.services.anomaly_detector import RobustZScoreDetector
from services.api.tests.conftest import make_feature_frame

FEATURES = ["torque_nm", "tool_wear_min"]


def _detector(**kwargs) -> RobustZScoreDetector:
    defaults = dict(
        feature_keys=FEATURES,
        feature_z_threshold=3.0,
        anomaly_score_threshold=3.0,
        min_group_size=10_000,
    )
    defaults.update(kwargs)
    return RobustZScoreDetector(**defaults)


def test_valid_anomaly_detection_and_score_math():
    frame = make_feature_frame(
        torque=[10, 20, 30, 40, 50],
        wear=[0, 10, 20, 30, 40],
    )
    detector = _detector().fit(frame)

    result = detector.score({"torque_nm": 200.0, "tool_wear_min": 40.0})

    # torque: median 30, MAD 10, scale 14.826 -> z = (200-30)/14.826
    expected_torque_z = (200.0 - 30.0) / (10.0 * config.MAD_SCALE)
    expected_wear_z = (40.0 - 20.0) / (10.0 * config.MAD_SCALE)
    expected_score = math.sqrt(expected_torque_z**2 + expected_wear_z**2)

    assert result["anomaly_score"] == pytest.approx(expected_score, rel=1e-3)
    assert result["is_anomaly"] is True
    assert result["severity"] == "critical"
    assert result["ground_truth_used_for_detection"] is False
    assert result["anomalous_features"][0]["feature"] == "torque_nm"
    assert result["anomalous_features"][0]["direction"] == "high"


def test_normal_measurement_handling():
    frame = make_feature_frame(torque=[40, 41, 42, 43, 44], wear=[10, 11, 12, 13, 14])
    detector = _detector().fit(frame)
    result = detector.score({"torque_nm": 42.0, "tool_wear_min": 12.0})
    assert result["is_anomaly"] is False
    assert result["severity"] == "normal"
    assert result["anomalous_features"] == []


def test_mad_zero_fallback_chain():
    # Four identical values and one deviation -> MAD is 0, fallback to mean
    # absolute deviation (0.8), which is non-zero.
    frame = make_feature_frame(torque=[5, 5, 5, 5, 9], wear=[10, 10, 10, 10, 10])
    detector = _detector().fit(frame)
    result = detector.score({"torque_nm": 9.0, "tool_wear_min": 10.0})
    torque = next(f for f in result["features"] if f["feature"] == "torque_nm")
    assert torque["robust_zscore"] == pytest.approx(5.0, rel=1e-3)


def test_fully_degenerate_feature_scores_zero_at_median():
    frame = make_feature_frame(torque=[7, 7, 7, 7, 7], wear=[1, 2, 3, 4, 5])
    detector = _detector().fit(frame)
    result = detector.score({"torque_nm": 7.0, "tool_wear_min": 3.0})
    torque = next(f for f in result["features"] if f["feature"] == "torque_nm")
    assert torque["robust_zscore"] == 0.0
    assert torque["is_anomalous"] is False


def test_threshold_behavior():
    frame = make_feature_frame(torque=[0, 10, 20, 30, 40], wear=[0, 10, 20, 30, 40])
    low = _detector(anomaly_score_threshold=100.0).fit(frame)
    high = _detector(anomaly_score_threshold=1.0).fit(frame)
    observation = {"torque_nm": 60.0, "tool_wear_min": 20.0}
    assert low.score(observation)["is_anomaly"] is False
    assert high.score(observation)["is_anomaly"] is True


def test_missing_feature_raises():
    frame = make_feature_frame(torque=[10, 20, 30], wear=[1, 2, 3])
    detector = _detector().fit(frame)
    with pytest.raises(ValueError, match="Missing required features"):
        detector.score({"torque_nm": 10.0})


def test_non_finite_values_raise():
    frame = make_feature_frame(torque=[10, 20, 30], wear=[1, 2, 3])
    detector = _detector().fit(frame)
    with pytest.raises(ValueError, match="not finite"):
        detector.score({"torque_nm": float("nan"), "tool_wear_min": 2.0})
    with pytest.raises(ValueError, match="not finite"):
        detector.score({"torque_nm": float("inf"), "tool_wear_min": 2.0})


def test_ground_truth_columns_never_in_features():
    assert "Machine failure" not in config.FEATURE_KEYS
    for column in config.GROUND_TRUTH_COLUMNS:
        assert column not in config.FEATURE_KEYS


def test_ground_truth_labels_do_not_affect_scores():
    frame = make_feature_frame(torque=[10, 20, 30, 40, 50], wear=[0, 10, 20, 30, 40])
    frame["Machine failure"] = [0, 0, 1, 0, 1]
    other = frame.copy()
    other["Machine failure"] = [1, 1, 0, 1, 0]

    first = _detector().fit(frame).score({"torque_nm": 30.0, "tool_wear_min": 20.0})
    second = _detector().fit(other).score({"torque_nm": 30.0, "tool_wear_min": 20.0})
    assert first["anomaly_score"] == second["anomaly_score"]


def test_score_before_fit_raises():
    with pytest.raises(RuntimeError, match="must be fit"):
        _detector().score({"torque_nm": 1.0, "tool_wear_min": 1.0})


def test_severity_bands():
    detector = _detector(anomaly_score_threshold=4.0)
    assert detector._severity_for(3.9) == "normal"
    assert detector._severity_for(4.0) == "low"
    assert detector._severity_for(5.0) == "medium"
    assert detector._severity_for(6.0) == "high"
    assert detector._severity_for(8.0) == "critical"
    assert detector._severity_for(100.0) == "critical"


@pytest.mark.parametrize("threshold", [0, -1, float("nan"), float("inf")])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(ValueError, match="finite and positive"):
        _detector(anomaly_score_threshold=threshold)


def test_training_rejects_empty_and_nonfinite_data():
    frame = make_feature_frame(torque=[10, 20, 30], wear=[1, 2, 3])
    with pytest.raises(ValueError, match="empty"):
        _detector().fit(frame.iloc[:0])
    frame.loc[0, "Torque [Nm]"] = float("nan")
    with pytest.raises(ValueError, match="not finite"):
        _detector().fit(frame)


def test_negative_overflow_retains_anomaly_direction():
    detector = _detector().fit(make_feature_frame(torque=[7] * 3, wear=[1, 2, 3]))
    result = detector.score({"torque_nm": -1e308, "tool_wear_min": 2})
    torque = next(f for f in result["features"] if f["feature"] == "torque_nm")
    assert torque["robust_zscore"] == -config.MAX_ABS_ZSCORE
    assert result["is_anomaly"]
