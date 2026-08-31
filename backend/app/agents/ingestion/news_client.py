from typing import Any, Dict, List, Optional

import requests


class NewsClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://newsapi.org/v2/everything",
        default_query: str = "maritime OR shipping OR navigation",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.default_query = default_query

    def fetch_news(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        if query is None:
            query = self.default_query

        params = {
            "q": query,
            "pageSize": limit,
            "language": language,
        }

        if self.api_key:
            params["apiKey"] = self.api_key

        response = requests.get(self.base_url, params=params)
        response.raise_for_status()

        payload = response.json()
        articles = payload.get("articles", [])

        return [self._serialize_article(article) for article in articles]

    def _serialize_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": article.get("title"),
            "description": article.get("description"),
            "content": article.get("content"),
            "source": article.get("source", {}).get("name"),
            "url": article.get("url"),
            "published_at": article.get("publishedAt"),
        }
