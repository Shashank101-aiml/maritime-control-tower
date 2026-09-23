"""Where a position sits relative to the digital twin: nearest shipping
lane and nearest port. Small-area planar distances are accurate enough at
the tens-to-hundreds of nautical miles these checks work at, and longitude
is unwrapped so lanes crossing the antimeridian (trans-Pacific) still work."""

from math import cos, hypot, radians
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.twin.coordinates import PORT_COORDINATES
from app.twin.digital_twin import WAYPOINT_COORDINATES, haversine_nm

NM_PER_DEGREE = 60.0


def _relative_xy(lat0: float, lon0: float, lat: float, lon: float) -> Tuple[float, float]:
    dlon = ((lon - lon0 + 180.0) % 360.0) - 180.0
    return dlon * cos(radians(lat0)) * NM_PER_DEGREE, (lat - lat0) * NM_PER_DEGREE


def distance_to_segment_nm(lat: float, lon: float, a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Shortest distance from a point to the segment a-b, in nautical miles."""
    ax, ay = _relative_xy(lat, lon, *a)
    bx, by = _relative_xy(lat, lon, *b)
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
    return hypot(ax + t * dx, ay + t * dy)


def lane_polyline(edge: Dict[str, Any]) -> List[Tuple[float, float]]:
    points = [PORT_COORDINATES[edge["lane_port_a"]]]
    points += [WAYPOINT_COORDINATES[name] for name in edge["waypoints"] if name in WAYPOINT_COORDINATES]
    points.append(PORT_COORDINATES[edge["lane_port_b"]])
    return points


def nearest_lane(lat: float, lon: float, edges: Iterable[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], float]]:
    """(edge attrs, distance in nm) of the closest lane, or None if the twin has no lanes."""
    best: Optional[Tuple[Dict[str, Any], float]] = None
    for edge in edges:
        poly = lane_polyline(edge)
        offset = min(distance_to_segment_nm(lat, lon, p, q) for p, q in zip(poly, poly[1:]))
        if best is None or offset < best[1]:
            best = (edge, offset)
    return best


def nearest_port(lat: float, lon: float) -> Tuple[str, float]:
    name, (plat, plon) = min(
        PORT_COORDINATES.items(), key=lambda item: haversine_nm(lat, lon, item[1][0], item[1][1])
    )
    return name, haversine_nm(lat, lon, plat, plon)
