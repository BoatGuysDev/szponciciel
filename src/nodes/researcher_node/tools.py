from __future__ import annotations

from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from logging_config import get_logger
from research_categories import NEWS_CATEGORIES
from utils.logging import log_exception
from utils.pipeline_log import tool_span

log = get_logger(__name__)

CATEGORIES = NEWS_CATEGORIES
_DEFAULT_QUERY_BY_CATEGORY = dict(NEWS_CATEGORIES)


@tool
def fetch_news_candidates(query: str | None = None, category: str | None = None) -> list[dict]:
    """Fetches recent news articles via Tavily and deduplicates them by URL.

    If a query is given, searches for that query; otherwise sweeps the default
    news categories. Returns candidate dicts with keys: title, url, content,
    query, and category.
    """
    search = TavilySearch(max_results=5, topic="news", time_range="day")
    category = (category or "").strip().lower() or None
    if query:
        queries = [(category, query)]
    elif category and category in _DEFAULT_QUERY_BY_CATEGORY:
        queries = [(category, _DEFAULT_QUERY_BY_CATEGORY[category])]
    else:
        queries = CATEGORIES

    candidates: list[dict] = []
    seen_urls: set[str] = set()

    for query_category, search_query in queries:
        try:
            with tool_span("tavily.search", input={"query": search_query, "category": query_category}) as call:
                response = search.invoke({"query": search_query})
                call["output"] = response
        except Exception as exc:
            log_exception(log, "researcher.news_fetch_failed", exc, query=search_query, category=query_category)
            continue
        articles = response.get("results", []) if isinstance(response, dict) else []
        for r in articles:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidate = {
                "title": r.get("title", ""),
                "url": url,
                "content": r.get("content", ""),
                "query": search_query,
                "category": query_category,
            }
            published_date = (
                r.get("published_date") or r.get("publishedDate") or r.get("published_at") or r.get("publishedAt")
            )
            if published_date:
                candidate["published_date"] = published_date
            candidates.append(candidate)

    return candidates
