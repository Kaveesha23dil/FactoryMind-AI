"""Run from the repository root: python -m scripts.evaluate_anomalies."""

import argparse
import json
from pathlib import Path

from services.api.services.evaluation_service import EvaluationService


def main():
    parser = argparse.ArgumentParser(description="Export reproducible held-out anomaly metrics")
    parser.add_argument("--output", type=Path, default=Path("reports/anomaly-evaluation.json"))
    args = parser.parse_args()
    report = EvaluationService().report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
