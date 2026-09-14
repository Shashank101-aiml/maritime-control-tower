from typing import Any, Dict, List, Optional, Sequence

try:
    import openai
except ImportError:  
    openai = None

from app.agents.explanation.prompt_builder import PromptBuilder


class ExplanationAgent:
    def __init__(
        self,
        provider: str = "fallback",
        model: str = "gpt-4.1",
        api_key: Optional[str] = None,
    ) -> None:
        self.provider = provider
        self.model = model

        if self.provider == "openai":
            if openai is None or not api_key:
                self.provider = "fallback"
            else:
                openai.api_key = api_key

    def explain(
        self,
        route: Dict[str, Any],
        event: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        prompt = PromptBuilder.build_route_explanation_prompt(
            route=route,
            risk=risk,
            recommendations=recommendations,
        )
        return self._generate_explanation(
            prompt, route=route, event=event, risk=risk, recommendations=recommendations
        )

    def _generate_explanation(
        self,
        prompt: str,
        route: Dict[str, Any],
        event: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        if self.provider == "openai" and openai:
            try:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an explanation agent for a maritime control system."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                )
                return response.choices[0].message["content"].strip()
            except Exception:
                pass

        return self._fallback_explanation(route=route, event=event, risk=risk, recommendations=recommendations)

    def _fallback_explanation(
        self,
        route: Dict[str, Any],
        event: Optional[Dict[str, Any]] = None,
        risk: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        """Built directly from the real route/event/risk data for this
        specific execution -- not a canned sentence. Used whenever no
        OpenAI provider is configured (the only path actually exercised
        in the real pipeline today, since ExplanationAgent() is always
        constructed with no arguments there) or the OpenAI call itself
        failed, so a "fallback" explanation still says something true
        about what happened rather than the same fixed paragraph every
        time regardless of input.
        """
        sentences: List[str] = []

        if event:
            event_type = event.get("event_type") or "an event"
            location = event.get("location")
            severity = event.get("severity")
            where = f" near {location}" if location else ""
            sev = f" ({severity} severity)" if severity else ""
            sentences.append(f"The Ingestion Agent detected {event_type}{where}{sev}.")

        if risk:
            score = risk.get("score")
            risk_severity = risk.get("severity")
            category = risk.get("category")
            if score is not None:
                cat = f", category: {category}" if category else ""
                sentences.append(
                    f"The Risk Agent scored this at {score}/100 "
                    f"({risk_severity or 'unclassified'} severity{cat})."
                )

        if route:
            summary = route.get("route")
            detail = route.get("reason")
            if not detail:
                distance, transit, route_risk = (
                    route.get("distance_nm"), route.get("transit_days"), route.get("risk"),
                )
                if distance is not None and transit is not None and route_risk is not None:
                    detail = f"{distance:.0f} nm, ~{transit:.1f} days, risk {route_risk}/100"
            elif detail.endswith("."):
                detail = detail[:-1]  # `reason` already ends in a period; avoid doubling it up
            if summary:
                sentences.append(
                    f"The Route Optimization Agent recommends {summary}" + (f" -- {detail}." if detail else ".")
                )

        if recommendations:
            top_summary = recommendations[0].get("summary") if recommendations[0] else None
            if top_summary:
                sentences.append(f"Recommendation: {top_summary}.")

        if not sentences:
            sentences.append("No event, risk, or route data was available to explain this execution.")

        return " ".join(sentences)