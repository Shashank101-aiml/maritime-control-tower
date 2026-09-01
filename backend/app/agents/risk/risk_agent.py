from typing import Any, Dict, Optional, Union

from app.agents.risk.risk_model import get_risk_model
from app.schemas.agent_io import IngestedEvent, RiskAssessment


class RiskAgent:
    def calculate_risk(
        self,
        event: Union[IngestedEvent, Dict[str, Any]],
        route: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        # Agents pass a typed IngestedEvent; the /risks and /dashboard
        # HTTP routes still call this with the dict IngestionAgent.collect_data()
        # returns. Both are accepted so this doesn't force every caller to
        # convert, but the return type is always the typed contract.
        event_dict = event.model_dump() if isinstance(event, IngestedEvent) else dict(event)

        severity = self._normalize_severity(event_dict.get("severity"))
        normalized_event = {**event_dict, "severity": severity}

        prediction = get_risk_model().predict(event=normalized_event, route=route)

        return RiskAssessment(
            score=prediction["score"],
            severity=severity,
            likelihood=prediction["likelihood"],
            impact=prediction["impact"],
            category=event_dict.get("event_type") or "operational",
            description=event_dict.get("description"),
            scoring_method=prediction["scoring_method"],
        )

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
