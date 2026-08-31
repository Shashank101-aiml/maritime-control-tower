from typing import Any, Dict, Optional

from app.agents.risk.risk_model import get_risk_model


class RiskAgent:
    def calculate_risk(
        self,
        event: Dict[str, Any],
        route: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        severity = self._normalize_severity(event.get("severity"))
        normalized_event = {**event, "severity": severity}

        prediction = get_risk_model().predict(event=normalized_event, route=route)

        return {
            "score": prediction["score"],
            "severity": severity,
            "likelihood": prediction["likelihood"],
            "impact": prediction["impact"],
            "category": event.get("event_type", "operational"),
            "description": event.get("description"),
            "scoring_method": prediction["scoring_method"],
        }

    def _normalize_severity(self, severity: Any) -> str:
        if not severity:
            return "info"
        text = str(severity).strip().lower()
        if text in {"critical", "high", "warning", "warn", "medium", "low", "info"}:
            return "warning" if text == "warn" else text
        return "info"

    def assess_confidence(self, score: int, scoring_method: str = "ml") -> float:
        """Scores near the 0/100 extremes are unambiguous; scores near the
        middle sit closer to a band boundary and are less certain. A score
        that fell back to the rule-based formula (no trained model on disk)
        is inherently less trustworthy than one from the trained model, so
        it's penalized to make that degraded state visible to governance."""
        distance_from_midpoint = abs(score - 50) / 50
        confidence = 0.6 + 0.35 * distance_from_midpoint
        if scoring_method != "ml":
            confidence *= 0.85
        return round(confidence, 2)
