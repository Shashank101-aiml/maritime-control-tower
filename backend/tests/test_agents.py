import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app

from app.api.routes import agents as agents_routes  # ensure routes module exists

client = TestClient(app)


def test_agents_router_importable():
    assert hasattr(agents_routes, "router")
    assert isinstance(agents_routes.router, APIRouter)


def test_agents_router_contains_agent_paths():
    assert any("agent" in route.path for route in agents_routes.router.routes)


@pytest.mark.parametrize("path", ["/api/agents", "/api/agents/1"])
def test_agents_endpoints_return_json(path):
    response = client.get(path)
    assert response.status_code in {200, 401, 403, 404}
    assert "application/json" in response.headers.get("content-type", "")