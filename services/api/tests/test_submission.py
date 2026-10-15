"""Submission views must not turn historical observations into verified diagnoses."""
from copy import deepcopy
from types import SimpleNamespace

from services.api.services.submission_service import audit_report, overview
from services.api.tests.test_investigations import investigation_env, anomaly_ids  # noqa: F401


def example():
    job = {'investigation_id': 'INV-TEST', 'incident_id': 'INC-TEST', 'report': {
        'evidence_catalog': ['EV-1'], 'hypotheses': [{'hypothesis_id':'H-1', 'supporting_evidence_ids':['EV-1']}],
        'critic_review': {'revision_required':False, 'citation_issues':['Weak relationship']}}}
    record = {'evidence_id':'EV-1', 'investigation_id':'INV-TEST', 'incident_id':'INC-TEST',
              'evidence_type':'manual_passage', 'source':'DOC-1 / SEC-1', 'provenance':'Synthetic reference',
              'observation':'Actual passage', 'payload':{'document_id':'DOC-1','section_id':'SEC-1'}}
    knowledge = SimpleNamespace(get_passage=lambda *_: SimpleNamespace(text='Actual passage'))
    return job, record, knowledge


def test_historical_critic_issues_require_attention_without_revision_flag():
    job, record, knowledge = example()
    audit = audit_report(job, [record], knowledge)
    assert audit['critic_attention_required']
    assert not audit['relationship_reviews_available']
    assert audit['resolved_citation_links'] == 1
    assert not audit['source_issues']


def test_bad_source_and_unknown_evidence_are_not_hidden():
    job, record, knowledge = example()
    job['report']['hypotheses'][0]['supporting_evidence_ids'].append('EV-UNKNOWN')
    record['observation'] = 'Fabricated passage'
    audit = audit_report(job, [record], knowledge)
    assert audit['invalid_evidence_ids'] == ['EV-UNKNOWN']
    assert audit['source_issues']


def test_audit_is_read_only_and_detects_catalog_and_ownership_mismatch():
    job, record, knowledge = example()
    job['report']['evidence_catalog'] = []
    record['incident_id'] = 'INC-OTHER'
    before = deepcopy((job, record))
    audit = audit_report(job, [record], knowledge)
    assert not audit['catalog_matches_storage']
    assert audit['source_issues']
    assert (job, record) == before


def test_empty_store_has_no_fabricated_demo(investigation_env):
    from services.api.services.anomaly_engine import get_engine
    result = overview(investigation_env, get_engine())
    assert result['demo'] is None
    assert result['integrity']['audited_reports'] == 0
    assert result['active_incidents'] == 0


def test_scripted_run_is_never_selected_as_google_demo(investigation_env, anomaly_ids):
    from services.api.services.anomaly_engine import get_engine
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    investigation_env.start_investigation(incident['incident_id'])
    result = overview(investigation_env, get_engine())
    assert result['investigations']['completed'] == 1
    assert result['demo'] is None


def test_submission_endpoint_reads_configured_store(client, investigation_env):
    response = client.get('/api/submission/overview')
    assert response.status_code == 200
    assert response.json()['demo'] is None
    assert response.json()['investigations']['completed'] == 0


def test_offline_evaluation_does_not_count_scripted_latency(investigation_env, anomaly_ids):
    from scripts.evaluate_submission import evaluate_saved
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    investigation_env.start_investigation(incident['incident_id'])
    with investigation_env.repository.database.connect() as connection:
        result = evaluate_saved(connection)
    assert result['latency_seconds']['samples'] == 0
    assert result['citation_id_resolution']['rate'] is None
    assert result['saved_counterfactuals']['leakage_scenario_rate'] is None
