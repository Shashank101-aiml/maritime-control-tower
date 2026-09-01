"""Tests for the typed agent-to-agent contracts (app/schemas/agent_io.py)
and the coordinator pipeline that uses them.

Before this, agents passed each other plain dicts read with .get() and
silent defaults -- e.g. the coordinator reading a missing risk score as
`risk.get("score", 50)` rather than failing. These tests exist to prove
two things: the contracts actually reject a malformed hand-off instead
of silently defaulting, and the full pipeline still produces real,
non-fabricated values end to end (fresh execution *and* resumed from a
persisted trace, since GovernanceEngine round-trips every hand-off
through a JSON column between steps).
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.risk.risk_agent import RiskAgent
from app.api.dependencies.database import get_db
from app.main import app
from app.schemas.agent_io import IngestedEvent, RiskAssessment, RouteRecommendation

client = TestClient(app)
with client:
    pass  # triggers the lifespan startup once so governance agents exist


def test_risk_assessment_requires_score():
    """A risk agent that forgets to produce a score must fail loudly, not
    silently become "medium risk" the way `risk.get("score", 50)` did."""
    with pytest.raises(ValidationError):
        RiskAssessment(
            severity="warning",
            likelihood="low",
            impact="low",
            category="operational",
            scoring_method="ml",
        )


def test_risk_assessment_score_is_bounded():
    with pytest.raises(ValidationError):
        RiskAssessment(
            score=150,
            severity="warning",
            likelihood="low",
            impact="low",
            category="operational",
            scoring_method="ml",
        )


def test_ingested_event_requires_event_type():
    with pytest.raises(ValidationError):
        IngestedEvent(severity="warning")


def test_ingested_event_accepts_the_real_shape_ingestion_produces():
    """Mirrors IngestionAgent._normalize_event()'s output plus the extra
    fields the live path and collect_data_with_confidence() add."""
    event = IngestedEvent(
        event_type="Moderate Swell & Strong Winds",
        severity="warning",
        source="open-meteo",
        description="Cape of Good Hope: 3.3 m significant wave height.",
        location="Cape of Good Hope",
        timestamp="2026-09-01T17:22:58Z",
        latitude=-34.6,
        longitude=19.5,
        conditions={"wave_height_m": 3.34, "wind_gusts_kmh": 27.7},
        weather=None,
        related_news=[],
    )
    assert event.location == "Cape of Good Hope"
    assert event.latitude == -34.6


def test_risk_agent_accepts_both_a_typed_event_and_a_plain_dict():
    """calculate_risk() is called with a typed IngestedEvent from the
    coordinator, and with a plain dict from the HTTP routes that predate
    the typed contracts (dashboard.py, risks.py) -- both must work."""
    event_dict = {
        "event_type": "Storm",
        "severity": "critical",
        "location": "Arabian Sea",
        "description": None,
    }
    result_from_dict = RiskAgent().calculate_risk(event_dict)
    assert isinstance(result_from_dict, RiskAssessment)
    assert 0 <= result_from_dict.score <= 100

    result_from_model = RiskAgent().calculate_risk(IngestedEvent(**event_dict))
    assert isinstance(result_from_model, RiskAssessment)
    assert 0 <= result_from_model.score <= 100


def test_route_recommendation_round_trips_through_a_plain_dict():
    """This is exactly what GovernanceEngine does between coordinator
    steps: model_dump() into a JSON column, then model_validate() back
    out on the next call (or on resuming a session from a persisted
    trace) -- confirm nothing is lost in that round trip."""
    original = RouteRecommendation(route="Direct Deepwater Corridor", reason="Low risk.")
    as_dict = original.model_dump()
    rehydrated = RouteRecommendation.model_validate(as_dict)
    assert rehydrated == original


class TestCoordinatorPipeline:
    """End-to-end through the real coordinator, database, and governance
    engine -- not mocked. ENABLE_LIVE_INGESTION is off (conftest.py), so
    this never touches the network."""

    def test_full_pipeline_produces_real_typed_values(self):
        import uuid

        from app.agents.coordinator.coordinator_agent import CoordinatorAgent
        from app.governance.policy import resolve_approval

        db = next(get_db())
        session_id = f"test-contract-pipeline-{uuid.uuid4()}"
        result = CoordinatorAgent().run(db=db, session_id=session_id)

        # Every step that requires human approval must be walked through
        # explicitly -- resuming re-enters the coordinator each time,
        # exercising the model_validate() rehydration path from a
        # persisted (JSON-column) trace rather than a fresh in-memory one.
        seen_statuses = [result["status"]]
        for _ in range(5):
            if result["status"] != "PENDING_APPROVAL":
                break
            resolve_approval(db, result["approval_id"], "APPROVED", "test-runner")
            result = CoordinatorAgent().run(db=db, session_id=session_id)
            seen_statuses.append(result["status"])

        assert result["status"] == "COMPLETED", (
            f"Pipeline did not complete; status history: {seen_statuses}"
        )

        # The values the old code could fabricate or silently default:
        assert isinstance(result["risk_score"], int)
        assert 0 <= result["risk_score"] <= 100

        # These two specific strings were hardcoded fallbacks that could
        # never actually be reached (trace3/trace4 are always set by the
        # time they're read) -- if they show up, the dead branch came back.
        assert result["route"]["route"] != "Corridor Beta (Southern Bypass)"
        assert "Multi-agent pipeline completed risk assessment" not in result["explanation"]

        assert set(result["route"].keys()) == {"route", "reason"}
        assert isinstance(result["event"]["event_type"], str)
