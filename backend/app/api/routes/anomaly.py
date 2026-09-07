from fastapi import APIRouter, HTTPException

from app.agents.anomaly.anomaly_agent import get_anomaly_agent
from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.core.logging import get_logger
from app.twin.coordinates import PORT_COORDINATES

logger = get_logger(__name__)

router = APIRouter()

# Reuses the same Open-Meteo client the Fleet Overview hazard feed uses
# (parallel per-location fetch, stale-while-revalidate cache), pointed at
# the 20 curated port coordinates instead of the 8 monitored corridors.
# `cache_key="ports"` keeps this fully independent of that corridor
# cache -- otherwise the two location sets would clobber each other.
_port_conditions_client = LiveConditionsClient(
    locations=[{"name": name, "lat": lat, "lon": lon} for name, (lat, lon) in PORT_COORDINATES.items()],
    cache_key="ports",
)


def _live_conditions_by_port() -> dict:
    try:
        events = _port_conditions_client.get_all_events()
    except Exception as exc:
        logger.warning("Live port conditions unavailable: %s", exc)
        return {}
    return {
        event["location"]: {
            "severity": event["severity"],
            "event_type": event["event_type"],
            "conditions": event["conditions"],
        }
        for event in events
    }


@router.get("/anomalies")
def get_anomalies():
    """Real anomaly score for every port with congestion history --
    each port's most recent real weekly snapshot, scored by the trained
    Isolation Forest against that port's own history. Sorted most
    anomalous first (lowest score = most anomalous).

    Each entry also carries `live_conditions`: real current wind/wave/
    visibility at that port's coordinates from Open-Meteo -- genuinely
    live, unlike the weekly anomaly snapshot above, which only advances
    when new training data lands. `live_conditions` is null for a port
    Open-Meteo can't be reached for; that's reported honestly rather
    than silently omitted or backfilled with the last anomaly reading.
    """
    agent = get_anomaly_agent()
    if not agent.is_available:
        raise HTTPException(503, "Anomaly model is not available -- run pipeline/train_anomaly_model.py.")

    reports = [agent.detect(port).model_dump() for port in agent.known_ports]
    reports.sort(key=lambda r: r["anomaly_score"])

    live_by_port = _live_conditions_by_port()
    for r in reports:
        r["live_conditions"] = live_by_port.get(r["affected_region"])

    return {
        "anomalies": reports,
        "live_conditions_status": _port_conditions_client.cache_status(),
    }


@router.get("/anomalies/{port}")
def get_anomaly_for_port(port: str):
    agent = get_anomaly_agent()
    if not agent.is_available:
        raise HTTPException(503, "Anomaly model is not available -- run pipeline/train_anomaly_model.py.")
    try:
        return agent.detect(port).model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/anomalies/{port}/snapshot")
def get_port_snapshot(port: str):
    """Everything needed to expand one port's card: its real recent
    trend (for a sparkline) and the real feature values a manual
    congestion prediction for this port would use (for a "use this
    port's data" prefill) -- kept out of the main /anomalies list so
    a routine poll of all 20 ports doesn't drag 26 weeks of history
    along for every one of them.
    """
    agent = get_anomaly_agent()
    if not agent.is_available:
        raise HTTPException(503, "Anomaly model is not available -- run pipeline/train_anomaly_model.py.")
    try:
        snapshot = agent.port_snapshot(port)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    snapshot["live_conditions"] = _live_conditions_by_port().get(port)
    return snapshot
