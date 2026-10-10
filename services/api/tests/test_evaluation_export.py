"""Evaluation exports must not accept arbitrary filesystem destinations."""

import json

import pytest

from scripts import evaluate_anomalies


def test_cli_rejects_output_path_argument(monkeypatch, tmp_path):
    outside = tmp_path / "outside.json"
    monkeypatch.setattr("sys.argv", ["evaluate_anomalies", "--output", str(outside)])
    with pytest.raises(SystemExit) as error:
        evaluate_anomalies.main()
    assert error.value.code == 2
    assert not outside.exists()


def test_export_uses_script_repository_reports_directory(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("sys.argv", ["evaluate_anomalies"])
    monkeypatch.setattr(evaluate_anomalies, "__file__", str(tmp_path / "scripts" / "evaluate_anomalies.py"))
    report = {"algorithm": "robust_zscore_v1", "precision": 0.1818}
    monkeypatch.setattr(evaluate_anomalies.EvaluationService, "report", lambda self: report)
    evaluate_anomalies.main()
    saved = tmp_path / "reports" / "anomaly-evaluation.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == report
    assert json.loads(capsys.readouterr().out) == report
