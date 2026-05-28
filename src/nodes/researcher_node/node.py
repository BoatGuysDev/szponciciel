from __future__ import annotations

from typing import Any

from langchain_tavily import TavilySearch
from sqlmodel import Session

from db import get_engine
from models import Run
from nodes.state import ResearcherState

CATEGORIES: list[tuple[str, str]] = [
    ("AI", "latest artificial intelligence news"),
    ("Tech", "latest technology startup news"),
    ("Finance", "latest stock market finance news"),
    ("Politics", "latest politics government news"),
    ("World", "latest world international news"),
]

_TOPIC_BOOST: dict[str, float] = {
    "AI": 0.15,
    "Tech": 0.10,
    "Finance": 0.05,
    "Politics": 0.05,
    "World": 0.00,
}


def _virality_score(result: dict, category: str) -> float:
    tavily_score = float(result.get("score", 0.0))
    return round(tavily_score * 0.85 + _TOPIC_BOOST.get(category, 0.0), 4)


def researcher_node(state: ResearcherState) -> dict[str, Any]:
    run_id = state.get("run_id")
    if not run_id:
        return {"is_fatal_error": True, "error_message": "run_id is required"}

    tool = TavilySearch(max_results=5)
    candidates: list[dict] = []

    for category, query in CATEGORIES:
        try:
            response = tool.invoke({"query": query})
            articles = response.get("results", []) if isinstance(response, dict) else []
            for r in articles:
                candidates.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "virality_score": _virality_score(r, category),
                    "category": category,
                })
        except Exception:
            continue

    if not candidates:
        return {"is_fatal_error": True, "error_message": "No articles found"}

    best = max(candidates, key=lambda c: c["virality_score"])

    try:
        with Session(get_engine()) as session:
            run = session.get(Run, run_id)
            if not run:
                return {"is_fatal_error": True, "error_message": f"Run {run_id} not found"}
            run.source_article_url = best["url"]
            run.source_article_title = best["title"]
            session.commit()
    except Exception as exc:
        return {"is_fatal_error": True, "error_message": f"DB error: {exc}"}

    return {
        "source_article_url": best["url"],
        "source_article_title": best["title"],
    }
