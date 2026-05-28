from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from nodes.state import ResearcherState

try:
    from langchain_community.tools.tavily_search import TavilySearchResults as _TavilySearchResults
except Exception:
    _TavilySearchResults = None

CATEGORIES: list[tuple[str, str]] = [
    ("AI", "latest artificial intelligence news"),
    ("Tech", "latest technology startup news"),
    ("Finance", "latest stock market finance news"),
    ("Politics", "latest politics government news"),
    ("World", "latest world international news"),
]


class CategoryResult(BaseModel):
    category: str
    title: str
    url: str


def _fetch_top(tool: Any, query: str) -> dict[str, str] | None:
    try:
        results = tool.invoke({"query": query})
        if results:
            top = results[0]
            return {"title": top.get("title", ""), "url": top.get("url", "")}
    except Exception:
        pass
    return None


def researcher_node(state: ResearcherState) -> dict[str, Any]:
    if _TavilySearchResults is None:
        return {"is_fatal_error": True, "error_message": "TavilySearchResults not available"}

    tool = _TavilySearchResults(max_results=1)
    results: list[dict] = []

    for category, query in CATEGORIES:
        raw = _fetch_top(tool, query)
        if raw is None:
            continue
        try:
            entry = CategoryResult(category=category, **raw)
            results.append(entry.model_dump())
        except ValidationError:
            continue

    return {"results": results}
