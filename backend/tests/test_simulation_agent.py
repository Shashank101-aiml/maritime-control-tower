"""Tests for the Simulation Agent (Slice 08): real what-if scenarios
over a *copy* of the digital twin -- moderate/severe disruption at a
chosen monitored corridor, compared against today's real baseline.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.simulation.simulation_agent import SimulationAgent
from app.main import app
from app.twin.digital_twin import get_digital_twin

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


@pytest.fixture(autouse=True)
def deterministic_live_feed(monkeypatch):
    monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])


class TestSimulationAgentValidation:
    def test_rejects_unknown_scenario(self):
        with pytest.raises(ValueError):
            SimulationAgent().simulate("Shanghai", "Rotterdam", "Suez Canal (Gulf of Suez)", "CATASTROPHIC")

    def test_rejects_unknown_corridor(self):
        with pytest.raises(ValueError):
            SimulationAgent().simulate("Shanghai", "Rotterdam", "Bermuda Triangle", "MODERATE")

    def test_propagates_unreachable_ports_from_the_optimizer(self):
        with pytest.raises(ValueError):
            SimulationAgent().simulate("Shanghai", "Nowhere", "Suez Canal (Gulf of Suez)", "MODERATE")


class TestSimulationAgentScenarios:
    def test_none_scenario_is_just_todays_real_recommendation(self):
        result = SimulationAgent().simulate("Shanghai", "Rotterdam", "Suez Canal (Gulf of Suez)", "NONE")

        assert result.scenario == "NONE"
        assert result.route_changed is False
        assert result.no_viable_route is False
        assert result.scenario_lane_ids == result.baseline_lane_ids
        assert result.lanes_affected == 0

    def test_corridor_not_on_the_path_leaves_the_route_unchanged(self):
        # Every real candidate path between Shanghai and Los Angeles is
        # open ocean (see lanes.py) -- none crosses Suez, so disrupting
        # Suez should honestly report zero *query-relevant* lanes
        # affected, even though Suez-crossing lanes exist elsewhere in
        # the network (that's what the earlier "lanes_affected" bug
        # conflated: a global count, not a query-scoped one).
        result = SimulationAgent().simulate(
            "Shanghai", "Los Angeles", "Suez Canal (Gulf of Suez)", "SEVERE"
        )
        assert result.lanes_affected == 0
        assert result.route_changed is False
        assert "doesn't change" in result.summary

    def test_severe_disruption_forces_the_only_remaining_real_alternative(self):
        # Shanghai-Rotterdam has exactly two real alternatives: via Suez
        # (crosses Suez Canal) and via the Cape (does not). Removing
        # every lane that crosses Suez should force the Cape route.
        result = SimulationAgent().simulate(
            "Shanghai", "Rotterdam", "Suez Canal (Gulf of Suez)", "SEVERE"
        )
        assert result.lanes_affected >= 1
        assert result.route_changed is True
        assert result.scenario_lane_ids == ["shanghai-rotterdam-cape"]
        assert result.no_viable_route is False

    def test_moderate_disruption_raises_risk_to_at_least_the_simulated_band(self):
        # Dubai -> Colombo's only direct lane crosses Arabian Sea with a
        # real baseline risk of 64 (Colombo's own congestion percentile,
        # since the mocked live feed has no corridor data) -- lower than
        # the 70 moderate-disruption band, so the bump is genuinely
        # visible rather than swallowed by an already-higher congestion
        # floor (as Shanghai<->Rotterdam's 75-congestion endpoint would).
        baseline = SimulationAgent().simulate(
            "Dubai (Jebel Ali)", "Colombo", "Arabian Sea", "NONE"
        )
        assert baseline.baseline_risk == 64

        result = SimulationAgent().simulate(
            "Dubai (Jebel Ali)", "Colombo", "Arabian Sea", "MODERATE"
        )
        assert result.lanes_affected >= 1
        assert result.scenario_risk == 70
        assert result.scenario_risk > result.baseline_risk

    def test_moderate_disruption_never_lowers_risk_below_the_congestion_floor(self):
        # Shanghai<->Rotterdam's congestion-only baseline (75, from
        # Rotterdam) already exceeds the 70 moderate band -- simulating
        # a moderate disruption there must not report risk dropping.
        result = SimulationAgent().simulate(
            "Shanghai", "Rotterdam", "Suez Canal (Gulf of Suez)", "MODERATE",
        )
        assert result.scenario_risk >= result.baseline_risk >= 70

    def test_scenario_never_mutates_the_shared_twin_singleton(self):
        live_twin = get_digital_twin()
        before = {
            (u, v, k): data["risk"]
            for u, v, k, data in live_twin.graph.edges(keys=True, data=True)
        }

        SimulationAgent().simulate("Shanghai", "Rotterdam", "Suez Canal (Gulf of Suez)", "SEVERE")

        after = {
            (u, v, k): data["risk"]
            for u, v, k, data in live_twin.graph.edges(keys=True, data=True)
        }
        assert before.keys() == after.keys(), "SEVERE scenario must not remove edges from the shared twin"
        assert before == after


class TestSimulateApiRoute:
    def _token(self):
        res = client.post(
            "/api/auth/login",
            data={"username": "admin@example.com", "password": "admin"},
        )
        return res.json()["access_token"]

    def test_simulate_endpoint_returns_real_scenario_data(self):
        token = self._token()
        res = client.get(
            "/api/simulate",
            params={
                "origin": "Shanghai", "destination": "Rotterdam",
                "corridor": "Suez Canal (Gulf of Suez)", "scenario": "SEVERE",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["scenario"] == "SEVERE"
        assert body["scenario_lane_ids"] == ["shanghai-rotterdam-cape"]

    def test_unknown_corridor_is_a_client_error_not_a_500(self):
        token = self._token()
        res = client.get(
            "/api/simulate",
            params={
                "origin": "Shanghai", "destination": "Rotterdam",
                "corridor": "Bermuda Triangle", "scenario": "MODERATE",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404
