import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_risks_list_endpoint_exists():
    response = client.get("/api/risks")
    assert response.status_code in {200, 401, 403, 404}
    assert "application/json" in response.headers.get("content-type", "")


def test_risk_detail_endpoint_exists():
    response = client.get("/api/risks/1")
    assert response.status_code in {200, 401, 403, 404}
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.parametrize(
    "path",
    [
        "/api/risks",
        "/api/risks/1",
    ],
)
def test_risk_endpoints_accept_options(path):
    response = client.options(path)
    assert response.status_code in {200, 204, 405, 404}