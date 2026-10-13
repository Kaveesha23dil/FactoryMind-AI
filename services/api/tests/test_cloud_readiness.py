"""Cloud contracts tested without credentials, cloud resources, or live Gemini."""
import copy
import io
import threading
import time
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.api.core import config, security
from services.api.core.production import validate_configuration
from services.api.services import firestore_repository as fs
from services.api.tests.test_investigations import investigation_env, anomaly_ids


def production(**changes):
    values = dict(app_env='production', persistence_backend='firestore', upload_backend='gcs', upload_bucket='private-test',
        gcp_project='test-project', auth_audience='https://backend.run.app', api_callers=['web@example.com'],
        worker_callers=['tasks@example.com'], job_dispatch='tasks', investigation_async=True,
        tasks_queue='projects/test/locations/test/queues/test', tasks_target='https://backend.run.app',
        tasks_service_account='tasks@example.com', ai_provider='google', ai_investigation_enabled=False,
        investigation_timeout_seconds=40, investigation_max_retries=1)
    return replace(config.settings, **{**values, **changes})


def test_production_profile_is_valid():
    validate_configuration(production())


@pytest.mark.parametrize('change', [dict(persistence_backend='sqlite'), dict(upload_backend='local'),
    dict(job_dispatch='thread'), dict(auth_audience=None), dict(api_callers=[]), dict(cors_origins=['*']),
    dict(ai_provider='scripted'), dict(investigation_timeout_seconds=90, investigation_max_retries=3),
    dict(tasks_queue=None)])
def test_unsafe_production_configuration_is_rejected(change):
    with pytest.raises(RuntimeError):
        validate_configuration(production(**change))


def test_cloud_run_cannot_use_development_profile(monkeypatch):
    monkeypatch.setenv('K_SERVICE', 'test-service')
    with pytest.raises(RuntimeError, match='production profile'):
        validate_configuration(replace(config.settings, app_env='development'))


def test_health_and_readiness_do_not_call_models(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', replace(config.settings, app_env='production'))
    assert client.get('/healthz').status_code == 200
    assert client.get('/readyz').status_code == 200
    assert client.get('/api/incidents').status_code == 401


def test_oidc_roles_protect_all_api_writes(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', production())
    monkeypatch.setattr(security.id_token, 'verify_oauth2_token', lambda *args: {'email':'intruder@example.com','email_verified':True})
    assert client.post('/api/incidents', json={'record_id':1}, headers={'Authorization':'Bearer token'}).status_code == 403
    monkeypatch.setattr(security.id_token, 'verify_oauth2_token', lambda *args: {'email':'web@example.com','email_verified':True})
    assert client.post('/api/investigations/INV-NOPE/process', headers={'Authorization':'Bearer token'}).status_code == 403
    monkeypatch.setattr(security.id_token, 'verify_oauth2_token', lambda *args: {'email':'tasks@example.com','email_verified':True})
    assert client.post('/api/incidents', json={'record_id':1}, headers={'Authorization':'Bearer token'}).status_code == 403


def test_invalid_oidc_and_unverified_email_are_rejected(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', production())
    monkeypatch.setattr(security.id_token, 'verify_oauth2_token', Mock(side_effect=ValueError('bad token')))
    assert client.get('/api/incidents', headers={'Authorization':'Bearer token'}).status_code == 401
    monkeypatch.setattr(security.id_token, 'verify_oauth2_token', lambda *args: {'email':'web@example.com','email_verified':False})
    assert client.get('/api/incidents', headers={'Authorization':'Bearer token'}).status_code == 403


class Snapshot:
    def __init__(self, value):
        self.exists = value is not None
        self.value = copy.deepcopy(value)
    def to_dict(self):
        return copy.deepcopy(self.value)


class Ref:
    def __init__(self, db, path):
        self.db, self.path = db, path
    def get(self, transaction=None, **kwargs):
        if transaction:
            assert not transaction.writes, 'Firestore forbids reading after writing in a transaction'
        return Snapshot(self.db.data.get(self.path))
    def create(self, data, **kwargs):
        assert self.path not in self.db.data
        self.db.data[self.path] = copy.deepcopy(data)
    def collection(self, name):
        return Collection(self.db, self.path+'/'+name)


class Collection:
    def __init__(self, db, path, filter=None, limit=None):
        self.db, self.path, self.filter, self.maximum = db, path, filter, limit
    def document(self, name):
        return Ref(self.db, self.path+'/'+name)
    def limit(self, value):
        return Collection(self.db, self.path, self.filter, value)
    def where(self, filter):
        return Collection(self.db, self.path, filter, self.maximum)
    def stream(self, **kwargs):
        rows = [value for path, value in self.db.data.items() if path.rsplit('/',1)[0] == self.path]
        if self.filter:
            rows = [r for r in rows if r.get(self.filter.field_path) == self.filter.value]
        return iter([Snapshot(row) for row in rows[:self.maximum]])


class Transaction:
    def __init__(self, db):
        self.db, self.writes = db, []
    def set(self, ref, value):
        self.writes.append((ref.path, copy.deepcopy(value), False))
    def create(self, ref, value):
        assert ref.path not in self.db.data
        self.writes.append((ref.path, copy.deepcopy(value), False))
    def update(self, ref, value):
        self.writes.append((ref.path, copy.deepcopy(value), True))
    def commit(self):
        for path, value, merge in self.writes:
            self.db.data[path] = {**self.db.data[path], **value} if merge else value


class FakeFirestore:
    def __init__(self):
        self.data = {}
        self.lock = threading.RLock()
    def collection(self, name):
        return Collection(self, name)


@pytest.fixture
def firestore(monkeypatch):
    db = FakeFirestore()
    def transaction(self, callback):
        with db.lock:
            tx = Transaction(db)
            result = callback(tx)
            tx.commit()
            return result
    monkeypatch.setattr(fs.FirestoreRepository, '_tx', transaction)
    monkeypatch.setattr(fs, 'client', lambda: db)
    return db


def test_firestore_incident_transactions_and_events(firestore):
    import sqlite3
    repo = fs.FirestoreIncidentRepository(firestore)
    record = {'incident_id':'INC-A', 'record_id':1, 'algorithm':'test', 'status':'open', 'created_at':'test'}
    event = {'incident_id':'INC-A','status':'open','timestamp':'1','note':None}
    repo.insert(record, event)
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert({**record, 'incident_id':'INC-B'}, event)
    repo.update_status('INC-A', 'resolved', {**event, 'status':'resolved', 'expected_status':'open', 'timestamp':'2'})
    assert repo.find_active(1,'test') is None and len(repo.events('INC-A')) == 2
    repo.insert({**record, 'incident_id':'INC-B'}, event)
    with pytest.raises(Exception):
        repo.update_status('INC-A','open',{**event,'expected_status':'resolved'})


def test_firestore_job_claims_and_immutable_evidence(firestore):
    import sqlite3
    repo = fs.FirestoreInvestigationRepository(firestore)
    job = {'investigation_id':'INV-A', 'incident_id':'INC-A', 'status':'queued','created_at':'1','stage_history':[], 'agent_activity':[]}
    repo.insert(job)
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert({**job,'investigation_id':'INV-B'})
    assert repo.claim('INV-A') and not repo.claim('INV-A')
    repo.update('INV-A', lease_expires_at=0)
    assert repo.claim('INV-A')
    repo.append_stage('INV-A', {'stage':'collecting_evidence','timestamp':'1'})
    repo.upsert_agent('INV-A', {'agent':'sensor_agent','status':'running'})
    repo.upsert_agent('INV-A', {'agent':'sensor_agent','status':'completed'})
    record = {'investigation_id':'INV-A','evidence_id':'EV-SENSOR-001','observation':'original'}
    repo.save_evidence([record])
    repo.save_evidence([{**record,'observation':'altered'}])
    assert repo.get_evidence('INV-A')[0]['observation'] == 'original'
    assert len(repo.get('INV-A')['agent_activity']) == 1


def test_firestore_counterfactual_and_image_metadata(firestore):
    cf = fs.FirestoreCounterfactualRepository(firestore)
    cf.insert({'scenario_id':'CFT-A','original_investigation_id':'INV-A','created_at':'1','status':'running'})
    cf.update('CFT-A', status='failed')
    assert cf.list_for_investigation('INV-A')[0]['status'] == 'failed'
    images = fs.FirestoreVisualRepository(firestore)
    images.insert({'image_id':'IMG-A','incident_id':'INC-A','created_at':'1'})
    assert images.list_for_incident('INC-A')[0]['image_id'] == 'IMG-A'


def test_firestore_request_control_is_shared(firestore, monkeypatch):
    from services.api.agents import firestore_control
    monkeypatch.setattr(config, 'settings', replace(config.settings, gemini_concurrency=1))
    assert firestore_control.acquire('one', 30)
    assert not firestore_control.acquire('two', 30)
    firestore_control.release('one')
    assert firestore_control.acquire('two', 30)
    firestore_control.save('model', 'RPD', 100)
    assert firestore_control.cooldown('model')[0] == 'RPD'


def test_gcs_private_objects_and_size_validation():
    from services.api.services.object_storage import GcsObjectStore
    blob = Mock(size=1, generation=2)
    blob.download_as_bytes.return_value = b'x'
    bucket = Mock()
    bucket.blob.return_value = blob
    store = GcsObjectStore(bucket)
    store.write('IMG-A.png', b'x', 'image/png')
    blob.upload_from_string.assert_called_once_with(b'x', content_type='image/png', if_generation_match=0, timeout=30)
    assert store.read('IMG-A.png') == b'x'
    with pytest.raises(ValueError):
        store.read('../escape.png')
    blob.size = config.VISUAL_MAX_IMAGE_BYTES+1
    with pytest.raises(ValueError):
        store.read('IMG-A.png')


def test_production_image_validation():
    from PIL import Image
    from services.api.services.image_utils import verify_image
    data = io.BytesIO()
    Image.new('RGB',(1,1)).save(data, format='PNG')
    verify_image(data.getvalue())
    with pytest.raises(Exception):
        verify_image(b'\x89PNG\r\n\x1a\n')


def test_tasks_use_oidc_not_embedded_secrets(monkeypatch):
    from services.api.services.task_dispatch import dispatch
    monkeypatch.setattr(config, 'settings', production())
    task_client = Mock()
    dispatch('INV-A', task_client)
    task = task_client.create_task.call_args.kwargs['task']
    assert task['http_request']['oidc_token']['service_account_email'] == 'tasks@example.com'
    assert task['http_request']['url'].endswith('/INV-A/process')
    assert 'headers' not in task['http_request']


def test_restricted_prepared_context_survives_restart(investigation_env, anomaly_ids):
    from services.api.agents.orchestrator import PreparedContext
    from services.api.services.investigation_repository import SqliteInvestigationRepository
    from services.api.db.database import Database
    incident = investigation_env.incident_service.create_incident(anomaly_ids[0])
    job = investigation_env.create_queued_investigation(incident['incident_id'])
    from dataclasses import asdict
    prepared = PreparedContext({}, {'measurements':{}}, {}, {}, [], [], {'excluded_evidence_ids':['EV-SENSOR-001']})
    investigation_env.repository.update(job['investigation_id'], prepared_context=asdict(prepared))
    restarted = SqliteInvestigationRepository(Database(investigation_env.repository.database.path))
    loaded = PreparedContext(**restarted.get(job['investigation_id'])['prepared_context'])
    assert loaded.counterfactual['excluded_evidence_ids'] == ['EV-SENSOR-001'] and loaded.evidence_records == []
