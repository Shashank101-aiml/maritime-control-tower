from typing import Any, Dict, Optional

from app.agents.ingestion.live_conditions_client import LiveConditionsClient
from app.agents.ingestion.maritime_client import MaritimeClient
from app.agents.ingestion.news_client import NewsClient
from app.agents.ingestion.weather_client import WeatherClient
from app.agents.understanding.event_understanding_agent import EventUnderstandingAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.agent_io import IngestedEvent

logger = get_logger(__name__)

FALLBACK_EVENT = {
    "event_type": "Storm",
    "location": "Arabian Sea",
    "severity": "critical",
}


class IngestionAgent:
    def __init__(
        self,
        maritime_client: Optional[MaritimeClient] = None,
        weather_client: Optional[WeatherClient] = None,
        news_client: Optional[NewsClient] = None,
        live_client: Optional[LiveConditionsClient] = None,
    ) -> None:
        self.maritime_client = maritime_client or MaritimeClient()
        self.weather_client = weather_client or WeatherClient(api_key=settings.WEATHER_API_KEY)
        self.news_client = news_client or NewsClient(api_key=settings.NEWS_API_KEY)
        self.live_client = live_client or LiveConditionsClient()
        self.understanding_agent = EventUnderstandingAgent()

    def collect_data(self, source_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dict form, for the HTTP routes (dashboard/events/risks) that
        were already written against dict access before agent hand-offs
        were typed. See collect_data_with_confidence() for the typed
        version other agents should consume."""
        event, _ = self.collect_data_with_confidence(source_payload)
        return event.model_dump()

    def collect_data_with_confidence(
        self, source_payload: Optional[Dict[str, Any]] = None
    ) -> "tuple[IngestedEvent, float]":
        """Same as collect_data, but also reports how much the ingested event
        should be trusted based on where it actually came from."""
        if source_payload is not None:
            # Caller-supplied payloads are unverified, so treat them as
            # moderately trustworthy rather than assuming full confidence.
            return IngestedEvent(**self._normalize_event(source_payload)), 0.7

        event, confidence = self._collect_maritime_event()
        event["weather"] = self._collect_weather(event.get("latitude"), event.get("longitude"))
        event["related_news"] = self._collect_news(event.get("location"))
        return IngestedEvent(**event), confidence

    def _collect_maritime_event(self) -> "tuple[Dict[str, Any], float]":
        """Source chain, most trustworthy first:
        1. Live sea-state feed (Open-Meteo, no API key) -> confidence 0.95
        2. Local sample file                            -> confidence 0.80
        3. Hardcoded fallback constant                  -> confidence 0.50
        Confidence drops with each step down so governance can see how
        stale/synthetic the underlying observation actually was.
        """
        if settings.ENABLE_LIVE_INGESTION:
            try:
                live_event = self.live_client.get_event()
                logger.info(
                    "Live conditions ingested: %s at %s (%s)",
                    live_event.get("event_type"),
                    live_event.get("location"),
                    live_event.get("severity"),
                )
                normalized = self._normalize_event(live_event)
                normalized["conditions"] = live_event.get("conditions")
                normalized["latitude"] = live_event.get("latitude")
                normalized["longitude"] = live_event.get("longitude")
                return normalized, 0.95
            except Exception as exc:
                logger.warning("Live conditions feed unavailable: %s", exc)

        try:
            raw_event = self.maritime_client.get_event()
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Maritime source data unavailable, using fallback event: %s", exc)
            return dict(FALLBACK_EVENT), 0.5

        return self._normalize_event(raw_event), 0.80

    def _collect_weather(
        self, latitude: Optional[float], longitude: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        if latitude is None or longitude is None or not settings.WEATHER_API_KEY:
            return None
        try:
            return self.weather_client.fetch_current_weather(latitude, longitude)
        except Exception as exc:  # network/API failures shouldn't break ingestion
            logger.warning("Weather enrichment failed for (%s, %s): %s", latitude, longitude, exc)
            return None

    def _collect_news(self, location: Optional[str]) -> list:
        if not settings.NEWS_API_KEY:
            return []
        try:
            # The synthesized event_type ("Moderate Swell & Strong
            # Winds") used to be appended verbatim here -- a wave-height
            # description, not a phrase anyone writes news about, so it
            # matched real headlines only by coincidence. The corridor's
            # real location name is what actually shows up in shipping
            # news (Suez, Hormuz, Gulf of Aden...); pair it with generic
            # maritime terms rather than searching for the description.
            query = f'"{location}" AND (shipping OR maritime OR vessel)' if location else None
            articles = self.news_client.fetch_news(query=query, limit=5)
        except Exception as exc:  # network/API failures shouldn't break ingestion
            logger.warning("News enrichment failed: %s", exc)
            return []

        # Slice 07 (Event Understanding, spec section 7): structured
        # category + real-location extraction over each article's own
        # text, not the whole article handed to an LLM for what's
        # fundamentally text classification.
        for article in articles:
            text = " ".join(filter(None, [article.get("title"), article.get("description"), article.get("content")]))
            article["understanding"] = self.understanding_agent.analyze(text).model_dump()
        return articles

    def _normalize_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_type": str(payload.get("event_type", "unknown")).strip(),
            "severity": self._normalize_severity(payload.get("severity")),
            "source": self._normalize_source(payload),
            "description": payload.get("description"),
            "location": payload.get("location"),
            "timestamp": payload.get("timestamp"),
        }

    def _normalize_severity(self, severity: Any) -> str:
        if severity is None:
            return "info"
        severity_value = str(severity).strip().lower()
        if severity_value in {"high", "critical", "urgent"}:
            return "critical"
        if severity_value in {"medium", "moderate"}:
            return "warning"
        if severity_value in {"low", "minor"}:
            return "info"
        return severity_value

    def _normalize_source(self, payload: Dict[str, Any]) -> Optional[str]:
        return (
            payload.get("source")
            or payload.get("location")
            or payload.get("source_system")
            or None
        )
