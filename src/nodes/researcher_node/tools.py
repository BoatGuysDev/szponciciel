from __future__ import annotations

from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from logging_config import get_logger
from utils.logging import log_exception

log = get_logger(__name__)

CATEGORIES: list[tuple[str, str]] = [
    ("AI", "latest artificial intelligence breakthroughs"),
    ("Tech", "latest technology and startup news"),
    ("Finance", "latest stock market and finance news"),
    ("Politics", "latest politics and government news"),
    ("World", "latest world and international news"),
]


@tool
def fetch_news_candidates(topic: str | None = None) -> list[dict]:
    """Fetches recent news articles via Tavily and deduplicates them by URL.

    If a topic is given, searches for that topic; otherwise sweeps the default
    news categories. Returns a list of candidate dicts with keys: title, url, content.
    """
    search = TavilySearch(max_results=5, topic="news", time_range="day")
    queries = [topic] if topic else [query for _, query in CATEGORIES]
    candidates: list[dict] = []
    seen_urls: set[str] = set()

    for query in queries:
        try:
            response = search.invoke({"query": query})
        except Exception as exc:
            log_exception(log, "researcher.news_fetch_failed", exc, query=query)
            continue
        articles = response.get("results", []) if isinstance(response, dict) else []
        for r in articles:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "title": r.get("title", ""),
                    "url": url,
                    "content": r.get("content", ""),
                }
            )

    return candidates
