"""Tests for the Explanation Agent's fallback path.

ExplanationAgent() is always constructed with no arguments in the real
pipeline (coordinator_agent.py), so `provider` defaults to "fallback"
and this path -- not the OpenAI one -- is what every real explanation
in this system actually goes through. It used to return one fixed,
hardcoded paragraph regardless of input; these prove it's now built
from the real route/event/risk data passed in.
"""

import pytest

from app.agents.explanation.explanation_agent import ExplanationAgent


@pytest.fixture
def agent():
    return ExplanationAgent()


ROUTE = {
    "route": "Singapore to Rotterdam via SGP-DXB + DXB-RTM",
    "reason": "2-leg route via SGP-DXB, DXB-RTM -- 8500 nm, ~28.4 days, risk 35/100.",
    "distance_nm": 8500.0,
    "transit_days": 28.4,
    "risk": 35,
}

EVENT = {
    "event_type": "Rough Seas & Gale Conditions",
    "location": "Cape of Good Hope",
    "severity": "high",
}

RISK = {
    "score": 72,
    "severity": "high",
    "category": "Rough Seas & Gale Conditions",
}


class TestFallbackIsDynamic:
    def test_uses_the_real_event_type_and_location(self, agent):
        text = agent.explain(route=ROUTE, event=EVENT, risk=RISK)
        assert "Rough Seas & Gale Conditions" in text
        assert "Cape of Good Hope" in text

    def test_uses_the_real_risk_score(self, agent):
        text = agent.explain(route=ROUTE, event=EVENT, risk=RISK)
        assert "72/100" in text

    def test_uses_the_real_route_reason(self, agent):
        text = agent.explain(route=ROUTE, event=EVENT, risk=RISK)
        assert ROUTE["reason"].rstrip(".") in text

    def test_different_inputs_produce_different_output(self, agent):
        """The bug this fixes: the old fallback returned the identical
        string no matter what was passed in."""
        first = agent.explain(route=ROUTE, event=EVENT, risk=RISK)

        other_route = {**ROUTE, "route": "Shanghai to Los Angeles via SHA-LAX", "reason": None}
        other_event = {"event_type": "Slight Sea", "location": "Strait of Malacca", "severity": "low"}
        other_risk = {"score": 12, "severity": "low", "category": "Slight Sea"}
        second = agent.explain(route=other_route, event=other_event, risk=other_risk)

        assert first != second
        assert "Shanghai to Los Angeles" in second
        assert "12/100" in second

    def test_route_without_a_precomputed_reason_falls_back_to_computed_detail(self, agent):
        route = {"route": "A to B via X", "reason": None, "distance_nm": 100.0, "transit_days": 2.0, "risk": 10}
        text = agent.explain(route=route)
        assert "100 nm" in text
        assert "2.0 days" in text
        assert "risk 10/100" in text

    def test_missing_event_and_risk_still_describes_the_route(self, agent):
        text = agent.explain(route=ROUTE)
        assert ROUTE["route"] in text
        assert "Ingestion Agent" not in text
        assert "Risk Agent" not in text

    def test_no_data_at_all_is_reported_honestly_not_with_the_old_canned_text(self, agent):
        text = agent.explain(route={})
        assert text == "No event, risk, or route data was available to explain this execution."
        assert "vessel and crew safety" not in text  # the old hardcoded sentence


class TestRealPipelineShapesWork:
    """The actual call site (coordinator_agent.py) passes
    RouteRecommendation/IngestedEvent/RiskAssessment .model_dump()'d --
    confirms those real field names (not a simplified test shape) work."""

    def test_real_route_recommendation_shape(self, agent):
        route = {
            "route": "Suez Canal (Gulf of Suez) direct",
            "reason": "Direct route via SUEZ -- 1200 nm, ~4.0 days, risk 55/100.",
            "origin": "Port of Singapore",
            "destination": "Suez Canal (Gulf of Suez)",
            "lane_ids": ["SGP-SUEZ"],
            "distance_nm": 1200.0,
            "transit_days": 4.0,
            "cost_usd": 45000.0,
            "emissions_estimate": 1200.0,
            "risk": 55,
            "score": 0.42,
            "alternatives": [],
        }
        event = {
            "event_type": "Moderate Swell & Strong Winds", "severity": "warning", "source": "open-meteo",
            "description": None, "location": "Suez Canal (Gulf of Suez)", "timestamp": "2026-01-01T00:00:00Z",
            "latitude": 29.35, "longitude": 32.60, "conditions": None, "weather": None, "related_news": [],
        }
        risk = {
            "score": 55, "severity": "warning", "likelihood": "likely", "impact": "moderate",
            "category": "Moderate Swell & Strong Winds", "description": None, "scoring_method": "ml",
        }
        text = agent.explain(route=route, event=event, risk=risk)
        assert "Moderate Swell & Strong Winds" in text
        assert "55/100" in text
        assert "Suez Canal (Gulf of Suez) direct" in text
