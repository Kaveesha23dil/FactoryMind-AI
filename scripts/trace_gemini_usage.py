"""Reproducible mocked ADK request trace; never contacts Gemini or changes dev data."""
import base64
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.agents.model import ScriptedLlm
from services.api.agents.runtime import AdkRuntime
from services.api.core import config
from services.api.db.database import Database
from services.api.routes import incidents as incident_routes
from services.api.services.anomaly_engine import get_engine
from services.api.services.incident_service import IncidentService, SqliteIncidentRepository
from services.api.services.investigation_service import InvestigationService
from services.api.services.investigation_repository import SqliteInvestigationRepository
from services.api.services.counterfactual_service import CounterfactualService
from services.api.services.counterfactual_repository import SqliteCounterfactualRepository
from services.api.services.visual_evidence_service import VisualEvidenceService
from services.api.services.visual_repository import SqliteVisualEvidenceRepository
from services.api.tests.conftest import default_scripted_responses

turns = []
prompts = []


class TracedModel(ScriptedLlm):
    agent_name: str = ''

    async def generate_content_async(self, llm_request, stream=False):
        turns.append(self.agent_name)
        async for response in super().generate_content_async(llm_request, stream):
            yield response


class TracedRuntime(AdkRuntime):
    def _model_for(self, spec):
        return TracedModel(response_text=self.scripted_responses[spec.name], agent_name=spec.name)

    async def run(self, spec, prompt, image_parts=None):
        prompts.append({'agent': spec.name, 'prompt_characters': len(prompt)})
        return await super().run(spec, prompt, image_parts)


def main():
    result = {'measurement': 'mocked ADK model invocations, not live HTTP/billing measurements', 'workloads': []}
    with tempfile.TemporaryDirectory(prefix='factorymind-usage-') as root:
        root = Path(root)
        config.settings = replace(config.settings, ai_provider='scripted', database_path=root/'trace.db',
            investigation_async=False, investigation_cache_enabled=False)
        database = Database()
        incidents = IncidentService(SqliteIncidentRepository(database))
        incidents.initialize()
        incident_routes._service = incidents
        runtime_factory = lambda: TracedRuntime('scripted', config.settings.gemini_model, default_scripted_responses())
        investigations = InvestigationService(SqliteInvestigationRepository(database), incidents, runtime_factory)
        incident = incidents.create_incident(get_engine()._anomalies[0]['record_id'])

        def trace(label, action):
            before = len(turns)
            before_prompts = len(prompts)
            output = action()
            selected = turns[before:]
            result['workloads'].append({'name': label, 'model_invocations': len(selected),
                'agents': selected, 'prompt_characters': sum(p['prompt_characters'] for p in prompts[before_prompts:])})
            return output

        trace('fresh_investigation', lambda: investigations.start_investigation(incident['incident_id']))
        trace('unchanged_repeat_cache_disabled_baseline', lambda: investigations.start_investigation(incident['incident_id']))
        config.settings = replace(config.settings, investigation_cache_enabled=True)
        trace('unchanged_repeat_cache_enabled', lambda: investigations.start_investigation(incident['incident_id']))
        original = trace('explicit_rerun', lambda: investigations.start_investigation(incident['incident_id'], force_rerun=True))
        counterfactual = CounterfactualService(investigations, SqliteCounterfactualRepository(database))
        scenario = trace('counterfactual_excluding_sensor', lambda: counterfactual.create_scenario(
            original['investigation_id'], ['EV-SENSOR-001'], 'Exclude this measurement in a mocked request trace.'))
        assert scenario['status'] == 'completed'
        visual = VisualEvidenceService(incidents, investigations, SqliteVisualEvidenceRepository(database), root/'images')
        data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
        image = visual.store(incident['incident_id'], 'mock-inspection.png', 'image/png', data)
        trace('visual_inspection', lambda: visual.analyze(image['image_id'], runtime_factory=runtime_factory))
    output_path = Path(__file__).resolve().parents[1]/'reports'/'gemini-usage-trace.json'
    output_path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
