"""Operator fleets: register vessels, watch them live, and see what the
monitoring agent has found.

Each vessel belongs to the account that registered it. An operator sees and
manages only their own fleet; supervisors and admins can read every fleet
(`scope=all`), and admins can also change or remove any vessel. A vessel
that isn't yours is reported as not found rather than forbidden, so
registrations can't be probed by ID.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.agents.fleet.fleet_monitor_agent import sync_tracker
from app.agents.fleet.tracker import fleet_tracker
from app.api.dependencies.auth import ROLE_RANK, effective_role, get_current_active_user
from app.api.dependencies.database import get_db
from app.core.config import settings
from app.core.constants import UserRole
from app.fleet.identifiers import (
    VESSEL_TYPE_LABELS, VESSEL_TYPES, clean_imo, imo_is_valid, mmsi_is_valid,
    normalize_name, verify_identity,
)
from app.models.fleet import Vessel, VesselAlert, VoyagePlan
from app.models.user import User

router = APIRouter()

RECENT_ALERTS_LIMIT = 20


# --- request bodies ------------------------------------------------------

class VesselCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mmsi: str
    imo: Optional[str] = None
    vessel_type: str = "other"
    call_sign: Optional[str] = Field(default=None, max_length=16)
    flag: Optional[str] = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        name = normalize_name(value)
        if not name:
            raise ValueError("Vessel name is required")
        return name

    @field_validator("mmsi")
    @classmethod
    def _mmsi(cls, value: str) -> str:
        mmsi = (value or "").strip()
        if not mmsi_is_valid(mmsi):
            raise ValueError("MMSI must be 9 digits starting with a ship country code (MID 201-775)")
        return mmsi

    @field_validator("imo", mode="before")
    @classmethod
    def _imo(cls, value: Optional[str]) -> Optional[str]:
        imo = clean_imo(value)
        if imo is not None and not imo_is_valid(imo):
            raise ValueError("IMO number must be 7 digits with a valid check digit")
        return imo

    @field_validator("vessel_type")
    @classmethod
    def _type(cls, value: str) -> str:
        if value not in VESSEL_TYPES:
            raise ValueError(f"vessel_type must be one of: {', '.join(VESSEL_TYPES)}")
        return value

    @field_validator("call_sign", "flag")
    @classmethod
    def _blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        value = (value or "").strip()
        return value or None


class VesselUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    vessel_type: Optional[str] = None
    call_sign: Optional[str] = Field(default=None, max_length=16)
    flag: Optional[str] = Field(default=None, max_length=64)
    monitoring_enabled: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        name = normalize_name(value)
        if not name:
            raise ValueError("Vessel name is required")
        return name

    @field_validator("vessel_type")
    @classmethod
    def _type(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in VESSEL_TYPES:
            raise ValueError(f"vessel_type must be one of: {', '.join(VESSEL_TYPES)}")
        return value


# --- access --------------------------------------------------------------

def _can_read_all(user: User) -> bool:
    return ROLE_RANK[effective_role(user)] >= ROLE_RANK[UserRole.SUPERVISOR]


def _is_admin(user: User) -> bool:
    return effective_role(user) == UserRole.ADMIN


def _require_scope(scope: str, user: User) -> None:
    if scope == "all" and not _can_read_all(user):
        raise HTTPException(status_code=403, detail="Viewing every fleet requires the supervisor role or higher")


def _load_vessel(db: Session, vessel_id: int, user: User, *, write: bool = False) -> Vessel:
    vessel = db.query(Vessel).filter(Vessel.id == vessel_id).first()
    visible = vessel is not None and (vessel.owner_id == user.id or _can_read_all(user))
    if not visible:
        raise HTTPException(status_code=404, detail="Vessel not found")
    if write and vessel.owner_id != user.id and not _is_admin(user):
        raise HTTPException(status_code=403, detail="Only the owner or an admin can change this vessel")
    return vessel


def _tracked_count(db: Session) -> int:
    return db.query(Vessel).filter(Vessel.monitoring_enabled.is_(True)).count()


def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat() + "Z" if moment else None


# --- serialization -------------------------------------------------------

def _serialize(vessel: Vessel, owners: Dict[int, str], open_alerts: int, viewer: User) -> Dict[str, Any]:
    live = fleet_tracker.latest(int(vessel.mmsi)) if vessel.monitoring_enabled else None

    position = None
    if live and live.get("latitude") is not None and live.get("longitude") is not None and live.get("received_at"):
        at, latitude, longitude = live["received_at"], live["latitude"], live["longitude"]
        sog, cog, nav = live.get("sog_knots"), live.get("cog_degrees"), live.get("nav_status")
    elif vessel.last_latitude is not None and vessel.last_longitude is not None and vessel.last_position_at:
        at, latitude, longitude = vessel.last_position_at, vessel.last_latitude, vessel.last_longitude
        sog, cog, nav = vessel.last_sog, vessel.last_cog, vessel.last_nav_status
    else:
        at = None
    if at is not None:
        age_minutes = max(0.0, (datetime.utcnow() - at).total_seconds() / 60)
        position = {
            "latitude": latitude, "longitude": longitude, "sog_knots": sog, "cog_degrees": cog,
            "nav_status": nav, "reported_at": _iso(at), "age_minutes": round(age_minutes, 1),
            "live": age_minutes <= settings.FLEET_POSITION_STALE_MINUTES,
        }

    ais_name = (live or {}).get("name") or vessel.ais_name
    ais_imo = (live or {}).get("imo") or vessel.ais_imo
    verification, note = verify_identity(name=vessel.name, imo=vessel.imo, ais_name=ais_name, ais_imo=ais_imo)

    risk = None
    if vessel.risk_score is not None:
        risk = {
            "score": vessel.risk_score, "level": vessel.risk_level, "detail": vessel.risk_detail,
            "wave_height_m": vessel.wave_height_m, "wind_gusts_kmh": vessel.wind_gusts_kmh,
        }

    return {
        "id": vessel.id,
        "name": vessel.name,
        "imo": vessel.imo,
        "mmsi": vessel.mmsi,
        "call_sign": vessel.call_sign,
        "flag": vessel.flag,
        "vessel_type": vessel.vessel_type,
        "vessel_type_label": VESSEL_TYPE_LABELS.get(vessel.vessel_type, vessel.vessel_type),
        "monitoring_enabled": vessel.monitoring_enabled,
        "owner": owners.get(vessel.owner_id),
        "is_mine": vessel.owner_id == viewer.id,
        "identity": {
            "verification": verification, "note": note,
            "ais_name": ais_name, "ais_imo": str(ais_imo) if ais_imo else None,
            "ais_ship_type": vessel.ais_ship_type,
        },
        "position": position,
        "status": vessel.status,
        "status_detail": vessel.status_detail,
        "risk": risk,
        "twin": {
            "lane_id": vessel.lane_id, "lane_risk": vessel.lane_risk, "lane_offset_nm": vessel.lane_offset_nm,
            "corridor": vessel.corridor, "nearest_port": vessel.nearest_port,
            "nearest_port_nm": vessel.nearest_port_nm,
        },
        "open_alerts": open_alerts,
        "monitored_at": _iso(vessel.monitored_at),
    }


def _owner_names(db: Session, vessels: List[Vessel]) -> Dict[int, str]:
    ids = {v.owner_id for v in vessels}
    if not ids:
        return {}
    return {u.id: u.username for u in db.query(User).filter(User.id.in_(ids)).all()}


def _open_alert_counts(db: Session, vessel_ids: List[int]) -> Dict[int, int]:
    if not vessel_ids:
        return {}
    counts: Dict[int, int] = {}
    for alert in db.query(VesselAlert).filter(
        VesselAlert.vessel_id.in_(vessel_ids), VesselAlert.resolved_at.is_(None)
    ).all():
        counts[alert.vessel_id] = counts.get(alert.vessel_id, 0) + 1
    return counts


def _serialize_alert(alert: VesselAlert, vessel_names: Dict[int, str]) -> Dict[str, Any]:
    return {
        "id": alert.id, "vessel_id": alert.vessel_id, "vessel_name": vessel_names.get(alert.vessel_id),
        "kind": alert.kind, "severity": alert.severity, "message": alert.message,
        "created_at": _iso(alert.created_at), "resolved_at": _iso(alert.resolved_at),
    }


# --- routes --------------------------------------------------------------

@router.get("/fleet/vessels")
def list_vessels(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    _require_scope(scope, user)
    query = db.query(Vessel)
    if scope == "mine":
        query = query.filter(Vessel.owner_id == user.id)
    vessels = query.order_by(Vessel.name).all()

    owners = _owner_names(db, vessels)
    alert_counts = _open_alert_counts(db, [v.id for v in vessels])
    items = [_serialize(v, owners, alert_counts.get(v.id, 0), user) for v in vessels]

    return {
        "scope": scope,
        "vessels": items,
        "summary": {
            "total": len(items),
            "tracking": sum(1 for i in items if i["status"] == "tracking"),
            "awaiting_signal": sum(1 for i in items if i["status"] == "awaiting_signal"),
            "no_signal": sum(1 for i in items if i["status"] == "no_signal"),
            "elevated_risk": sum(1 for i in items if i["risk"] and i["risk"]["level"] in ("medium", "high")),
            "open_alerts": sum(i["open_alerts"] for i in items),
        },
        "tracking": {**fleet_tracker.status(), "tracked": _tracked_count(db)},
    }


@router.post("/fleet/vessels", status_code=status.HTTP_201_CREATED)
def register_vessel(
    payload: VesselCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    if _tracked_count(db) >= settings.FLEET_MAX_TRACKED_VESSELS:
        raise HTTPException(
            status_code=409,
            detail=f"Fleet tracking is at capacity ({settings.FLEET_MAX_TRACKED_VESSELS} vessels on the current AIS plan).",
        )
    if db.query(Vessel).filter(Vessel.mmsi == payload.mmsi).first():
        raise HTTPException(status_code=409, detail="A vessel with that MMSI is already registered.")
    if payload.imo and db.query(Vessel).filter(Vessel.imo == payload.imo).first():
        raise HTTPException(status_code=409, detail="A vessel with that IMO number is already registered.")

    vessel = Vessel(
        owner_id=user.id, name=payload.name, mmsi=payload.mmsi, imo=payload.imo,
        vessel_type=payload.vessel_type, call_sign=payload.call_sign, flag=payload.flag,
        monitoring_enabled=True, status="awaiting_signal",
        status_detail="No AIS position received yet. Ships appear once a coastal AIS receiver hears them; "
                      "mid-ocean coverage is patchy.",
    )
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    sync_tracker(db)
    return _serialize(vessel, {user.id: user.username}, 0, user)


@router.get("/fleet/vessels/{vessel_id}")
def get_vessel(
    vessel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    vessel = _load_vessel(db, vessel_id, user)
    owners = _owner_names(db, [vessel])
    alerts = (
        db.query(VesselAlert)
        .filter(VesselAlert.vessel_id == vessel.id)
        .order_by(VesselAlert.created_at.desc())
        .limit(RECENT_ALERTS_LIMIT)
        .all()
    )
    detail = _serialize(vessel, owners, sum(1 for a in alerts if a.resolved_at is None), user)
    detail["trail"] = fleet_tracker.trail(int(vessel.mmsi))
    detail["alerts"] = [_serialize_alert(a, {vessel.id: vessel.name}) for a in alerts]
    return detail


@router.patch("/fleet/vessels/{vessel_id}")
def update_vessel(
    vessel_id: int,
    payload: VesselUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    vessel = _load_vessel(db, vessel_id, user, write=True)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("monitoring_enabled") and not vessel.monitoring_enabled:
        if _tracked_count(db) >= settings.FLEET_MAX_TRACKED_VESSELS:
            raise HTTPException(
                status_code=409,
                detail=f"Fleet tracking is at capacity ({settings.FLEET_MAX_TRACKED_VESSELS} vessels on the current AIS plan).",
            )

    for field in ("name", "vessel_type", "monitoring_enabled"):
        if changes.get(field) is not None:
            setattr(vessel, field, changes[field])
    for field in ("call_sign", "flag"):
        if field in changes:
            setattr(vessel, field, (changes[field] or "").strip() or None)

    if "monitoring_enabled" in changes and changes["monitoring_enabled"] is False:
        vessel.status = "paused"
        vessel.status_detail = "Monitoring is switched off for this vessel."

    db.commit()
    db.refresh(vessel)
    sync_tracker(db)
    owners = _owner_names(db, [vessel])
    return _serialize(vessel, owners, _open_alert_counts(db, [vessel.id]).get(vessel.id, 0), user)


@router.delete("/fleet/vessels/{vessel_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vessel(
    vessel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    vessel = _load_vessel(db, vessel_id, user, write=True)
    db.query(VesselAlert).filter(VesselAlert.vessel_id == vessel.id).delete()
    db.query(VoyagePlan).filter(VoyagePlan.vessel_id == vessel.id).delete()
    db.delete(vessel)
    db.commit()
    sync_tracker(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/fleet/alerts")
def list_alerts(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    include_resolved: bool = False,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    _require_scope(scope, user)
    query = db.query(VesselAlert)
    if scope == "mine":
        query = query.filter(VesselAlert.owner_id == user.id)
    if not include_resolved:
        query = query.filter(VesselAlert.resolved_at.is_(None))
    alerts = query.order_by(VesselAlert.created_at.desc()).limit(limit).all()

    names = {v.id: v.name for v in db.query(Vessel).filter(Vessel.id.in_({a.vessel_id for a in alerts})).all()} if alerts else {}
    return {"scope": scope, "alerts": [_serialize_alert(a, names) for a in alerts]}
