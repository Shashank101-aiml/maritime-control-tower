"""Tests for the Event Understanding Agent (Slice 10): real TF-IDF
category classification and gazetteer-based location extraction over
free text, plus its wiring into IngestionAgent's news enrichment.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.ingestion.ingestion_agent import IngestionAgent
from app.agents.ingestion.news_client import NewsClient
from app.agents.understanding.event_understanding_agent import EventUnderstandingAgent
from app.core.config import settings
from app.main import app

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


class TestEventUnderstandingAgent:
    def test_classifies_a_storm_headline_and_finds_the_real_corridor(self):
        result = EventUnderstandingAgent().analyze(
            "A severe storm forced the closure of the Suez Canal for container vessels this week."
        )
        assert result.category == "Storm / Weather"
        assert result.category_confidence > 0
        assert "Suez Canal (Gulf of Suez)" in result.matched_locations

    def test_classifies_a_piracy_headline(self):
        result = EventUnderstandingAgent().analyze(
            "Armed pirates hijacked a cargo vessel and held the crew for ransom near the Gulf of Aden."
        )
        assert result.category == "Piracy / Security"
        assert "Gulf of Aden" in result.matched_locations

    def test_classifies_a_congestion_headline(self):
        result = EventUnderstandingAgent().analyze(
            "Shanghai port congestion worsens as ships queue at anchorage waiting for berth capacity."
        )
        assert result.category == "Port Congestion"
        assert "Shanghai" in result.matched_locations

    def test_unrelated_text_matches_no_real_location(self):
        result = EventUnderstandingAgent().analyze("The quarterly earnings report exceeded analyst expectations.")
        assert result.matched_locations == []

    def test_empty_text_is_honestly_uncategorized_not_a_guess(self):
        result = EventUnderstandingAgent().analyze("")
        assert result.category == "Uncategorized"
        assert result.category_confidence == 0.0

    def test_gazetteer_includes_real_ports_and_corridors(self):
        from app.agents.understanding.event_understanding_agent import GAZETTEER
        assert "Shanghai" in GAZETTEER
        assert "Suez Canal (Gulf of Suez)" in GAZETTEER
        assert len(GAZETTEER) >= 28  # 20 ports + 8 corridors, no duplicates


class TestIngestionAgentNewsUnderstanding:
    def test_each_related_news_article_gets_real_understanding(self, monkeypatch):
        monkeypatch.setattr(settings, "NEWS_API_KEY", "test-key")
        monkeypatch.setattr(
            NewsClient, "fetch_news",
            lambda self, query=None, limit=10, language="en": [
                {"title": "Storm closes Suez Canal to shipping", "description": None, "content": None,
                 "source": "Test Wire", "url": "https://example.com/1", "published_at": None},
            ],
        )

        agent = IngestionAgent()
        articles = agent._collect_news("Suez Canal (Gulf of Suez)")

        assert len(articles) == 1
        understanding = articles[0]["understanding"]
        assert understanding["category"] == "Storm / Weather"
        assert "Suez Canal (Gulf of Suez)" in understanding["matched_locations"]

    def test_no_key_means_no_call_and_no_understanding(self, monkeypatch):
        monkeypatch.setattr(settings, "NEWS_API_KEY", None)
        assert IngestionAgent()._collect_news("Shanghai") == []


class TestUnderstandApiRoute:
    def _token(self):
        res = client.post(
            "/api/auth/login",
            data={"username": "admin@example.com", "password": "admin"},
        )
        return res.json()["access_token"]

    def test_understand_endpoint_returns_real_classification(self):
        token = self._token()
        res = client.get(
            "/api/understand",
            params={"text": "Oil spill reported near Rotterdam after tanker collision."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["category"] == "Environmental / Spill"
        assert "Rotterdam" in body["matched_locations"]
