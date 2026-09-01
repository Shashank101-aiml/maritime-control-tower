"""Tests for the digital twin graph (app/twin/digital_twin.py).

Three kinds of thing worth checking here: the curated data is internally
consistent (no waypoint or port name typo that would silently never
match anything), the geometry is real (a known-longer real-world route
actually comes out longer), and risk annotation picks the worse of its
two real inputs rather than averaging them away.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.ingestion.live_conditions_client import LiveConditionsClient, MONITORED_LOCATIONS
from app.main import app
from app.twin.coordinates import PORT_COORDINATES
from app.twin.digital_twin import DigitalTwin, haversine_nm
from app.twin.lanes import SHIPPING_LANES

MONITORED_NAMES = {loc["name"] for loc in MONITORED_LOCATIONS}

client = TestClient(app)
with client:
    pass  # triggers the lifespan startup once so governance agents exist


def test_every_lane_port_is_a_known_port():
    """A typo'd port name in lanes.py would silently create an isolated
    node instead of failing -- catch that here instead."""
    for lane in SHIPPING_LANES:
        assert lane.port_a in PORT_COORDINATES, f"{lane.lane_id}: unknown port {lane.port_a!r}"
        assert lane.port_b in PORT_COORDINATES, f"{lane.lane_id}: unknown port {lane.port_b!r}"


def test_every_waypoint_is_a_monitored_corridor():
    """A typo'd waypoint name would silently mean that lane never
    receives a live risk score -- it would just always fall through to
    the congestion-only branch and nobody would notice."""
    for lane in SHIPPING_LANES:
        for name in lane.waypoints:
            assert name in MONITORED_NAMES, f"{lane.lane_id}: {name!r} is not in MONITORED_LOCATIONS"


def test_lane_ids_are_unique():
    ids = [lane.lane_id for lane in SHIPPING_LANES]
    assert len(ids) == len(set(ids))


def test_haversine_same_point_is_zero():
    assert haversine_nm(31.23, 121.47, 31.23, 121.47) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    # Equator, 90 degrees of longitude apart -- a quarter of Earth's
    # circumference. Earth's mean circumference is ~21,600 nm by
    # definition (1 nm = 1 minute of arc), so a quarter is ~5,400 nm.
    distance = haversine_nm(0, 0, 0, 90)
    assert distance == pytest.approx(5400, rel=0.01)


class TestGraphStructure:
    @pytest.fixture
    def twin(self):
        return DigitalTwin()

    def test_node_count_matches_curated_ports(self, twin):
        assert twin.graph.number_of_nodes() == len(PORT_COORDINATES)

    def test_edge_count_matches_curated_lanes(self, twin):
        assert twin.graph.number_of_edges() == len(SHIPPING_LANES)

    def test_every_node_has_real_congestion_data(self, twin):
        """All 20 curated ports are drawn from port_congestion.csv's own
        port list, so every node should find a matching row -- a
        mismatch here would mean the CSV and the curated coordinates
        have silently drifted apart."""
        for port, attrs in twin.graph.nodes(data=True):
            assert attrs["congestion_index"] is not None, f"{port} has no congestion data"
            assert attrs["country"] is not None, f"{port} has no country"

    def test_cape_route_is_longer_than_suez_route(self, twin):
        """The real reason ships take Suez over the Cape at all --
        confirms the multi-segment haversine distance is at least
        directionally realistic, not just internally consistent."""
        suez = twin.graph.edges["Shanghai", "Rotterdam", "shanghai-rotterdam-suez"]
        cape = twin.graph.edges["Shanghai", "Rotterdam", "shanghai-rotterdam-cape"]
        assert cape["distance_nm"] > suez["distance_nm"]

    def test_edge_has_no_risk_before_annotation(self, twin):
        edge = twin.graph.edges["Shanghai", "Los Angeles", "shanghai-losangeles"]
        assert edge["risk"] is None

    def test_placeholder_fields_are_labeled(self, twin):
        """cost_usd/emissions_estimate are distance-based placeholders,
        not sourced freight or bunker data -- the _model field must say
        so on every edge, since that's the only thing stopping a future
        caller from treating them as real."""
        for _, _, _, attrs in twin.graph.edges(keys=True, data=True):
            assert attrs["cost_model"] == "distance_based_placeholder"
            assert attrs["emissions_model"] == "distance_based_placeholder"


class TestRiskAnnotation:
    @pytest.fixture
    def twin(self):
        return DigitalTwin()

    def test_corridor_risk_wins_when_higher(self, twin):
        twin.annotate_risk({"Suez Canal (Gulf of Suez)": 90, "Strait of Malacca": 5})
        edge = twin.graph.edges["Shanghai", "Rotterdam", "shanghai-rotterdam-suez"]
        assert edge["risk"] == 90
        assert "sea-state" in edge["risk_reason"]

    def test_congestion_wins_when_higher_than_corridor(self, twin):
        # Every corridor at 0 risk -- whatever risk shows up must have
        # come from port congestion, not sea state.
        twin.annotate_risk({name: 0 for name in MONITORED_NAMES})
        edge = twin.graph.edges["Shanghai", "Los Angeles", "shanghai-losangeles"]
        assert edge["risk"] == max(
            twin.graph.nodes["Shanghai"]["congestion_percentile"],
            twin.graph.nodes["Los Angeles"]["congestion_percentile"],
        )
        assert "congestion" in edge["risk_reason"]

    def test_lane_with_no_waypoints_is_unaffected_by_corridor_scores(self, twin):
        """A lane that never crosses a monitored corridor must be
        completely indifferent to how severe conditions are elsewhere --
        it genuinely isn't exposed to those corridors, so its risk
        should be identical whether every corridor is calm or severe."""
        edge_key = ("Shanghai", "Los Angeles", "shanghai-losangeles")

        twin.annotate_risk({name: 0 for name in MONITORED_NAMES})
        risk_when_calm = twin.graph.edges[edge_key]["risk"]

        twin.annotate_risk({name: 100 for name in MONITORED_NAMES})
        risk_when_severe = twin.graph.edges[edge_key]["risk"]

        assert risk_when_calm == risk_when_severe


class TestTwinApiRoute:
    def test_get_twin_returns_annotated_graph(self, monkeypatch):
        """Patches the live feed rather than relying on real network
        access during the test run (unlike ENABLE_LIVE_INGESTION, which
        only gates IngestionAgent, LiveConditionsClient itself has no
        offline switch -- this route calls it directly, the same way
        /api/risks/corridors already does)."""
        monkeypatch.setattr(LiveConditionsClient, "get_all_events", lambda self, use_cache=True: [])

        response = client.get("/api/twin")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == len(PORT_COORDINATES)
        assert len(data["edges"]) == len(SHIPPING_LANES)
        assert data["corridors_used"] == []
        # No live corridor scores -- every edge must still fall back to
        # a real (non-None) congestion-only score, not silently skip risk.
        for edge in data["edges"]:
            assert edge["risk"] is not None
