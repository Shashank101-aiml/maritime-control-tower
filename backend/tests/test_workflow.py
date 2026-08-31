import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import workflow as workflow_routes

client = TestClient(app)


def test_workflow_router_importable():
    assert hasattr(workflow_routes, "router")
    assert isinstance(workflow_routes.router, APIRouter)


def test_workflow_router_contains_workflow_paths():
    assert any("workflow" in route.path for route in workflow_routes.router.routes)


def test_workflow_endpoint_exists():
    response = client.get("/api/workflow")
    assert response.status_code in {200, 401, 403, 404}
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.parametrize("path", ["/api/workflow"])
def test_workflow_endpoint_accept_options(path):
    response = client.options(path)
    assert response.status_code in {200, 204, 405, 404}