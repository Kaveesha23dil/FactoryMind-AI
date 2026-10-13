"""Content-addressed report reuse; counterfactual conclusions never enter it."""
import hashlib
import json
from pathlib import Path

from services.api.agents import sensor_agent, knowledge_agent, investigation_agent, critic_agent
from services.api.agents.orchestrator import _knowledge_query
from services.api.core import config
from services.api.tools.anomaly_tools import get_anomaly_analysis, get_baseline_statistics
from services.api.tools.knowledge_tools import retrieve_knowledge


def report_key(incident):
    anomaly = get_anomaly_analysis(incident['incident_id'])
    specs = [sensor_agent.SPEC, knowledge_agent.SPEC, investigation_agent.SPEC, critic_agent.SPEC]
    # Hash implementation bytes as well as the explicit prompt version, so a
    # forgotten version bump cannot reuse a report after a validator change.
    paths = [*Path(config.API_ROOT / 'agents').glob('*.py'),
             *Path(config.API_ROOT / 'tools').glob('*.py'),
             Path(__file__), config.API_ROOT / 'services' / 'anomaly_detector.py']
    implementation = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(paths))).hexdigest()
    payload = {'incident': {k: incident.get(k) for k in ('incident_id', 'record_id', 'machine_type',
                    'product_id', 'source_measurements', 'algorithm', 'status', 'created_at')},
        'anomaly': anomaly, 'baselines': get_baseline_statistics(incident['machine_type']),
        'passages': retrieve_knowledge(_knowledge_query(anomaly), config.KNOWLEDGE_TOP_K),
        'provider': config.settings.ai_provider, 'model': config.settings.gemini_model,
        'prompt_version': config.settings.prompt_version, 'implementation': implementation,
        'instructions': [s.instruction for s in specs],
        'schemas': [s.output_schema.model_json_schema() for s in specs],
        'configuration': {'top_k': config.KNOWLEDGE_TOP_K,
            'max_hypotheses': config.settings.investigation_max_hypotheses,
            'max_retries': config.settings.investigation_max_retries,
            'max_llm_calls': config.settings.gemini_max_model_calls,
            'timeout': config.settings.investigation_timeout_seconds}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def evidence_digest(records):
    rows = [{k: r.get(k) for k in ('evidence_id', 'evidence_type', 'source', 'observation',
                                  'value', 'units', 'provenance', 'payload')} for r in records]
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda r: r['evidence_id']), sort_keys=True).encode()).hexdigest()


def report_digest(report):
    content = {k: value for k, value in report.items() if k != 'cache_report_digest'}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
