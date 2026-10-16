"""PostgreSQL transport for existing relational repositories; no SQLite files in cloud.

The SQL dialect bridge is intentionally limited to the statements used by the
existing repository interfaces. Versioned migrations are explicit operator work.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import sqlite3
import uuid

from services.api.core import config

execution_owner = ContextVar('portable_execution_owner', default=None)


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def normalized(row):
    if row is None:
        return None
    return Row({key: value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else value for key, value in row.items()})


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        return normalized(self.cursor.fetchone())

    def fetchall(self):
        return [normalized(row) for row in self.cursor.fetchall()]


def sql_statement(sql):
    if sql.strip().upper() == 'BEGIN IMMEDIATE':
        return 'SELECT pg_advisory_xact_lock(71192001)'
    ignore = 'INSERT OR IGNORE' in sql
    sql = sql.replace('INSERT OR IGNORE', 'INSERT').replace('?', '%s')
    sql = sql.replace('MAX(expires_at,excluded.expires_at)', 'GREATEST(gemini_provider_cooldowns.expires_at,excluded.expires_at)')
    return sql.rstrip().rstrip(';') + (' ON CONFLICT DO NOTHING' if ignore else '')


class Connection:
    def __init__(self, connection):
        self.raw = connection

    def execute(self, sql, params=()):
        from psycopg import IntegrityError
        try:
            owner = execution_owner.get()
            if owner and sql.lstrip().split()[0].upper() in ('UPDATE', 'INSERT', 'DELETE'):
                row = self.raw.execute('SELECT execution_token FROM investigations WHERE investigation_id=%s FOR SHARE', (owner[0],)).fetchone()
                if not row or row['execution_token'] != owner[1]:
                    raise RuntimeError('Investigation execution ownership expired; stale writes rejected')
            return Cursor(self.raw.execute(sql_statement(sql), params))
        except IntegrityError:
            # Existing services already translate relational conflicts into 409s.
            raise sqlite3.IntegrityError('Relational constraint rejected the write') from None

    def commit(self):
        self.raw.commit()


def connect_raw():
    import psycopg
    from psycopg.rows import dict_row
    try:
        return psycopg.connect(config.settings.database_url, row_factory=dict_row,
            connect_timeout=10, prepare_threshold=None,
            options='-c statement_timeout=15000 -c lock_timeout=10000 -c search_path=factorymind,public')
    except Exception:
        raise RuntimeError('PostgreSQL connection unavailable; check server configuration') from None


def check_schema(url):
    with connect_raw() as connection:
        row = connection.execute('SELECT version FROM factorymind_schema_versions WHERE version=1').fetchone()
        if not row:
            raise RuntimeError('PostgreSQL schema migration 001 is required')


class PostgresDatabase:
    def initialize(self):
        check_schema(config.settings.database_url)

    @contextmanager
    def connect(self):
        with connect_raw() as connection:
            yield Connection(connection)


@contextmanager
def execution_lock(identifier):
    """Session lock plus write fencing: a disconnected old runner cannot overwrite a retry."""
    token = uuid.uuid4().hex
    with connect_raw() as connection:
        connection.autocommit = True
        acquired = connection.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS acquired', (identifier,)).fetchone()['acquired']
        if not acquired:
            yield False
            return
        handle = None
        try:
            partial = connection.execute("SELECT 1 AS present FROM investigation_evidence e JOIN investigations j ON j.investigation_id=e.investigation_id WHERE j.investigation_id=%s AND j.status IN ('running','failed') LIMIT 1", (identifier,)).fetchone()
            if partial:
                connection.execute("UPDATE investigations SET execution_token=%s,status='failed',stage='failed',completed_at=now(),updated_at=now(),error='Interrupted execution retained partial evidence. Start a new explicit investigation; existing evidence was preserved.' WHERE investigation_id=%s", (token, identifier))
                yield False
                return
            connection.execute("UPDATE investigations SET execution_token=%s, status=CASE WHEN status='running' THEN 'queued' ELSE status END WHERE investigation_id=%s", (token, identifier))
            handle = execution_owner.set((identifier, token))
            yield True
        finally:
            if handle is not None:
                execution_owner.reset(handle)
            try:
                connection.execute('UPDATE investigations SET execution_token=NULL WHERE investigation_id=%s AND execution_token=%s', (identifier, token))
            except Exception:
                pass  # A lost session releases its lock; a later owner fences writes.
            # Connection close releases its advisory lock, including on exceptions.


def repository(kind):
    from services.api.services.incident_service import SqliteIncidentRepository
    from services.api.services.investigation_repository import SqliteInvestigationRepository
    from services.api.services.counterfactual_repository import SqliteCounterfactualRepository
    from services.api.services.visual_repository import SqliteVisualEvidenceRepository
    factories = {'incidents': SqliteIncidentRepository, 'investigations': SqliteInvestigationRepository,
                 'counterfactuals': SqliteCounterfactualRepository, 'images': SqliteVisualEvidenceRepository}
    return factories[kind](PostgresDatabase())
