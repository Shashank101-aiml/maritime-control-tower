from typing import Any, Dict, List, Optional, Sequence


class PromptBuilder:
    @staticmethod
    def _serialize_section(title: str, values: Dict[str, Any]) -> str:
        lines = [f"{title}:"]
        for key, value in values.items():
            if value is None:
                continue
            lines.append(f"- {key.replace('_', ' ').capitalize()}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _serialize_recommendations(
        recommendations: Sequence[Dict[str, Any]]
    ) -> str:
        if not recommendations:
            return "Recommendations:\n- None available."
        lines = ["Recommendations:"]
        for rec in recommendations:
            summary = rec.get("summary", "No summary provided")
            status = rec.get("status", "unknown")
            source = rec.get("source", "unknown source")
            lines.append(
                f"- {summary} (status: {status}, source: {source})"
            )
        return "\n".join(lines)

    @classmethod
    def build_event_explanation_prompt(
        cls,
        event: Dict[str, Any],
        risk: Optional[Dict[str, Any]] = None,
        route: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        prompt_parts: List[str] = [
            "You are an Explanation Agent for a maritime control system.",
            "Translate the following system state into a clear, concise explanation for operators."
        ]

        prompt_parts.append(cls._serialize_section("Event details", event))

        if risk:
            prompt_parts.append(cls._serialize_section("Risk assessment", risk))

        if route:
            prompt_parts.append(cls._serialize_section("Route details", route))

        if recommendations is not None:
            prompt_parts.append(cls._serialize_recommendations(recommendations))

        prompt_parts.append(
            "Produce an explanation that includes:\n"
            "- what happened\n"
            "- why it matters\n"
            "- any risk implications\n"
            "- recommended next steps\n"
            "- whether follow-up action is required"
        )

        return "\n\n".join(prompt_parts)

    @classmethod
    def build_risk_explanation_prompt(
        cls,
        risk: Dict[str, Any],
        event: Optional[Dict[str, Any]] = None,
        route: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        prompt_parts = [
            "You are an Explanation Agent for maritime risk management.",
            "Summarize the risk information in a way that is actionable for operators."
        ]

        prompt_parts.append(cls._serialize_section("Risk details", risk))

        if event:
            prompt_parts.append(cls._serialize_section("Related event", event))

        if route:
            prompt_parts.append(cls._serialize_section("Related route", route))

        if recommendations is not None:
            prompt_parts.append(cls._serialize_recommendations(recommendations))

        prompt_parts.append(
            "Explain:\n"
            "- the nature of the risk\n"
            "- the likely impact\n"
            "- recommended mitigation steps\n"
            "- any connection to current route or event context"
        )

        return "\n\n".join(prompt_parts)

    @classmethod
    def build_route_explanation_prompt(
        cls,
        route: Dict[str, Any],
        risk: Optional[Dict[str, Any]] = None,
        recommendations: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        prompt_parts = [
            "You are an Explanation Agent for maritime route planning.",
            "Provide a clear summary of the route plan and any operational concerns."
        ]

        prompt_parts.append(cls._serialize_section("Route details", route))

        if risk:
            prompt_parts.append(cls._serialize_section("Route risk", risk))

        if recommendations is not None:
            prompt_parts.append(cls._serialize_recommendations(recommendations))

        prompt_parts.append(
            "Describe:\n"
            "- route origin and destination\n"
            "- current status\n"
            "- potential hazards or risk factors\n"
            "- suggested next steps or checks"
        )

        return "\n\n".join(prompt_parts)
