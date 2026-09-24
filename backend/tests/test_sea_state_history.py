"""Per-corridor sea-state history: exactly what was recorded, in order,
inside the window -- nothing smoothed, filled in or invented."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.database import get_db
from app.main import app
from app.models.observation import ConditionReading
from app.services.observation_service import sea_state_history

from tests.fleet_support import make_engine_and_session

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once


def stamp(hours_ago, minutes=0):
    moment = datetime.now(timezone.utc) - timedelta(hours=hours_ago, minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M")


def add(db, location, observed_at, wave, gusts, severity="low"):
    db.add(ConditionReading(location=location, observed_at=observed_at, wave_height_m=wave,
                            wind_gusts_kmh=gusts, severity=severity, event_type="Slight Sea"))
    db.commit()


@pytest.fixture
def db():
    Session = make_engine_and_session()
    session = Session()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()


def test_each_corridor_gets_its_own_series_oldest_first(db):
    add(db, "Cape of Good Hope", stamp(1), 2.0, 40.0)
    add(db, "Cape of Good Hope", stamp(3), 1.5, 35.0)
    add(db, "Strait of Hormuz", stamp(2), 0.4, 20.0)

    history = sea_state_history(db, 24)

    cape = history["corridors"]["Cape of Good Hope"]
    assert [p["wave_height_m"] for p in cape] == [1.5, 2.0]          # 3 h ago, then 1 h ago
    assert [p["wind_gusts_kmh"] for p in cape] == [35.0, 40.0]
    assert list(history["corridors"]) == ["Cape of Good Hope", "Strait of Hormuz"]


def test_readings_outside_the_window_are_excluded(db):
    add(db, "Arabian Sea", stamp(30), 1.0, 20.0)
    add(db, "Arabian Sea", stamp(2), 2.0, 30.0)

    assert [p["wave_height_m"] for p in sea_state_history(db, 24)["corridors"]["Arabian Sea"]] == [2.0]
    assert len(sea_state_history(db, 48)["corridors"]["Arabian Sea"]) == 2


def test_gaps_are_left_as_gaps_and_missing_values_stay_missing(db):
    add(db, "Suez Canal (Gulf of Suez)", stamp(20), None, 30.0)   # this corridor has no wave data
    add(db, "Suez Canal (Gulf of Suez)", stamp(1), None, 33.0)

    series = sea_state_history(db, 24)["corridors"]["Suez Canal (Gulf of Suez)"]

    assert len(series) == 2                                         # no points invented in between
    assert all(p["wave_height_m"] is None for p in series)


def test_hours_is_clamped(db):
    assert sea_state_history(db, 0)["hours"] == 1
    assert sea_state_history(db, 9999)["hours"] == 168


def test_empty_history_is_an_empty_map_not_an_error(db):
    assert sea_state_history(db, 24) == {"hours": 24, "corridors": {}}


def test_the_route_returns_the_history_and_validates_hours(db):
    add(db, "Gulf of Aden", stamp(1), 0.3, 15.0)

    ok = client.get("/api/conditions/history?hours=6").json()

    assert ok["hours"] == 6 and ok["corridors"]["Gulf of Aden"][0]["wave_height_m"] == 0.3
    assert client.get("/api/conditions/history?hours=0").status_code == 422
    assert client.get("/api/conditions/history?hours=500").status_code == 422
