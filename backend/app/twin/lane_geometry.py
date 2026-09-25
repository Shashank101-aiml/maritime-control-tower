"""The drawn and measured path of a shipping lane: from the origin port's
sea approach, through each named waypoint, to the destination port's sea
approach, with the sea-only turning points from sea_legs.py between each
consecutive pair so no segment crosses land."""

from typing import Any, Dict, List, Tuple

from app.twin.coordinates import PORT_APPROACH_COORDINATES, PORT_COORDINATES
from app.twin.sea_legs import SEA_LEGS


def _leg(x: str, y: str) -> List[Tuple[float, float]]:
    if (x, y) in SEA_LEGS:
        return SEA_LEGS[(x, y)]
    return list(reversed(SEA_LEGS.get((y, x), [])))


def lane_points(port_a: str, waypoints: List[str], port_b: str,
                waypoint_coords: Dict[str, Tuple[float, float]]) -> List[Dict[str, Any]]:
    """[{lat, lon, name}] along the lane; name is None for a pure geometry point."""
    def coords(name: str) -> Tuple[float, float]:
        return PORT_APPROACH_COORDINATES.get(name) or waypoint_coords.get(name) or PORT_COORDINATES[name]

    names = [port_a, *[w for w in waypoints if w in waypoint_coords], port_b]
    points = []
    for i, name in enumerate(names):
        lat, lon = coords(name)
        points.append({"lat": lat, "lon": lon, "name": name})
        if i + 1 < len(names):
            points += [{"lat": la, "lon": lo, "name": None} for la, lo in _leg(name, names[i + 1])]
    return points
