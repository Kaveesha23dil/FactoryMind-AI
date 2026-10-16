"""Portable contracts without Supabase, PostgreSQL servers, cloud keys or Gemini."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
import json
import sqlite3

import httpx
import pytest

from services.api.core import config, portable
from services.api.core.production import validate_configuration
from services.api.db import postgres
from services.api.services.supabase_storage import SupabaseObjectStore
from scripts.migrate_postgres import collect, redact


def render_settings(**changes):
    values = dict(app_env='production', deployment_target='render', persistence_backend='postgres',
        database_url='postgresql://operator:placeholder@pooler.example:5432/postgres?sslmode=require',
        upload_backend='supabase', upload_bucket='private-evidence', supabase_url='https://example.supabase.co',
        supabase_anon_key='public-key', supabase_service_key='server-only', portable_readers=['reader'], portable_writers=['writer'],
        portable_writes_enabled=False, job_dispatch='portable', investigation_async=False,
        investigation_timeout_seconds=20, investigation_max_retries=0, gemini_concurrency=1,
        ai_provider='google', ai_investigation_enabled=False, use_vertex_ai=False, cors_origins=['https://frontend.example'])
    return replace(config.settings, **{**values, **changes})


def test_render_profile_requires_no_google_credentials():
    validate_configuration(render_settings(google_api_key=None, gcp_project=None, auth_audience=None))


@pytest.mark.parametrize('changes', [dict(persistence_backend='sqlite'), dict(upload_backend='local'), dict(job_dispatch='thread'),
    dict(investigation_async=True), dict(investigation_max_retries=1), dict(investigation_timeout_seconds=90),
    dict(database_url='postgresql://example/database'),
    dict(database_url='postgresql://example:6543/database?sslmode=require'),
    dict(portable_readers=[], portable_writers=[]), dict(cors_origins=['*'])])
def test_render_profile_fails_closed(changes):
    with pytest.raises(RuntimeError):
        validate_configuration(render_settings(**changes))


def test_render_host_cannot_launch_development_security(monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(RuntimeError, match='production profile'):
        validate_configuration(replace(config.settings, app_env='development'))


def test_portable_auth_blocks_anonymous_unknown_users_and_reader_writes(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', render_settings())
    assert client.get('/api/dataset/summary', headers={'X-User-ID': 'writer'}).status_code == 401
    monkeypatch.setattr(portable, 'verify_user', lambda _: 'outsider')
    assert client.get('/api/dataset/summary', headers={'Authorization': 'Bearer signed'}).status_code == 403
    monkeypatch.setattr(portable, 'verify_user', lambda _: 'reader')
    headers = {'Authorization': 'Bearer signed', 'X-User-ID': 'writer'}
    assert client.get('/api/dataset/summary', headers=headers).status_code == 200
    assert client.post('/api/incidents', json={'record_id': 1}, headers=headers).status_code == 403
    assert client.post('/api/investigations/INV-X/process', headers=headers).status_code == 403
    assert client.get('/api/auth/session', headers=headers).json()['can_write'] is False


def test_presenter_ai_disabled_and_daily_budget_enforced(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', render_settings(portable_writes_enabled=True))
    monkeypatch.setattr(portable, 'verify_user', lambda _: 'writer')
    headers = {'Authorization': 'Bearer signed'}
    assert client.post('/api/investigations/INV-X/execute', headers=headers).status_code == 503
    monkeypatch.setattr(config, 'settings', render_settings(portable_writes_enabled=True, ai_investigation_enabled=True, google_api_key='sentinel'))
    monkeypatch.setattr(portable, 'consume_ai_budget', lambda _: False)
    response = client.post('/api/investigations/INV-X/execute', headers=headers)
    assert response.status_code == 429 and response.headers['retry-after']
    assert 'sentinel' not in response.text


def test_invalid_user_session_fails_closed(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', render_settings())
    monkeypatch.setattr(portable, 'verify_user', Mock(side_effect=RuntimeError('private provider details')))
    response = client.get('/api/incidents', headers={'Authorization': 'Bearer bad'})
    assert response.status_code == 401 and 'private provider details' not in response.text


def test_postgres_dialect_parameters_types_and_integrity_translation():
    assert postgres.sql_statement('SELECT * FROM incidents WHERE incident_id=?') == 'SELECT * FROM incidents WHERE incident_id=%s'
    assert postgres.sql_statement('INSERT OR IGNORE INTO investigation_evidence VALUES (?)').endswith('ON CONFLICT DO NOTHING')
    assert 'pg_advisory_xact_lock' in postgres.sql_statement('BEGIN IMMEDIATE')
    assert 'GREATEST' in postgres.sql_statement('MAX(expires_at,excluded.expires_at)')
    assert postgres.normalized({'created_at': datetime(2026, 10, 16, tzinfo=timezone.utc)})['created_at'].endswith('+00:00')
    assert postgres.Row({'c': 3})[0] == 3
    from psycopg import IntegrityError
    raw = Mock(); raw.execute.side_effect = IntegrityError('private database detail')
    with pytest.raises(sqlite3.IntegrityError, match='Relational constraint'):
        postgres.Connection(raw).execute('INSERT INTO incidents VALUES (?)', ('safe',))


def test_stale_executor_writes_are_fenced():
    raw = Mock(); raw.execute.return_value.fetchone.return_value = {'execution_token': 'new-owner'}
    handle = postgres.execution_owner.set(('INV-A', 'old-owner'))
    try:
        with pytest.raises(RuntimeError, match='stale writes rejected'):
            postgres.Connection(raw).execute('UPDATE investigations SET status=? WHERE investigation_id=?', ('completed', 'INV-A'))
        assert raw.execute.call_count == 1  # No stale UPDATE reached PostgreSQL.
    finally:
        postgres.execution_owner.reset(handle)


def test_execution_lock_prevents_duplicates_and_recovers_interrupted_owner(monkeypatch):
    raw = Mock(); raw.execute.return_value.fetchone.side_effect = [{'acquired': True}, None]
    @contextmanager
    def connection():
        yield raw
    monkeypatch.setattr(postgres, 'connect_raw', connection)
    with postgres.execution_lock('INV-A') as acquired:
        assert acquired and postgres.execution_owner.get()[0] == 'INV-A'
    assert postgres.execution_owner.get() is None
    assert any("status='running'" in call.args[0] for call in raw.execute.call_args_list)
    raw.reset_mock(); raw.execute.return_value.fetchone.side_effect = [{'acquired': False}]
    with postgres.execution_lock('INV-A') as acquired:
        assert not acquired and postgres.execution_owner.get() is None
    assert raw.execute.call_count == 1


def test_interrupted_partial_evidence_is_preserved_not_silently_replaced(monkeypatch):
    raw = Mock(); raw.execute.return_value.fetchone.side_effect = [{'acquired': True}, {'present': 1}]
    @contextmanager
    def connection():
        yield raw
    monkeypatch.setattr(postgres, 'connect_raw', connection)
    with postgres.execution_lock('INV-A') as acquired:
        assert not acquired
    statements = [call.args[0] for call in raw.execute.call_args_list]
    assert any("status='failed'" in statement for statement in statements)
    assert not any('DELETE' in statement for statement in statements)


def test_supabase_private_upload_signed_read_and_no_overwrite(monkeypatch):
    monkeypatch.setattr(config, 'settings', render_settings())
    calls = []
    def handle(request):
        calls.append(request)
        if '/bucket/' in request.url.path:
            return httpx.Response(200, json={'public': False})
        if request.method == 'POST' and '/object/sign/' in request.url.path:
            assert json.loads(request.content)['expiresIn'] == 60
            return httpx.Response(200, json={'signedURL': '/object/sign/private-evidence/uploads/IMG-A.png?token=short-lived'})
        if request.method == 'GET':
            return httpx.Response(200, content=b'bounded-image')
        return httpx.Response(200, json={})
    store = SupabaseObjectStore(httpx.Client(transport=httpx.MockTransport(handle)))
    store.write('IMG-A.png', b'image', 'image/png')
    assert store.read('IMG-A.png') == b'bounded-image'
    assert calls[1].headers['x-upsert'] == 'false'
    assert 'Authorization' not in calls[-1].headers  # Signed read has no service key.
    with pytest.raises(ValueError):
        store.signed_url('IMG-A.png', 3600)
    with pytest.raises(ValueError):
        store.write('../escape.png', b'image', 'image/png')


def test_supabase_public_bucket_is_rejected(monkeypatch):
    monkeypatch.setattr(config, 'settings', render_settings())
    store = SupabaseObjectStore(httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'public': True}))))
    with pytest.raises(RuntimeError, match='not private'):
        store.check()


def test_signed_download_transport_errors_do_not_leak_tokens(monkeypatch):
    monkeypatch.setattr(config, 'settings', render_settings())
    client = Mock(); client.stream.side_effect = httpx.ConnectError('https://storage.example?token=PRIVATE')
    store = SupabaseObjectStore(client)
    monkeypatch.setattr(store, 'signed_url', lambda _: 'https://storage.example?token=PRIVATE')
    with pytest.raises(RuntimeError) as failure:
        store.read('IMG-A.png')
    assert 'PRIVATE' not in str(failure.value) and failure.value.__suppress_context__


def test_reviewed_image_copy_preserves_refs_and_rejects_conflicting_objects(tmp_path):
    from PIL import Image
    from scripts.migrate_postgres import copy_images
    path = tmp_path / 'IMG-A.png'
    Image.new('RGB', (1, 1)).save(path)
    records = [{'storage_ref': path.name, 'mime_type': 'image/png', 'storage_backend': 'local'}]
    store = Mock(); store.exists.return_value = False
    copy_images(records, tmp_path, store)
    assert records[0]['storage_ref'] == path.name and records[0]['storage_backend'] == 'supabase'
    store.write.assert_called_once()
    store.exists.return_value = True; store.read.return_value = b'different'
    with pytest.raises(ValueError, match='not overwritten'):
        copy_images(records, tmp_path, store)


def test_migration_collect_is_read_only_and_preserves_ids(investigation_env, anomaly_ids):
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    job = investigation_env.start_investigation(incident['incident_id'])
    # Test fixture uses two SQLite files; copy its incident rows into the investigation snapshot.
    with investigation_env.incident_service.repository.database.connect() as source:
        row = dict(source.execute('SELECT * FROM incidents').fetchone())
    with investigation_env.repository.database.connect() as connection:
        keys = list(row)
        connection.execute(f'INSERT INTO incidents ({",".join(keys)}) VALUES ({",".join("?" for _ in keys)})', list(row.values()))
        connection.commit()
        before = connection.total_changes
        records = collect(connection, {job['investigation_id']})
        assert connection.total_changes == before
    assert records['investigations'][0]['investigation_id'] == job['investigation_id']
    assert records['investigation_evidence']
    assert records['incidents'][0]['note'] is None
    assert redact('Bearer SECRET-TOKEN') == '[REDACTED]'


def test_versioned_schema_has_foreign_keys_indexes_and_private_schema():
    sql = (Path(__file__).resolve().parents[1] / 'db/migrations/001_portable.sql').read_text()
    assert 'PRIMARY KEY(investigation_id,evidence_id)' in sql
    assert 'REFERENCES investigations(investigation_id,incident_id)' in sql
    assert 'execution_token' in sql and 'TIMESTAMPTZ' in sql
    assert 'REVOKE ALL ON SCHEMA factorymind FROM PUBLIC' in sql


def test_schema_dry_run_guard_cannot_call_a_database(monkeypatch, capsys):
    from scripts import migrate_postgres
    monkeypatch.setattr('sys.argv', ['migrate_postgres', 'schema'])
    # Both schema execution and the connection entry point are replaced, so this
    # test is incapable of executing DDL even if the dry-run guard regresses.
    execute = Mock(side_effect=AssertionError('DDL must not run'))
    connect = Mock(side_effect=AssertionError('Database must not connect'))
    monkeypatch.setattr(migrate_postgres, 'migrate_schema', execute)
    monkeypatch.setattr(migrate_postgres, 'connect_raw', connect)
    migrate_postgres.main()
    execute.assert_not_called(); connect.assert_not_called()
    assert 'Dry run' in capsys.readouterr().out


from services.api.tests.test_investigations import investigation_env, anomaly_ids  # noqa: E402,F401
from services.api.tests.test_visual_inspection import visual_env, PNG_BYTES  # noqa: E402,F401


def test_supabase_upload_metadata_and_content_use_the_portable_store(visual_env, anomaly_ids, monkeypatch):
    from services.api.services import object_storage
    service = visual_env
    incident = service.incident_service.create_incident(anomaly_ids[0])
    store = Mock(); store.read.return_value = PNG_BYTES
    monkeypatch.setattr(object_storage, 'object_store', lambda: store)
    monkeypatch.setattr(config, 'settings', replace(config.settings, upload_backend='supabase'))
    image = service.store(incident['incident_id'], filename='benchmark.png', mime_type='image/png', data=PNG_BYTES)
    assert service.get(image['image_id'])['storage_backend'] == 'supabase'
    assert service.content_bytes(image['image_id']) == PNG_BYTES
    store.write.assert_called_once()


def test_visual_evidence_cannot_cross_incidents(visual_env, anomaly_ids):
    from services.api.services.visual_evidence_service import VisualEvidenceError
    first = visual_env.incident_service.create_incident(anomaly_ids[0])
    second = visual_env.incident_service.create_incident(anomaly_ids[1])
    job = visual_env.investigations.start_investigation(second['incident_id'])
    image = visual_env.store(first['incident_id'], filename='fixture.png', mime_type='image/png', data=PNG_BYTES)
    with pytest.raises(VisualEvidenceError, match='same incident'):
        visual_env.analyze(image['image_id'], job['investigation_id'])
    assert visual_env.get(image['image_id'])['status'] == 'stored'


def test_completed_portable_execution_does_not_claim_a_new_run(client, investigation_env, anomaly_ids, monkeypatch):
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    job = investigation_env.start_investigation(incident['incident_id'])
    before = investigation_env.get(job['investigation_id'])
    monkeypatch.setattr(config, 'settings', replace(config.settings, deployment_target='render'))
    investigation_env._runtime_factory = Mock(side_effect=AssertionError('No new model execution'))
    response = client.post(f'/api/investigations/{job["investigation_id"]}/execute')
    assert response.status_code == 200 and response.json()['executed'] is False
    assert investigation_env.get(job['investigation_id']) == before
