from typing import Dict, List

from app.schemas.agent_io import Decision, RouteRecommendation

# Matches the agent's own confidence_threshold registered in
# app/main.py's AgentIdentity seed -- kept here as the default so a
# direct DecisionAgent().decide() call (tests, scripts) behaves the
# same as the governed pipeline without needing to know that seed
# value lives elsewhere.
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# A pick this risky deserves a human look even when it's still the
# best real alternative available -- matches the elevated-risk
# threshold already used for badges/coloring across the frontend
# (RouteComparisonChart, RouteCard, RiskAnalysis).
ELEVATED_RISK_THRESHOLD = 60


def _as_candidate(data: Dict) -> Dict:
    """RouteRecommendation and RouteAlternative overlap on exactly the
    fields a candidate comparison needs -- this reads either shape."""
    return {
        "lane_ids": data["lane_ids"],
        "distance_nm": data["distance_nm"],
        "transit_days": data["transit_days"],
        "cost_usd": data["cost_usd"],
        "risk": data["risk"],
    }


class DecisionAgent:
    """Turns a ranked RouteRecommendation into a structured decision:
    what changes if the recommendation is followed, versus the most
    obvious alternative (shortest distance) -- and whether that change
    is confident enough to act on without a human sign-off.
    """

    def decide(
        self,
        route: RouteRecommendation,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> Decision:
        recommended = _as_candidate(route.model_dump())
        candidates: List[Dict] = [recommended] + [
            _as_candidate(alt.model_dump()) for alt in route.alternatives
        ]

        # The naive comparison point: whichever candidate is shortest,
        # i.e. what a chooser that ignored risk entirely would pick.
        # Real data already computed by RouteOptimizer -- no baseline
        # is invented here.
        baseline = min(candidates, key=lambda c: c["distance_nm"])

        expected_delay_days = round(recommended["transit_days"] - baseline["transit_days"], 1)
        estimated_cost_change_usd = round(recommended["cost_usd"] - baseline["cost_usd"], 2)
        risk_reduction = baseline["risk"] - recommended["risk"]

        # Confidence reflects how exposed the recommended lane still is,
        # not a model-reported figure that doesn't exist for this agent
        # -- a 10/100-risk pick is a confident recommendation, a
        # 75/100-risk pick is the best available but not reassuring.
        confidence = round(1 - recommended["risk"] / 100, 2)
        requires_human_approval = (
            confidence < confidence_threshold or recommended["risk"] >= ELEVATED_RISK_THRESHOLD
        )

        if recommended["lane_ids"] == baseline["lane_ids"]:
            recommendation = (
                f"{' + '.join(recommended['lane_ids'])} is both the shortest available route and "
                "the safest ranked one -- no trade-off to make."
            )
        else:
            direction = "safer" if risk_reduction > 0 else "riskier" if risk_reduction < 0 else "no different"
            delay_word = "slower" if expected_delay_days > 0 else "faster" if expected_delay_days < 0 else "no slower"
            cost_word = "more" if estimated_cost_change_usd > 0 else "less" if estimated_cost_change_usd < 0 else "no more"
            recommendation = (
                f"Take {' + '.join(recommended['lane_ids'])} instead of the shortest option "
                f"({' + '.join(baseline['lane_ids'])}): {abs(risk_reduction)} points {direction}, "
                f"{abs(expected_delay_days)} days {delay_word}, ~${abs(estimated_cost_change_usd):,.0f} {cost_word}."
            )

        return Decision(
            recommendation=recommendation,
            baseline_lane_ids=baseline["lane_ids"],
            recommended_lane_ids=recommended["lane_ids"],
            expected_delay_days=expected_delay_days,
            estimated_cost_change_usd=estimated_cost_change_usd,
            risk_reduction=risk_reduction,
            confidence=confidence,
            requires_human_approval=requires_human_approval,
        )
