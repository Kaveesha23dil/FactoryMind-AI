"""Fail closed rather than launching Cloud Run with ephemeral or public writes."""
from services.api.core import config
import os


def validate_configuration(settings=None):
    s = settings or config.settings
    if s.app_env not in ('development', 'production'):
        raise RuntimeError('Unsupported application environment')
    if os.environ.get('K_SERVICE') and s.app_env != 'production':
        raise RuntimeError('Cloud Run requires the production profile')
    if os.environ.get('RENDER') and s.app_env != 'production':
        raise RuntimeError('Render requires the production profile')
    if s.persistence_backend not in ('sqlite', 'firestore', 'postgres') or s.upload_backend not in ('local', 'gcs', 'supabase'):
        raise RuntimeError('Unsupported storage backend')
    if s.job_dispatch not in ('thread', 'tasks', 'portable'):
        raise RuntimeError('Unsupported investigation dispatch backend')
    if s.app_env != 'production':
        return
    if s.deployment_target == 'render':
        from urllib.parse import urlsplit, parse_qs
        database = urlsplit(s.database_url or '')
        valid = (s.persistence_backend == 'postgres' and database.scheme in ('postgres', 'postgresql') and
            database.hostname and database.port in (None, 5432) and parse_qs(database.query).get('sslmode', [''])[0] in ('require', 'verify-full') and
            s.upload_backend == 'supabase' and bool(s.upload_bucket and s.supabase_service_key and s.supabase_anon_key) and
            s.supabase_url and s.supabase_url.startswith('https://') and
            s.job_dispatch == 'portable' and not s.investigation_async and
            bool(s.portable_readers or s.portable_writers) and '*' not in s.cors_origins and
            s.investigation_max_retries == 0 and 1 <= s.investigation_timeout_seconds <= 20 and
            s.gemini_concurrency == 1 and s.ai_provider == 'google' and not s.use_vertex_ai and
            (not s.ai_investigation_enabled or bool(s.google_api_key)))
        if not valid:
            raise RuntimeError('Portable production requires SSL PostgreSQL, private Supabase storage/auth, explicit members and bounded synchronous execution; check portable environment template')
        return
    if s.deployment_target != 'gcp':
        raise RuntimeError('Unsupported production deployment target')
    checks = {
        'production requires Firestore': s.persistence_backend == 'firestore',
        'production requires a private GCS upload bucket': s.upload_backend == 'gcs' and bool(s.upload_bucket),
        'production requires project and exact JWT audience': bool(s.gcp_project and s.auth_audience and s.auth_audience.startswith('https://')),
        'production requires allowed API and worker principals': bool(s.api_callers and s.worker_callers),
        'wildcard CORS is forbidden': '*' not in s.cors_origins,
        'production requires durable Cloud Tasks dispatch': s.job_dispatch == 'tasks' and s.investigation_async,
        'Cloud Tasks configuration is incomplete': bool(s.tasks_queue and s.tasks_target and s.tasks_service_account),
        'Cloud Tasks deadline must be within 30 minutes': 60 <= s.tasks_deadline <= 1800,
        'agent budget exceeds task deadline': 6 * ((max(0, min(5, s.investigation_max_retries)) + 1) * s.investigation_timeout_seconds + max(0, min(5, s.investigation_max_retries)) * 61) + 30 < s.tasks_deadline,
        'production cannot use scripted AI': s.ai_provider == 'google',
        'Gemini credentials are not configured': not s.ai_investigation_enabled or bool(s.google_api_key or (s.use_vertex_ai and s.gcp_location)),
    }
    for reason, valid in checks.items():
        if not valid:
            raise RuntimeError(reason)
