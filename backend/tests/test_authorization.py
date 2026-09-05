"""Tests for real least-privilege authorization (Slice 12 / spec
section 17). check_authorization() used to query AgentPermission,
discard the result, and unconditionally return True -- these prove
enforcement actually happens now: a seeded (agent, resource, action)
grant passes, anything not explicitly granted is denied, and a
quarantined/disabled agent is denied regardless of a grant existing.
"""

import pytest

from app.api.dependencies.database import get_db
from app.governance.authorization import check_authorization
from app.main import app
from app.models.governance import AgentIdentity, AgentPermission
from fastapi.testclient import TestClient

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once, seeding real agents + permissions


@pytest.fixture
def db():
    gen = get_db()
    session = next(gen)
    yield session
    gen.close()


class TestRealAuthorization:
    def test_a_real_seeded_permission_is_authorized(self, db):
        # Seeded in main.py's seed_governance_agents() for the real
        # coordinator call site risk-agent / ANALYZE / EXECUTE.
        assert check_authorization(db, "risk-agent", "ANALYZE", "EXECUTE") is True

    def test_every_real_call_site_has_a_seeded_permission(self, db):
        """The exact set this codebase's engine.execute_agent_task()
        call sites use -- coordinator_agent.py's five steps plus the
        three standalone prediction routes. Guards against a future
        governed call site being added without a matching grant, which
        would silently start denying real work rather than erroring
        loudly at review time."""
        real_call_sites = [
            ("ingestion-agent", "COLLECT"),
            ("risk-agent", "ANALYZE"),
            ("route-agent", "PLAN"),
            ("decision-agent", "DECIDE"),
            ("explanation-agent", "EXPLAIN"),
            ("congestion-agent", "PREDICT"),
            ("delay-agent", "PREDICT"),
            ("fuel-agent", "PREDICT"),
        ]
        for agent_id, resource in real_call_sites:
            assert check_authorization(db, agent_id, resource, "EXECUTE") is True, (
                f"{agent_id}/{resource} has no seeded permission -- it would be denied at runtime."
            )

    def test_an_unlisted_resource_is_denied_not_defaulted_to_allow(self, db):
        # risk-agent is real and ACTIVE, but has never been granted
        # this resource/action -- least privilege means denied, not the
        # old unconditional `return True`.
        assert check_authorization(db, "risk-agent", "DELETE_EVERYTHING", "EXECUTE") is False

    def test_an_unknown_agent_is_denied(self, db):
        assert check_authorization(db, "not-a-real-agent", "ANALYZE", "EXECUTE") is False

    def test_quarantined_agent_is_denied_even_with_a_real_grant(self, db):
        agent = db.query(AgentIdentity).filter(AgentIdentity.id == "risk-agent").first()
        original_status = agent.status
        agent.status = "QUARANTINED"
        db.commit()
        try:
            assert check_authorization(db, "risk-agent", "ANALYZE", "EXECUTE") is False
        finally:
            agent.status = original_status
            db.commit()

    def test_permission_grants_are_scoped_to_their_own_agent(self, db):
        # risk-agent's real grant is (ANALYZE, EXECUTE) -- it must not
        # authorize a different agent for the same resource/action.
        grant = db.query(AgentPermission).filter(
            AgentPermission.agent_id == "risk-agent", AgentPermission.resource == "ANALYZE",
        ).first()
        assert grant is not None
        assert check_authorization(db, "route-agent", "ANALYZE", "EXECUTE") is False
