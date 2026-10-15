"""Read-only competition overview and structural evidence audits. No model calls."""
from datetime import datetime

from services.api.services.knowledge_repository import get_knowledge_repository
from services.api.tools.grounding import critic_requires_revision


def audit_report(job, evidence, knowledge=None):
    knowledge = knowledge or get_knowledge_repository()
    report = job.get('report') or {}
    records = {e['evidence_id']: e for e in evidence}
    links = [(h.get('hypothesis_id'), relation, identifier)
             for h in report.get('hypotheses', [])
             for relation in ('supporting_evidence_ids', 'contradicting_evidence_ids')
             for identifier in h.get(relation, [])]
    invalid = [identifier for _, _, identifier in links if identifier not in records]
    source_issues = []
    for record in evidence:
        if record.get('investigation_id') != job['investigation_id'] or record.get('incident_id') != job['incident_id']:
            source_issues.append(f"{record['evidence_id']}: record ownership mismatch")
        if not record.get('source') or not record.get('provenance'):
            source_issues.append(f"{record['evidence_id']}: missing provenance")
        if record.get('evidence_type') == 'manual_passage':
            payload = record.get('payload') or {}
            passage = knowledge.get_passage(payload.get('document_id'), payload.get('section_id'))
            if not passage or passage.text != record.get('observation'):
                source_issues.append(f"{record['evidence_id']}: passage missing or changed")
    review = report.get('critic_review') or {}
    duration = None
    if job.get('started_at') and job.get('completed_at'):
        duration = (datetime.fromisoformat(job['completed_at']) - datetime.fromisoformat(job['started_at'])).total_seconds()
    return {
        'stored_evidence': len(evidence), 'citation_links': len(links),
        'resolved_citation_links': len(links) - len(invalid), 'invalid_evidence_ids': sorted(set(invalid)),
        'source_issues': source_issues,
        'catalog_matches_storage': set(report.get('evidence_catalog', [])) == set(records),
        'relationship_reviews_available': bool(review.get('citation_reviews')),
        'critic_attention_required': critic_requires_revision(review),
        'duration_seconds': duration,
        'scope': 'ID resolution and stored source checks; not proof of semantic entailment or physical root cause.',
    }


def overview(investigations, engine):
    repo = investigations.repository
    counts = {status: repo.list_all(0, 0, status)[0] for status in ('queued', 'running', 'completed', 'failed')}
    incidents = investigations.incident_service.repository
    active = sum(incidents.list(0, 0, status=status, severity=None)[0] for status in ('open', 'under_review'))
    total, completed = repo.list_all(100, 0, 'completed')
    audited = []
    demo = None
    for row in completed:
        job = repo.get(row['investigation_id'])
        if not job or not job.get('report'):
            continue
        audit = audit_report(job, repo.get_evidence(job['investigation_id']))
        audited.append(audit)
        activities = job.get('agent_activity', [])
        genuine_record = job.get('provider') == 'google' and all(
            any(a.get('agent') == agent and a.get('status') == 'completed' for a in activities)
            for agent in ('sensor_agent', 'knowledge_agent', 'investigation_agent', 'critic_agent'))
        if demo is None and genuine_record and audit['citation_links'] and not audit['invalid_evidence_ids'] and not audit['source_issues'] and audit['catalog_matches_storage']:
            incident = investigations.incident_service.get_incident(job['incident_id'])
            demo = {'investigation_id': job['investigation_id'], 'incident_id': job['incident_id'],
                    'record_id': incident['record_id'], 'generated_at': job['report']['generated_at'],
                    'model': job['model'], 'audit': audit,
                    'label': 'Historical saved Google-provider result; no live AI call. Critic limitations remain visible.'}
    recent = investigations.list_investigations(limit=5)['items']
    return {'dataset': 'AI4I 2020 synthetic benchmark; not live machine telemetry',
            'anomalies': engine.summary()['detected_anomaly_count'],
            'severity_distribution': engine.summary()['severity_distribution'],
            'active_incidents': active, 'investigations': counts, 'recent': recent,
            'integrity': {'audited_reports': len(audited), 'completed_reports': total,
                          'scan_limit': 100, 'citation_links': sum(a['citation_links'] for a in audited),
                          'resolved_citation_links': sum(a['resolved_citation_links'] for a in audited),
                          'reports_needing_attention': sum(bool(a['invalid_evidence_ids'] or a['source_issues'] or not a['catalog_matches_storage'] or a['critic_attention_required']) for a in audited)},
            'demo': demo}
