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

from app.agents.ingestion.live_conditions_client import LiveConditionsClient
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
    original = RouteRecommendation(
        route="Shanghai to Rotterdam via shanghai-rotterdam-suez",
        reason="Direct route via shanghai-rotterdam-suez -- 8478 nm, ~19.6 days, risk 24/100.",
        origin="Shanghai",
        destination="Rotterdam",
        lane_ids=["shanghai-rotterdam-suez"],
        distance_nm=8478,
        transit_days=19.6,
        cost_usd=8478,
        emissions_estimate=8478,
        risk=24,
        score=0.0,
    )
    as_dict = original.model_dump()
    rehydrated = RouteRecommendation.model_validate(as_dict)
    assert rehydrated == original


class TestCoordinatorPipeline:
    """End-to-end through the real coordinator, database, and governance
    engine -- not mocked. ENABLE_LIVE_INGESTION is off (conftest.py) for
    the ingestion step, but the route step's fetch_live_corridor_scores()
    calls LiveConditionsClient directly (same as GET /api/twin) and
    isn't gated by that flag -- monkeypatched here for the same reason
    test_digital_twin.py's API-route test patches it: determinism, not
    dependence on a third-party feed being reachable during a test run.
    """

    def test_full_pipeline_produces_real_typed_values(self, monkeypatch):
        import uuid

        from app.agents.coordinator.coordinator_agent import CoordinatorAgent
        from app.governance.policy import resolve_approval

        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

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

        # None of route_agent.py's four retired fixed route names --
        # confirms the real optimizer is in the loop, not the old ladder.
        for fabricated_name in (
            "Cape of Good Hope Bypass",
            "Corridor Beta (Southern Bypass)",
            "Suez Canal Commercial Passage",
            "Direct Deepwater Corridor",
        ):
            assert fabricated_name not in result["route"]["route"]

        # Real, digital-twin-backed fields (Slice 06) -- not a canned string.
        route = result["route"]
        assert route["origin"] in route["route"]
        assert route["destination"] in route["route"]
        assert len(route["lane_ids"]) >= 1
        assert route["distance_nm"] > 0
        assert 0 <= route["risk"] <= 100
        assert isinstance(route["alternatives"], list)

        assert isinstance(result["event"]["event_type"], str)

        # Slice 07: a real structured decision, not a route with no
        # trade-off framing -- confidence is derived from the
        # recommended lane's own live risk (see decision_agent.py).
        decision = result["decision"]
        assert decision["confidence"] == round(1 - route["risk"] / 100, 2)
        assert isinstance(decision["requires_human_approval"], bool)
        assert decision["recommended_lane_ids"] == route["lane_ids"]
        assert isinstance(decision["baseline_lane_ids"], list) and len(decision["baseline_lane_ids"]) >= 1

        # Slice 13: the sample fixture's real risk score (28) is above
        # the adaptive-orchestration threshold, so this run took the
        # full chain -- confirms which path actually executed rather
        # than inferring it from route/decision being non-null.
        assert result["adaptive_pipeline"] == "full"


class TestAdaptiveOrchestration:
    """Spec section 21: a nominal-risk event should take a genuinely
    shorter path through the coordinator, not the same fixed chain
    regardless of what the risk agent found."""

    def test_a_nominal_risk_event_skips_route_decision_and_explanation(self, monkeypatch):
        import uuid

        from app.agents.coordinator.coordinator_agent import CoordinatorAgent
        from app.agents.risk.risk_agent import RiskAgent
        from app.governance.policy import resolve_approval
        from app.schemas.agent_io import RiskAssessment

        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

        def fixed_nominal_score(self, event, route=None):
            return RiskAssessment(
                score=5, severity="info", likelihood="low", impact="low",
                category="Calm Conditions", scoring_method="rule_based",
            )

        monkeypatch.setattr(RiskAgent, "calculate_risk", fixed_nominal_score)

        db = next(get_db())
        session_id = f"test-adaptive-simple-{uuid.uuid4()}"
        result = CoordinatorAgent().run(db=db, session_id=session_id)

        # The risk-agent step can still itself be gated (e.g. CRITICAL
        # criticality always requires approval, independent of the
        # score) -- walk through any such gate the same way the full-
        # pipeline test does, so this exercises the real adaptive
        # decision point after risk scoring, not a lucky first pass.
        for _ in range(5):
            if result["status"] != "PENDING_APPROVAL":
                break
            resolve_approval(db, result["approval_id"], "APPROVED", "test-runner")
            result = CoordinatorAgent().run(db=db, session_id=session_id)

        assert result["status"] == "COMPLETED"
        assert result["risk_score"] == 5
        assert result["adaptive_pipeline"] == "simple"
        assert result["route"] is None
        assert result["decision"] is None
        assert result["decision_execution_id"] is None
        assert "skipped" in result["explanation"].lower()

    def test_an_elevated_risk_event_still_takes_the_full_chain(self, monkeypatch):
        import uuid

        from app.agents.coordinator.coordinator_agent import CoordinatorAgent
        from app.agents.risk.risk_agent import RiskAgent
        from app.governance.policy import resolve_approval
        from app.schemas.agent_io import RiskAssessment

        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

        def fixed_elevated_score(self, event, route=None):
            return RiskAssessment(
                score=80, severity="critical", likelihood="high", impact="high",
                category="Severe Storm", scoring_method="rule_based",
            )

        monkeypatch.setattr(RiskAgent, "calculate_risk", fixed_elevated_score)

        db = next(get_db())
        session_id = f"test-adaptive-full-{uuid.uuid4()}"
        result = CoordinatorAgent().run(db=db, session_id=session_id)
        for _ in range(5):
            if result["status"] != "PENDING_APPROVAL":
                break
            resolve_approval(db, result["approval_id"], "APPROVED", "test-runner")
            result = CoordinatorAgent().run(db=db, session_id=session_id)

        assert result["status"] == "COMPLETED"
        assert result["adaptive_pipeline"] == "full"
        assert result["route"] is not None
        assert result["decision"] is not None
