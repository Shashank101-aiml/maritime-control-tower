"""Tests for persisted observation and risk history."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.observation import ConditionReading, RiskReading
from app.services.observation_service import (
    record_conditions,
    record_risk,
    risk_history,
)


@pytest.fixture
def db():
    """Throwaway in-memory database per test."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _condition(location="Arabian Sea", observed_at="2026-09-01T11:30", severity="warning"):
    return {
        "location": location,
        "latitude": 18.0,
        "longitude": 65.0,
        "event_type": "Moderate Swell & Strong Winds",
        "severity": severity,
        "conditions": {
            "wave_height_m": 3.14,
            "swell_height_m": 1.7,
            "wind_gusts_kmh": 50.8,
            "observed_at": observed_at,
        },
    }


def test_conditions_are_recorded(db):
    written = record_conditions(db, [_condition(), _condition("Gulf of Aden")])
    assert written == 2
    assert db.query(ConditionReading).count() == 2


def test_same_observation_is_not_duplicated(db):
    """The pollers run far more often than the source publishes, so
    re-recording an identical observation must be a no-op."""
    record_conditions(db, [_condition()])
    written = record_conditions(db, [_condition()])
    assert written == 0
    assert db.query(ConditionReading).count() == 1


def test_new_observation_time_creates_a_new_row(db):
    record_conditions(db, [_condition(observed_at="2026-09-01T11:30")])
    record_conditions(db, [_condition(observed_at="2026-09-01T11:45")])
    assert db.query(ConditionReading).count() == 2


def test_condition_without_location_is_skipped(db):
    assert record_conditions(db, [{"conditions": {"observed_at": "x"}}]) == 0


def test_risk_reading_is_recorded(db):
    record_risk(db, {"score": 42, "severity": "warning", "scoring_method": "ml"}, location="Arabian Sea")
    row = db.query(RiskReading).one()
    assert row.score == 42
    assert row.scoring_method == "ml"


def test_risk_without_score_is_ignored(db):
    record_risk(db, {"severity": "warning"})
    assert db.query(RiskReading).count() == 0


def test_history_buckets_empty_periods_as_null(db):
    """No reading is not a risk of zero. Plotting an empty bucket as 0
    would invent a dip that never happened."""
    record_risk(db, {"score": 30})
    result = risk_history(db, hours=24, buckets=24)

    populated = [p for p in result["series"] if p["score"] is not None]
    empty = [p for p in result["series"] if p["score"] is None]

    assert len(populated) == 1
    assert len(empty) == 23
    assert all(p["samples"] == 0 for p in empty)


def test_history_averages_within_a_bucket(db):
    for score in (10, 20, 60):
        record_risk(db, {"score": score})
    result = risk_history(db, hours=24, buckets=24)
    populated = [p for p in result["series"] if p["score"] is not None]
    assert populated[-1]["score"] == 30  # (10+20+60)/3
    assert populated[-1]["samples"] == 3


def test_history_reports_coverage_and_peak(db):
    record_risk(db, {"score": 12})
    record_risk(db, {"score": 88})
    result = risk_history(db, hours=24)
    assert result["total_readings"] == 2
    assert result["peak_score"] == 88
    assert result["recorded_from"] is not None


def test_history_excludes_readings_outside_the_window(db):
    old = RiskReading(score=99, recorded_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=48))
    db.add(old)
    db.commit()

    result = risk_history(db, hours=24)
    assert result["total_readings"] == 0
    assert result["peak_score"] is None
