"""Tests for real route optimization (Slice 06): RouteOptimizer's path
search and scoring, RouteAgent's twin-backed recommendation, config
weight parsing, and the GET /api/route/optimize endpoint.

The four fixed route names route_agent.py used to return regardless of
any real distance/risk/cost -- "Cape of Good Hope Bypass", "Corridor
Beta (Southern Bypass)", "Suez Canal Commercial Passage", "Direct
Deepwater Corridor" -- are asserted absent throughout, the same way
test_agent_contracts.py asserts the coordinator's old dead fallbacks
stay gone.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.risk.risk_agent import RiskAgent
from app.agents.route.optimizer import RouteOptimizer
from app.agents.route.route_agent import RouteAgent
from app.core.config import Settings
from app.main import app
from app.schemas.agent_io import RiskAssessment
from app.twin.digital_twin import DigitalTwin

client = TestClient(app)
with client:
    pass  # triggers the lifespan startup once so governance agents exist

FABRICATED_ROUTE_NAMES = (
    "Cape of Good Hope Bypass",
    "Corridor Beta (Southern Bypass)",
    "Suez Canal Commercial Passage",
    "Direct Deepwater Corridor",
)


class TestRouteOptimizerPathSearch:
    @pytest.fixture
    def twin(self):
        return DigitalTwin()

    def test_finds_both_real_alternatives_between_shanghai_and_rotterdam(self, twin):
        """Shanghai-Rotterdam has two genuinely distinct curated lanes
        (via Suez, via the Cape) -- both must come back as separate
        candidates, not collapsed into one."""
        twin.annotate_risk({})
        candidates = RouteOptimizer().find_routes(twin.graph, "Shanghai", "Rotterdam")
        lane_id_sets = [set(c.lane_ids) for c in candidates]
        assert {"shanghai-rotterdam-suez"} in lane_id_sets
        assert {"shanghai-rotterdam-cape"} in lane_id_sets

    def test_direct_suez_lane_is_shorter_than_cape_detour(self, twin):
        twin.annotate_risk({})
        candidates = {
            frozenset(c.lane_ids): c
            for c in RouteOptimizer().find_routes(twin.graph, "Shanghai", "Rotterdam")
        }
        suez = candidates[frozenset({"shanghai-rotterdam-suez"})]
        cape = candidates[frozenset({"shanghai-rotterdam-cape"})]
        assert suez.distance_nm < cape.distance_nm

    def test_unknown_origin_raises(self, twin):
        twin.annotate_risk({})
        with pytest.raises(ValueError, match="Atlantis"):
            RouteOptimizer().find_routes(twin.graph, "Atlantis", "Rotterdam")

    def test_unknown_destination_raises(self, twin):
        twin.annotate_risk({})
        with pytest.raises(ValueError, match="Atlantis"):
            RouteOptimizer().find_routes(twin.graph, "Shanghai", "Atlantis")

    def test_candidates_are_sorted_ascending_by_score(self, twin):
        twin.annotate_risk({})
        candidates = RouteOptimizer().find_routes(twin.graph, "Shanghai", "Rotterdam")
        scores = [c.score for c in candidates]
        assert scores == sorted(scores)


class TestRouteOptimizerWeighting:
    """Proves the weights are genuinely used, not decorative -- the
    spec's Optimization Agent requirement (§12) is specifically that
    weights be configurable, which only means something if changing
    them actually changes the recommendation."""

    @pytest.fixture
    def twin(self):
        twin = DigitalTwin()
        # Suez badly stormy, Cape calm -- the two real alternatives
        # between Shanghai and Rotterdam should now clearly disagree on
        # which is "better" depending on what's being optimized for.
        twin.annotate_risk({
            "Suez Canal (Gulf of Suez)": 95,
            "Strait of Malacca": 10,
            "Cape of Good Hope": 5,
        })
        return twin

    def test_risk_heavy_weights_prefer_the_calmer_longer_route(self, twin):
        candidates = RouteOptimizer().find_routes(
            twin.graph, "Shanghai", "Rotterdam",
            weights={"risk": 0.9, "cost": 0.033, "delay": 0.033, "emissions": 0.034},
        )
        assert candidates[0].lane_ids == ["shanghai-rotterdam-cape"]

    def test_cost_and_delay_heavy_weights_prefer_the_shorter_riskier_route(self, twin):
        candidates = RouteOptimizer().find_routes(
            twin.graph, "Shanghai", "Rotterdam",
            weights={"risk": 0.05, "cost": 0.45, "delay": 0.45, "emissions": 0.05},
        )
        assert candidates[0].lane_ids == ["shanghai-rotterdam-suez"]

    def test_weights_dont_need_to_sum_to_one(self, twin):
        """Settings.ROUTE_OPTIMIZATION_WEIGHTS is normalized by its own
        sum at use time, so a partial override still ranks sensibly."""
        candidates = RouteOptimizer().find_routes(
            twin.graph, "Shanghai", "Rotterdam", weights={"risk": 40},
        )
        assert candidates[0].lane_ids == ["shanghai-rotterdam-cape"]


class TestRouteAgent:
    def test_suggest_route_returns_real_data_not_a_fabricated_label(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

        recommendation = RouteAgent().suggest_route("Shanghai", "Rotterdam")

        for name in FABRICATED_ROUTE_NAMES:
            assert name not in recommendation.route
            assert name not in recommendation.reason

        assert recommendation.origin == "Shanghai"
        assert recommendation.destination == "Rotterdam"
        assert len(recommendation.lane_ids) >= 1
        assert recommendation.distance_nm > 0
        assert 0 <= recommendation.risk <= 100
        assert len(recommendation.alternatives) >= 1
        # The recommended candidate should not also appear as its own alternative.
        assert recommendation.lane_ids not in [alt.lane_ids for alt in recommendation.alternatives]


class TestRouteOptimizationWeightsConfig:
    def test_default_weights(self):
        settings = Settings()
        assert settings.ROUTE_OPTIMIZATION_WEIGHTS == {
            "risk": 0.4, "cost": 0.25, "delay": 0.25, "emissions": 0.1,
        }

    def test_parses_csv_env_string(self, monkeypatch):
        monkeypatch.setenv("ROUTE_OPTIMIZATION_WEIGHTS", "risk:0.6,cost:0.2,delay:0.1,emissions:0.1")
        settings = Settings()
        assert settings.ROUTE_OPTIMIZATION_WEIGHTS == {
            "risk": 0.6, "cost": 0.2, "delay": 0.1, "emissions": 0.1,
        }


class TestRouteOptimizeApiRoute:
    def test_returns_real_ranked_alternatives(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

        response = client.get(
            "/api/route/optimize", params={"origin": "Shanghai", "destination": "Rotterdam"}
        )
        assert response.status_code == 200
        data = response.json()
        for name in FABRICATED_ROUTE_NAMES:
            assert name not in data["route"]
        assert data["origin"] == "Shanghai"
        assert len(data["alternatives"]) >= 1

    def test_unknown_port_is_404_not_500(self, monkeypatch):
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

        response = client.get(
            "/api/route/optimize", params={"origin": "Atlantis", "destination": "Rotterdam"}
        )
        assert response.status_code == 404

    def test_malformed_weights_is_422_not_500(self):
        response = client.get(
            "/api/route/optimize",
            params={"origin": "Shanghai", "destination": "Rotterdam", "weights": "not-valid"},
        )
        assert response.status_code == 422

    def test_custom_weights_change_the_result(self, monkeypatch):
        """End-to-end version of TestRouteOptimizerWeighting -- confirms
        the config-driven weighting is actually reachable through the
        HTTP layer, not just at the RouteOptimizer unit level.

        RiskAgent.calculate_risk() is monkeypatched directly here rather
        than crafting an event dict the real trained model happens to
        score high -- that model's exact scoring behavior is a separate
        concern (test_risk_model.py's), and depending on it here would
        make this test fragile to a model retrain. One corridor event
        with severity="critical" is still supplied so the real
        location-keying logic in fetch_live_corridor_scores() is
        exercised, just not the ML scoring itself.
        """
        def stormy_suez_event(self, use_cache=True):
            return [
                {"location": "Suez Canal (Gulf of Suez)", "severity": "critical",
                 "event_type": "Severe Storm", "latitude": 29.35, "longitude": 32.60},
            ]

        def fixed_high_score(self, event, route=None):
            return RiskAssessment(
                score=95, severity="critical", likelihood="high", impact="critical",
                category="Severe Storm", scoring_method="ml",
            )

        monkeypatch.setattr(LiveConditionsClient, "get_all_events", stormy_suez_event)
        monkeypatch.setattr(RiskAgent, "calculate_risk", fixed_high_score)

        response = client.get(
            "/api/route/optimize",
            params={
                "origin": "Shanghai", "destination": "Rotterdam",
                "weights": "risk:0.9,cost:0.03,delay:0.03,emissions:0.04",
            },
        )
        assert response.status_code == 200
        assert response.json()["lane_ids"] == ["shanghai-rotterdam-cape"]
