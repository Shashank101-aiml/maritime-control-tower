from typing import Any, Dict, List, Optional

import requests

DEFAULT_TIMEOUT_SECONDS = 10


class NewsClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://newsapi.org/v2/everything",
        default_query: str = "maritime OR shipping OR navigation",
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_query = default_query
        self.timeout = timeout

    def fetch_news(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        language: str = "en",
        sort_by: Optional[str] = None,
        from_date: Optional[str] = None,
        search_in: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if query is None:
            query = self.default_query

        params = {
            "q": query,
            "pageSize": limit,
            "language": language,
        }
        if sort_by:
            params["sortBy"] = sort_by
        if from_date:
            params["from"] = from_date
        if search_in:
            params["searchIn"] = search_in

        if self.api_key:
            params["apiKey"] = self.api_key

        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()

        payload = response.json()
        articles = payload.get("articles", [])

        return [self._serialize_article(article) for article in articles]

    def _serialize_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": article.get("title"),
            "description": article.get("description"),
            "content": article.get("content"),
            "source": (article.get("source") or {}).get("name"),
            "url": article.get("url"),
            "published_at": article.get("publishedAt"),
        }
