import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.agents.delay.delay_agent import get_delay_agent
from app.agents.fleet.tracker import fleet_tracker
from app.api.dependencies.auth import get_current_active_user
from app.api.dependencies.database import get_db
from app.api.routes.fleet import _load_vessel, _require_scope
from app.core.config import settings
from app.core.limiter import RATE_LIMIT, limiter
from app.fleet.voyage import assess_voyage
from app.governance.core import GovernanceEngine
from app.models.fleet import Vessel, VoyagePlan
from app.models.governance import ApprovalRequest
from app.models.user import User
from app.schemas.delay import DelayAssessmentRequest, VoyagePlanUpdate
from app.twin.coordinates import PORT_COORDINATES
from app.twin.digital_twin import fetch_live_corridor_scores, get_digital_twin

router = APIRouter()


@router.get("/delay/overview")
def get_delay_overview():
    """What the real container-journey data covers: how many journeys and
    lanes, the date range, which lanes have enough history to report on,
    what was dropped while cleaning and why, and the backtest that decided
    the service reports lane statistics rather than a model score."""
    agent = get_delay_agent()
    if not agent.is_available:
        raise HTTPException(503, "Transit journey data is not available.")
    return agent.overview()


@router.post("/delay/assess")
@limiter.limit(RATE_LIMIT)
def assess_delay(request: Request, payload: DelayAssessmentRequest, db: Session = Depends(get_db)):
    """Real transit statistics for one lane, run through governance like
    every other agent (identity, permission, audit trace)."""
    agent = get_delay_agent()
    if not agent.is_available:
        raise HTTPException(503, "Transit journey data is not available.")
    try:
        agent.validate_lane(payload.origin, payload.destination)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    engine = GovernanceEngine(db)
    session_id = str(uuid.uuid4())

    def run(data):
        live = fetch_live_corridor_scores() if settings.ENABLE_LIVE_INGESTION else {}
        result = agent.assess(data["origin"], data["destination"], payload.loading_date, live)
        return result, result["confidence"]

    try:
        trace, requires_approval = engine.execute_agent_task(
            "delay-agent", "ASSESS", payload.model_dump(mode="json"), run
        )
    except Exception as exc:
        return {"status": "FAILED", "session_id": session_id, "error": str(exc)}

    trace.request_id = session_id
    db.commit()

    if trace.approval_status == "PENDING":
        approval = db.query(ApprovalRequest).filter(ApprovalRequest.execution_id == trace.id).first()
        return {
            "status": "PENDING_APPROVAL",
            "session_id": session_id,
            "agent_id": "delay-agent",
            "approval_id": approval.id if approval else None,
            "reason": trace.policy_decisions.get("reason") if trace.policy_decisions else None,
        }
    if trace.approval_status == "REJECTED":
        return {"status": "REJECTED", "session_id": session_id, "error": "The assessment request was rejected."}

    return {"status": "COMPLETED", "session_id": session_id, "assessment": trace.output_data}


# --- live voyages ---------------------------------------------------------

def _position(vessel: Vessel, now: datetime):
    """Latest position for a vessel: the live tracker if it has heard the ship, else what was stored."""
    live = fleet_tracker.latest(int(vessel.mmsi)) if vessel.monitoring_enabled else None
    if live and live.get("latitude") is not None and live.get("longitude") is not None and live.get("received_at"):
        return {
            "latitude": live["latitude"], "longitude": live["longitude"],
            "sog_knots": live.get("sog_knots"), "reported_at": live["received_at"],
        }
    if vessel.last_latitude is not None and vessel.last_longitude is not None and vessel.last_position_at:
        return {
            "latitude": vessel.last_latitude, "longitude": vessel.last_longitude,
            "sog_knots": vessel.last_sog, "reported_at": vessel.last_position_at,
        }
    return None


def _serialize_plan(plan: Optional[VoyagePlan]):
    if plan is None:
        return None
    return {
        "destination_port": plan.destination_port,
        "scheduled_arrival": plan.scheduled_arrival.isoformat() + "Z" if plan.scheduled_arrival else None,
    }


def _port_snapshot(twin):
    def snapshot(name: str):
        if name not in twin.graph:
            return None
        node = twin.graph.nodes[name]
        return {
            "name": name, "country": node.get("country"),
            "has_congestion_data": node.get("has_congestion_data", False),
            "congestion_percentile": node.get("congestion_percentile"),
            "avg_wait_days": node.get("avg_wait_days"),
            "as_of": node.get("metrics_as_of"),
        }
    return snapshot


def assess_fleet_voyages(vessels: List[Vessel], plans: Dict[int, VoyagePlan], now: datetime):
    """Live voyage assessment for each vessel, plus how much of it rests on
    a reference arrival (which sets the run's confidence)."""
    twin = get_digital_twin()
    snapshot = _port_snapshot(twin)
    items = []
    for vessel in vessels:
        live = fleet_tracker.latest(int(vessel.mmsi)) if vessel.monitoring_enabled else None
        plan = plans.get(vessel.id)
        assessment = assess_voyage(
            position=_position(vessel, now),
            ais_destination=(live or {}).get("destination"),
            ais_eta=(live or {}).get("ais_eta"),
            plan_destination=plan.destination_port if plan else None,
            scheduled_arrival=plan.scheduled_arrival if plan else None,
            trail=fleet_tracker.trail(int(vessel.mmsi)),
            twin=twin,
            port_snapshot=snapshot,
            now=now,
        )
        items.append({
            "vessel_id": vessel.id, "name": vessel.name, "mmsi": vessel.mmsi, "imo": vessel.imo,
            "owner": None, "is_mine": None, "plan": _serialize_plan(plan), **assessment,
        })
    return items


@router.get("/delay/voyages")
def list_voyages(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """Where each fleet vessel will arrive against when it is due, from its
    live AIS position and speed. Run through governance like every agent."""
    _require_scope(scope, user)
    query = db.query(Vessel)
    if scope == "mine":
        query = query.filter(Vessel.owner_id == user.id)
    vessels = query.order_by(Vessel.name).all()
    plans = {
        p.vessel_id: p for p in db.query(VoyagePlan).filter(VoyagePlan.vessel_id.in_([v.id for v in vessels])).all()
    } if vessels else {}
    owners = {u.id: u.username for u in db.query(User).filter(User.id.in_({v.owner_id for v in vessels})).all()} if vessels else {}
    now = datetime.utcnow()

    def run(_data):
        items = assess_fleet_voyages(vessels, plans, now)
        with_reference = sum(1 for i in items if i["references"])
        share = with_reference / len(items) if items else 0.0
        return items, round(0.7 + 0.25 * share, 2)

    try:
        trace, _ = GovernanceEngine(db).execute_agent_task(
            "delay-agent", "ASSESS", {"scope": scope, "vessels": len(vessels)}, run
        )
    except Exception as exc:
        raise HTTPException(500, f"Voyage assessment failed: {exc}")
    db.commit()
    if trace.approval_status in ("PENDING", "REJECTED"):
        raise HTTPException(409, "This assessment is waiting on, or was refused by, governance.")

    by_id = {v.id: v for v in vessels}
    items = trace.output_data
    for item in items:
        vessel = by_id[item["vessel_id"]]
        item["owner"], item["is_mine"] = owners.get(vessel.owner_id), vessel.owner_id == user.id

    counts: Dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"scope": scope, "voyages": items, "summary": counts, "generated_at": now.isoformat() + "Z"}


@router.put("/delay/voyages/{vessel_id}")
def set_voyage_plan(
    vessel_id: int,
    payload: VoyagePlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """Set where a vessel is due and when. Empty fields fall back on the ship's own AIS."""
    vessel = _load_vessel(db, vessel_id, user, write=True)
    port = (payload.destination_port or "").strip() or None
    if port and port not in PORT_COORDINATES:
        raise HTTPException(422, f"'{port}' is not a port in the digital twin.")
    arrival = payload.scheduled_arrival
    if arrival is not None and arrival.tzinfo is not None:
        arrival = arrival.astimezone(timezone.utc).replace(tzinfo=None)

    plan = db.query(VoyagePlan).filter(VoyagePlan.vessel_id == vessel.id).first()
    if port is None and arrival is None:
        if plan:
            db.delete(plan)
            db.commit()
        return {"plan": None}
    if plan is None:
        plan = VoyagePlan(vessel_id=vessel.id, owner_id=vessel.owner_id)
        db.add(plan)
    plan.destination_port, plan.scheduled_arrival = port, arrival
    db.commit()
    return {"plan": _serialize_plan(plan)}
