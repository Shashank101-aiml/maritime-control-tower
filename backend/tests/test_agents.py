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

# --- the dashboard's agent list comes from the governance registry ---------

from datetime import datetime

from app.api.dependencies.database import get_db
from app.models.governance import AgentExecutionTrace, AgentHealth, AgentIdentity

from tests.fleet_support import make_engine_and_session


def _seed(db):
    for agent_id, name in (("risk-agent", "Risk Agent"), ("fuel-agent", "Fuel Efficiency Agent"),
                           ("route-agent", "Route Agent"), ("delay-agent", "Delay Intelligence Agent")):
        db.add(AgentIdentity(id=agent_id, agent_name=name, agent_type="ANALYZER", version="v1.0"))
        db.add(AgentHealth(agent_id=agent_id, status="HEALTHY", execution_count=3))
    db.commit()
    db.query(AgentHealth).filter(AgentHealth.agent_id == "fuel-agent").one().status = "DEGRADED"
    db.query(AgentIdentity).filter(AgentIdentity.id == "route-agent").one().status = "QUARANTINED"
    db.add(AgentExecutionTrace(id="t1", agent_id="risk-agent", started_at=datetime(2026, 9, 25, 9, 30)))
    db.commit()


def test_agents_endpoint_reports_every_registered_agent_with_its_real_status():
    Session = make_engine_and_session()
    db = Session()
    _seed(db)

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    try:
        body = client.get("/api/agents").json()
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()

    by_id = {a["id"]: a for a in body}
    assert len(body) == 4  # exactly what is registered, not a fixed five
    assert by_id["risk-agent"]["status"] == "ONLINE" and by_id["risk-agent"]["last_active"] == "2026-09-25 09:30:00 UTC"
    assert by_id["fuel-agent"]["status"] == "DEGRADED"
    assert by_id["route-agent"]["status"] == "QUARANTINED"
    assert by_id["delay-agent"]["last_active"] is None  # never ran: no invented timestamp
    # what the hover panel shows: the agent's objective and its real governance settings
    assert "live ETA" in by_id["delay-agent"]["synopsis"]
    assert by_id["risk-agent"]["confidence_threshold"] == 0.7 and by_id["risk-agent"]["executions"] == 3
