from typing import Any, Dict, Optional


class RouteAgent:
    def suggest_route(
        self,
        risk_score: Any,
        current_route: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        if isinstance(risk_score, dict):
            risk_score = risk_score.get("score", 50)
        try:
            risk_score = float(risk_score)
        except (TypeError, ValueError):
            risk_score = 50.0

        if risk_score >= 90:
            return {
                "route": "Cape of Good Hope Bypass",
                "reason": "Extreme risk detected. Recommend a longer but safer passage to avoid severe condition cell."
            }

        if risk_score >= 70:
            return {
                "route": "Corridor Beta (Southern Bypass)",
                "reason": "High risk conditions present. Shifting waypoints 120 nm south to bypass severe weather system."
            }

        if risk_score >= 40:
            return {
                "route": "Suez Canal Commercial Passage",
                "reason": "Moderate risk. Proceed with caution along standard commercial channel."
            }

        return {
            "route": "Direct Deepwater Corridor",
            "reason": "Low risk conditions. Optimal direct high-speed navigation route."
        }

    def suggest_route_from_context(
        self,
        risk_score: float,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        route_status: Optional[str] = None,
    ) -> Dict[str, str]:
        recommendation = self.suggest_route(risk_score)

        if route_status and route_status.lower() in {"in_progress", "active"}:
            recommendation["reason"] += " Current route is already active, so update cautiously."

        if origin and destination:
            recommendation["reason"] += f" Origin: {origin}, destination: {destination}."

        return recommendation