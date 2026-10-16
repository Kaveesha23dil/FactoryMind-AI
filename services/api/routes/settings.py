"""Read-only system visibility under existing production authentication."""
from datetime import datetime, timezone
import hashlib

from fastapi import APIRouter, Request
from services.api.core import config
from services.api.agents.runtime import InvestigationProviderError
from services.api.routes.investigations import get_service
from services.api.services.anomaly_engine import get_engine
from services.api.services.knowledge_repository import get_knowledge_repository
from services.api.schemas.settings import SettingsResponse, SystemResponse

router = APIRouter(prefix='/api/settings', tags=['settings'])


def _usage(jobs):
    entries = [entry for job in jobs for entry in (job.get('report') or {}).get('usage', []) if isinstance(entry, dict)]
    def total(key):
        values = [entry[key] for entry in entries if isinstance(entry.get(key), int) and not isinstance(entry[key], bool) and entry[key] >= 0]
        return sum(values) if values else None
    return {'requests': total('request_count'), 'input_tokens': total('input_tokens'), 'output_tokens': total('output_tokens'),
            'scope': 'Recorded usage in the latest 100 completed reports only; excludes unrecorded failed/vision requests. Not provider quota or billing totals.'}


@router.get('', response_model=SettingsResponse)
def settings(request: Request):
    s = config.settings
    engine = get_engine()
    service = get_service()
    _, jobs = service.repository.list_all(100, 0, 'completed')
    _, failed = service.repository.list_all(1, 0, 'failed')
    knowledge = get_knowledge_repository()
    threshold = engine.detector.anomaly_score_threshold
    database_provider = {'sqlite': 'SQLite', 'firestore': 'Firestore', 'postgres': 'PostgreSQL'}[s.persistence_backend]
    image_provider = {'local': 'Local files', 'gcs': 'Private Google Cloud Storage', 'supabase': 'Private Supabase Storage'}[s.upload_backend]
    portable = s.app_env == 'production' and s.deployment_target == 'render'
    role = ('Presenter' if request.state.principal in s.portable_writers else 'Viewer') if portable else None
    return {
        'workspace': {'workspace': 'FactoryMind workspace', 'application': 'FactoryMind AI', 'team': 'AetherForge', 'environment': s.app_env},
        'ai': {'provider': s.ai_provider, 'model': s.gemini_model, 'enabled': s.ai_investigation_enabled,
               'credentials_configured': bool(s.google_api_key or (s.use_vertex_ai and s.gcp_project and s.gcp_location)),
               'timeout_seconds': s.investigation_timeout_seconds, 'max_retries': max(0, min(5, s.investigation_max_retries)),
               'max_concurrent_requests': s.gemini_concurrency, 'max_concurrent_investigations': None,
               'max_model_calls_per_agent': s.gemini_max_model_calls, 'cache_enabled': s.investigation_cache_enabled,
               'cooldown_until': service._provider_cooldown(),
               'latest_error_category': InvestigationProviderError(failed[0].get('error') or '').category if failed else None,
               'last_success_at': jobs[0].get('completed_at') if jobs else None, 'usage': _usage(jobs)},
        'anomaly': {'algorithm': engine.detector.algorithm, 'threshold': threshold, 'feature_z_threshold': engine.detector.feature_z_threshold,
                    'severity_bands': {key: [round(low * threshold, 4), round(high * threshold, 4) if high is not None else None] for key, (low, high) in config.SEVERITY_MULTIPLIERS.items()},
                    'train_count': len(engine.train_frame), 'validation_count': len(engine.validation_frame), 'test_count': len(engine.test_frame),
                    'split_seed': config.RANDOM_SEED, 'last_evaluation_at': None},
        'data': {'name': config.DATASET_NAME, 'origin': config.DATASET_SOURCE, 'classification': 'Synthetic benchmark',
                 'records': engine.summary()['analyzed_sample_count'], 'version': hashlib.sha256(s.dataset_path.read_bytes()).hexdigest()[:12],
                 'last_refresh_at': None, 'database_provider': database_provider,
                 'image_provider': image_provider,
                 'document_count': len({p.document_id for p in knowledge.passages}), 'passage_count': len(knowledge.passages),
                 'document_status': 'Packaged synthetic/general reference corpus; indexed for deterministic retrieval', 'storage_usage_bytes': None},
        'security': {'authentication': 'Verified Supabase user' if portable else ('Verified Google service identity' if s.app_env == 'production' else 'Unauthenticated local development'),
                     'role': role, 'session': 'Expiring Supabase user session' if portable else 'End-user sessions are not implemented', 'access_management': 'Explicit server-side members of one shared demo workspace' if portable else 'End-user role management is not configured',
                     'operational_settings': 'Deployment administrator only; no runtime configuration write API'},
    }


@router.get('/system', response_model=SystemResponse)
def system(request: Request):
    database = 'unknown'
    try:
        get_service().repository.get('__settings_health_probe__')
        database = 'connected'
    except Exception:
        database = 'unavailable'
    storage = 'unknown'
    if config.settings.upload_backend in ('gcs', 'supabase'):
        try:
            from services.api.services.object_storage import object_store
            object_store().check()
            storage = 'connected'
        except Exception:
            storage = 'unavailable'
    return {'application_version': request.app.version, 'api_status': 'connected', 'database_status': database,
            'image_storage_status': storage, 'gemini_status': 'Not probed; rendering Settings never generates content',
            'environment': config.settings.app_env, 'checked_at': datetime.now(timezone.utc).isoformat()}
