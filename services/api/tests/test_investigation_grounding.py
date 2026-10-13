"""Evidence-pipeline regressions; all model calls are scripted, never Gemini."""
import asyncio
import json
import math
import subprocess
import sys

import pytest

from services.api import data
from services.api.agents.orchestrator import Orchestrator, PreparedContext
from services.api.agents import orchestrator as orchestrator_module
from services.api.agents.prompts import format_knowledge
from services.api.agents.runtime import AdkRuntime
from services.api.db.database import Database
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.knowledge_repository import KnowledgeRepository
from services.api.tests.conftest import default_scripted_responses, make_feature_frame
from services.api.tests.test_agent_orchestration import RecordingReporter
from services.api.tests.test_investigations import investigation_env, anomaly_ids  # noqa: F401
from services.api.tools.evidence_tools import build_deterministic_evidence, evidence_catalog
from services.api.tools.grounding import normalize_analysis, text_issues, validate_sensor_snapshot
from services.api.tools.knowledge_tools import retrieve_knowledge
from services.api.tools.anomaly_tools import get_anomaly_analysis
from services.api.tools.incident_tools import get_incident_measurements
from services.api.tools import incident_tools, anomaly_tools
from services.api.services.anomaly_detector import RobustZScoreDetector


def _manual_catalog():
    passage = retrieve_knowledge('torque overload', top_k=1)[0]
    record = {'evidence_id': 'EV-MANUAL-007', 'evidence_type': 'manual_passage',
              'observation': passage['text'], 'payload': passage, 'value': None}
    return passage, {record['evidence_id']: record}


def test_no_match_and_zero_limit_are_empty():
    repo = KnowledgeRepository()
    assert repo.search('xylophone quasar') == []
    assert repo.search('torque', top_k=0) == []
    assert repo.search('torque', min_score=999) == []


def test_exact_document_and_section_references():
    repo = KnowledgeRepository()
    for passage in repo.search('speed torque'):
        assert repo.get_passage(passage.document_id, passage.section_id) == passage
        assert 'synthetic' in passage.source['publisher']


def test_prompt_exposes_actual_id_and_nested_citations_are_counted():
    passage, catalog = _manual_catalog()
    prompt = format_knowledge([{**passage, 'evidence_id': 'EV-MANUAL-007'}])
    assert 'EV-MANUAL-007' in prompt
    assert passage['document_id'] in prompt and passage['text'] in prompt
    output, issues = normalize_analysis({'summary': 'General maintenance guidance.',
        'guidance': [{'guidance': 'Review the load.', 'evidence_ids': ['EV-MANUAL-007', 'EV-MANUAL-007']}],
        'referenced_evidence_ids': []}, catalog, 'knowledge')
    assert issues == []
    assert output['referenced_evidence_ids'] == ['EV-MANUAL-007']


@pytest.mark.parametrize('ids,text', [([], 'Check the load.'),
    (['EV-GHOST-001'], 'Check the load.'),
    (['EV-MANUAL-007'], 'According to DOC-FAKE-999, replace the drive.')])
def test_untrusted_guidance_is_removed(ids, text):
    _, catalog = _manual_catalog()
    output, issues = normalize_analysis({'summary': 'Guidance.',
        'guidance': [{'guidance': text, 'evidence_ids': ids}]}, catalog, 'knowledge')
    assert output['guidance'] == [] and output['referenced_evidence_ids'] == []
    assert issues


def test_empty_retrieval_cannot_supply_knowledge_from_memory():
    output, issues = normalize_analysis({'summary': 'Replace a bearing.',
        'guidance': [{'guidance': 'Replace the bearing.', 'evidence_ids': []}]}, {}, 'knowledge')
    assert output['guidance'] == []
    assert 'documentation is missing' in output['summary']
    assert issues


def test_sensor_units_and_invented_numbers():
    records = [{'evidence_id': 'EV-SENSOR-001', 'value': 1500, 'units': 'rpm', 'payload': {'robust_zscore': 3.5}},
               {'evidence_id': 'EV-SENSOR-002', 'value': 6283.1853, 'units': 'W', 'payload': {}}]
    assert text_issues('1500 rpm, 6.28 kW, robust z-score 3.50.', records) == []
    assert text_issues('9999 rpm', records)
    assert text_issues('robust z-score 99.5', records)


def test_power_and_sensor_snapshot_consistency():
    row = make_feature_frame([40], [5]).iloc[0]
    raw = data.to_measurement(row)
    assert raw['rotational_speed_rpm'] == 1500
    assert raw['torque_nm'] == 40
    assert raw['derived_features']['mechanical_power_w'] == pytest.approx(40 * 2 * math.pi * 1500 / 60)
    anomaly = {'features': [{'feature': key, 'observed_value': value}
                           for key, value in raw['derived_features'].items()]}
    validate_sensor_snapshot({'measurements': raw}, anomaly)
    raw['derived_features']['mechanical_power_w'] += 100
    with pytest.raises(ValueError, match='Mechanical power'):
        validate_sensor_snapshot({'measurements': raw}, anomaly)


def test_inconsistent_raw_speed_and_torque_cannot_hide_behind_equal_power():
    raw = data.to_measurement(make_feature_frame([40], [5]).iloc[0])
    raw['rotational_speed_rpm'] *= 2
    raw['torque_nm'] /= 2
    with pytest.raises(ValueError, match='Raw and derived'):
        validate_sensor_snapshot({'measurements': raw}, {})


@pytest.mark.parametrize('value', [None, float('nan'), float('inf')])
def test_missing_sensor_measurements_fail_closed(value):
    with pytest.raises(ValueError, match='sensor measurement'):
        validate_sensor_snapshot({'measurements': {'rotational_speed_rpm': value, 'torque_nm': 40}}, {})


def test_imported_snapshot_cannot_leak_ground_truth(monkeypatch):
    class Store:
        def get_incident(self, incident_id):
            return {'record_id': 1, 'machine_type': 'L', 'source_measurements': {
                'torque_nm': 40, 'Machine failure': 1, 'failure_flags': {'TWF': 1},
                'derived_features': {'torque_nm': 40, 'TWF': 1}}}
    monkeypatch.setattr(incident_tools, '_service', lambda: Store())
    output = get_incident_measurements('INC-TEST')['measurements']
    assert output == {'torque_nm': 40, 'derived_features': {'torque_nm': 40}}


def test_baseline_tool_matches_degenerate_group_fallback(monkeypatch):
    import pandas as pd
    frame = pd.concat([make_feature_frame([10, 10, 10], [1, 2, 3], machine_type='L'),
                       make_feature_frame([20, 30, 40], [1, 2, 3], machine_type='M')])
    detector = RobustZScoreDetector(feature_keys=['torque_nm'], min_group_size=3).fit(frame)
    class Engine:
        pass
    engine = Engine()
    engine.detector = detector
    monkeypatch.setattr(anomaly_tools, 'get_engine', lambda: engine)
    stats = anomaly_tools.get_baseline_statistics('L')['baselines']['torque_nm']
    assert stats == detector.global_baselines['torque_nm'].to_dict()
    assert stats != detector.group_baselines['L']['torque_nm'].to_dict()


def test_unreviewed_citations_fail_closed():
    orchestrator = Orchestrator(AdkRuntime('scripted', 'scripted'), None)
    hypotheses, _ = orchestrator._normalize_hypotheses({'hypotheses': [{
        'hypothesis_id': 'H-001', 'title': 'Wear', 'supporting_evidence_ids': ['EV-MANUAL-001']}]},
        {'EV-MANUAL-001': {}})
    critic = {'citation_reviews': []}
    orchestrator._apply_citation_reviews(hypotheses, critic)
    assert hypotheses[0].supporting_evidence_ids == []
    assert hypotheses[0].assessment == 'unsupported'
    assert critic['citation_issues']


def test_support_contradiction_conflict_and_uncited_assessment():
    orchestrator = Orchestrator(AdkRuntime('scripted', 'scripted'), None)
    draft = {'hypotheses': [{'title': 'Load', 'assessment': 'plausible',
        'supporting_evidence_ids': ['EV-SENSOR-001'], 'contradicting_evidence_ids': ['EV-SENSOR-001']},
        {'title': 'Wear', 'assessment': 'plausible'}]}
    hypotheses, _ = orchestrator._normalize_hypotheses(draft, {'EV-SENSOR-001': {}})
    assert all(h.assessment == 'unsupported' and h.missing_evidence for h in hypotheses)
    assert any('both' in x for x in hypotheses[0].missing_evidence)


def test_semantically_rejected_citation_is_removed():
    orchestrator = Orchestrator(AdkRuntime('scripted', 'scripted'), None)
    hypotheses, _ = orchestrator._normalize_hypotheses({'hypotheses': [{
        'hypothesis_id': 'H-001', 'title': 'Wear', 'supporting_evidence_ids': ['EV-MANUAL-001']}]},
        {'EV-MANUAL-001': {}})
    critic = {'citation_reviews': [{'hypothesis_id': 'H-001', 'evidence_id': 'EV-MANUAL-001',
        'relationship': 'supporting', 'valid': False, 'reason': 'Passage discusses coolant, not wear.'}]}
    orchestrator._apply_citation_reviews(hypotheses, critic)
    assert hypotheses[0].supporting_evidence_ids == []
    assert critic['citation_issues']


def test_full_pipeline_counts_persistence_and_critic_disagreement(client, investigation_env, anomaly_ids):
    service = investigation_env
    incident = service.incident_service.create_incident(anomaly_ids[0])
    responses = default_scripted_responses()
    knowledge = json.loads(responses['knowledge_agent'])
    knowledge['referenced_evidence_ids'] = []
    responses['knowledge_agent'] = json.dumps(knowledge)
    critic = json.loads(responses['critic_agent'])
    critic['contradictions'] = ['Load is not confirmed by a single observation.']
    critic['revision_required'] = False
    responses['critic_agent'] = json.dumps(critic)
    service._runtime_factory = lambda: AdkRuntime('scripted', 'scripted', responses)
    job = service.start_investigation(incident['incident_id'])
    assert job['status'] == 'completed'
    activity = next(x for x in job['agent_activity'] if x['agent'] == 'knowledge_agent')
    assert activity['evidence_count'] == 1
    assert job['report']['revision_count'] == 1
    assert job['report']['critic_review']['revision_required'] is True
    # A new repository/SQLite connection represents process-local state being lost.
    restarted = SqliteInvestigationRepository(Database(service.repository.database.path))
    restarted.initialize()
    assert restarted.get(job['investigation_id'])['report'] == job['report']
    stored = restarted.get_evidence(job['investigation_id'])
    assert len([r for r in stored if r['evidence_type'] == 'manual_passage']) == 5
    assert set(job['report']['evidence_catalog']) == {r['evidence_id'] for r in stored}
    assert restarted.get(job['investigation_id'])['report']['knowledge_analysis']['referenced_evidence_ids'] == ['EV-MANUAL-001']
    api_report = client.get(f"/api/investigations/{job['investigation_id']}").json()['report']
    api_evidence = client.get(f"/api/investigations/{job['investigation_id']}/evidence").json()
    assert api_report['knowledge_analysis'] == job['report']['knowledge_analysis']
    assert api_evidence['total'] == len(stored)
    # Read in an entirely new interpreter, with no in-memory repository or ADK session.
    script = (
        "import sqlite3,json,sys; c=sqlite3.connect(sys.argv[1]); "
        "r=c.execute('select report from investigations where investigation_id=?',(sys.argv[2],)).fetchone(); "
        "print(json.dumps(json.loads(r[0])['knowledge_analysis']['referenced_evidence_ids']))"
    )
    process = subprocess.run([sys.executable, '-c', script,
        str(service.repository.database.path), job['investigation_id']],
        capture_output=True, text=True, timeout=15, check=True)
    assert json.loads(process.stdout) == ['EV-MANUAL-001']


def test_empty_retrieval_full_pipeline(investigation_env, anomaly_ids, monkeypatch):
    monkeypatch.setattr(orchestrator_module, 'retrieve_knowledge', lambda *args, **kwargs: [])
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    job = investigation_env.start_investigation(incident['incident_id'])
    assert job['status'] == 'completed'
    assert job['report']['knowledge_analysis']['guidance'] == []
    assert job['report']['critic_review']['revision_required']
    assert not any(r['evidence_type'] == 'manual_passage'
                   for r in investigation_env.get_evidence(job['investigation_id'])['items'])
    assert next(a for a in job['agent_activity'] if a['agent'] == 'knowledge_agent')['evidence_count'] == 0


@pytest.mark.parametrize('tamper', ['document_id', 'text'])
def test_fake_retrieval_source_never_persisted(investigation_env, anomaly_ids, monkeypatch, tamper):
    passage = retrieve_knowledge('torque', top_k=1)[0]
    passage[tamper] = 'fabricated source content'
    monkeypatch.setattr(orchestrator_module, 'retrieve_knowledge', lambda *args, **kwargs: [passage])
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    job = investigation_env.start_investigation(incident['incident_id'])
    assert job['status'] == 'failed'
    assert 'provenance validation' in job['error']
    assert investigation_env.get_evidence(job['investigation_id'])['items'] == []


def test_counterfactual_passage_keeps_original_id(investigation_env, anomaly_ids):
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    anomaly = get_anomaly_analysis(incident['incident_id'])
    passages = retrieve_knowledge('torque speed', top_k=2)
    records = build_deterministic_evidence('INV-TEST', incident, anomaly, passages, '2026-10-13')
    records = [r for r in records if r['evidence_id'] != 'EV-MANUAL-001']
    responses = default_scripted_responses()
    captured = {}
    class CaptureRuntime(AdkRuntime):
        async def run(self, spec, prompt):
            captured[spec.name] = prompt
            return await super().run(spec, prompt)
    orchestrator = Orchestrator(CaptureRuntime('scripted', 'scripted', responses), investigation_env.incident_service)
    prepared = PreparedContext({**incident, 'severity': anomaly['severity']},
        get_incident_measurements(incident['incident_id']), anomaly, {}, [passages[1]], records)
    asyncio.run(orchestrator.run('INV-TEST', incident['incident_id'], RecordingReporter(), prepared))
    assert 'EV-MANUAL-002' in captured['knowledge_agent']
    assert 'EV-MANUAL-001' not in captured['knowledge_agent']
