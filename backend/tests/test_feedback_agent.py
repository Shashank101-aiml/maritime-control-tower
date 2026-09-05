"""Tests for the Feedback Agent (Slice 11): real human-decision and
outcome recording against real AgentExecutionTrace rows, and the
section 29 human-AI metrics computed from them.
"""

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.agents.feedback.feedback_agent import FeedbackAgent
from app.api.dependencies.database import get_db
from app.main import app
from app.models.governance import AgentExecutionTrace

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


@pytest.fixture
def db():
    """get_db() is a generator; calling next() on it directly (as
    earlier tests in this suite do) never reaches its `finally:
    db.close()`, leaking a pooled connection per call. Cheap in one
    test, but this file calls it many times across many test methods --
    enough to exhaust QueuePool when the full suite runs. Closing the
    generator here actually runs that cleanup."""
    gen = get_db()
    session = next(gen)
    yield session
    gen.close()


def _make_trace(db, agent_id="decision-agent", output_data=None):
    trace = AgentExecutionTrace(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        output_data=output_data or {"recommendation": "Take lane X instead of lane Y."},
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        approval_status="NOT_REQUIRED",
    )
    db.add(trace)
    db.commit()
    return trace


class TestFeedbackAgent:
    def test_records_a_real_decision_with_predicted_outcome_from_the_trace(self, db):
        trace = _make_trace(db)
        feedback = FeedbackAgent().record_decision(db, trace.id, "APPROVED")
        assert feedback.agent_id == "decision-agent"
        assert feedback.predicted_outcome == "Take lane X instead of lane Y."
        assert feedback.human_action == "APPROVED"

    def test_modified_action_requires_a_reason(self, db):
        trace = _make_trace(db)
        with pytest.raises(ValueError):
            FeedbackAgent().record_decision(db, trace.id, "MODIFIED")

    def test_modified_action_with_reason_succeeds(self, db):
        trace = _make_trace(db)
        feedback = FeedbackAgent().record_decision(
            db, trace.id, "MODIFIED", modification_reason="Chose the shorter lane instead."
        )
        assert feedback.modification_reason == "Chose the shorter lane instead."

    def test_invalid_action_rejected(self, db):
        trace = _make_trace(db)
        with pytest.raises(ValueError):
            FeedbackAgent().record_decision(db, trace.id, "MAYBE")

    def test_unknown_execution_id_rejected_not_invented(self, db):
        with pytest.raises(ValueError):
            FeedbackAgent().record_decision(db, "does-not-exist", "APPROVED")

    def test_record_outcome_sets_actual_outcome_and_timestamp(self, db):
        trace = _make_trace(db)
        feedback = FeedbackAgent().record_decision(db, trace.id, "APPROVED")
        updated = FeedbackAgent().record_outcome(
            db, feedback.id, "Route completed 0.3 days faster than predicted."
        )
        assert updated.actual_outcome == "Route completed 0.3 days faster than predicted."
        assert updated.outcome_recorded_at is not None

    def test_unknown_feedback_id_rejected(self, db):
        with pytest.raises(ValueError):
            FeedbackAgent().record_outcome(db, 999_999_999, "irrelevant")

    def test_metrics_reflect_real_recorded_rows(self, db):
        # The test DB persists across the suite (no per-test reset), so
        # this checks the real effect of one new row rather than
        # asserting an exact total that other tests would break.
        before = FeedbackAgent().metrics(db)
        trace = _make_trace(db)
        FeedbackAgent().record_decision(db, trace.id, "APPROVED")
        after = FeedbackAgent().metrics(db)
        assert after["total"] == before["total"] + 1
        assert 0 <= after["approval_rate"] <= 1
        assert 0 <= after["override_rate"] <= 1


class TestFeedbackApiRoutes:
    def test_create_and_fetch_feedback(self, db):
        trace = _make_trace(db)

        res = client.post("/api/feedback", json={"execution_id": trace.id, "human_action": "APPROVED"})
        assert res.status_code == 200
        body = res.json()
        assert body["human_action"] == "APPROVED"
        assert body["reviewer_id"] == "tester"  # from conftest's authenticated_by_default override

        res = client.get("/api/feedback")
        assert res.status_code == 200
        assert any(f["id"] == body["id"] for f in res.json())

    def test_record_outcome_via_api(self, db):
        trace = _make_trace(db)
        created = client.post("/api/feedback", json={"execution_id": trace.id, "human_action": "REJECTED"}).json()

        res = client.patch(f"/api/feedback/{created['id']}/outcome", json={"actual_outcome": "Reverted manually."})
        assert res.status_code == 200
        assert res.json()["actual_outcome"] == "Reverted manually."

    def test_modified_without_reason_is_a_client_error_not_a_500(self, db):
        trace = _make_trace(db)
        res = client.post("/api/feedback", json={"execution_id": trace.id, "human_action": "MODIFIED"})
        assert res.status_code == 404

    def test_metrics_endpoint(self):
        res = client.get("/api/feedback/metrics")
        assert res.status_code == 200
        body = res.json()
        assert "approval_rate" in body and "override_rate" in body
