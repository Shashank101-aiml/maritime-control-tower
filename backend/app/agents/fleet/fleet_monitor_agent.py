"""Fleet Monitoring Agent: continuous assessment of operators' registered ships.

Every cycle, for each vessel with monitoring on, it:
  1. takes the freshest AIS position (live from the tracker, else the last
     one saved) and checks the ship's own broadcast identity against what
     the operator registered;
  2. places the ship in the digital twin -- nearest shipping lane, nearest
     port, and the monitored corridor it is in, if any;
  3. scores the sea state at the ship's actual position (Open-Meteo through
     the same RiskAgent the corridors use);
  4. raises or clears alerts: silent AIS, elevated sea-state risk, stopped
     at sea, not under command, aground.

Nothing is invented: a ship never heard from is "awaiting signal", and a
risk score only exists when the sea-state feed answered. Each cycle runs
through the governance engine like every other agent, so it is registered,
permission-checked, audit-logged and can be quarantined.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.agents.fleet.tracker import FleetTracker, fleet_tracker
from app.agents.ingestion.ais_client import CORRIDOR_BOX_HALF_DEGREES
from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS, LiveConditionsClient
from app.agents.risk.risk_agent import RiskAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.fleet.geometry import nearest_lane, nearest_port
from app.fleet.identifiers import verify_identity
from app.governance.core import GovernanceEngine
from app.models.fleet import Vessel, VesselAlert
from app.twin.digital_twin import fetch_live_corridor_scores, get_digital_twin

logger = get_logger(__name__)

AGENT_ID = "fleet-monitor-agent"
ACTION = "MONITOR"

# A ship further than this from every known lane is "off known lanes".
LANE_MATCH_NM = 150.0
# "Stopped at sea" only counts well clear of a port (waiting at anchorage
# near a port is normal).
STOPPED_MIN_PORT_DISTANCE_NM = 30.0
STOPPED_SPEED_KNOTS = 0.5
SEA_STATE_CACHE_SECONDS = 900

# The risk level a ship sees comes from the physical sea-state severity
# band (Douglas sea scale / Beaufort wind force -- see SEVERITY_THRESHOLDS
# in live_conditions_client.py), not from the numeric risk-model score:
# that model's outputs are compressed into a narrow range (even a critical
# storm scores ~33/100), so a level cut from the score alone would never
# rise above "low". The score is still recorded alongside.
SEVERITY_TO_LEVEL = {"critical": "high", "high": "high", "warning": "medium", "low": "low", "info": "low"}
INITIAL_DELAY_SECONDS = 45


@dataclass
class Fix:
    latitude: float
    longitude: float
    sog: Optional[float]
    cog: Optional[float]
    nav_status: Optional[str]
    at: datetime
    from_live: bool


def corridor_containing(lat: float, lon: float) -> Optional[str]:
    """The monitored corridor whose box contains this position, if any --
    the same box the corridor AIS feed subscribes to."""
    half = CORRIDOR_BOX_HALF_DEGREES
    for loc in MONITORED_LOCATIONS:
        if abs(lat - loc["lat"]) <= half and abs(lon - loc["lon"]) <= half:
            return loc["name"]
    return None


def _age_text(minutes: float) -> str:
    if minutes < 60:
        return f"{int(minutes)} min"
    hours = minutes / 60
    return f"{hours:.0f} h" if hours < 48 else f"{hours / 24:.0f} days"


class FleetMonitorAgent:
    def __init__(
        self,
        tracker: FleetTracker = fleet_tracker,
        conditions_client: Optional[LiveConditionsClient] = None,
        risk_agent: Optional[RiskAgent] = None,
        clock: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        self.tracker = tracker
        self.conditions = conditions_client or LiveConditionsClient()
        self.risk_agent = risk_agent or RiskAgent()
        self._clock = clock
        self._sea_cache: Dict[Tuple[float, float], Tuple[float, Optional[Dict[str, Any]]]] = {}

    # -- inputs ----------------------------------------------------------

    def _fix_for(self, vessel: Vessel, live: Optional[Dict[str, Any]]) -> Optional[Fix]:
        if live and live.get("latitude") is not None and live.get("longitude") is not None and live.get("received_at"):
            return Fix(
                float(live["latitude"]), float(live["longitude"]), live.get("sog_knots"),
                live.get("cog_degrees"), live.get("nav_status"), live["received_at"], True,
            )
        if vessel.last_latitude is not None and vessel.last_longitude is not None and vessel.last_position_at:
            return Fix(
                vessel.last_latitude, vessel.last_longitude, vessel.last_sog,
                vessel.last_cog, vessel.last_nav_status, vessel.last_position_at, False,
            )
        return None

    def _sea_risk(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Sea-state risk at one position; None if the feed is off or down.
        Cached per quarter-degree cell -- ships in the same waters share a reading."""
        if not settings.ENABLE_LIVE_INGESTION:
            return None
        key = (round(lat * 4) / 4, round(lon * 4) / 4)
        cached = self._sea_cache.get(key)
        if cached and time.monotonic() - cached[0] < SEA_STATE_CACHE_SECONDS:
            return cached[1]

        result: Optional[Dict[str, Any]] = None
        try:
            conditions = self.conditions.fetch_conditions(lat, lon)
            classified = self.conditions.classify(conditions)
            assessment = self.risk_agent.calculate_risk({
                "event_type": classified["event_type"],
                "severity": classified["severity"],
                "source": "open-meteo",
                "description": classified.get("classification_reason"),
            })
            result = {
                "score": assessment.score,
                "level": SEVERITY_TO_LEVEL.get(classified["severity"], "low"),
                "detail": f"{classified['event_type']} at the vessel's position. {classified.get('classification_reason', '')}".strip(),
                "wave_height_m": conditions.get("wave_height_m"),
                "wind_gusts_kmh": conditions.get("wind_gusts_kmh"),
            }
        except Exception as exc:
            logger.warning("Sea-state lookup failed at (%.2f, %.2f): %s", lat, lon, exc)
        self._sea_cache[key] = (time.monotonic(), result)
        return result

    # -- one vessel ------------------------------------------------------

    def assess(self, db: Session, vessel: Vessel, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Refresh one vessel's row and alerts. Returns a small summary."""
        now = self._clock()
        live = self.tracker.latest(int(vessel.mmsi))

        if live:
            vessel.ais_name = live.get("name") or vessel.ais_name
            ais_imo = live.get("imo")
            vessel.ais_imo = str(ais_imo) if ais_imo and str(ais_imo) != "0" else vessel.ais_imo
            vessel.ais_ship_type = live.get("ship_type") or vessel.ais_ship_type
        vessel.verification, vessel.verification_note = verify_identity(
            name=vessel.name, imo=vessel.imo, ais_name=vessel.ais_name, ais_imo=vessel.ais_imo,
        )

        fix = self._fix_for(vessel, live)
        desired: Dict[str, Tuple[str, str]] = {}  # kind -> (severity, message)

        if fix is None:
            vessel.status = "awaiting_signal"
            vessel.status_detail = (
                "No AIS position received yet. Ships appear once a coastal AIS receiver hears them; "
                "mid-ocean coverage is patchy."
            )
            for column in ("risk_score", "risk_level", "risk_detail", "wave_height_m", "wind_gusts_kmh",
                           "corridor", "lane_id", "lane_risk", "lane_offset_nm", "nearest_port", "nearest_port_nm"):
                setattr(vessel, column, None)
        else:
            if fix.from_live:
                vessel.last_latitude, vessel.last_longitude = fix.latitude, fix.longitude
                vessel.last_sog, vessel.last_cog = fix.sog, fix.cog
                vessel.last_nav_status, vessel.last_position_at = fix.nav_status, fix.at

            age_minutes = max(0.0, (now - fix.at).total_seconds() / 60)
            silent = age_minutes > settings.FLEET_POSITION_STALE_MINUTES
            vessel.status = "no_signal" if silent else "tracking"
            vessel.status_detail = f"Last AIS report {_age_text(age_minutes)} ago."

            port, port_nm = nearest_port(fix.latitude, fix.longitude)
            vessel.nearest_port, vessel.nearest_port_nm = port, round(port_nm, 1)
            vessel.corridor = corridor_containing(fix.latitude, fix.longitude)

            lane = nearest_lane(fix.latitude, fix.longitude, edges)
            if lane and lane[1] <= LANE_MATCH_NM:
                vessel.lane_id, vessel.lane_offset_nm = lane[0]["lane_id"], round(lane[1], 1)
                vessel.lane_risk = lane[0].get("risk")
            else:
                vessel.lane_id = vessel.lane_offset_nm = vessel.lane_risk = None

            sea = self._sea_risk(fix.latitude, fix.longitude)
            if sea:
                vessel.risk_score, vessel.risk_level, vessel.risk_detail = sea["score"], sea["level"], sea["detail"]
                vessel.wave_height_m, vessel.wind_gusts_kmh = sea["wave_height_m"], sea["wind_gusts_kmh"]
            else:
                vessel.risk_score = vessel.risk_level = None
                vessel.wave_height_m = vessel.wind_gusts_kmh = None
                vessel.risk_detail = "Sea-state feed unavailable for this position right now."

            if silent:
                desired["AIS_SILENT"] = (
                    "warning",
                    f"No AIS report for {_age_text(age_minutes)} (last seen {fix.latitude:.2f}, {fix.longitude:.2f}).",
                )
            else:
                status = fix.nav_status
                if status == "Aground":
                    desired["AGROUND"] = ("critical", "Vessel reports it is aground.")
                elif status == "Not under command":
                    desired["NOT_UNDER_COMMAND"] = ("high", "Vessel reports it is not under command.")
                elif (
                    status == "Under way using engine"
                    and fix.sog is not None and fix.sog < STOPPED_SPEED_KNOTS
                    and port_nm > STOPPED_MIN_PORT_DISTANCE_NM
                ):
                    desired["STOPPED_AT_SEA"] = (
                        "warning",
                        f"Under way but stationary, {port_nm:.0f} nm from the nearest port ({port}).",
                    )
                if vessel.risk_level in ("medium", "high"):
                    desired["ELEVATED_RISK"] = ("high" if vessel.risk_level == "high" else "warning", vessel.risk_detail)

        vessel.monitored_at = now
        opened = self._sync_alerts(db, vessel, desired, now)
        # Sessions here run with autoflush off; flushing makes this
        # vessel's alerts visible to the next check within the same
        # transaction, so a condition can never open a duplicate alert.
        db.flush()
        return {"status": vessel.status, "risk_level": vessel.risk_level, "new_alerts": opened}

    def _sync_alerts(self, db: Session, vessel: Vessel, desired: Dict[str, Tuple[str, str]], now: datetime) -> int:
        """Open an alert when a condition starts, resolve it when it clears --
        never a duplicate alert for a condition that is still ongoing."""
        open_alerts = (
            db.query(VesselAlert)
            .filter(VesselAlert.vessel_id == vessel.id, VesselAlert.resolved_at.is_(None))
            .all()
        )
        by_kind = {a.kind: a for a in open_alerts}
        opened = 0
        for kind, (severity, message) in desired.items():
            existing = by_kind.get(kind)
            if existing is None:
                db.add(VesselAlert(
                    vessel_id=vessel.id, owner_id=vessel.owner_id, kind=kind,
                    severity=severity, message=message, created_at=now,
                ))
                opened += 1
            else:
                existing.severity, existing.message = severity, message
        for kind, alert in by_kind.items():
            if kind not in desired:
                alert.resolved_at = now
        return opened

    # -- one cycle -------------------------------------------------------

    def run_cycle(self, db: Session) -> Dict[str, Any]:
        vessels = db.query(Vessel).filter(Vessel.monitoring_enabled.is_(True)).all()
        summary = {"vessels": len(vessels), "tracking": 0, "no_signal": 0, "awaiting_signal": 0,
                   "elevated_risk": 0, "new_alerts": 0}
        if not vessels:
            return summary

        twin = get_digital_twin()
        twin.annotate_risk(fetch_live_corridor_scores() if settings.ENABLE_LIVE_INGESTION else {})
        edges = [attrs for _, _, attrs in twin.graph.edges(data=True)]

        for vessel in vessels:
            try:
                result = self.assess(db, vessel, edges)
            except Exception as exc:  # one bad vessel must not stop the fleet
                logger.warning("Monitoring failed for vessel %s: %s", vessel.mmsi, exc)
                continue
            summary[result["status"]] = summary.get(result["status"], 0) + 1
            summary["new_alerts"] += result["new_alerts"]
            if result["risk_level"] in ("medium", "high"):
                summary["elevated_risk"] += 1
        db.commit()
        return summary

    @staticmethod
    def confidence(summary: Dict[str, Any]) -> float:
        """Share of the fleet with a fresh position, scaled into 0.6-0.95:
        the agent is no more sure of its picture than it has data for."""
        total = summary.get("vessels") or 0
        share = (summary.get("tracking", 0) / total) if total else 1.0
        return round(0.6 + 0.35 * share, 2)


_shared_agent: Optional[FleetMonitorAgent] = None


def get_fleet_monitor_agent() -> FleetMonitorAgent:
    global _shared_agent
    if _shared_agent is None:
        _shared_agent = FleetMonitorAgent()
    return _shared_agent


def sync_tracker(db: Session, tracker: FleetTracker = fleet_tracker) -> None:
    """Point the AIS tracker at exactly the vessels that have monitoring on."""
    rows = db.query(Vessel.mmsi).filter(Vessel.monitoring_enabled.is_(True)).all()
    tracker.set_mmsis(int(mmsi) for (mmsi,) in rows)


def run_monitoring_cycle(db: Session, agent: Optional[FleetMonitorAgent] = None) -> Optional[Dict[str, Any]]:
    """One governed cycle: identity/health/permission checks, an execution
    trace and audit entries, like every other agent. Skipped entirely when
    there is nothing to monitor, so an idle system writes no empty traces."""
    agent = agent or get_fleet_monitor_agent()
    if db.query(Vessel.id).filter(Vessel.monitoring_enabled.is_(True)).first() is None:
        return None

    def task(_input: Dict[str, Any]):
        summary = agent.run_cycle(db)
        return summary, agent.confidence(summary)

    trace, _requires_approval = GovernanceEngine(db).execute_agent_task(
        AGENT_ID, ACTION, {"scope": "all monitored vessels"}, task,
    )
    return trace.output_data


class FleetMonitorLoop:
    """Runs a governed monitoring cycle on a fixed interval in a daemon thread."""

    def __init__(self, session_factory: Callable[[], Session], interval_seconds: Optional[int] = None) -> None:
        self._session_factory = session_factory
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="fleet-monitor", daemon=True)
        self._thread.start()
        logger.info("Fleet monitoring loop started.")

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        if self._stop.wait(INITIAL_DELAY_SECONDS):
            return
        while not self._stop.is_set():
            db = self._session_factory()
            try:
                sync_tracker(db)
                run_monitoring_cycle(db)
            except Exception as exc:
                logger.warning("Fleet monitoring cycle failed: %s", exc)
            finally:
                db.close()
            if self._stop.wait(self._interval or settings.FLEET_MONITOR_INTERVAL_SECONDS):
                return
