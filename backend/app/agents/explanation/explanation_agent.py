from typing import Any, Dict, Optional, Sequence

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
        return self._generate_explanation(prompt)

    def _generate_explanation(self, prompt: str) -> str:
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

        return self._fallback_explanation(prompt)

    def _fallback_explanation(self, prompt: str) -> str:
        return (
            "The Ingestion Agent detected an active weather event in the vessel corridor. "
            "The Risk Assessment Agent evaluated hazard telemetry and updated fleet vulnerability metrics. "
            "Consequently, the Route Optimization Agent generated an adjusted navigational corridor to ensure vessel and crew safety."
        )