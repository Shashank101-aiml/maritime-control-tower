from fastapi import APIRouter

from app.agents.ingestion.ais_client import registry
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.risk.risk_agent import RiskAgent
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/dashboard")
def get_dashboard_summary():
    """Fleet Overview's KPIs and live hazard feed.

    `recent_events` used to be one real ingested event followed by two
    permanently-hardcoded ones ("Piracy Warning" / "Port Congestion",
    complete with a static "10 minutes ago" that never actually aged) --
    now every entry is a real current reading for a monitored corridor
    (LiveConditionsClient.get_all_events(), the same source Event
    Monitor and Vessel Tracking already use), each carrying the full
    real conditions dict (wave/swell/secondary-swell/ocean-current/
    visibility/wind), not just a label. `active_vessels` was a
    hardcoded 42; it's now the real AIS registry count.
    """
    try:
        events = LiveConditionsClient().get_all_events()
    except Exception as exc:
        logger.warning("Live conditions unavailable for dashboard: %s", exc)
        events = []

    risk_score = None
    if events:
        try:
            risk_score = RiskAgent().calculate_risk(events[0]).score
        except Exception as exc:
            logger.warning("Risk scoring failed for dashboard: %s", exc)

    vessels_configured = bool(settings.AISSTREAM_API_KEY)
    active_vessels = len(registry.list_vessels()) if vessels_configured else None

    active_alerts = sum(1 for e in events if e["severity"] in ("critical", "high", "warning"))

    return {
        "active_vessels": active_vessels,
        "vessels_configured": vessels_configured,
        "active_alerts": active_alerts,
        "average_fleet_risk": risk_score,
        "recent_events": [
            {
                "id": e["location"],
                "event_type": e["event_type"],
                "location": e["location"],
                "severity": e["severity"],
                "timestamp": e["timestamp"],
                "latitude": e["latitude"],
                "longitude": e["longitude"],
                "description": e["description"],
                "conditions": e["conditions"],
                "classification_reason": e.get("classification_reason"),
            }
            for e in events
        ],
        "system_status": "OPERATIONAL" if events else "DEGRADED",
    }
