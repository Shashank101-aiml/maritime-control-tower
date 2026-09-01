"""Persisting live readings so the system accumulates history.

The pollers run far more often than the upstream publishes, so writes
are de-duplicated on (location, observed_at). Recording must never break
a request: a failure here is logged and swallowed, because losing a
history row is far less bad than failing the prediction the user asked
for.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.observation import ConditionReading, RiskReading

logger = get_logger(__name__)


def record_conditions(db: Session, conditions: List[Dict[str, Any]]) -> int:
    """Stores any corridor readings not already held. Returns how many
    were new."""
    written = 0
    for c in conditions:
        observed_at = (c.get("conditions") or {}).get("observed_at")
        location = c.get("location")
        if not location:
            continue

        exists = (
            db.query(ConditionReading.id)
            .filter(
                ConditionReading.location == location,
                ConditionReading.observed_at == observed_at,
            )
            .first()
        )
        if exists:
            continue

        m = c.get("conditions") or {}
        db.add(
            ConditionReading(
                location=location,
                latitude=c.get("latitude"),
                longitude=c.get("longitude"),
                event_type=c.get("event_type"),
                severity=c.get("severity"),
                wave_height_m=m.get("wave_height_m"),
                swell_height_m=m.get("swell_height_m"),
                wind_wave_height_m=m.get("wind_wave_height_m"),
                wave_period_s=m.get("wave_period_s"),
                wind_speed_kmh=m.get("wind_speed_kmh"),
                wind_gusts_kmh=m.get("wind_gusts_kmh"),
                wind_direction_deg=m.get("wind_direction_deg"),
                observed_at=observed_at,
            )
        )
        written += 1

    if not written:
        return 0

    try:
        db.commit()
    except IntegrityError:
        # Two workers racing on the same observation: the unique index
        # did its job, so this is expected rather than an error.
        db.rollback()
        return 0
    except Exception as exc:
        db.rollback()
        logger.warning("Could not record condition readings: %s", exc)
        return 0

    return written


def record_risk(db: Session, risk: Dict[str, Any], location: Optional[str] = None) -> None:
    """Stores one risk scoring. Never raises."""
    score = risk.get("score")
    if score is None:
        return
    try:
        db.add(
            RiskReading(
                score=int(score),
                severity=risk.get("severity"),
                category=risk.get("category"),
                location=location,
                scoring_method=risk.get("scoring_method"),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Could not record risk reading: %s", exc)


def risk_history(db: Session, hours: int = 24, buckets: int = 24) -> Dict[str, Any]:
    """Average risk score per time bucket over the last `hours`.

    Empty buckets are returned as null rather than zero — no reading is
    not the same as a risk of zero, and plotting it as zero would invent
    a dip that never happened.
    """
    hours = max(1, min(hours, 168))
    buckets = max(1, min(buckets, 96))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(hours=hours)
    bucket_span = timedelta(hours=hours) / buckets

    rows = (
        db.query(RiskReading)
        .filter(RiskReading.recorded_at >= window_start)
        .order_by(RiskReading.recorded_at)
        .all()
    )

    series = []
    for i in range(buckets):
        start = window_start + bucket_span * i
        end = start + bucket_span
        scores = [r.score for r in rows if start <= r.recorded_at < end]
        series.append(
            {
                "time": start.strftime("%H:%M"),
                "bucket_start": start.isoformat() + "Z",
                "score": round(sum(scores) / len(scores)) if scores else None,
                "samples": len(scores),
            }
        )

    earliest = db.query(func.min(RiskReading.recorded_at)).scalar()
    return {
        "hours": hours,
        "total_readings": len(rows),
        "recorded_from": earliest.isoformat() + "Z" if earliest else None,
        "peak_score": max((r.score for r in rows), default=None),
        "series": series,
    }
