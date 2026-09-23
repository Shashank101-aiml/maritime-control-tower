"""Operator fleets: the vessels users register, and the alerts the fleet
monitoring agent raises about them.

`Vessel` holds identity (IMO/MMSI), the last known position, and the
latest monitoring assessment, so a restart never loses where a ship was
last seen. Live positions between monitoring cycles come from the AIS
tracker's memory and are merged over these columns when read.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database.base import Base


class Vessel(Base):
    __tablename__ = "fleet_vessels"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Identity, as registered by the operator.
    name = Column(String(128), nullable=False)
    imo = Column(String(7), nullable=True, index=True)
    mmsi = Column(String(9), nullable=False, unique=True, index=True)
    call_sign = Column(String(16), nullable=True)
    flag = Column(String(64), nullable=True)
    vessel_type = Column(String(30), nullable=False, default="other")
    monitoring_enabled = Column(Boolean, nullable=False, default=True)

    # What the ship itself broadcasts, and how that compares.
    ais_name = Column(String(128), nullable=True)
    ais_imo = Column(String(7), nullable=True)
    ais_ship_type = Column(String(40), nullable=True)
    verification = Column(String(12), nullable=False, default="unverified")
    verification_note = Column(Text, nullable=True)

    # Last known position.
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_sog = Column(Float, nullable=True)
    last_cog = Column(Float, nullable=True)
    last_nav_status = Column(String(40), nullable=True)
    last_position_at = Column(DateTime, nullable=True)

    # Latest monitoring assessment.
    status = Column(String(20), nullable=False, default="awaiting_signal")
    status_detail = Column(Text, nullable=True)
    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String(10), nullable=True)
    risk_detail = Column(Text, nullable=True)
    wave_height_m = Column(Float, nullable=True)
    wind_gusts_kmh = Column(Float, nullable=True)
    corridor = Column(String(80), nullable=True)
    lane_id = Column(String(80), nullable=True)
    lane_risk = Column(Integer, nullable=True)
    lane_offset_nm = Column(Float, nullable=True)
    nearest_port = Column(String(80), nullable=True)
    nearest_port_nm = Column(Float, nullable=True)
    monitored_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class VesselAlert(Base):
    __tablename__ = "fleet_alerts"

    id = Column(Integer, primary_key=True, index=True)
    vessel_id = Column(Integer, ForeignKey("fleet_vessels.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
