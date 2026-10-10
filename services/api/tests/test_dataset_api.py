"""Protect Step 2 endpoints while extending anomaly and incident management."""


def test_existing_dataset_and_telemetry_endpoints(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/dataset/summary").status_code == 200
    page = client.get("/api/telemetry", params={"limit": 2, "offset": 0})
    assert page.status_code == 200
    assert client.get("/api/telemetry/1").status_code == 200
    assert client.get("/api/telemetry/999999").status_code == 404
