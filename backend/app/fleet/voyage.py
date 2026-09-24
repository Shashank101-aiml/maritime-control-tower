"""Live voyage ETA and delay for a vessel under way.

Ships don't run to a timetable the way trains do, but the arrival that
matters for a voyage does have a reference: the date the operator is due, or
failing that the ETA the crew broadcast over AIS. This module works out when
the ship will actually get there from where it is now, and compares the two.

  * destination -- the operator's planned port, else the port named in the
    ship's AIS destination text ("SGSIN", "SG SIN", "SINGAPORE", "CNSHA>USLAX");
  * distance    -- what is left to sail, measured along the digital twin's
    real shipping lanes where the ship is on one, otherwise a straight
    great-circle line (labelled, because that under-counts when land is
    in the way);
  * speed       -- the ship's recent speed over ground, not one reading;
  * verdict     -- predicted arrival against the reference, on time within a
    day either way.

Nothing is invented. A ship with no position, no resolvable destination, or
that isn't moving gets a status saying exactly that, never a guessed ETA.
"""

import re
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from app.fleet.geometry import _relative_xy, lane_polyline
from app.twin.coordinates import PORT_COORDINATES
from app.twin.digital_twin import haversine_nm

ON_TIME_TOLERANCE_HOURS = 24.0
# Below this a ship is at anchor / in port / drifting, not making passage.
MIN_UNDERWAY_KNOTS = 3.0
# A ship further than this from every lane isn't "on" the twin's network.
MAX_LANE_OFFSET_NM = 150.0
# Lanes within this many nm of the closest one are treated as the same corridor.
LANE_TIE_NM = 30.0
SPEED_SAMPLES = 12
STALE_POSITION_MINUTES = 30

# UN/LOCODEs crews commonly type as a destination, per twin port.
PORT_LOCODES: Dict[str, List[str]] = {
    "Shanghai": ["CNSHA"], "Ningbo": ["CNNGB"], "Shenzhen": ["CNSZX", "CNYTN", "CNSHK"],
    "Guangzhou": ["CNCAN", "CNNSA"], "Qingdao": ["CNTAO"], "Hong Kong": ["HKHKG"], "Busan": ["KRPUS"],
    "Laem Chabang": ["THLCH"], "Singapore": ["SGSIN"], "Tanjung Pelepas": ["MYTPP"],
    "Tanjung Priok": ["IDJKT", "IDTPP"], "Colombo": ["LKCMB"], "Dubai (Jebel Ali)": ["AEJEA", "AEDXB"],
    "Nhava Sheva (Mumbai)": ["INNSA", "INBOM"], "Mundra": ["INMUN"], "Chennai": ["INMAA"],
    "Cochin": ["INCOK"], "Visakhapatnam": ["INVTZ"], "Rotterdam": ["NLRTM"], "Antwerp": ["BEANR"],
    "Hamburg": ["DEHAM"], "Felixstowe": ["GBFXT"], "Los Angeles": ["USLAX"], "Long Beach": ["USLGB"],
    "New York": ["USNYC", "USEWR"],
}
_LOCODE_TO_PORT = {code: port for port, codes in PORT_LOCODES.items() for code in codes}

# Plain-text names, longest first so "LONG BEACH" is tried before a shorter clash.
_NAME_TO_PORT = {
    "SHANGHAI": "Shanghai", "NINGBO": "Ningbo", "YANTIAN": "Shenzhen", "SHEKOU": "Shenzhen",
    "SHENZHEN": "Shenzhen", "GUANGZHOU": "Guangzhou", "NANSHA": "Guangzhou", "QINGDAO": "Qingdao",
    "HONG KONG": "Hong Kong", "HONGKONG": "Hong Kong", "BUSAN": "Busan", "PUSAN": "Busan",
    "LAEM CHABANG": "Laem Chabang", "SINGAPORE": "Singapore", "TANJUNG PELEPAS": "Tanjung Pelepas",
    "TANJUNG PRIOK": "Tanjung Priok", "JAKARTA": "Tanjung Priok", "COLOMBO": "Colombo",
    "JEBEL ALI": "Dubai (Jebel Ali)", "DUBAI": "Dubai (Jebel Ali)", "NHAVA SHEVA": "Nhava Sheva (Mumbai)",
    "JAWAHARLAL NEHRU": "Nhava Sheva (Mumbai)", "MUMBAI": "Nhava Sheva (Mumbai)", "JNPT": "Nhava Sheva (Mumbai)",
    "MUNDRA": "Mundra", "CHENNAI": "Chennai", "COCHIN": "Cochin", "KOCHI": "Cochin",
    "VISAKHAPATNAM": "Visakhapatnam", "VIZAG": "Visakhapatnam", "ROTTERDAM": "Rotterdam",
    "ANTWERPEN": "Antwerp", "ANTWERP": "Antwerp", "HAMBURG": "Hamburg", "FELIXSTOWE": "Felixstowe",
    "LOS ANGELES": "Los Angeles", "LONG BEACH": "Long Beach", "NEW YORK": "New York", "NEWARK": "New York",
}
_NAMES_LONGEST_FIRST = sorted(_NAME_TO_PORT, key=len, reverse=True)


def resolve_destination(text: Optional[str]) -> Optional[str]:
    """The twin port an AIS destination string refers to, or None.

    Crews type destinations freehand, so this reads what real ones look like:
    a UN/LOCODE ("SGSIN"), a locode with a space ("SG SIN", "US LGB"), a port
    name ("SINGAPORE", "PORT OF LOS ANGELES"), or a route ("CNSHA>USLAX",
    "SHANGHAI-LONG BEACH"), where the last leg is where it is going.
    Anything else ("FOR ORDERS", "CHINA") is honestly unresolved."""
    if not text:
        return None
    upper = text.upper()
    for segment in reversed([s for s in re.split(r"[>\-/,;]|=>|\bTO\b", upper) if s.strip()]):
        letters = re.sub(r"[^A-Z]", "", segment)
        if len(letters) == 5 and letters in _LOCODE_TO_PORT:
            return _LOCODE_TO_PORT[letters]
        tidy = re.sub(r"[^A-Z ]", " ", segment)
        tidy = " ".join(tidy.split())
        for name in _NAMES_LONGEST_FIRST:
            if re.search(rf"\b{re.escape(name)}\b", tidy):
                return _NAME_TO_PORT[name]
    return None


def resolve_ais_eta(eta: Optional[Dict[str, int]], now: datetime) -> Optional[datetime]:
    """AIS ETAs carry no year: take the year that puts it closest to `now`."""
    if not eta:
        return None
    candidates = []
    for year in (now.year - 1, now.year, now.year + 1):
        try:
            candidates.append(datetime(year, eta["month"], eta["day"], eta["hour"], eta["minute"]))
        except ValueError:  # e.g. 29 Feb in a non-leap year
            continue
    return min(candidates, key=lambda c: abs(c - now)) if candidates else None


# --- distance along the twin's lanes --------------------------------------

def _project(lat: float, lon: float, poly: List[Tuple[float, float]]) -> Tuple[float, float, float]:
    """(offset from the line, distance along it from its start, distance left to its end), nm."""
    lengths = [haversine_nm(*a, *b) for a, b in zip(poly, poly[1:])]
    starts = [0.0]
    for length in lengths:
        starts.append(starts[-1] + length)

    best_offset, best_along = float("inf"), 0.0
    for i, (a, b) in enumerate(zip(poly, poly[1:])):
        ax, ay = _relative_xy(lat, lon, *a)
        bx, by = _relative_xy(lat, lon, *b)
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / span))
        offset = ((ax + t * dx) ** 2 + (ay + t * dy) ** 2) ** 0.5
        if offset < best_offset:
            best_offset, best_along = offset, starts[i] + t * lengths[i]
    return best_offset, best_along, starts[-1] - best_along


def _lane_weight(_u: str, _v: str, parallel: Dict[Any, Dict[str, Any]]) -> float:
    return min(attrs["distance_nm"] for attrs in parallel.values())


def remaining_distance(lat: float, lon: float, destination: str, twin) -> Dict[str, Any]:
    """What is left to sail to `destination`, and how it was measured.

    On the twin's network: the distance along the ship's own lane to the lane end
    that gets it closest, plus the shortest lane route from there. Off the
    network (or with no route): a straight great-circle line, labelled as such."""
    graph = twin.graph
    straight = haversine_nm(lat, lon, *PORT_COORDINATES[destination])

    if destination in graph:
        candidates = []
        for u, v, attrs in graph.edges(data=True):
            offset, to_start, to_end = _project(lat, lon, lane_polyline(attrs))
            if offset <= MAX_LANE_OFFSET_NM:
                candidates.append((offset, attrs, to_start, to_end))
        if candidates:
            nearest = min(c[0] for c in candidates)
            best_total, best_lane = None, None
            for offset, attrs, to_start, to_end in (c for c in candidates if c[0] <= nearest + LANE_TIE_NM):
                for end_port, along in ((attrs["lane_port_a"], to_start), (attrs["lane_port_b"], to_end)):
                    if end_port == destination:
                        rest = 0.0
                    else:
                        try:
                            rest = nx.shortest_path_length(graph, end_port, destination, weight=_lane_weight)
                        except nx.NetworkXNoPath:
                            continue
                    total = along + rest
                    if best_total is None or total < best_total:
                        best_total, best_lane = total, attrs["lane_id"]
            if best_total is not None:
                return {"nm": round(best_total, 1), "basis": "twin_lanes", "lane_id": best_lane,
                        "great_circle_nm": round(straight, 1)}

    return {"nm": round(straight, 1), "basis": "great_circle", "lane_id": None, "great_circle_nm": round(straight, 1)}


# --- speed ----------------------------------------------------------------

def recent_speed(current_sog: Optional[float], trail: Optional[List[List[Any]]]) -> Tuple[Optional[float], str]:
    """Median of the ship's recent under-way speeds (steadier than one reading), else the current one."""
    samples = [p[3] for p in (trail or [])[-SPEED_SAMPLES:] if len(p) > 3 and p[3] is not None and p[3] >= MIN_UNDERWAY_KNOTS]
    if len(samples) >= 3:
        return round(float(median(samples)), 1), f"median of the last {len(samples)} reports"
    if current_sog is not None and current_sog >= MIN_UNDERWAY_KNOTS:
        return round(float(current_sog), 1), "latest report"
    return None, "not making passage"


# --- the verdict ----------------------------------------------------------

def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat() + "Z" if moment else None


def _hours(delta: timedelta) -> float:
    return round(delta.total_seconds() / 3600, 1)


def _port_signal(port: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not port or not port.get("has_congestion_data"):
        return None
    percentile = port.get("congestion_percentile")
    if percentile is None:
        return None
    if percentile >= 75:
        level, text = "congested", f"Congestion at the destination is unusually high ({percentile}th percentile of its own history): expect waiting for a berth."
    elif percentile <= 25:
        level, text = "quiet", f"Congestion at the destination is low ({percentile}th percentile of its own history)."
    else:
        level, text = "normal", f"Congestion at the destination is typical ({percentile}th percentile of its own history)."
    return {"level": level, "text": text, "as_of": port.get("as_of")}


def assess_voyage(
    *,
    position: Optional[Dict[str, Any]],
    ais_destination: Optional[str],
    ais_eta: Optional[Dict[str, int]],
    plan_destination: Optional[str],
    scheduled_arrival: Optional[datetime],
    trail: Optional[List[List[Any]]],
    twin,
    port_snapshot,
    now: datetime,
) -> Dict[str, Any]:
    """One vessel's live ETA and how it compares with its reference arrival.

    `position` is {latitude, longitude, sog_knots, reported_at (datetime), live (bool)} or None.
    `port_snapshot(port_name)` returns the twin's congestion snapshot for a port."""
    flags: List[str] = []
    result: Dict[str, Any] = {
        "status": None, "headline": None, "destination": None, "remaining": None, "speed_knots": None,
        "speed_basis": None, "predicted_arrival": None, "references": {}, "port": None, "port_signal": None,
        "flags": flags,
    }

    # Destination: the operator's plan wins; else what the ship says.
    resolved_from_ais = resolve_destination(ais_destination)
    if plan_destination:
        destination, source = plan_destination, "plan"
    elif resolved_from_ais:
        destination, source = resolved_from_ais, "ais"
    else:
        destination, source = None, None
    result["destination"] = {
        "port": destination, "source": source, "ais_declared": ais_destination,
        "ais_resolved": resolved_from_ais,
    }
    if ais_destination and not resolved_from_ais and not plan_destination:
        flags.append(f'The ship\'s declared destination "{ais_destination}" isn\'t a port this system recognises.')
    if plan_destination and resolved_from_ais and resolved_from_ais != plan_destination:
        flags.append(f"Your plan says {plan_destination}, but the ship is broadcasting {resolved_from_ais}.")

    if position is None:
        result.update(status="no_position", headline="No AIS position yet, so no ETA can be worked out.")
        return result

    age_minutes = max(0.0, (now - position["reported_at"]).total_seconds() / 60)
    result["position_age_minutes"] = round(age_minutes, 1)
    if age_minutes > STALE_POSITION_MINUTES:
        flags.append(f"The last position is {round(age_minutes)} minutes old; the ETA assumes the ship kept sailing.")

    if destination is None:
        result.update(status="no_destination", headline="No destination: set one below, or wait for the ship to broadcast one.")
        return result

    port = port_snapshot(destination)
    result["port"], result["port_signal"] = port, _port_signal(port)

    speed, speed_basis = recent_speed(position.get("sog_knots"), trail)
    result["speed_knots"], result["speed_basis"] = speed, speed_basis
    distance = remaining_distance(position["latitude"], position["longitude"], destination, twin)
    result["remaining"] = distance
    if distance["basis"] == "great_circle":
        flags.append("Distance is a straight line, which under-counts if land or a strait is in the way.")

    if speed is None:
        result.update(status="not_underway", headline="Not making passage right now (at anchor, in port, or drifting), so no ETA.")
        return result

    predicted = position["reported_at"] + timedelta(hours=distance["nm"] / speed)
    result["predicted_arrival"] = _iso(predicted)

    references = {}
    if scheduled_arrival is not None:
        references["scheduled"] = {"at": _iso(scheduled_arrival), "delta_hours": _hours(predicted - scheduled_arrival)}
    declared = resolve_ais_eta(ais_eta, now)
    if declared is not None:
        references["ais_eta"] = {"at": _iso(declared), "delta_hours": _hours(predicted - declared)}
        if resolved_from_ais and destination != resolved_from_ais:
            references["ais_eta"]["note"] = "The broadcast ETA is for a different port than the one being assessed."
    result["references"] = references

    primary = references.get("scheduled") or references.get("ais_eta")
    if primary is None:
        result.update(status="no_reference", headline="Predicted arrival worked out; there is no scheduled date or broadcast ETA to compare it with.")
        return result

    delta = primary["delta_hours"]
    label = "your scheduled arrival" if "scheduled" in references else "the ETA the ship broadcast"
    if abs(delta) <= ON_TIME_TOLERANCE_HOURS:
        result.update(status="on_time", headline=f"On time: predicted within a day of {label}.")
    elif delta > 0:
        result.update(status="late", headline=f"Running about {round(delta / 24, 1)} days later than {label}.")
    else:
        result.update(status="early", headline=f"Running about {round(-delta / 24, 1)} days ahead of {label}.")
    return result
