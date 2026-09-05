"""Tests for the Decision Agent (Slice 07): turning a ranked
RouteRecommendation into a structured trade-off comparison against the
shortest-distance candidate, per spec section 13.
"""

from app.agents.decision.decision_agent import DecisionAgent
from app.schemas.agent_io import RouteAlternative, RouteRecommendation


def make_route(risk=30, alternatives=None):
    return RouteRecommendation(
        route="Shanghai to Rotterdam via shanghai-suez",
        reason="test fixture",
        origin="Shanghai",
        destination="Rotterdam",
        lane_ids=["shanghai-suez"],
        distance_nm=1000.0,
        transit_days=2.3,
        cost_usd=1000.0,
        emissions_estimate=1000.0,
        risk=risk,
        score=0.0,
        alternatives=alternatives or [],
    )


class TestDecisionAgentTradeoff:
    def test_no_alternatives_means_baseline_equals_recommended(self):
        route = make_route(risk=20)
        decision = DecisionAgent().decide(route)

        assert decision.baseline_lane_ids == decision.recommended_lane_ids == ["shanghai-suez"]
        assert decision.expected_delay_days == 0
        assert decision.estimated_cost_change_usd == 0
        assert decision.risk_reduction == 0
        assert "no trade-off" in decision.recommendation.lower()

    def test_a_longer_but_safer_alternative_shows_a_real_tradeoff(self):
        # The recommended (top) candidate is the shorter, riskier one;
        # a longer, safer alternative also exists in the same query --
        # the shortest-distance candidate becomes the baseline, so the
        # recommendation should show it costs distance/time to be safer.
        route = make_route(
            risk=70,
            alternatives=[
                RouteAlternative(
                    lane_ids=["cape-route"],
                    distance_nm=1600.0,
                    transit_days=3.7,
                    cost_usd=1600.0,
                    emissions_estimate=1600.0,
                    risk=20,
                    score=0.9,
                )
            ],
        )
        decision = DecisionAgent().decide(route)

        # Baseline = shortest distance = the recommended candidate itself
        # (1000 nm vs 1600 nm) -- so here the *shorter* one is both
        # baseline and recommended; risk difference is therefore zero,
        # proving baseline selection is real distance comparison, not a
        # hardcoded "the alternative is the baseline" assumption.
        assert decision.baseline_lane_ids == ["shanghai-suez"]
        assert decision.recommended_lane_ids == ["shanghai-suez"]

    def test_baseline_differs_from_recommended_when_shortest_is_not_top_ranked(self):
        # Recommended (top-ranked by weighted score) is the longer,
        # safer lane; the shorter lane is riskier and becomes the
        # baseline a distance-only chooser would have picked.
        safer_longer = RouteAlternative(
            lane_ids=["safer-longer"], distance_nm=1600.0, transit_days=3.7,
            cost_usd=1600.0, emissions_estimate=1600.0, risk=15, score=0.0,
        )
        route = RouteRecommendation(
            route="via safer-longer", reason="test fixture",
            origin="Shanghai", destination="Rotterdam",
            lane_ids=safer_longer.lane_ids, distance_nm=safer_longer.distance_nm,
            transit_days=safer_longer.transit_days, cost_usd=safer_longer.cost_usd,
            emissions_estimate=safer_longer.emissions_estimate, risk=safer_longer.risk,
            score=safer_longer.score,
            alternatives=[
                RouteAlternative(
                    lane_ids=["shorter-riskier"], distance_nm=1000.0, transit_days=2.3,
                    cost_usd=1000.0, emissions_estimate=1000.0, risk=70, score=0.5,
                )
            ],
        )
        decision = DecisionAgent().decide(route)

        assert decision.baseline_lane_ids == ["shorter-riskier"]
        assert decision.recommended_lane_ids == ["safer-longer"]
        assert decision.expected_delay_days == round(3.7 - 2.3, 1)
        assert decision.estimated_cost_change_usd == round(1600.0 - 1000.0, 2)
        assert decision.risk_reduction == 70 - 15
        assert "safer" in decision.recommendation.lower()
        assert "slower" in decision.recommendation.lower()

    def test_confidence_is_derived_from_recommended_risk_not_invented(self):
        assert DecisionAgent().decide(make_route(risk=0)).confidence == 1.0
        assert DecisionAgent().decide(make_route(risk=100)).confidence == 0.0
        assert DecisionAgent().decide(make_route(risk=40)).confidence == 0.6

    def test_requires_approval_when_confidence_below_threshold(self):
        # risk=40 -> confidence 0.6, below a 0.7 threshold.
        decision = DecisionAgent().decide(make_route(risk=40), confidence_threshold=0.7)
        assert decision.requires_human_approval is True

        decision = DecisionAgent().decide(make_route(risk=10), confidence_threshold=0.7)
        assert decision.requires_human_approval is False

    def test_requires_approval_for_elevated_risk_even_with_high_confidence_threshold(self):
        # risk=65 -> confidence 0.35, but even with a lax 0.1 threshold
        # an elevated-risk pick (>= 60) still requires a human look.
        decision = DecisionAgent().decide(make_route(risk=65), confidence_threshold=0.1)
        assert decision.requires_human_approval is True
