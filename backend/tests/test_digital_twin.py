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
from app.twin.coordinates import EXTRA_WAYPOINT_COORDINATES, PORT_COORDINATES
from app.twin.digital_twin import DigitalTwin, WAYPOINT_COORDINATES, haversine_nm
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


def test_every_waypoint_is_known():
    """A typo'd waypoint name would silently mean that lane's geometry
    just skips it (WAYPOINT_COORDINATES[name] would KeyError instead,
    so this would already fail loudly at import time for a totally
    unknown name) -- this instead catches a name that's spelled right
    but doesn't correspond to anything: not a live-monitored corridor
    and not a curated geometry-only waypoint either."""
    known_names = MONITORED_NAMES | set(EXTRA_WAYPOINT_COORDINATES)
    for lane in SHIPPING_LANES:
        for name in lane.waypoints:
            assert name in known_names, f"{lane.lane_id}: {name!r} is not a known waypoint"


def test_geometry_only_waypoints_are_never_treated_as_monitored():
    """A geometry-only waypoint (e.g. Strait of Gibraltar) must never
    silently start being read as though it had live sea-state data --
    it's a distinct set from MONITORED_LOCATIONS, not an overlapping
    alias for one."""
    assert MONITORED_NAMES.isdisjoint(EXTRA_WAYPOINT_COORDINATES)


def test_suez_atlantic_lanes_route_via_gibraltar():
    """The real bug this closes: every Suez<->Atlantic-port lane used to
    jump straight from the Suez Canal waypoint to the destination, so
    the plotted line cut across Southern/Eastern Europe instead of
    following the real track out through Gibraltar."""
    suez_atlantic_lane_ids = {
        "shanghai-rotterdam-suez", "shanghai-hamburg-suez", "ningbo-rotterdam-suez",
        "singapore-rotterdam-suez", "hongkong-felixstowe-suez", "dubai-rotterdam",
        "shanghai-newyork-suez", "ningbo-newyork-suez",
    }
    by_id = {lane.lane_id: lane for lane in SHIPPING_LANES}
    for lane_id in suez_atlantic_lane_ids:
        lane = by_id[lane_id]
        assert "Suez Canal (Gulf of Suez)" in lane.waypoints
        assert "Strait of Gibraltar" in lane.waypoints
        # Real travel order: out of the Red Sea at Suez, then out of the
        # Mediterranean at Gibraltar -- not the other way around.
        assert lane.waypoints.index("Suez Canal (Gulf of Suez)") < lane.waypoints.index("Strait of Gibraltar")


def test_north_europe_bound_lanes_follow_the_coast_in_travel_order():
    """Gibraltar -> Rotterdam/Hamburg/Felixstowe must go up the Iberian
    coast, across Biscay and through the Channel, in that order -- a
    straight line between them clips Iberia and France."""
    order = ["Strait of Gibraltar", "Cape St. Vincent", "Cape Finisterre", "Ushant", "English Channel (Dover)"]
    by_id = {lane.lane_id: lane for lane in SHIPPING_LANES}
    for lane_id in ("shanghai-rotterdam-suez", "shanghai-hamburg-suez", "ningbo-rotterdam-suez",
                    "singapore-rotterdam-suez", "hongkong-felixstowe-suez", "dubai-rotterdam"):
        wps = by_id[lane_id].waypoints
        idx = [wps.index(name) for name in order]
        assert idx == sorted(idx), lane_id
    for lane_id in ("shanghai-rotterdam-cape", "singapore-rotterdam-cape"):
        wps = by_id[lane_id].waypoints
        assert wps.index("Cape of Good Hope") < wps.index("Off Cape Verde") < wps.index("Ushant"), lane_id


def test_to_dict_exposes_real_coordinates_for_every_waypoint_actually_used():
    """The frontend used to be able to resolve a waypoint's coordinates
    only from the live conditions feed, so a geometry-only waypoint (no
    live feed by definition) or a monitored one during an outage would
    just vanish from the plotted line instead of rendering. to_dict()
    must report a real coordinate for every waypoint any edge actually
    references, live feed or not."""
    twin = DigitalTwin()
    data = twin.to_dict()
    used_names = {name for edge in data["edges"] for name in edge["waypoints"]}

    assert used_names, "expected at least one lane with waypoints to exist"
    assert set(data["waypoints"].keys()) == used_names
    for name, coords in data["waypoints"].items():
        expected_lat, expected_lon = WAYPOINT_COORDINATES[name]
        assert coords["lat"] == pytest.approx(expected_lat)
        assert coords["lon"] == pytest.approx(expected_lon)
        assert coords["is_monitored"] == (name in MONITORED_NAMES)

    assert data["waypoints"]["Strait of Gibraltar"]["is_monitored"] is False


def test_to_dict_edges_keep_the_lanes_own_direction():
    """Waypoints run port_a -> port_b as declared in lanes.py; a client
    walking a lane reverses them when it traverses b -> a. If to_dict()
    reported NetworkX's iteration order instead, a Shanghai->Hamburg lane
    could come back as Hamburg->Shanghai and be drawn backwards."""
    data = DigitalTwin().to_dict()
    by_id = {lane.lane_id: lane for lane in SHIPPING_LANES}
    for edge in data["edges"]:
        lane = by_id[edge["lane_id"]]
        assert (edge["port_a"], edge["port_b"]) == (lane.port_a, lane.port_b), edge["lane_id"]


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
