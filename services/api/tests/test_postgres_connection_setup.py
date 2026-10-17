"""Offline diagnostics and PowerShell setup tests; only synthetic credentials."""
from pathlib import Path
import shutil
import subprocess
from unittest.mock import MagicMock, Mock
from urllib.parse import quote

import pytest
from scripts.check_postgres_connection import check, metadata

PASSWORD = 'synthetic@:/?#%&+ space'
URI = 'postgresql://postgres.qeetbmeleqsmlqywtdyr:' + quote(PASSWORD, safe='') + '@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require'


@pytest.mark.parametrize('value', ['', None, PASSWORD, 'postgresql://user:password@host:6543/postgres?sslmode=require',
    'postgresql://user:password@host:5432/postgres', 'postgresql://user:%xx@host:5432/postgres?sslmode=require'])
def test_invalid_configuration_never_connects(value):
    driver = Mock()
    assert check(value, driver=driver) == {'success': False, 'category': 'Invalid connection URI'}
    driver.connect.assert_not_called()


@pytest.mark.parametrize('message,expected', [
    ('password authentication failed', 'Incorrect password'),
    ('could not translate host name', 'DNS failure'),
    ('connection timeout expired', 'Network timeout'),
    ('SSL certificate verify failed', 'SSL error'),
    ('Tenant or user not found', 'Other configuration errors')])
def test_provider_errors_are_classified_without_echoing_secrets(message, expected):
    driver = Mock()
    driver.connect.side_effect = RuntimeError(message + ' ' + URI)
    result = check(URI, driver=driver)
    assert result['category'] == expected and result['success'] is False
    assert PASSWORD not in str(result) and URI not in str(result)


def test_driver_missing(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'psycopg', None)
    assert check(URI)['category'] == 'Missing driver'


def test_select_one_precedes_read_only_schema_verification():
    driver = MagicMock()
    connection = driver.connect.return_value.__enter__.return_value
    connection.execute.return_value.fetchone.return_value = (1,)
    connection.execute.return_value.fetchall.return_value = []
    result = check(URI, driver=driver)
    assert result['success']
    connection.execute.assert_called_once_with('SELECT 1')
    assert 'default_transaction_read_only=on' in driver.connect.call_args.kwargs['options']
    assert check(URI, driver=driver, verify_schema=True)['success'] is False
    assert all(call.args[0].startswith('SELECT') for call in connection.execute.call_args_list)
    assert metadata(URI)['password_present'] is True


def test_powershell_dot_source_encodes_password_without_output_or_files():
    executable = shutil.which('pwsh') or shutil.which('powershell')
    if not executable:
        pytest.skip('PowerShell unavailable')
    script = Path(__file__).resolve().parents[3] / 'scripts/setup_supabase_connection.ps1'
    command = f"""
    function Read-Host {{ param($Prompt, [switch]$AsSecureString) ConvertTo-SecureString '{PASSWORD}' -AsPlainText -Force }}
    . '{str(script).replace(chr(39), chr(39)*2)}'
    if ($env:FACTORYMIND_DATABASE_URL -cne '{URI}') {{ throw 'Synthetic URI encoding mismatch' }}
    if (Get-Variable plainPassword,encodedPassword,securePassword -ErrorAction SilentlyContinue) {{ throw 'Temporary variables leaked' }}
    Remove-Item Env:FACTORYMIND_DATABASE_URL
    Write-Output 'SYNTHETIC_SETUP_OK'
    """
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, 'Synthetic PowerShell setup failed (output suppressed)'
    assert 'SYNTHETIC_SETUP_OK' in result.stdout
    assert PASSWORD not in result.stdout + result.stderr
    assert URI not in result.stdout + result.stderr
