"""Offline evaluation. Reads a SQLite snapshot; never starts workers or calls Gemini.

Run: python -m scripts.evaluate_submission --database services/api/data/incidents.db
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from services.api.core import config
from services.api.services.evaluation_service import EvaluationService
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.knowledge_repository import KNOWLEDGE_PATH
from services.api.services.submission_service import audit_report
from services.api.services.exclusion import resolve_excluded_features, filter_evidence_records


def decoded_evidence(connection, identifier):
    records = [dict(row) for row in connection.execute('SELECT * FROM investigation_evidence WHERE investigation_id=?', (identifier,))]
    for record in records:
        record['payload'] = json.loads(record['payload'])
    return records


def evaluate_saved(connection):
    audits, durations = [], []
    statuses = Counter()
    failures = Counter()
    jobs = {}
    for row in connection.execute('SELECT * FROM investigations ORDER BY investigation_id'):
        job = SqliteInvestigationRepository._row_to_job(row)
        jobs[job['investigation_id']] = job
        statuses[job['status']] += 1
        if job['status'] == 'failed':
            text = (job.get('error') or '').lower()
            category = ('quota' if '429' in text or 'quota' in text else 'timeout' if 'timed out' in text or 'timeout' in text else 'unavailable' if '503' in text else 'other')
            failures[category] += 1
        if job['status'] != 'completed' or job.get('provider') != 'google' or not job.get('report'):
            continue
        audit = audit_report(job, decoded_evidence(connection, job['investigation_id']))
        audits.append({'investigation_id': job['investigation_id'], **audit})
        if audit['duration_seconds'] is not None:
            durations.append(audit['duration_seconds'])
    scenarios = []
    for row in connection.execute("SELECT * FROM counterfactual_scenarios WHERE status='completed'"):
        original = decoded_evidence(connection, row['original_investigation_id'])
        excluded = set(json.loads(row['excluded_evidence_ids']))
        features, _ = resolve_excluded_features(excluded, original)
        _, dropped = filter_evidence_records(original, excluded, features)
        forbidden = excluded | {item['evidence_id'] for item in dropped}
        revised = jobs.get(row['revised_investigation_id'])
        if not revised or revised['status'] != 'completed' or revised['provider'] != 'google':
            continue
        actual = decoded_evidence(connection, revised['investigation_id'])
        report = revised.get('report') or {}
        cited = {identifier for h in report.get('hypotheses', []) for key in ('supporting_evidence_ids', 'contradicting_evidence_ids') for identifier in h.get(key, [])}
        leaked = forbidden & ({item['evidence_id'] for item in actual} | cited | set(report.get('evidence_catalog', [])))
        scenarios.append({'scenario_id': row['scenario_id'], 'leaked_ids': sorted(leaked)})
    links = sum(a['citation_links'] for a in audits)
    resolved = sum(a['resolved_citation_links'] for a in audits)
    return {'job_statuses': dict(statuses), 'failed_categories': dict(failures), 'completed_google_reports': audits,
            'citation_id_resolution': {'resolved': resolved, 'total': links, 'rate': resolved / links if links else None,
                                       'limitation': 'Structural ID resolution, not semantic citation accuracy. Source mismatches and critic issues are reported separately.'},
            'saved_counterfactuals': {'samples': len(scenarios), 'scenarios': scenarios,
                                     'leakage_scenario_rate': sum(bool(s['leaked_ids']) for s in scenarios) / len(scenarios) if scenarios else None,
                                     'scope': 'Stored/cited explicit and dependency-closed evidence IDs; does not prove absence of paraphrased leakage.'},
            'latency_seconds': {'samples': len(durations), 'mean': sum(durations)/len(durations) if durations else None,
                                'values': durations, 'scope': 'Stored completed Google-provider job start-to-completion durations; not a benchmark of current live capacity.'},
            'root_cause_top1_top3': {'result': None, 'reason': 'No independent machine-specific root-cause labels. AI4I failure flags are not hypothesis-ranking ground truth.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=config.settings.database_path)
    parser.add_argument('--output', type=Path, default=Path('reports/submission-evaluation.json'))
    args = parser.parse_args()
    result = {'dataset_sha256': hashlib.sha256(config.settings.dataset_path.read_bytes()).hexdigest(),
              'knowledge_sha256': hashlib.sha256(KNOWLEDGE_PATH.read_bytes()).hexdigest(),
              'anomaly_evaluation': EvaluationService().report(), 'saved_runs': None}
    if args.database.exists():
        with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            connection.row_factory = sqlite3.Row
            result['saved_runs'] = evaluate_saved(connection)
    else:
        result['saved_runs_limitation'] = 'No local SQLite snapshot available; no saved-run metrics claimed.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Offline evaluation written to {args.output}; no model calls or source record writes.')


if __name__ == '__main__':
    main()
