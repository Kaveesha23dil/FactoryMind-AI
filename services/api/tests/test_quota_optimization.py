"""No live Gemini calls: trace model turns and verify optimization invariants."""
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from services.api.agents import runtime as runtime_module
from services.api.agents.model import ScriptedLlm
from services.api.agents.runtime import AdkRuntime, InvestigationProviderError, MeteredGemini
from services.api.agents.request_control import request_slot
from services.api.core import config
from services.api.db.database import Database
from services.api.services.investigation_cache import report_key
from services.api.tests.test_investigations import investigation_env, anomaly_ids
from services.api.tests.test_counterfactuals import counterfactual_env
from services.api.tests.test_visual_inspection import visual_env, PNG_BYTES
from services.api.tools.knowledge_tools import retrieve_knowledge, _search
from services.api.services.knowledge_repository import get_knowledge_repository


@pytest.fixture
def model_trace(monkeypatch):
    calls = []
    original = ScriptedLlm.generate_content_async
    async def traced(self, llm_request, stream=False):
        calls.append(1)
        async for response in original(self, llm_request, stream):
            yield response
    monkeypatch.setattr(ScriptedLlm, 'generate_content_async', traced)
    return calls


@pytest.mark.parametrize('message,category,retryable', [
    ('429 RequestsPerMinute please check billing', 'RPM', True),
    ('429 TokensPerMinute', 'TPM', True), ('429 RequestsPerDay', 'RPD', False),
    ('429 spending limit exceeded', 'spending_limit', False),
    ("429 quotaValue: '0'", 'model_allocation', False),
    ('404 NOT_FOUND', 'model_allocation', False), ('429 RESOURCE_EXHAUSTED', 'quota_unknown', True),
])
def test_quota_categories(message, category, retryable):
    failure = InvestigationProviderError(message)
    assert failure.category == category and failure.retryable == retryable


def test_retry_after_header_is_preserved_across_adk_errors():
    class Error(Exception):
        response = SimpleNamespace(headers={'Retry-After': '14'})
    error = InvestigationProviderError.from_exception(Error('429 RESOURCE_EXHAUSTED'))
    assert error.retry_after_seconds == 14
    assert InvestigationProviderError(str(error)).retry_after_seconds == 14


def test_measured_report_reuse_and_explicit_rerun(client, investigation_env, anomaly_ids, model_trace):
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    path = f"/api/incidents/{incident['incident_id']}/investigate"
    first = client.post(path).json()
    assert len(model_trace) == 4
    second = client.post(path).json()
    assert second['reused'] is True and first['reused'] is False
    assert first['investigation_id'] == second['investigation_id'] and len(model_trace) == 4
    forced = client.post(path, params={'force_rerun': True}).json()
    assert forced['investigation_id'] != first['investigation_id'] and len(model_trace) == 8


@pytest.mark.parametrize('change', ['model', 'prompt', 'configuration', 'sensor', 'evidence', 'report'])
def test_cache_invalidation(investigation_env, anomaly_ids, model_trace, monkeypatch, change):
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    first = investigation_env.start_investigation(incident['incident_id'])
    if change == 'model':
        monkeypatch.setattr(config, 'settings', replace(config.settings, gemini_model='explicit-test-model'))
    elif change == 'prompt':
        monkeypatch.setattr(config, 'settings', replace(config.settings, prompt_version='new-test-version'))
    elif change == 'configuration':
        monkeypatch.setattr(config, 'KNOWLEDGE_TOP_K', 3)
    elif change == 'sensor':
        changed = dict(incident)
        changed['source_measurements'] = {**incident['source_measurements'], 'torque_nm': 999}
        assert report_key(incident) != report_key(changed)
        return
    elif change == 'report':
        report = dict(first['report'])
        report['summary'] = 'Altered conclusion'
        investigation_env.repository.update(first['investigation_id'], report=report)
    else:
        with investigation_env.repository.database.connect() as connection:
            connection.execute("UPDATE investigation_evidence SET observation='altered content' WHERE investigation_id=? AND evidence_id='EV-MANUAL-001'", (first['investigation_id'],))
            connection.commit()
    second = investigation_env.start_investigation(incident['incident_id'])
    assert second['investigation_id'] != first['investigation_id'] and len(model_trace) > 4


def test_counterfactual_bypasses_original_report_cache(client, counterfactual_env, anomaly_ids, model_trace):
    service = counterfactual_env['investigations']
    incident = service.incident_service.create_incident(anomaly_ids[0])
    first = service.start_investigation(incident['incident_id'])
    assert len(model_trace) == 4
    response = client.post(f"/api/investigations/{first['investigation_id']}/counterfactual",
        json={'excluded_evidence_ids': ['EV-SENSOR-001'], 'rationale': 'Remove this sensor observation.'})
    assert response.status_code == 200 and response.json()['status'] == 'completed'
    revised = service.get(response.json()['revised_investigation_id'])
    assert revised['investigation_id'] != first['investigation_id']
    assert revised['report'].get('cache_key') is None
    assert 'EV-SENSOR-001' not in revised['report']['evidence_catalog']
    assert len(model_trace) == 10  # four original turns, six restricted/revised turns
    assert service.start_investigation(incident['incident_id'])['investigation_id'] == first['investigation_id']
    assert len(model_trace) == 10


def test_visual_request_trace(visual_env, anomaly_ids, model_trace):
    incident = visual_env.incident_service.create_incident(anomaly_ids[0])
    image = visual_env.store(incident['incident_id'], 'inspection.png', 'image/png', PNG_BYTES)
    result = visual_env.analyze(image['image_id'])
    assert result['status'] == 'analyzed' and len(model_trace) == 1


def test_retrieval_cache_returns_independent_values(monkeypatch):
    repo = get_knowledge_repository()
    _search.cache_clear()
    calls = []
    original = repo.search
    def search(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(repo, 'search', search)
    first = retrieve_knowledge('quota cache torque')
    text = first[0]['text']
    first[0]['text'] = 'mutated by caller'
    second = retrieve_knowledge('quota cache torque')
    assert len(calls) == 1 and second[0]['text'] == text


def test_atomic_job_claim(investigation_env, anomaly_ids):
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    job = investigation_env.create_queued_investigation(incident['incident_id'])
    from services.api.services.investigation_repository import SqliteInvestigationRepository
    other = SqliteInvestigationRepository(Database(investigation_env.repository.database.path))
    assert investigation_env.repository.claim(job['investigation_id'])
    assert not other.claim(job['investigation_id'])


def test_shared_request_concurrency_and_cleanup(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'settings', replace(config.settings, database_path=tmp_path/'leases.db', gemini_concurrency=1))
    active = 0
    maximum = 0
    async def work():
        nonlocal active, maximum
        async with request_slot():
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.02)
            active -= 1
    async def run():
        await asyncio.gather(work(), work(), work())
    asyncio.run(run())
    assert maximum == 1
    with Database().connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM gemini_request_leases').fetchone()[0] == 0


def test_sdk_retries_disabled():
    runtime = AdkRuntime('google', 'explicit-test-model')
    from services.api.agents import sensor_agent
    model = runtime._model_for(sensor_agent.SPEC)
    assert isinstance(model, MeteredGemini) and model.retry_options.attempts == 1


def test_metered_request_logging_has_no_prompt_or_secrets(monkeypatch, tmp_path, caplog):
    from google.adk.models import Gemini
    monkeypatch.setattr(config, 'settings', replace(config.settings, database_path=tmp_path/'usage.db'))
    async def generate(self, request, stream=False):
        yield SimpleNamespace(error_message=None, usage_metadata=SimpleNamespace(prompt_token_count=120, candidates_token_count=35))
    monkeypatch.setattr(Gemini, 'generate_content_async', generate)
    runtime = AdkRuntime('google', 'metered-test-model')
    from services.api.agents import sensor_agent
    model = runtime._model_for(sensor_agent.SPEC)
    async def run():
        return [r async for r in model.generate_content_async('SECRET sensitive prompt')]
    with caplog.at_level('INFO', logger=runtime_module.__name__):
        asyncio.run(run())
    assert len(runtime.request_metrics) == 1
    usage = runtime.request_metrics[0]
    assert usage['input_tokens'] == 120 and usage['output_tokens'] == 35
    assert usage['request_count'] == 1 and usage['latency_ms'] >= 0
    assert 'SECRET' not in caplog.text and 'sensitive prompt' not in caplog.text


def test_long_quota_cooldown_shared_with_visual_requests(monkeypatch, tmp_path):
    from google.adk.models import Gemini
    monkeypatch.setattr(config, 'settings', replace(config.settings, database_path=tmp_path/'quota.db'))
    calls = []
    async def generate(self, request, stream=False):
        calls.append(1)
        raise InvestigationProviderError("429 RequestsPerDay retryDelay: '42136s'")
        yield
    monkeypatch.setattr(Gemini, 'generate_content_async', generate)
    model = MeteredGemini(model='shared-quota-test', metrics=[])
    async def run():
        for _ in range(2):
            with pytest.raises(InvestigationProviderError):
                async for response in model.generate_content_async(None):
                    pass
    asyncio.run(run())
    assert len(calls) == 1 and len(model.metrics) == 1


def test_report_cache_persists_after_service_restart(investigation_env, anomaly_ids, model_trace):
    from services.api.services.investigation_service import InvestigationService
    from services.api.services.investigation_repository import SqliteInvestigationRepository
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    first = investigation_env.start_investigation(incident['incident_id'])
    restarted = InvestigationService(SqliteInvestigationRepository(Database(investigation_env.repository.database.path)),
                                    investigation_env.incident_service)
    assert restarted.start_investigation(incident['incident_id'])['investigation_id'] == first['investigation_id']
    assert len(model_trace) == 4


def test_corpus_changes_invalidate_retrieval_cache(monkeypatch, tmp_path):
    from services.api.services import knowledge_repository as module
    corpus = {'documents': [{'doc_id':'DOC-TEST', 'title':'Synthetic test', 'sections':[
        {'section_id':'SEC-TEST', 'heading':'Torque', 'text':'torque first', 'keywords':['torque']}]}]}
    path = tmp_path/'documents.json'
    path.write_text(json.dumps(corpus), encoding='utf-8')
    monkeypatch.setattr(module, 'KNOWLEDGE_PATH', path)
    assert retrieve_knowledge('torque')[0]['text'] == 'torque first'
    corpus['documents'][0]['sections'][0]['text'] = 'torque newer'
    path.write_text(json.dumps(corpus), encoding='utf-8')
    assert retrieve_knowledge('torque')[0]['text'] == 'torque newer'


def test_http_date_retry_after():
    from datetime import datetime, timezone, timedelta
    from email.utils import format_datetime
    class Error(Exception):
        response = SimpleNamespace(headers={'Retry-After': format_datetime(datetime.now(timezone.utc)+timedelta(seconds=20), usegmt=True)})
    failure = InvestigationProviderError.from_exception(Error('429 RESOURCE_EXHAUSTED'))
    assert 18 <= failure.retry_after_seconds <= 20


def test_expired_request_lease_is_recovered(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'settings', replace(config.settings, database_path=tmp_path/'lease.db'))
    database = Database()
    database.initialize()
    with database.connect() as connection:
        connection.execute('INSERT INTO gemini_request_leases VALUES (?,?)', ('abandoned', 0))
        connection.commit()
    async def run():
        async with request_slot():
            with database.connect() as connection:
                assert connection.execute('SELECT COUNT(*) FROM gemini_request_leases').fetchone()[0] == 1
    asyncio.run(run())


def test_sensor_prompt_context_reduction(investigation_env, anomaly_ids):
    from services.api.agents import sensor_agent
    from services.api.agents.prompts import format_measurements, format_anomaly, format_baselines
    from services.api.tools.anomaly_tools import get_anomaly_analysis, get_baseline_statistics
    from services.api.tools.incident_tools import get_incident_context, get_incident_measurements
    from services.api.tools.evidence_tools import build_deterministic_evidence
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    anomaly = get_anomaly_analysis(incident['incident_id'])
    passages = retrieve_knowledge('torque speed')
    records = build_deterministic_evidence('INV-PROMPT', incident, anomaly, passages, 'test')
    context = {'incident':get_incident_context(incident['incident_id']), 'anomaly':anomaly,
        'baselines':get_baseline_statistics(incident['machine_type']),
        'measurements':get_incident_measurements(incident['incident_id']), 'evidence':records}
    old_catalog = '\n'.join(f"- {r['evidence_id']} [{r['evidence_type']}] source={r['source']} :: {r['observation']}" for r in records)
    baseline = (format_measurements(context['measurements']) + format_anomaly(anomaly)
                + format_baselines(context['baselines']) + old_catalog)
    optimized = sensor_agent.build_prompt(context)
    assert len(optimized) < len(baseline)
    assert 'EV-SENSOR-001' in optimized and 'Provenance registry:' in optimized
    assert 'EV-MANUAL-001' not in optimized


def test_cache_disabled_baseline_uses_eight_turns(investigation_env, anomaly_ids, model_trace, monkeypatch):
    monkeypatch.setattr(config, 'settings', replace(config.settings, investigation_cache_enabled=False))
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    first = investigation_env.start_investigation(incident['incident_id'])
    second = investigation_env.start_investigation(incident['incident_id'])
    assert first['investigation_id'] != second['investigation_id'] and len(model_trace) == 8
