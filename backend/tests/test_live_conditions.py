"""Tests for the live conditions client.

Classification and event-selection logic is tested offline with stubbed
readings — no network calls, so these stay fast and deterministic.
"""

import pytest

from app.agents.ingestion.live_conditions_client import LiveConditionsClient


@pytest.fixture
def client():
    return LiveConditionsClient(locations=[{"name": "Test Corridor", "lat": 0.0, "lon": 0.0}])


def test_classify_critical_on_high_waves(client):
    result = client.classify({"wave_height_m": 7.2, "wind_gusts_kmh": 40})
    assert result["severity"] == "critical"


def test_classify_critical_on_extreme_gusts_alone(client):
    """Either dimension crossing its threshold is enough — a storm-force
    gust matters even if the sea has not built yet."""
    result = client.classify({"wave_height_m": 0.5, "wind_gusts_kmh": 95})
    assert result["severity"] == "critical"


def test_classify_calm(client):
    result = client.classify({"wave_height_m": 0.3, "wind_gusts_kmh": 8})
    assert result["severity"] == "info"
    assert result["event_type"] == "Calm Conditions"


def test_classify_handles_missing_readings(client):
    """Absent values must not raise; they fall through to calm."""
    result = client.classify({})
    assert result["severity"] == "info"


def test_get_event_returns_most_severe_corridor(monkeypatch):
    client = LiveConditionsClient(locations=[
        {"name": "Calm Bay", "lat": 1.0, "lon": 1.0},
        {"name": "Storm Passage", "lat": 2.0, "lon": 2.0},
    ])

    readings = {
        (1.0, 1.0): {"wave_height_m": 0.2, "wind_gusts_kmh": 5},
        (2.0, 2.0): {"wave_height_m": 6.5, "wind_gusts_kmh": 95},
    }
    monkeypatch.setattr(
        client, "fetch_conditions", lambda lat, lon: readings[(lat, lon)]
    )

    event = client.get_event()
    assert event["location"] == "Storm Passage"
    assert event["severity"] == "critical"


def test_get_event_skips_failing_corridors(monkeypatch):
    """One unreachable corridor must not abort the whole sweep."""
    client = LiveConditionsClient(locations=[
        {"name": "Broken", "lat": 1.0, "lon": 1.0},
        {"name": "Working", "lat": 2.0, "lon": 2.0},
    ])

    def fetch(lat, lon):
        if lat == 1.0:
            raise ConnectionError("unreachable")
        return {"wave_height_m": 3.0, "wind_gusts_kmh": 45}

    monkeypatch.setattr(client, "fetch_conditions", fetch)

    event = client.get_event()
    assert event["location"] == "Working"


def test_get_event_raises_when_all_corridors_fail(monkeypatch):
    client = LiveConditionsClient(locations=[{"name": "Broken", "lat": 1.0, "lon": 1.0}])
    monkeypatch.setattr(
        client, "fetch_conditions",
        lambda lat, lon: (_ for _ in ()).throw(ConnectionError("down")),
    )

    with pytest.raises(RuntimeError, match="No live conditions"):
        client.get_event()
