"""Tests for the Agent Trust Score (Slice 12 / spec section 18): a
real formula over AgentHealth's own tracked execution history and
Feedback's real override data, not an invented reputation number.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.database import get_db
from app.governance.trust import compute_trust_score
from app.main import app
from app.models.governance import AgentExecutionTrace, AgentHealth, Feedback

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents/health rows exist


@pytest.fixture
def db():
    gen = get_db()
    session = next(gen)
    yield session
    gen.close()


def _set_health(db, agent_id, **kwargs):
    health = db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
    for key, value in kwargs.items():
        setattr(health, key, value)
    db.commit()
    return health


class TestTrustScore:
    def test_no_executions_yet_is_honestly_none(self, db):
        # A real agent seeded at startup, but AgentHealth still at its
        # default zero-execution state.
        _set_health(db, "fuel-agent", execution_count=0)
        assert compute_trust_score(db, "fuel-agent") is None

    def test_unknown_agent_is_none(self, db):
        assert compute_trust_score(db, "not-a-real-agent") is None

    def test_perfect_record_scores_at_the_ceiling(self, db):
        _set_health(db, "fuel-agent", execution_count=10, success_rate=1.0,
                    denied_actions=0, policy_violation_count=0)
        assert compute_trust_score(db, "fuel-agent") == 1.0

    def test_denials_and_violations_reduce_the_score(self, db):
        _set_health(db, "fuel-agent", execution_count=10, success_rate=1.0,
                    denied_actions=2, policy_violation_count=1)
        # denial_rate=0.2, violation_rate=0.1 -> 1.0 * 0.8 * 0.9
        assert compute_trust_score(db, "fuel-agent") == round(0.8 * 0.9, 3)

    def test_failure_rate_reduces_the_score_via_success_rate(self, db):
        _set_health(db, "fuel-agent", execution_count=10, success_rate=0.5,
                    denied_actions=0, policy_violation_count=0)
        assert compute_trust_score(db, "fuel-agent") == 0.5

    def test_human_overrides_reduce_the_score_when_feedback_exists(self, db):
        _set_health(db, "decision-agent", execution_count=10, success_rate=1.0,
                    denied_actions=0, policy_violation_count=0)

        trace = AgentExecutionTrace(id=str(uuid.uuid4()), agent_id="decision-agent")
        db.add(trace)
        db.commit()
        db.add(Feedback(execution_id=trace.id, agent_id="decision-agent", human_action="REJECTED"))
        db.commit()

        score = compute_trust_score(db, "decision-agent")
        assert score < 1.0  # the override must actually move the score

    def test_no_feedback_rows_means_no_override_penalty(self, db):
        # congestion-agent has never had feedback recorded (in this test
        # run) -- absence of data must not be treated as evidence of
        # distrust.
        _set_health(db, "congestion-agent", execution_count=5, success_rate=1.0,
                    denied_actions=0, policy_violation_count=0)
        existing_feedback = db.query(Feedback).filter(Feedback.agent_id == "congestion-agent").count()
        if existing_feedback == 0:
            assert compute_trust_score(db, "congestion-agent") == 1.0


class TestTrustScoreInAgentsEndpoint:
    def test_agents_endpoint_reports_a_real_trust_score(self):
        res = client.get("/api/governance/agents")
        assert res.status_code == 200
        agents = res.json()
        assert any("trust_score" in a for a in agents)
