from typing import Any, Dict, Optional


class RiskScorer:
    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    @staticmethod
    def _severity_weight(severity: Any) -> int:
        mapping = {
            "critical": 100,
            "high": 80,
            "warning": 60,
            "medium": 40,
            "low": 20,
            "info": 10,
        }
        return mapping.get(RiskScorer._normalize_text(severity), 10)

    @staticmethod
    def _likelihood_weight(likelihood: Any) -> int:
        mapping = {
            "very high": 100,
            "high": 80,
            "medium": 50,
            "low": 25,
            "very low": 10,
        }
        return mapping.get(RiskScorer._normalize_text(likelihood), 50)

    @staticmethod
    def _impact_weight(impact: Any) -> int:
        mapping = {
            "critical": 100,
            "high": 80,
            "medium": 50,
            "low": 25,
            "minor": 10,
        }
        return mapping.get(RiskScorer._normalize_text(impact), 50)

    @staticmethod
    def _status_modifier(status: Any) -> int:
        mapping = {
            "pending": 5,
            "planned": 10,
            "in_progress": 20,
            "active": 20,
            "open": 15,
            "failed": 30,
            "completed": -10,
            "closed": -20,
        }
        return mapping.get(RiskScorer._normalize_text(status), 0)

    @staticmethod
    def _route_complexity_modifier(route: Optional[Dict[str, Any]]) -> int:
        if not route:
            return 0

        modifier = 0
        status = RiskScorer._normalize_text(route.get("status"))
        modifier += RiskScorer._status_modifier(status)

        waypoints = route.get("waypoints")
        if isinstance(waypoints, list):
            modifier += min(len(waypoints) * 2, 20)
        elif isinstance(waypoints, str) and waypoints.strip():
            modifier += min(10, waypoints.count(",") + 1)

        if route.get("notes"):
            modifier += 2

        return modifier

    @classmethod
    def score_event(cls, event: Dict[str, Any], route: Optional[Dict[str, Any]] = None) -> int:
        severity_score = cls._severity_weight(event.get("severity"))
        base_score = severity_score
        base_score += cls._route_complexity_modifier(route)
        return max(0, min(100, base_score))

    @classmethod
    def score_risk(
        cls,
        risk: Dict[str, Any],
        event: Optional[Dict[str, Any]] = None,
        route: Optional[Dict[str, Any]] = None,
    ) -> int:
        likelihood_score = cls._likelihood_weight(risk.get("likelihood"))
        impact_score = cls._impact_weight(risk.get("impact"))
        status_modifier = cls._status_modifier(risk.get("status"))

        route_mod = cls._route_complexity_modifier(route)
        event_mod = cls._severity_weight(event.get("severity")) if event else 0

        total = int(round((likelihood_score * 0.35) + (impact_score * 0.35) + (event_mod * 0.2) + (route_mod * 0.1) + status_modifier))
        return max(0, min(100, total))

    @staticmethod
    def risk_level(score: int) -> str:
        if score >= 75:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    @classmethod
    def evaluate(
        cls,
        event: Optional[Dict[str, Any]] = None,
        route: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if risk:
            score = cls.score_risk(risk=risk, event=event, route=route)
        elif event:
            score = cls.score_event(event=event, route=route)
        else:
            score = 0

        return {
            "score": score,
            "level": cls.risk_level(score),
            "event_severity": cls._normalize_text(event.get("severity")) if event else None,
            "risk_likelihood": cls._normalize_text(risk.get("likelihood")) if risk else None,
            "risk_impact": cls._normalize_text(risk.get("impact")) if risk else None,
        }
