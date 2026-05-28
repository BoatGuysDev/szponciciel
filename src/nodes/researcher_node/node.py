from __future__ import annotations

from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import settings
from db import get_engine
from models import Run
from nodes.researcher_node.system_prompt import RESEARCHER_SYSTEM_PROMPT
from nodes.state import ResearcherState

CATEGORIES: list[tuple[str, str]] = [
    ("AI", "latest artificial intelligence breakthroughs"),
    ("Tech", "latest technology and startup news"),
    ("Finance", "latest stock market and finance news"),
    ("Politics", "latest politics and government news"),
    ("World", "latest world and international news"),
]


class ResearcherResult(TypedDict, total=False):
    article_url: str
    article_title: str
    is_fatal_error: bool
    error_message: str | None


class _ScoredArticle(BaseModel):
    index: int = Field(description="Zero-based index of the candidate.")
    virality_score: float = Field(ge=0.0, le=1.0)


class _ArticleRanking(BaseModel):
    rankings: list[_ScoredArticle]


def _fetch_candidates() -> list[dict]:
    tool = TavilySearch(max_results=5, topic="news", time_range="day")
    candidates: list[dict] = []
    seen_urls: set[str] = set()

    for _, query in CATEGORIES:
        try:
            response = tool.invoke({"query": query})
        except Exception:
            continue
        articles = response.get("results", []) if isinstance(response, dict) else []
        for r in articles:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append({
                "title": r.get("title", ""),
                "url": url,
                "content": r.get("content", ""),
            })

    return candidates


def _score_with_llm(candidates: list[dict]) -> list[dict]:
    summary = "\n".join(
        f"[{i}] {c['title']} — {c['content'][:300]}"
        for i, c in enumerate(candidates)
    )
    llm = ChatGoogleGenerativeAI(model=settings.llm_model)
    structured = llm.with_structured_output(_ArticleRanking)
    ranking: _ArticleRanking = structured.invoke(
        f"{RESEARCHER_SYSTEM_PROMPT}\n\nCandidates:\n{summary}"
    )

    scored: list[dict] = []
    for entry in ranking.rankings:
        if 0 <= entry.index < len(candidates):
            scored.append({**candidates[entry.index], "virality_score": entry.virality_score})
    return scored


def researcher_node(state: ResearcherState) -> ResearcherResult:
    """Fetches news candidates, scores them by virality with an LLM, and saves the winner to the Run row."""

    run_id = state.get("run_id")
    if not run_id:
        return {"is_fatal_error": True, "error_message": "run_id is required"}

    candidates = _fetch_candidates()
    if not candidates:
        return {"is_fatal_error": True, "error_message": "No articles found"}

    try:
        scored = _score_with_llm(candidates)
    except Exception as exc:
        return {"is_fatal_error": True, "error_message": f"Scoring error: {exc}"}

    if not scored:
        return {"is_fatal_error": True, "error_message": "No scored articles"}

    best = max(scored, key=lambda c: c["virality_score"])

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
        "article_url": best["url"],
        "article_title": best["title"],
    }
