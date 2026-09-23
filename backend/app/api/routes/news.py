from typing import Optional

from fastapi import APIRouter, Query

from app.services.news_service import get_maritime_news

router = APIRouter()


@router.get("/news")
def get_news(
    corridor: Optional[str] = Query(None, description="Only articles tagged with this monitored corridor."),
    limit: int = Query(20, ge=1, le=50),
):
    """Recent maritime news, newest first, each tagged with the corridors it
    mentions and a category by the Event Understanding Agent. Served from a
    cached batch (see app/services/news_service.py), so calling this never
    spends a NewsAPI request beyond the cache's own refresh."""
    feed = get_maritime_news()
    articles = feed["articles"]
    if corridor:
        articles = [a for a in articles if corridor in a["corridors"]]
    return {
        "configured": feed["configured"],
        "corridor": corridor,
        "total": len(articles),
        "articles": articles[:limit],
        "fetched_at": feed["fetched_at"],
        "refresh_in_seconds": feed["refresh_in_seconds"],
        "stale": feed["stale"],
        "error": feed["error"],
    }
