"""Read-only PostgreSQL diagnostic. Never display exception text or a connection URI."""
import argparse
import json
import re
from urllib.parse import parse_qs, urlsplit


def metadata(uri):
    try:
        parsed = urlsplit(uri or '')
        if (parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname or
                not parsed.username or not parsed.password or parsed.port != 5432 or
                parsed.path != '/postgres' or
                parse_qs(parsed.query).get('sslmode') not in (['require'], ['verify-full']) or
                re.search(r'%(?![0-9a-fA-F]{2})', uri)):
            raise ValueError
        # Host is configuration, but do not echo arbitrary user input to the terminal.
        if not re.fullmatch(r'[a-zA-Z0-9.-]+', parsed.hostname):
            raise ValueError
        return {'scheme': parsed.scheme, 'host': parsed.hostname, 'port': parsed.port,
                'database': 'postgres', 'username_present': True, 'password_present': True,
                'sslmode': parse_qs(parsed.query)['sslmode'][0]}
    except (ValueError, TypeError):
        raise ValueError('Invalid connection URI') from None


def category(error):
    # Inspect provider text only in memory; never return or log it.
    message = re.sub(r'postgres(?:ql)?://\S+', '', str(error).lower())
    if getattr(error, 'sqlstate', None) == '28P01' or 'password authentication failed' in message:
        return 'Incorrect password'
    if any(term in message for term in ('getaddrinfo', 'name or service not known', 'could not translate host', 'nodename nor servname', 'no such host')):
        return 'DNS failure'
    if re.search(r'\b(?:ssl|tls)\b|certificate', message):
        return 'SSL error'
    if any(term in message for term in ('timeout', 'timed out')):
        return 'Network timeout'
    return 'Other configuration errors'


def check(uri, *, verify_schema=False, driver=None):
    try:
        safe = metadata(uri)
    except ValueError:
        return {'success': False, 'category': 'Invalid connection URI'}
    if driver is None:
        try:
            import psycopg as driver
        except ImportError:
            return {'success': False, 'category': 'Missing driver', 'connection': safe}
    try:
        # No schema search path requirement: this must work before migration 001.
        with driver.connect(uri, connect_timeout=10, prepare_threshold=None,
                            options='-c statement_timeout=15000 -c default_transaction_read_only=on') as connection:
            if connection.execute('SELECT 1').fetchone()[0] != 1:
                raise ValueError('Unexpected diagnostic result')
            result = {'success': True, 'category': 'Connected', 'connection': safe}
            if verify_schema:
                tables = [row[0] for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='factorymind' ORDER BY table_name").fetchall()]
                required = {'factorymind_schema_versions', 'incidents', 'incident_events', 'investigations',
                    'investigation_evidence', 'counterfactual_scenarios', 'visual_evidence',
                    'gemini_request_leases', 'gemini_provider_cooldowns', 'portable_ai_usage'}
                version = None
                if 'factorymind_schema_versions' in tables:
                    row = connection.execute('SELECT version FROM factorymind.factorymind_schema_versions WHERE version=1').fetchone()
                    version = row[0] if row else None
                result.update(tables=sorted(required.intersection(tables)), missing_tables=sorted(required.difference(tables)), schema_version=version)
                result['success'] = required.issubset(tables) and version == 1
                result['category'] = 'Schema verified' if result['success'] else 'Schema missing or incomplete'
            return result
    except Exception as error:
        return {'success': False, 'category': category(error), 'connection': safe}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-schema', action='store_true', help='Also check migration 001 tables/version without writes')
    args = parser.parse_args()
    from services.api.core.config import settings
    result = check(settings.database_url, verify_schema=args.verify_schema)
    print(json.dumps(result))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
