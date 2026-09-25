"""Shipping lanes are drawn and measured over water, from each port's sea
approach. The land-crossing check itself lives in pipeline/check_lane_land.py
(it needs the Natural Earth coastline, which isn't a runtime dependency), so
that part runs only where shapely and the coastline are available."""

import sys
from pathlib import Path

import pytest

from app.twin.coordinates import PORT_APPROACH_COORDINATES, PORT_COORDINATES
from app.twin.digital_twin import WAYPOINT_COORDINATES, get_digital_twin, haversine_nm
from app.twin.lane_geometry import lane_points
from app.twin.sea_legs import SEA_LEGS

REPO = Path(__file__).resolve().parents[2]


def test_every_port_has_a_sea_approach_near_it():
    assert set(PORT_APPROACH_COORDINATES) == set(PORT_COORDINATES)
    for port, (lat, lon) in PORT_APPROACH_COORDINATES.items():
        assert haversine_nm(lat, lon, *PORT_COORDINATES[port]) < 110, port


def test_a_lane_path_runs_from_approach_to_approach_through_its_waypoints():
    points = lane_points("Singapore", ["Gulf of Aden", "Suez Canal (Gulf of Suez)"], "Rotterdam", WAYPOINT_COORDINATES)
    named = [p["name"] for p in points if p["name"]]
    assert named == ["Singapore", "Gulf of Aden", "Suez Canal (Gulf of Suez)", "Rotterdam"]
    assert (points[0]["lat"], points[0]["lon"]) == PORT_APPROACH_COORDINATES["Singapore"]
    assert len(points) > len(named)  # sea-only turning points were inserted


def test_a_lane_read_backwards_is_the_same_path_reversed():
    forward = lane_points("Dubai (Jebel Ali)", ["Strait of Hormuz", "Arabian Sea"], "Singapore", WAYPOINT_COORDINATES)
    backward = lane_points("Singapore", ["Arabian Sea", "Strait of Hormuz"], "Dubai (Jebel Ali)", WAYPOINT_COORDINATES)
    assert [(p["lat"], p["lon"]) for p in forward] == [(p["lat"], p["lon"]) for p in reversed(backward)]


def test_sea_legs_were_generated_for_the_lanes():
    assert len(SEA_LEGS) > 60 and any(SEA_LEGS.values())


def test_no_lane_crosses_land():
    pytest.importorskip("shapely")
    pytest.importorskip("shapefile")
    land = REPO / "pipeline" / ".cache" / "ne_10m_land.shp"
    if not land.exists():
        pytest.skip("Natural Earth coastline not downloaded (run pipeline/check_lane_land.py once)")
    sys.path.insert(0, str(REPO / "pipeline"))
    from check_lane_land import crossings, land_geometry
    from shapely.affinity import translate
    from shapely.ops import unary_union
    from shapely.prepared import prep

    from app.fleet.geometry import lane_polyline

    geom = land_geometry(land)
    geom = unary_union([geom, translate(geom, xoff=360)])
    prepared = prep(geom)
    offenders = {
        attrs["lane_id"]: sum(h[2] for h in crossings(prepared, lane_polyline(attrs), geom))
        for _, _, attrs in get_digital_twin().graph.edges(data=True)
    }
    assert {k: v for k, v in offenders.items() if v} == {}
