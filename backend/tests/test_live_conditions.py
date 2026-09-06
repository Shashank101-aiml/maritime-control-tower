"""Tests for the live conditions client.

Classification and event-selection logic is tested offline with stubbed
readings — no network calls, so these stay fast and deterministic.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agents.ingestion import live_conditions_client
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


class TestStaleWhileRevalidate:
    """A cache-miss used to block the calling request on a full sweep.
    Once the cache has ever been populated, an expired entry must be
    served immediately, with the refresh happening in the background."""

    def test_cold_start_blocks_synchronously(self, monkeypatch):
        """With nothing cached yet, there is nothing stale to serve --
        the very first call has no choice but to wait for real data."""
        client = LiveConditionsClient(locations=[{"name": "Corridor", "lat": 1.0, "lon": 1.0}])
        monkeypatch.setattr(client, "fetch_conditions", lambda lat, lon: {"wave_height_m": 0.5, "wind_gusts_kmh": 5})

        events = client.get_all_events()
        assert len(events) == 1
        assert live_conditions_client._cache["events"] is not None

    def test_stale_cache_is_served_immediately_not_blocked_on_refresh(self, monkeypatch):
        client = LiveConditionsClient(locations=[{"name": "Corridor", "lat": 1.0, "lon": 1.0}])

        # Populate the cache with a fast, real fetch first.
        monkeypatch.setattr(client, "fetch_conditions", lambda lat, lon: {"wave_height_m": 0.5, "wind_gusts_kmh": 5})
        first = client.get_all_events()

        # Expire it, then swap in a fetch that blocks until released --
        # simulating a slow upstream sweep.
        live_conditions_client._cache["expires_at"] = time.monotonic() - 1
        release = threading.Event()
        calls = []

        def slow_fetch(lat, lon):
            calls.append(1)
            release.wait(timeout=5)
            return {"wave_height_m": 9.0, "wind_gusts_kmh": 99}

        monkeypatch.setattr(client, "fetch_conditions", slow_fetch)

        # If this blocked on the slow refresh it would exceed the timeout
        # and raise, failing the test outright.
        with ThreadPoolExecutor(max_workers=1) as pool:
            second = pool.submit(client.get_all_events).result(timeout=1)

        assert second == first  # stale copy, not the new "critical" reading
        assert second[0]["conditions"]["wave_height_m"] == 0.5

        release.set()
        _wait_until(lambda: not live_conditions_client._cache["refreshing"])
        assert calls == [1]
        assert live_conditions_client._cache["events"][0]["conditions"]["wave_height_m"] == 9.0

    def test_only_one_background_refresh_runs_at_a_time(self, monkeypatch):
        """Two stale calls in quick succession must not spawn two
        competing sweeps."""
        client = LiveConditionsClient(locations=[{"name": "Corridor", "lat": 1.0, "lon": 1.0}])
        monkeypatch.setattr(client, "fetch_conditions", lambda lat, lon: {"wave_height_m": 0.5, "wind_gusts_kmh": 5})
        client.get_all_events()
        live_conditions_client._cache["expires_at"] = time.monotonic() - 1

        release = threading.Event()
        calls = []

        def slow_fetch(lat, lon):
            calls.append(1)
            release.wait(timeout=5)
            return {"wave_height_m": 1.0, "wind_gusts_kmh": 5}

        monkeypatch.setattr(client, "fetch_conditions", slow_fetch)

        client.get_all_events()  # spawns the one refresh
        client.get_all_events()  # must not spawn a second

        release.set()
        _wait_until(lambda: not live_conditions_client._cache["refreshing"])
        assert calls == [1]


class TestFetchConditionsParallelism:
    def test_marine_and_wind_requests_run_concurrently(self, monkeypatch):
        """These two upstream calls are independent; running them
        sequentially was doubling every corridor's fetch latency."""
        delay = 0.2

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self._payload

        def fake_get(url, params=None, timeout=None):
            time.sleep(delay)
            if url == live_conditions_client.MARINE_URL:
                return FakeResponse({"current": {"wave_height": 1.0}})
            return FakeResponse({"current": {"wind_speed_10m": 10}})

        monkeypatch.setattr(live_conditions_client.requests, "get", fake_get)

        client = LiveConditionsClient()
        start = time.monotonic()
        result = client.fetch_conditions(1.0, 1.0)
        elapsed = time.monotonic() - start

        assert result["wave_height_m"] == 1.0
        assert result["wind_speed_kmh"] == 10
        # Sequential would take ~2x delay; concurrent should take ~1x.
        assert elapsed < delay * 1.7


def _wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met within timeout")
