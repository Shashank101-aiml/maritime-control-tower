"""Tests for the Shipment Delay agent's real-data overview/profile
additions -- the manual prediction form used to be a single hardcoded
example with no connection to the real training data at all (its
default plant/port combination, PLANT03 + PORT08, does not even occur
together in the real data). These prove the new endpoints are built
from that real data, not invented.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.delay.delay_agent import DelayAgent
from app.main import app

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


class TestDelayAgentOverview:
    def test_has_reference_data(self):
        agent = DelayAgent()
        assert agent.has_reference_data

    def test_overview_reports_real_totals(self):
        agent = DelayAgent()
        overview = agent.overview()
        assert overview["orders"] == 9215
        assert 0 < overview["overall_late_rate"] < 1

    def test_known_values_match_the_real_small_categorical_universe(self):
        """This dataset genuinely only has 3 origin ports and 1
        destination port -- not a bug, the real shape of the data."""
        agent = DelayAgent()
        overview = agent.overview()
        assert set(overview["known_values"]["origin_port"]) == {"PORT04", "PORT05", "PORT09"}
        assert overview["known_values"]["destination_port"] == ["PORT09"]
        assert len(overview["known_values"]["carrier"]) == 3
        assert len(overview["known_values"]["plant_code"]) == 7

    def test_breakdown_sorted_worst_first_and_sums_to_total_orders(self):
        agent = DelayAgent()
        overview = agent.overview()
        carrier_breakdown = overview["breakdown"]["carrier"]
        rates = [c["late_rate"] for c in carrier_breakdown]
        assert rates == sorted(rates, reverse=True)
        assert sum(c["orders"] for c in carrier_breakdown) == overview["orders"]

    def test_typical_values_are_real_dataset_medians(self):
        agent = DelayAgent()
        overview = agent.overview()
        expected_freight_rate_median = float(agent._orders["freight_rate"].median())
        assert overview["typical"]["freight_rate"] == pytest.approx(expected_freight_rate_median)
        assert overview["typical"]["weight"] is not None

    def test_plant_ports_mapping_is_real_and_not_a_fabricated_link_to_congestion(self):
        """PLANT03's real port is PORT04 -- the old hardcoded form
        default (plant_code=PLANT03, origin_port=PORT08) was never a
        real combination in this data."""
        agent = DelayAgent()
        overview = agent.overview()
        assert overview["plant_ports"]["PLANT03"] == ["PORT04"]


class TestDelayAgentPlantProfile:
    def test_unknown_plant_raises(self):
        agent = DelayAgent()
        with pytest.raises(ValueError):
            agent.plant_profile("PLANT99")

    def test_profile_values_are_real_aggregates_not_invented(self):
        agent = DelayAgent()
        profile = agent.plant_profile("PLANT16")
        assert profile["orders"] > 0
        assert profile["real_ports"] == ["PORT09"]
        # Every numeric field the model was trained on but the old form
        # never collected must now be present and real (not None).
        for field in ["freight_rate", "freight_min_cost", "wh_cost_per_unit", "wh_daily_capacity"]:
            assert profile["profile"][field] is not None

    def test_profile_categoricals_are_real_values_for_that_plant(self):
        agent = DelayAgent()
        profile = agent.plant_profile("PLANT16")
        overview = agent.overview()
        assert profile["profile"]["carrier"] in overview["known_values"]["carrier"]
        assert profile["profile"]["origin_port"] in overview["known_values"]["origin_port"]


class TestDelayApiRoutes:
    def _token(self):
        res = client.post(
            "/api/auth/login",
            data={"username": "admin@example.com", "password": "admin"},
        )
        return res.json()["access_token"]

    def test_overview_endpoint(self):
        token = self._token()
        res = client.get("/api/delay/overview", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["orders"] == 9215
        assert "live_fleet_context" in body
        # Real, separate from the delay data -- how many of the 20
        # congestion-monitored ports are currently flagged, not a
        # fabricated join with this dataset's PORT0x codes.
        if body["live_fleet_context"]:
            assert body["live_fleet_context"]["monitored_ports"] == 20

    def test_plant_profile_endpoint(self):
        token = self._token()
        res = client.get("/api/delay/plant/PLANT16/profile", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["plant_code"] == "PLANT16"

    def test_unknown_plant_profile_is_a_client_error(self):
        token = self._token()
        res = client.get("/api/delay/plant/PLANT99/profile", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404
