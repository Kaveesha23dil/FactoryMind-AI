"""Native Firestore adapters for the existing repository contracts.

Single-field queries plus demo-scale in-memory sorting preserve the existing
offset/count APIs. Transactions own duplicate prevention and job claims.
"""
import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from services.api.core import config
from services.api.services.incident_service import InvalidTransitionError


def now():
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def client():
    from google.cloud import firestore
    return firestore.Client(project=config.settings.gcp_project, database=config.settings.firestore_database)


class FirestoreRepository:
    def __init__(self, kind, key, db=None):
        self.client = db or client()
        self.kind, self.key = kind, key
        self.collection = self.client.collection(f'{config.settings.firestore_prefix}_{kind}')

    def initialize(self):
        list(self.collection.limit(1).stream(timeout=5, retry=None))

    def _tx(self, callback):
        from google.cloud import firestore
        return firestore.transactional(callback)(self.client.transaction())

    @staticmethod
    def _clean(data):
        encoded = json.dumps(data, allow_nan=False)
        if len(encoded.encode()) > 850_000:
            raise ValueError('Record exceeds the supported Firestore document budget')
        return json.loads(encoded)

    def _ref(self, identifier):
        if not identifier or '/' in str(identifier):
            raise ValueError('Invalid record identifier')
        return self.collection.document(str(identifier))

    def get(self, identifier):
        snapshot = self._ref(identifier).get(timeout=10)
        return snapshot.to_dict() if snapshot.exists else None

    def insert(self, record):
        self._ref(record[self.key]).create(self._clean(record), timeout=10)

    def _mutate(self, identifier, callback):
        ref = self._ref(identifier)
        def operation(tx):
            snapshot = ref.get(transaction=tx)
            if not snapshot.exists:
                raise InvalidTransitionError('Record no longer exists')
            value = callback(snapshot.to_dict())
            tx.set(ref, self._clean(value))
            return value
        return self._tx(operation)

    def update(self, identifier, **fields):
        fields.setdefault('updated_at', now())
        return self._mutate(identifier, lambda record: {**record, **fields})

    def _rows(self, field=None, value=None):
        query = self.collection
        if field:
            from google.cloud.firestore_v1.base_query import FieldFilter
            query = query.where(filter=FieldFilter(field, '==', value))
        return [snapshot.to_dict() for snapshot in query.stream(timeout=15)]

    @staticmethod
    def _page(rows, limit, offset):
        rows.sort(key=lambda r: (r.get('created_at', ''), str(r)), reverse=True)
        return len(rows), rows[offset:offset+limit]


class FirestoreIncidentRepository(FirestoreRepository):
    def __init__(self, db=None):
        super().__init__('incidents', 'incident_id', db)

    def _active_ref(self, record_id, algorithm):
        key = hashlib.sha256(f'{record_id}:{algorithm}'.encode()).hexdigest()
        return self.client.collection(f'{config.settings.firestore_prefix}_incident_locks').document(key)

    def insert(self, incident, event):
        lock = self._active_ref(incident['record_id'], incident['algorithm'])
        ref = self._ref(incident['incident_id'])
        def operation(tx):
            snapshot = lock.get(transaction=tx)
            previous = snapshot.to_dict() if snapshot.exists else {}
            if previous.get('incident_id'):
                active = self._ref(previous['incident_id']).get(transaction=tx)
                if active.exists and active.to_dict()['status'] != 'resolved':
                    raise sqlite3.IntegrityError('Active incident exists')
            tx.create(ref, self._clean(incident))
            tx.set(lock, {'incident_id': incident['incident_id']})
            tx.create(ref.collection('events').document(uuid.uuid4().hex), self._clean(event))
        self._tx(operation)

    def find_active(self, record_id, algorithm):
        snapshot = self._active_ref(record_id, algorithm).get(timeout=10)
        if not snapshot.exists:
            return None
        record = self.get(snapshot.to_dict()['incident_id'])
        return record if record and record['status'] != 'resolved' else None

    def list(self, limit, offset, status=None, severity=None):
        rows = self._rows('status', status) if status else self._rows()
        return self._page([r for r in rows if not severity or r['severity'] == severity], limit, offset)

    def update_status(self, identifier, status, event):
        ref = self._ref(identifier)
        current = self.get(identifier)
        lock = self._active_ref(current['record_id'], current['algorithm'])
        def operation(tx):
            snapshot = ref.get(transaction=tx)
            record = snapshot.to_dict()
            locked = lock.get(transaction=tx)
            previous = locked.to_dict() if locked.exists else {}
            other = self._ref(previous['incident_id']).get(transaction=tx) if previous.get('incident_id') else None
            if record['status'] != event['expected_status']:
                raise InvalidTransitionError('Incident status changed; refresh before retrying')
            if status != 'resolved' and other and other.exists and other.to_dict()['incident_id'] != identifier and other.to_dict()['status'] != 'resolved':
                raise InvalidTransitionError('Another active incident exists')
            tx.update(ref, {'status': status, 'updated_at': event['timestamp']})
            if status != 'resolved':
                tx.set(lock, {'incident_id': identifier})
            tx.create(ref.collection('events').document(uuid.uuid4().hex), self._clean(event))
        self._tx(operation)

    def events(self, identifier):
        rows = [s.to_dict() for s in self._ref(identifier).collection('events').stream(timeout=10)]
        return sorted(rows, key=lambda row: row['timestamp'])

    def active_record_statuses(self, record_ids):
        result = {}
        for record in self._rows():
            if record['record_id'] in record_ids and record['status'] != 'resolved':
                result[record['record_id']] = {k: record[k] for k in ('incident_id', 'status', 'severity')}
        return result


class FirestoreInvestigationRepository(FirestoreRepository):
    def __init__(self, db=None):
        super().__init__('investigations', 'investigation_id', db)

    def insert(self, job):
        lock = self.client.collection(f'{config.settings.firestore_prefix}_investigation_locks').document(job['incident_id'])
        def operation(tx):
            snapshot = lock.get(transaction=tx)
            previous = snapshot.to_dict() if snapshot.exists else {}
            if previous.get('investigation_id'):
                active = self._ref(previous['investigation_id']).get(transaction=tx)
                if active.exists and active.to_dict()['status'] in ('queued', 'running'):
                    raise sqlite3.IntegrityError('Active investigation exists')
            tx.create(self._ref(job['investigation_id']), self._clean(job))
            tx.set(lock, {'investigation_id': job['investigation_id']})
        self._tx(operation)

    def claim(self, identifier):
        ref = self._ref(identifier)
        def operation(tx):
            snapshot = ref.get(transaction=tx)
            if not snapshot.exists:
                return False
            record = snapshot.to_dict()
            if record['status'] == 'completed' or (record['status'] == 'running' and record.get('lease_expires_at', float('inf')) > time.time()):
                return False
            tx.update(ref, {'status': 'running', 'started_at': now(), 'updated_at': now(), 'error': None,
                            'attempt_count': record.get('attempt_count', 0)+1,
                            'lease_expires_at': time.time() + config.settings.tasks_deadline + 120})
            return True
        return self._tx(operation)

    def find_active(self, incident_id):
        rows = self._rows('incident_id', incident_id)
        return next((r for r in rows if r['status'] in ('queued', 'running')), None)

    def list_for_incident(self, incident_id, limit, offset):
        return self._page(self._rows('incident_id', incident_id), limit, offset)

    def list_all(self, limit, offset, status=None):
        return self._page(self._rows('status', status) if status else self._rows(), limit, offset)

    def queued_jobs(self, limit=5):
        return sorted(self._rows('status', 'queued'), key=lambda r: r['created_at'])[:limit]

    def append_stage(self, identifier, entry):
        return self._mutate(identifier, lambda r: {**r, 'stage': entry['stage'], 'updated_at': now(),
                                                   'stage_history': [*r.get('stage_history', []), entry]})

    def upsert_agent(self, identifier, activity):
        def mutate(record):
            items = list(record.get('agent_activity', []))
            for index, item in enumerate(items):
                if item['agent'] == activity['agent']:
                    items[index] = {**item, **activity}
                    break
            else:
                items.append(activity)
            return {**record, 'agent_activity': items, 'updated_at': now()}
        return self._mutate(identifier, mutate)

    def save_evidence(self, records):
        for record in records:
            ref = self._ref(record['investigation_id']).collection('evidence').document(record['evidence_id'])
            def operation(tx):
                if not ref.get(transaction=tx).exists:
                    tx.create(ref, self._clean(record))
            self._tx(operation)

    def get_evidence(self, identifier):
        return sorted([s.to_dict() for s in self._ref(identifier).collection('evidence').stream(timeout=15)], key=lambda r:r['evidence_id'])


class FirestoreCounterfactualRepository(FirestoreRepository):
    def __init__(self, db=None):
        super().__init__('counterfactuals', 'scenario_id', db)

    def list_for_investigation(self, identifier):
        return sorted(self._rows('original_investigation_id', identifier), key=lambda r:r['created_at'], reverse=True)


class FirestoreVisualRepository(FirestoreRepository):
    def __init__(self, db=None):
        super().__init__('images', 'image_id', db)

    def list_for_incident(self, identifier):
        return sorted(self._rows('incident_id', identifier), key=lambda r:r['created_at'])


def repository(kind, local_factory):
    if config.settings.persistence_backend == 'postgres':
        from services.api.db.postgres import repository as postgres_repository
        return postgres_repository(kind)
    if config.settings.persistence_backend == 'sqlite':
        return local_factory()
    factories = {'incidents': FirestoreIncidentRepository, 'investigations': FirestoreInvestigationRepository,
                 'counterfactuals': FirestoreCounterfactualRepository, 'images': FirestoreVisualRepository}
    if config.settings.persistence_backend != 'firestore':
        raise RuntimeError('Unsupported persistence backend')
    return factories[kind]()
