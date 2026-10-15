"""Settings expose an allowlist, never operational writes or model requests."""
from dataclasses import replace
from services.api.core import config
from services.api.routes import settings as routes


def test_settings_matches_runtime_and_dataset(client, engine):
    response = client.get('/api/settings')
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['anomaly']['threshold'] == engine.detector.anomaly_score_threshold
    assert body['anomaly']['algorithm'] == engine.detector.algorithm
    assert body['data']['records'] == 10000
    assert body['data']['document_count'] > 0
    assert body['data']['passage_count'] >= body['data']['document_count']
    assert body['ai']['max_concurrent_investigations'] is None
    assert body['security']['role'] is None


def test_secret_and_private_configuration_redaction(client, monkeypatch):
    secret = 'SENTINEL-SECRET-DO-NOT-EXPOSE'
    monkeypatch.setattr(config, 'settings', replace(config.settings, google_api_key=secret, auth_audience=secret, gcp_project=secret))
    for path in ['/api/settings', '/api/settings/system']:
        response = client.get(path)
        assert response.status_code == 200
        assert secret not in response.text
        assert str(config.settings.database_path).replace('\\', '\\\\') not in response.text
        assert 'google_api_key' not in response.text


def test_no_runtime_configuration_writes(client):
    for path in ['/api/settings', '/api/settings/preferences', '/api/settings/anomaly']:
        response = client.patch(path, json={'threshold': -1, 'gemini_model': 'unapproved'})
        assert response.status_code in (404, 405)


def test_system_reports_unknown_unprobed_services(client):
    body = client.get('/api/settings/system').json()
    assert body['api_status'] == 'connected'
    assert body['database_status'] == 'connected'
    assert body['image_storage_status'] == 'unknown'
    assert 'Not probed' in body['gemini_status']


def test_database_failure_is_not_healthy(client, monkeypatch):
    def fail():
        raise RuntimeError('private backend details')
    monkeypatch.setattr(routes, 'get_service', fail)
    response = client.get('/api/settings/system')
    assert response.status_code == 200
    assert response.json()['database_status'] == 'unavailable'
    assert 'private backend details' not in response.text


def test_usage_unknown_and_partial_metrics_are_not_quota_totals():
    assert routes._usage([])['requests'] is None
    usage = routes._usage([{'report': {'usage': [{'request_count': 1, 'input_tokens': 10}, {'request_count': 1, 'input_tokens': None}]}}])
    assert usage['requests'] == 2
    assert usage['input_tokens'] == 10
    assert usage['output_tokens'] is None
    assert 'Not provider quota' in usage['scope']


def test_production_settings_and_writes_require_identity(client, monkeypatch):
    monkeypatch.setattr(config, 'settings', replace(config.settings, app_env='production'))
    for method, path in [('get', '/api/settings'), ('get', '/api/settings/system'), ('patch', '/api/settings/anomaly')]:
        assert getattr(client, method)(path).status_code == 401
