from typing import Any, Dict, List, Optional


class RouteOptimizer:
    def optimize_route(
        self,
        route: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        constraints = constraints or {}
        waypoints = self._normalize_waypoints(route.get("waypoints"))
        optimized_waypoints = self._apply_constraints(waypoints, constraints)
        route_score = self._score_route(
            origin=route.get("origin"),
            destination=route.get("destination"),
            waypoints=optimized_waypoints,
            status=route.get("status"),
            constraints=constraints,
        )

        return {
            **route,
            "waypoints": optimized_waypoints,
            "optimized": True,
            "optimization_score": route_score,
            "estimated_time_of_arrival": self._estimate_eta(
                optimized_waypoints, route.get("status")
            ),
            "notes": route.get("notes", "") + " Optimized route plan.",
        }

    def _normalize_waypoints(self, waypoints: Any) -> List[Dict[str, Any]]:
        if isinstance(waypoints, list):
            return [self._normalize_waypoint(point) for point in waypoints]
        if isinstance(waypoints, str) and waypoints.strip():
            points = [
                segment.strip() for segment in waypoints.split(",") if segment.strip()
            ]
            return [self._normalize_waypoint(point) for point in points]
        return []

    def _normalize_waypoint(self, waypoint: Any) -> Dict[str, Any]:
        if isinstance(waypoint, dict):
            return waypoint
        if isinstance(waypoint, str):
            return {"label": waypoint}
        return {"label": str(waypoint)}

    def _apply_constraints(
        self, waypoints: List[Dict[str, Any]], constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not waypoints:
            return waypoints

        optimized = waypoints.copy()
        if constraints.get("avoid_waypoints"):
            excluded = set(constraints["avoid_waypoints"])
            optimized = [
                waypoint
                for waypoint in optimized
                if waypoint.get("label") not in excluded
            ]

        if constraints.get("preferred_waypoints"):
            preferred = constraints["preferred_waypoints"]
            optimized = sorted(
                optimized,
                key=lambda wp: 0 if wp.get("label") in preferred else 1,
            )

        return optimized

    def _score_route(
        self,
        origin: Optional[str],
        destination: Optional[str],
        waypoints: List[Dict[str, Any]],
        status: Optional[str],
        constraints: Dict[str, Any],
    ) -> float:
        score = 50.0
        if origin and destination:
            score += 10.0
        score += min(len(waypoints) * 5.0, 25.0)

        if status and status.lower() in {"planned", "confirmed"}:
            score += 10.0
        elif status and status.lower() in {"in_progress", "active"}:
            score += 5.0

        if constraints.get("avoid_waypoints"):
            avoided = set(constraints["avoid_waypoints"])
            score -= min(
                15.0,
                sum(1 for wp in waypoints if wp.get("label") in avoided),
            )

        if constraints.get("preferred_waypoints"):
            preferred = set(constraints["preferred_waypoints"])
            score += min(
                15.0,
                sum(1 for wp in waypoints if wp.get("label") in preferred),
            )

        return max(0.0, min(100.0, score))

    def _estimate_eta(
        self, waypoints: List[Dict[str, Any]], status: Optional[str]
    ) -> Optional[str]:
        if not waypoints:
            return None
        base_hours = len(waypoints) * 4
        if status and status.lower() in {"in_progress", "active"}:
            base_hours += 2
        return f"2026-07-0{min(9, base_hours // 24 + 2)}T08:00:00Z"
