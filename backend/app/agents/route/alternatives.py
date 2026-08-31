from typing import Any, Dict, List, Optional


class RouteAlternatives:
    def generate_alternatives(
        self,
        route: Dict[str, Any],
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        base_origin = route.get("origin", "unknown origin")
        base_destination = route.get("destination", "unknown destination")
        waypoints = route.get("waypoints") or []
        status = route.get("status", "planned")

        alternatives = []
        for idx in range(1, count + 1):
            alternative = self._build_alternative(
                origin=base_origin,
                destination=base_destination,
                waypoints=waypoints,
                status=status,
                index=idx,
            )
            alternatives.append(alternative)

        return alternatives

    def _build_alternative(
        self,
        origin: str,
        destination: str,
        waypoints: Any,
        status: str,
        index: int,
    ) -> Dict[str, Any]:
        adjusted_waypoints = self._adjust_waypoints(waypoints, index)
        risk_modifier = self._estimate_risk_modifier(adjusted_waypoints, status)
        estimated_eta = self._estimate_eta(adjusted_waypoints, index)

        return {
            "origin": origin,
            "destination": destination,
            "status": status,
            "waypoints": adjusted_waypoints,
            "estimated_time_of_arrival": estimated_eta,
            "notes": f"Alternative route option {index}",
            "risk_score": risk_modifier,
            "alternative_index": index,
        }

    def _adjust_waypoints(self, waypoints: Any, index: int) -> Any:
        if isinstance(waypoints, list):
            return waypoints[index - 1 :] + waypoints[: index - 1]
        if isinstance(waypoints, str) and waypoints.strip():
            points = [p.strip() for p in waypoints.split(",")]
            rotated = points[index - 1 :] + points[: index - 1]
            return ", ".join(rotated)
        return waypoints

    def _estimate_risk_modifier(self, waypoints: Any, status: str) -> int:
        modifier = 0
        if status in {"in_progress", "active"}:
            modifier += 10
        if isinstance(waypoints, list):
            modifier += min(len(waypoints) * 2, 20)
        elif isinstance(waypoints, str) and waypoints.strip():
            modifier += min(10, waypoints.count(",") + 1)
        return min(100, modifier + 10)

    def _estimate_eta(self, waypoints: Any, index: int) -> Optional[str]:
        if not waypoints:
            return None
        return f"2026-07-0{index + 1}T08:00:00Z"
