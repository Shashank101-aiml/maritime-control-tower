"""Time-series tables.

Until now every reading was fetched live and discarded, so nothing in
the system had history. That is why the Fleet Risk Trajectory chart had
no data to draw and why the Event Monitor timeline was originally
hardcoded.

These two tables are append-only: one row per corridor per observation,
and one row per risk scoring.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String

from app.database.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConditionReading(Base):
    """A single corridor's sea state at one observation time."""

    __tablename__ = "condition_readings"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(String(80), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    event_type = Column(String(80), nullable=True)
    severity = Column(String(20), nullable=True, index=True)

    wave_height_m = Column(Float, nullable=True)
    swell_height_m = Column(Float, nullable=True)
    wind_wave_height_m = Column(Float, nullable=True)
    wave_period_s = Column(Float, nullable=True)
    wind_speed_kmh = Column(Float, nullable=True)
    wind_gusts_kmh = Column(Float, nullable=True)
    wind_direction_deg = Column(Float, nullable=True)

    # When the upstream says the observation is for, versus when we
    # stored it. The source publishes on 15-minute boundaries, so these
    # differ and both matter for de-duplication.
    observed_at = Column(String(40), nullable=True)
    recorded_at = Column(DateTime, default=_utcnow, nullable=False, index=True)

    __table_args__ = (
        # One row per corridor per upstream observation: the poller runs
        # far more often than the source publishes, so without this the
        # table would fill with duplicates of the same reading.
        Index("ix_condition_unique_observation", "location", "observed_at", unique=True),
    )


class RiskReading(Base):
    """A risk score produced by the model, retained so the trajectory
    chart can plot real history rather than an invented curve."""

    __tablename__ = "risk_readings"

    id = Column(Integer, primary_key=True, index=True)
    score = Column(Integer, nullable=False)
    severity = Column(String(20), nullable=True)
    category = Column(String(120), nullable=True)
    location = Column(String(80), nullable=True, index=True)
    # "ml" or "rule_based" — lets a trend be read in the light of which
    # scorer produced it.
    scoring_method = Column(String(20), nullable=True)
    recorded_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
