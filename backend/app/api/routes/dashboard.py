from fastapi import APIRouter

from app.agents.ingestion.ais_client import registry
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.risk.risk_agent import RiskAgent
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _vessels_by_corridor(events):
    """How many tracked vessels sit closest to each monitored corridor. AIS is only
    collected inside a box around each corridor, so nearest is the box it came from."""
    counts = {e["location"]: 0 for e in events}
    if not counts:
        return []
    for vessel in registry.list_vessels():
        lat, lon = vessel.get("latitude"), vessel.get("longitude")
        if lat is None or lon is None:
            continue
        nearest = min(events, key=lambda e: (lat - e["latitude"]) ** 2 + (lon - e["longitude"]) ** 2)
        counts[nearest["location"]] += 1
    return [{"location": name, "vessels": n} for name, n in sorted(counts.items(), key=lambda kv: -kv[1])]


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

    # Fleet hazard risk is the mean of every monitored corridor's own risk score
    # (it used to be the first corridor's alone, whichever that happened to be).
    risk_by_corridor = []
    for event in events:
        try:
            risk_by_corridor.append({
                "location": event["location"], "severity": event["severity"],
                "score": RiskAgent().calculate_risk(event).score,
            })
        except Exception as exc:
            logger.warning("Risk scoring failed for %s: %s", event.get("location"), exc)
    risk_score = round(sum(r["score"] for r in risk_by_corridor) / len(risk_by_corridor)) if risk_by_corridor else None

    vessels_configured = bool(settings.AISSTREAM_API_KEY)
    active_vessels = len(registry.list_vessels()) if vessels_configured else None

    vessels_by_corridor = _vessels_by_corridor(events) if vessels_configured else []
    active_alerts = sum(1 for e in events if e["severity"] in ("critical", "high", "warning"))

    return {
        "active_vessels": active_vessels,
        "vessels_configured": vessels_configured,
        "active_alerts": active_alerts,
        "average_fleet_risk": risk_score,
        "risk_by_corridor": risk_by_corridor,
        "vessels_by_corridor": vessels_by_corridor,
        "alerts": [
            {"location": e["location"], "severity": e["severity"], "event_type": e["event_type"]}
            for e in events if e["severity"] in ("critical", "high", "warning")
        ],
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
