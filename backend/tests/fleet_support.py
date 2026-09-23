"""Shared helpers for the fleet tests: an isolated in-memory database,
account and vessel builders, and AIS message builders. Nothing here touches
the network or the real database."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.fleet.tracker import fleet_tracker
from app.core.constants import UserRole
from app.core.security import hash_password
from app.database.base import Base
from app.models.fleet import Vessel
from app.models.user import User

# Valid identifiers (IMO check digit and ship-station MID verified).
IMO_A, IMO_B = "9074729", "9811000"
MMSI_A, MMSI_B, MMSI_C = "636019825", "366999712", "477123400"


def make_engine_and_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    return Session


def make_user(db, username, role=UserRole.OPERATOR):
    user = User(
        email=f"{username}@example.com", username=username, full_name=username.title(),
        hashed_password=hash_password("unused-pass-1"), role=role, is_active=True,
        is_superuser=role == UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_vessel(db, owner, name="MV TEST", mmsi=MMSI_A, imo=None, **extra):
    vessel = Vessel(owner_id=owner.id, name=name, mmsi=mmsi, imo=imo, vessel_type="container_ship", **extra)
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    return vessel


def reset_tracker():
    """The tracker is a process-wide singleton; give every test a clean one."""
    fleet_tracker.set_mmsis([])
    fleet_tracker.registry._vessels.clear()
    fleet_tracker._trails.clear()
    fleet_tracker._received_at.clear()


def position_msg(mmsi, lat, lon, sog=12.0, cog=90.0, nav=0):
    mmsi = int(mmsi)
    return {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": mmsi, "ShipName": "TEST", "time_utc": "2026-09-24 12:00:00"},
        "Message": {"PositionReport": {
            "UserID": mmsi, "Latitude": lat, "Longitude": lon, "Sog": sog, "Cog": cog,
            "TrueHeading": 511, "NavigationalStatus": nav,
        }},
    }


def static_msg(mmsi, name, imo, ship_type=70):
    mmsi = int(mmsi)
    return {
        "MessageType": "ShipStaticData",
        "MetaData": {"MMSI": mmsi, "ShipName": name},
        "Message": {"ShipStaticData": {
            "UserID": mmsi, "Name": name, "ImoNumber": int(imo), "CallSign": "ABCD",
            "Type": ship_type, "Dimension": {"A": 200, "B": 100, "C": 20, "D": 20},
        }},
    }
