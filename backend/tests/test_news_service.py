"""Tests for the cached, corridor-tagged news feed (app/services/news_service.py).

The point of the service is that news stays current without spending a
NewsAPI request per page load, and keeps working through a failed refresh.
"""

import pytest
from fastapi.testclient import TestClient

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.agents.ingestion.news_client import NewsClient
from app.core.config import settings
from app.main import app
from app.services import news_service

client = TestClient(app)
with client:
    pass  # triggers lifespan startup once so governance agents exist


def _article(title, published_at, url=None):
    return {"title": title, "description": None, "content": None, "source": "Test Wire",
            "url": url or f"https://example.com/{title}", "published_at": published_at}


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(settings, "NEWS_API_KEY", "test-key")
    news_service.reset_cache()
    yield
    news_service.reset_cache()


def _patch_fetch(monkeypatch, articles, calls):
    def fake(self, query=None, limit=10, language="en", **kwargs):
        calls.append({"query": query, "limit": limit, **kwargs})
        return [dict(a) for a in articles]
    monkeypatch.setattr(NewsClient, "fetch_news", fake)


def test_query_covers_every_monitored_corridor_and_requires_shipping_terms():
    query = news_service.build_query()
    for loc in MONITORED_LOCATIONS:
        assert f'"{loc["name"].split(" (", 1)[0]}"' in query
    assert " AND " in query and "shipping" in query


def test_articles_are_newest_first_deduplicated_and_tagged(monkeypatch):
    calls = []
    _patch_fetch(monkeypatch, [
        _article("Storm closes Suez Canal to shipping", "2026-09-20T10:00:00Z", url="https://x/1"),
        _article("Hormuz tanker attack", "2026-09-23T10:00:00Z", url="https://x/2"),
        _article("Storm closes Suez Canal to shipping", "2026-09-20T10:00:00Z", url="https://x/1"),
    ], calls)

    feed = news_service.get_maritime_news()

    assert [a["url"] for a in feed["articles"]] == ["https://x/2", "https://x/1"]
    suez = feed["articles"][1]
    assert "Suez Canal (Gulf of Suez)" in suez["corridors"]
    assert suez["understanding"]["category"] == "Storm / Weather"


def test_request_is_recent_and_sorted_newest_first(monkeypatch):
    calls = []
    _patch_fetch(monkeypatch, [], calls)
    news_service.get_maritime_news()
    assert calls[0]["sort_by"] == "publishedAt"
    assert calls[0]["from_date"] is not None
    assert calls[0]["search_in"] == "title,description"


def test_under_covered_corridors_get_one_follow_up_query(monkeypatch):
    """When one corridor floods the results, the others are fetched in a
    second, targeted query instead of being crowded out."""
    calls = []

    def fake(self, query=None, limit=10, language="en", **kwargs):
        calls.append(query)
        if len(calls) == 1:
            return [_article(f"Strait of Hormuz shipping story {i}", f"2026-09-2{i}T10:00:00Z", url=f"https://h/{i}")
                    for i in range(1, 5)]
        return [_article("Strait of Malacca shipping jam", "2026-09-19T10:00:00Z", url="https://m/1")]
    monkeypatch.setattr(NewsClient, "fetch_news", fake)

    feed = news_service.get_maritime_news()

    assert len(calls) == 2
    assert '"Strait of Hormuz"' not in calls[1]  # already covered, not re-queried
    assert '"Strait of Malacca"' in calls[1]
    assert any("Strait of Malacca" in a["corridors"] for a in feed["articles"])


def test_failed_follow_up_query_keeps_the_main_batch(monkeypatch):
    def fake(self, query=None, limit=10, language="en", **kwargs):
        if fake.n:
            raise RuntimeError("429")
        fake.n += 1
        return [_article("Strait of Hormuz shipping story", "2026-09-22T10:00:00Z", url="https://h/1")]
    fake.n = 0
    monkeypatch.setattr(NewsClient, "fetch_news", fake)

    feed = news_service.get_maritime_news()

    assert len(feed["articles"]) == 1 and feed["stale"] is False


def test_second_call_within_ttl_is_served_from_cache(monkeypatch):
    calls = []
    _patch_fetch(monkeypatch, [_article("Suez Canal shipping delay", "2026-09-23T10:00:00Z")], calls)

    news_service.get_maritime_news()
    news_service.get_maritime_news()
    news_service.articles_for_location("Suez Canal (Gulf of Suez)")

    assert len(calls) <= 2  # main query + at most one follow-up, then cached
    before = len(calls)
    news_service.get_maritime_news()
    assert len(calls) == before


def test_failed_refresh_keeps_last_good_articles_and_flags_stale(monkeypatch):
    calls = []
    _patch_fetch(monkeypatch, [_article("Suez Canal shipping delay", "2026-09-23T10:00:00Z")], calls)
    first = news_service.get_maritime_news()
    assert first["stale"] is False

    def boom(self, *a, **k):
        raise RuntimeError("429 Too Many Requests")
    monkeypatch.setattr(NewsClient, "fetch_news", boom)
    news_service._state["next_attempt"] = 0.0  # cache expired

    second = news_service.get_maritime_news()

    assert second["stale"] is True
    assert "429" in second["error"]
    assert len(second["articles"]) == 1  # last good articles kept
    assert second["refresh_in_seconds"] > 0  # backed off, not retried immediately


def test_no_key_means_not_configured_and_no_call(monkeypatch):
    monkeypatch.setattr(settings, "NEWS_API_KEY", None)
    calls = []
    _patch_fetch(monkeypatch, [], calls)

    feed = news_service.get_maritime_news()

    assert feed["configured"] is False and feed["articles"] == []
    assert calls == []


def test_news_route_filters_by_corridor(monkeypatch):
    calls = []
    _patch_fetch(monkeypatch, [
        _article("Storm closes Suez Canal to shipping", "2026-09-20T10:00:00Z", url="https://x/1"),
        _article("Hormuz tanker attack", "2026-09-23T10:00:00Z", url="https://x/2"),
    ], calls)
    everything = client.get("/api/news").json()
    suez_only = client.get("/api/news", params={"corridor": "Suez Canal (Gulf of Suez)"}).json()

    assert everything["total"] == 2 and everything["configured"] is True
    assert suez_only["total"] == 1 and suez_only["articles"][0]["url"] == "https://x/1"
