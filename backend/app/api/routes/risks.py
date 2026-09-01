from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.ingestion.ais_client import registry, vessels_in_box
from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.risk.risk_agent import RiskAgent
from app.api.dependencies.database import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.services.observation_service import record_risk, risk_history

logger = get_logger(__name__)

router = APIRouter()


def _vessels_at(latitude, longitude, all_vessels, limit: int = 12):
    """Vessels currently positioned in one corridor's box, trimmed to a
    compact summary -- callers only need enough to show who's exposed,
    not a full AIS record per ship. Always returns (vessels, count),
    even when there's no position to check against."""
    if latitude is None or longitude is None:
        return [], 0
    matched = vessels_in_box(latitude, longitude, all_vessels)
    summarized = [
        {
            "mmsi": v.get("mmsi"),
            "name": v.get("name"),
            "ship_type": v.get("ship_type"),
            "destination": v.get("destination"),
        }
        for v in matched[:limit]
    ]
    return summarized, len(matched)


@router.get("/risks")
def get_risk(db: Session = Depends(get_db)):
    """Risk score for the single most severe corridor right now.

    Kept for the headline card and the trend history it feeds. For a
    breakdown across every monitored corridor, see /risks/corridors --
    this endpoint alone only ever describes one of them.
    """
    event = IngestionAgent().collect_data()
    risk_data = RiskAgent().calculate_risk(event)

    # Retained so the trajectory chart has real history to plot. Recording
    # never raises — a lost history row must not fail the request.
    record_risk(db, risk_data, location=event.get("location"))

    all_vessels = registry.list_vessels() if settings.AISSTREAM_API_KEY else []
    vessels, vessel_count = _vessels_at(event.get("latitude"), event.get("longitude"), all_vessels)

    return {
        "risk_score": risk_data.get("score", 0),
        "details": {
            **risk_data,
            "location": event.get("location"),
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
            "vessel_count": vessel_count,
            "vessels": vessels,
            "vessels_configured": bool(settings.AISSTREAM_API_KEY),
        },
    }


@router.get("/risks/corridors")
def get_risk_by_corridor():
    """Risk score for every monitored corridor, not just the worst one --
    each with its own location and the vessels currently positioned
    there. /risks alone shows a single aggregate number with no sense of
    which corridor it's about or what's actually passing through it;
    this is the per-corridor breakdown that backs it.

    Read-only: unlike /risks, nothing here is written to risk_readings,
    so polling this doesn't change the trend history.
    """
    try:
        events = LiveConditionsClient().get_all_events()
    except Exception as exc:
        logger.warning("Live conditions sweep failed for corridor risk: %s", exc)
        return {"corridors": [], "vessels_configured": bool(settings.AISSTREAM_API_KEY), "error": str(exc)}

    vessels_configured = bool(settings.AISSTREAM_API_KEY)
    all_vessels = registry.list_vessels() if vessels_configured else []

    agent = RiskAgent()
    corridors = []
    for event in events:
        risk_data = agent.calculate_risk(event)
        vessels, vessel_count = _vessels_at(event.get("latitude"), event.get("longitude"), all_vessels)
        corridors.append({
            "location": event.get("location"),
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
            "score": risk_data["score"],
            "severity": risk_data["severity"],
            "likelihood": risk_data["likelihood"],
            "impact": risk_data["impact"],
            "category": risk_data["category"],
            # Raw sea state, so the frontend can render one enriched grid
            # instead of stitching this together with a separate call to
            # /conditions.
            "conditions": event.get("conditions"),
            "vessel_count": vessel_count,
            "vessels": vessels,
        })

    corridors.sort(key=lambda c: c["score"], reverse=True)
    return {"corridors": corridors, "vessels_configured": vessels_configured}


@router.get("/risks/history")
def get_risk_history(hours: int = 24, buckets: int = 24, db: Session = Depends(get_db)):
    """Recorded risk scores over time.

    Nothing is backfilled, so a freshly deployed instance legitimately
    returns mostly-empty buckets; `recorded_from` tells the UI how much
    history actually exists.
    """
    return risk_history(db, hours=hours, buckets=buckets)
