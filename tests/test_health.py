from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_healthy_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_and_metrics_are_available():
    assert client.get("/").json()["service"] == "launchpad-demo"
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "launchpad_http_requests_total" in response.text
    assert "launchpad_http_request_duration_seconds" in response.text


def test_unknown_paths_share_bounded_metric_labels():
    from prometheus_client import REGISTRY

    for path in ("/unknown-customer-123", "/unknown-customer-456"):
        assert client.get(path).status_code == 404
    samples = [
        sample
        for metric in REGISTRY.collect()
        for sample in metric.samples
        if sample.name == "launchpad_http_requests_total"
    ]
    assert any(sample.labels["endpoint"] == "unmatched" for sample in samples)
    assert all("unknown-customer" not in sample.labels["endpoint"] for sample in samples)
