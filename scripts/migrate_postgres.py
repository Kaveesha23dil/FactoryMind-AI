"""Explicit, reviewed SQLite snapshot -> PostgreSQL import. Never called by API startup.

Default is a dry run. --apply requires --reviewed and a new backup path.
No source database, source file or cloud resource is deleted.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from services.api.core import config
from services.api.db.postgres import connect_raw
from services.api.services.submission_service import audit_report
from services.api.services.investigation_repository import SqliteInvestigationRepository

TABLES = ('incidents', 'incident_events', 'investigations', 'investigation_evidence', 'counterfactual_scenarios', 'visual_evidence')


def redact(value):
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    for pattern in (r'AIza[A-Za-z0-9_-]{20,}', r'Bearer\s+[A-Za-z0-9_.-]+', r'postgres(?:ql)?://[^\s"<>]+', r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_.-]+'):
        value = re.sub(pattern, '[REDACTED]', value)
    return value


def collect(connection, identifiers, all_terminal=False):
    connection.row_factory = sqlite3.Row
    rows = {table: [dict(row) for row in connection.execute(f'SELECT * FROM {table}')] for table in TABLES}
    jobs = [row for row in rows['investigations'] if (all_terminal or row['investigation_id'] in identifiers)]
    if identifiers - {row['investigation_id'] for row in jobs}:
        raise ValueError('Selected investigation does not exist')
    if any(row['status'] not in ('completed', 'failed') for row in jobs):
        raise ValueError('Reconcile queued/running jobs before importing; no active executor is migrated')
    job_ids = {row['investigation_id'] for row in jobs}
    incident_ids = {row['incident_id'] for row in jobs}
    result = {
        'incidents': [row for row in rows['incidents'] if row['incident_id'] in incident_ids],
        'incident_events': [row for row in rows['incident_events'] if row['incident_id'] in incident_ids],
        'investigations': jobs,
        'investigation_evidence': [row for row in rows['investigation_evidence'] if row['investigation_id'] in job_ids],
        'counterfactual_scenarios': [row for row in rows['counterfactual_scenarios'] if row['original_investigation_id'] in job_ids and row['revised_investigation_id'] in job_ids],
        'visual_evidence': [row for row in rows['visual_evidence'] if row['incident_id'] in incident_ids and (not row['investigation_id'] or row['investigation_id'] in job_ids)],
    }
    for job in jobs:
        if job['status'] != 'completed':
            continue
        decoded = SqliteInvestigationRepository._row_to_job(job)
        evidence = [{**row, 'payload': json.loads(row['payload'])} for row in result['investigation_evidence'] if row['investigation_id'] == job['investigation_id']]
        audit = audit_report(decoded, evidence)
        if audit['invalid_evidence_ids'] or audit['source_issues'] or not audit['catalog_matches_storage']:
            raise ValueError('Selected report fails stored citation/provenance audit; review before migration')
    # Notes and original upload filenames may identify people/facilities.
    for row in result['incidents'] + result['incident_events']:
        row['note'] = None
    for row in result['visual_evidence']:
        row['filename'] = row['image_id'] + Path(row['storage_ref']).suffix
    for table, records in result.items():
        for row in records:
            for column, value in list(row.items()):
                if isinstance(value, str) and (column.endswith('_at') or column == 'timestamp'):
                    parsed = datetime.fromisoformat(value)
                    if parsed.tzinfo is None:
                        raise ValueError('Naive source timestamp must be reconciled explicitly')
                    row[column] = parsed.astimezone(timezone.utc).isoformat()
                elif isinstance(value, str) and column in ('report', 'prepared_context', 'stage_history', 'agent_activity', 'payload', 'source_measurements', 'evidence', 'explanations', 'observations', 'limitations', 'comparison', 'dependency_trace', 'detection_config'):
                    row[column] = json.dumps(redact(json.loads(value)), allow_nan=False)
                else:
                    row[column] = redact(value)
            if table == 'investigations':
                row['execution_token'] = None
    return result


def migrate_schema():
    path = Path(__file__).resolve().parents[1] / 'services/api/db/migrations/001_portable.sql'
    with connect_raw() as connection:
        exists = connection.execute("SELECT to_regclass('factorymind.factorymind_schema_versions') AS name").fetchone()['name']
        if exists:
            if not connection.execute('SELECT version FROM factorymind_schema_versions WHERE version=1').fetchone():
                raise ValueError('Unknown schema version; manual reconciliation required')
            return
        connection.execute(path.read_text(encoding='utf-8'), prepare=False)


def import_rows(records):
    """One transaction. Identical IDs are idempotent; conflicting contents abort import."""
    from psycopg import sql
    with connect_raw() as connection:
        for table in TABLES:
            for row in records[table]:
                keys = list(row)
                statement = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING').format(sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, keys)), sql.SQL(',').join(sql.Placeholder() for _ in keys))
                cursor = connection.execute(statement, list(row.values()))
                if cursor.rowcount == 0:
                    primary = {'incident_events': ['id'], 'investigation_evidence': ['investigation_id', 'evidence_id']}.get(table, [keys[0]])
                    where = sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key in primary)
                    existing = connection.execute(sql.SQL('SELECT * FROM {} WHERE {}').format(sql.Identifier(table), where), [row[key] for key in primary]).fetchone()
                    from services.api.db.postgres import normalized
                    values = normalized(existing) or {}
                    if any(values.get(key) != value for key, value in row.items()):
                        raise ValueError('Destination contains a conflicting record; import rolled back')
        connection.execute("SELECT setval(pg_get_serial_sequence('factorymind.incident_events','id'), COALESCE((SELECT MAX(id) FROM incident_events),1), EXISTS(SELECT 1 FROM incident_events))")


def copy_images(records, directory, store=None):
    """Explicit reviewed object copy, preserving storage references and refusing overwrites."""
    from services.api.services.supabase_storage import SupabaseObjectStore
    from services.api.services.image_utils import verify_image, detect_mime_type
    if not directory:
        raise ValueError('Image-bearing snapshots require --images-dir pointing to reviewed local evidence; no rows imported')
    root = directory.resolve()
    store = store or SupabaseObjectStore()
    store.check()
    for row in records:
        path = (root / row['storage_ref']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Reviewed source image is missing or outside the selected image directory')
        if path.stat().st_size > config.VISUAL_MAX_IMAGE_BYTES:
            raise ValueError('Source image exceeds the upload limit')
        data = path.read_bytes()
        if len(data) > config.VISUAL_MAX_IMAGE_BYTES or detect_mime_type(data) != row['mime_type']:
            raise ValueError('Source image fails MIME/size validation')
        verify_image(data)
        if store.exists(row['storage_ref']):
            if store.read(row['storage_ref']) != data:
                raise ValueError('Destination image differs; existing object was not overwritten')
        else:
            store.write(row['storage_ref'], data, row['mime_type'])
        row['storage_backend'] = 'supabase'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('schema', 'import'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--images-dir', type=Path)
    parser.add_argument('--investigation', action='append', default=[])
    parser.add_argument('--all-terminal', action='store_true')
    parser.add_argument('--reviewed', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.operation == 'schema':
        if not args.apply:
            print('Dry run: migration 001 creates the private factorymind schema. Use --apply to execute.')
            return
        migrate_schema()
        print('Schema migration 001 applied or already present.')
        return
    if not args.source or not (args.investigation or args.all_terminal):
        parser.error('Import requires --source and explicit --investigation IDs or --all-terminal')
    source = args.source.resolve()
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as connection:
        records = collect(connection, set(args.investigation), args.all_terminal)
        if not args.apply:
            print(json.dumps({'dry_run': True, 'rows': {table: len(rows) for table, rows in records.items()}, 'note': 'No destination connection or write; review source content before --reviewed --apply.'}))
            return
        if not args.reviewed or not args.backup:
            parser.error('--apply requires --reviewed and a new --backup path')
        backup = args.backup.resolve()
        if backup == source or backup.exists():
            parser.error('Backup must be a new path distinct from the source')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(backup) as destination:
            connection.backup(destination)
    if records['visual_evidence']:
        copy_images(records['visual_evidence'], args.images_dir)
    import_rows(records)
    print(json.dumps({'imported': {table: len(rows) for table, rows in records.items()}, 'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(), 'source_deleted': False}))


if __name__ == '__main__':
    main()
