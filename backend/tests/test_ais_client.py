"""Offline tests for the AISStream client.

Message parsing, the vessel registry, and bounding-box construction are
all tested without a network connection or API key.
"""

import time

import pytest

from app.agents.ingestion.ais_client import (
    AISStreamCollector,
    VesselRegistry,
    _dimension_sum,
    _ship_type_label,
    _valid_heading,
    corridor_bounding_boxes,
)


@pytest.fixture
def collector():
    reg = VesselRegistry()
    return AISStreamCollector(api_key="test-key", vessel_registry=reg)


def test_collector_without_key_is_not_configured():
    c = AISStreamCollector(api_key=None)
    assert c.configured is False
    assert c.start() is False


def test_bounding_boxes_cover_every_monitored_corridor():
    boxes = corridor_bounding_boxes()
    assert len(boxes) == 8
    for (lat_min, lon_min), (lat_max, lon_max) in boxes:
        assert lat_min < lat_max
        assert lon_min < lon_max


def test_position_report_is_parsed(collector):
    collector._handle_message({
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 235095435, "ShipName": "MV TEST  ", "time_utc": "2026-08-31 10:00:00 UTC"},
        "Message": {"PositionReport": {
            "Latitude": 26.5, "Longitude": 56.4, "Sog": 12.3,
            "Cog": 240.1, "TrueHeading": 238, "NavigationalStatus": 0,
        }},
    })

    vessels = collector.registry.list_vessels()
    assert len(vessels) == 1
    v = vessels[0]
    assert v["mmsi"] == 235095435
    assert v["name"] == "MV TEST"          # trailing AIS padding stripped
    assert v["sog_knots"] == 12.3
    assert v["nav_status"] == "Under way using engine"


def test_static_data_merges_into_same_vessel(collector):
    """Position and static messages arrive separately; both must land on
    one vessel record rather than creating two."""
    collector._handle_message({
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": 111, "ShipName": "ALPHA"},
        "Message": {"PositionReport": {"Latitude": 1.0, "Longitude": 2.0, "Sog": 8.0}},
    })
    collector._handle_message({
        "MessageType": "ShipStaticData",
        "MetaData": {"MMSI": 111, "ShipName": "ALPHA"},
        "Message": {"ShipStaticData": {
            "Type": 80, "ImoNumber": 9999999, "Destination": "SINGAPORE",
            "MaximumStaticDraught": 12.5,
            "Dimension": {"A": 150, "B": 100, "C": 20, "D": 12},
        }},
    })

    vessels = collector.registry.list_vessels()
    assert len(vessels) == 1
    v = vessels[0]
    assert v["sog_knots"] == 8.0          # position data retained
    assert v["ship_type"] == "Tanker"     # static data merged in
    assert v["length_m"] == 250           # A + B
    assert v["width_m"] == 32             # C + D


def test_message_without_mmsi_is_ignored(collector):
    collector._handle_message({
        "MessageType": "PositionReport",
        "MetaData": {},
        "Message": {"PositionReport": {"Latitude": 1.0}},
    })
    assert collector.registry.list_vessels() == []


def test_stale_vessels_expire():
    reg = VesselRegistry(ttl_seconds=0)
    reg.upsert(123, {"name": "GHOST"})
    time.sleep(0.01)
    assert reg.list_vessels() == []


def test_heading_511_means_unavailable():
    assert _valid_heading(511) is None
    assert _valid_heading(238) == 238
    assert _valid_heading(None) is None


def test_ship_type_labels():
    assert _ship_type_label(74) == "Cargo"
    assert _ship_type_label(80) == "Tanker"
    assert _ship_type_label(30) == "Fishing"
    assert _ship_type_label(None) == "Unknown"


def test_dimension_sum_handles_missing_parts():
    assert _dimension_sum(150, 100) == 250
    assert _dimension_sum(None, 100) is None


def test_vessels_route_reports_not_configured_without_key(monkeypatch):
    """Forces the key to None rather than relying on the developer's local
    .env — otherwise this passes or fails depending on whether a real
    AISSTREAM_API_KEY happens to be configured on the machine."""
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "AISSTREAM_API_KEY", None)

    body = TestClient(app).get("/api/vessels").json()
    assert body["configured"] is False
    assert body["status"] == "not_configured"
    assert body["vessels"] == []


def test_vessels_route_serves_registry_contents(monkeypatch):
    """The path that only runs with a real API key: once the collector has
    populated the registry, the route must surface those vessels."""
    from fastapi.testclient import TestClient

    from app.agents.ingestion import ais_client
    from app.core.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "AISSTREAM_API_KEY", "test-key")
    ais_client.registry.upsert(636019825, {
        "name": "EVER GIVEN",
        "latitude": 30.02,
        "longitude": 32.58,
        "sog_knots": 11.2,
        "ship_type": "Cargo",
        "nav_status": "Under way using engine",
    })
    ais_client.registry.connected = True

    try:
        body = TestClient(app).get("/api/vessels").json()
        assert body["configured"] is True
        assert body["status"] == "connected"
        assert body["count"] == 1
        assert body["vessels"][0]["name"] == "EVER GIVEN"
        assert body["vessels"][0]["sog_knots"] == 11.2
    finally:
        ais_client.registry._vessels.clear()
        ais_client.registry.connected = False
