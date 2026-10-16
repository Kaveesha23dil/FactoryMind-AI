"""One joined acceptance workflow; model responses are scripted, never live Gemini."""
from copy import deepcopy

from services.api.agents.runtime import AdkRuntime
from services.api.db.database import Database
from services.api.routes import evidence_graph as graph_routes
from services.api.routes import investigations as investigation_routes
from services.api.routes import counterfactuals as counterfactual_routes
from services.api.services.evidence_graph_service import EvidenceGraphService
from services.api.services.anomaly_engine import get_engine
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.investigation_service import InvestigationService
from services.api.services.counterfactual_repository import SqliteCounterfactualRepository
from services.api.services.counterfactual_service import CounterfactualService
from services.api.services.submission_service import audit_report
from services.api.tests.test_counterfactuals import counterfactual_env  # noqa: F401
from services.api.tools.grounding import critic_requires_revision


def test_joined_workflow_and_reopened_results(client, counterfactual_env, monkeypatch):
    service = counterfactual_env['investigations']
    monkeypatch.setattr(graph_routes, '_service', EvidenceGraphService(service))
    prompts = []
    original_run = AdkRuntime.run

    async def capture(self, spec, prompt):
        assert self.provider == 'scripted'
        prompts.append((spec.name, prompt))
        return await original_run(self, spec, prompt)

    monkeypatch.setattr(AdkRuntime, 'run', capture)
    dataset = client.get('/api/dataset/summary')
    assert dataset.status_code == 200
    record = get_engine()._anomalies[0]
    incident_response = client.post('/api/incidents', json={'record_id': record['record_id']})
    assert incident_response.status_code == 201
    incident_id = incident_response.json()['incident_id']
    started = client.post(f'/api/incidents/{incident_id}/investigate')
    assert started.status_code == 202
    identifier = started.json()['investigation_id']
    original = client.get(f'/api/investigations/{identifier}').json()
    assert original['status'] == 'completed'
    assert {a['agent'] for a in original['agent_activity'] if a['status'] == 'completed'} == {
        'sensor_agent', 'knowledge_agent', 'investigation_agent', 'critic_agent'}
    evidence = client.get(f'/api/investigations/{identifier}/evidence').json()['items']
    manual = [e for e in evidence if e['evidence_type'] == 'manual_passage']
    assert manual and all(e['source'] and e['provenance'] for e in evidence)
    audit = audit_report(original, evidence)
    assert audit['citation_links'] > 0 and not audit['invalid_evidence_ids'] and not audit['source_issues']
    assert audit['catalog_matches_storage']
    knowledge = next(a for a in original['agent_activity'] if a['agent'] == 'knowledge_agent')
    assert knowledge['evidence_count'] > 0
    assert original['report']['critic_review']
    graph = client.get(f'/api/investigations/{identifier}/graph')
    assert graph.status_code == 200
    assert {e['evidence_id'] for e in evidence} <= {n['id'] for n in graph.json()['nodes']}

    before = deepcopy(service.repository.get(identifier))
    first_calls = len(prompts)
    excluded = next(e['evidence_id'] for e in evidence if e['evidence_type'] == 'sensor_measurement')
    created = client.post(f'/api/investigations/{identifier}/counterfactual', json={'excluded_evidence_ids': [excluded]})
    assert created.status_code == 200, created.text
    scenario = created.json()
    assert scenario['status'] == 'completed' and scenario['comparison']['anomaly']['recomputed']
    assert len(prompts) > first_calls  # Actual new model reasoning, not original report reuse.
    revised_id = scenario['revised_investigation_id']
    revised = client.get(f'/api/investigations/{revised_id}').json()
    assert revised_id != identifier and excluded not in revised['report']['evidence_catalog']
    assert excluded not in {e['evidence_id'] for e in service.repository.get_evidence(revised_id)}
    assert service.repository.get(identifier) == before
    # Scripted reuse of an excluded citation is surfaced by the critic, not silently approved.
    assert excluded in revised['report']['rejected_citations']
    assert critic_requires_revision(revised['report']['critic_review'])
    for _, prompt in prompts:
        for forbidden in ('"machine_failure"', '"failure_flags"', '"ground_truth"', '"Machine failure":'):
            assert forbidden not in prompt

    # Fresh repository/service instances read the persisted results, without rerunning models.
    reopened = InvestigationService(
        repository=SqliteInvestigationRepository(Database(service.repository.database.path)),
        incident_service=service.incident_service)
    reopened_scenarios = CounterfactualService(investigation_service=reopened,
        repository=SqliteCounterfactualRepository(Database(counterfactual_env['counterfactual'].repository.database.path)))
    monkeypatch.setattr(investigation_routes, '_service', reopened)
    monkeypatch.setattr(counterfactual_routes, '_service', reopened_scenarios)
    count = len(prompts)
    assert client.get(f'/api/investigations/{identifier}').json()['report'] == original['report']
    assert client.get(f'/api/investigations/{revised_id}').json()['report'] == revised['report']
    assert client.get(f'/api/counterfactuals/{scenario["scenario_id"]}').json()['comparison'] == scenario['comparison']
    assert client.get('/api/settings').status_code == 200
    assert client.patch('/api/settings/anomaly', json={'threshold': 0}).status_code in (404, 405)
    assert reopened.repository.get(identifier) == before
    assert len(prompts) == count
