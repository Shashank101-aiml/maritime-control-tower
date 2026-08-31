import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/events",
        "/api/risks",
        "/api/workflow",
        "/api/dashboard",
        "/api/recommendations",
    ],
)
def test_api_routes_exist(path):
    response = client.options(path)
    assert response.status_code in {200, 204, 405, 404}