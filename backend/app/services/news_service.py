"""Cached, corridor-tagged maritime news feed.

One batched NewsAPI query covers every monitored corridor (newest first,
last NEWS_LOOKBACK_DAYS days), plus at most one follow-up query for any
corridor the main batch under-covers. The result is cached for
NEWS_CACHE_TTL_SECONDS and each article is tagged by the Event
Understanding Agent. Per-corridor views are filtered from that cached batch
instead of spending an API request per corridor per page load -- which is
what kept the free-tier quota at risk and left calm corridors with an
empty, static-looking panel.

If a refresh fails (rate limit, outage) the last good articles are kept and
flagged stale, and the next attempt is delayed so a limited key isn't
hammered on every request.
"""

import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.agents.ingestion.news_client import NewsClient
from app.agents.understanding.event_understanding_agent import EventUnderstandingAgent
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_ARTICLES = 50
# A corridor with fewer articles than this after the main query gets one
# follow-up query of its own, so one corridor dominating the news (e.g.
# Hormuz during a crisis) can't crowd every other corridor out of the
# top-N. At most 2 NewsAPI requests per refresh.
MIN_ARTICLES_PER_CORRIDOR = 2
RETRY_AFTER_FAILURE_SECONDS = 300
SHIPPING_TERMS = "(ship OR shipping OR vessel OR tanker OR cargo OR maritime OR seafarers)"
MONITORED_NAMES = {loc["name"] for loc in MONITORED_LOCATIONS}

_lock = threading.Lock()
_state: Dict[str, Any] = {"articles": [], "fetched_at": None, "next_attempt": 0.0, "error": None}
_agent: Optional[EventUnderstandingAgent] = None


def reset_cache() -> None:
    with _lock:
        _state.update(articles=[], fetched_at=None, next_attempt=0.0, error=None)


def _search_name(canonical: str) -> str:
    """The name as real news writes it: the unqualified prefix of e.g.
    "Suez Canal (Gulf of Suez)"."""
    return canonical.split(" (", 1)[0]


def build_query(corridors: Optional[List[str]] = None) -> str:
    """Corridor names AND'd with shipping terms, so a place name alone
    doesn't pull in unrelated stories. Defaults to every monitored corridor."""
    names = [_search_name(c) for c in (corridors or [loc["name"] for loc in MONITORED_LOCATIONS])]
    return "(" + " OR ".join(f'"{n}"' for n in names) + ") AND " + SHIPPING_TERMS


def _understanding_agent() -> EventUnderstandingAgent:
    global _agent
    if _agent is None:
        _agent = EventUnderstandingAgent()
    return _agent


def _search(corridors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    from_date = (datetime.now(timezone.utc) - timedelta(days=settings.NEWS_LOOKBACK_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return NewsClient(api_key=settings.NEWS_API_KEY).fetch_news(
        query=build_query(corridors),
        limit=MAX_ARTICLES,
        sort_by="publishedAt",
        from_date=from_date,
        search_in="title,description",
    )


def _tag(article: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(filter(None, [article.get("title"), article.get("description"), article.get("content")]))
    understanding = _understanding_agent().analyze(text).model_dump()
    article["understanding"] = understanding
    article["corridors"] = [n for n in understanding["matched_locations"] if n in MONITORED_NAMES]
    return article


def _fetch() -> List[Dict[str, Any]]:
    articles: Dict[str, Dict[str, Any]] = {}

    def add(raw: List[Dict[str, Any]]) -> None:
        for article in raw:
            key = article.get("url") or article.get("title")
            if key and key not in articles:
                articles[key] = _tag(article)

    add(_search())

    covered = Counter(c for a in articles.values() for c in a["corridors"])
    under_covered = [n for n in sorted(MONITORED_NAMES) if covered[n] < MIN_ARTICLES_PER_CORRIDOR]
    if 0 < len(under_covered) < len(MONITORED_NAMES):
        try:
            add(_search(under_covered))
        except Exception as exc:  # the main batch is still good; don't lose it
            logger.warning("News follow-up query for under-covered corridors failed: %s", exc)

    return sorted(articles.values(), key=lambda a: a.get("published_at") or "", reverse=True)


def get_maritime_news() -> Dict[str, Any]:
    if not settings.NEWS_API_KEY:
        return {"configured": False, "articles": [], "fetched_at": None,
                "refresh_in_seconds": None, "stale": False, "error": None}

    with _lock:
        now = time.monotonic()
        if now >= _state["next_attempt"]:
            try:
                _state["articles"] = _fetch()
                _state["fetched_at"] = datetime.now(timezone.utc).isoformat()
                _state["error"] = None
                _state["next_attempt"] = now + settings.NEWS_CACHE_TTL_SECONDS
            except Exception as exc:
                logger.warning("News refresh failed, serving last good articles: %s", exc)
                _state["error"] = str(exc)
                _state["next_attempt"] = now + RETRY_AFTER_FAILURE_SECONDS

        return {
            "configured": True,
            "articles": list(_state["articles"]),
            "fetched_at": _state["fetched_at"],
            "refresh_in_seconds": max(0, int(_state["next_attempt"] - time.monotonic())),
            "stale": _state["error"] is not None,
            "error": _state["error"],
        }


def articles_for_location(location: Optional[str], limit: int = 5) -> List[Dict[str, Any]]:
    if not location:
        return []
    matching = [
        a for a in get_maritime_news()["articles"]
        if location in a["understanding"]["matched_locations"]
    ]
    return matching[:limit]
