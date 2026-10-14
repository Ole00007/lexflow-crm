"""Health & connectivity tests."""


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_invalid_endpoint_returns_404(client):
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404
