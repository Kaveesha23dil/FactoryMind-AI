"""Opt-in real PostgreSQL contract check against an operator-provided DISPOSABLE DB.

Apply migration 001 there first. No hosted service is provisioned by tests.
All inserted rows are inside a force-rollback transaction.
"""
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import uuid
import pytest
from services.api.core import config
from services.api.db import postgres
from services.api.services.incident_service import SqliteIncidentRepository
from services.api.services.investigation_repository import SqliteInvestigationRepository

pytestmark = pytest.mark.skipif(os.environ.get('FACTORYMIND_RUN_POSTGRES_TESTS') != '1' or not os.environ.get('FACTORYMIND_TEST_POSTGRES_URL'), reason='Real PostgreSQL requires an explicitly enabled disposable migrated test database')


def test_real_postgres_repository_roundtrip_and_composite_evidence(monkeypatch):
    monkeypatch.setattr(config, 'settings', replace(config.settings, database_url=os.environ['FACTORYMIND_TEST_POSTGRES_URL']))
    with postgres.connect_raw() as raw:
        with raw.transaction(force_rollback=True):
            class TestDatabase:
                @contextmanager
                def connect(self):
                    connection = postgres.Connection(raw)
                    connection.commit = lambda: None
                    yield connection
            db = TestDatabase()
            incidents = SqliteIncidentRepository(db)
            investigations = SqliteInvestigationRepository(db)
            now = datetime.now(timezone.utc).isoformat()
            suffix = uuid.uuid4().hex
            incident_id = 'INC-TEST-' + suffix
            incident = dict(incident_id=incident_id, record_id=1, product_id='TEST', machine_type='L', algorithm='test-'+suffix,
                anomaly_score=4.5, severity='low', status='open', source_measurements={}, evidence=[], explanations=[], note=None,
                detection_config={}, created_at=now, updated_at=now)
            incidents.insert(incident, dict(incident_id=incident_id,status='open',note=None,timestamp=now))
            assert incidents.get(incident_id)['created_at'].endswith('+00:00')
            for index in range(2):
                identifier = f'INV-TEST-{index}-{suffix}'
                job = dict(investigation_id=identifier, incident_id=incident_id,status='queued',stage='queued',provider='scripted',model='test',stage_history=[],agent_activity=[],attempt_count=0,created_at=now,started_at=None,completed_at=None,updated_at=now)
                investigations.insert(job)
                assert investigations.claim(identifier)
                assert not investigations.claim(identifier)
                investigations.append_stage(identifier, dict(stage='sensor_analysis', timestamp=now))
                investigations.upsert_agent(identifier, dict(agent='sensor_agent', status='completed'))
                record = dict(investigation_id=identifier,evidence_id='EV-SAME',incident_id=incident_id,evidence_type='sensor_measurement',source='Synthetic test',observation='Fixture',value=1.0,units='rpm',provenance='TEST ONLY',payload={},created_at=now)
                investigations.save_evidence([record, record])
                assert len(investigations.get_evidence(identifier)) == 1
                investigations.update(identifier,status='completed',stage='completed',report={'fixture':True},completed_at=now)
                assert investigations.get(identifier)['report'] == {'fixture':True}
            assert investigations.list_for_incident(incident_id,10,0)[0] == 2
