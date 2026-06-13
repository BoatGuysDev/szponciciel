from __future__ import annotations

from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import settings
from db import get_engine
from models import Run
from nodes.researcher_node.system_prompt import RESEARCHER_SYSTEM_PROMPT
from nodes.researcher_node.tools import fetch_news_candidates
from nodes.state import PersonaRunState
from utils.pipeline_log import agent_span, tool_span


class ResearcherResult(TypedDict, total=False):
    source_article_url: str
    source_article_title: str
    source_article_content: str
    is_fatal_error: bool
    error_message: str | None


class _ScoredArticle(BaseModel):
    index: int = Field(description="Zero-based index of the candidate.")
    virality_score: float = Field(ge=0.0, le=1.0)


class _ArticleRanking(BaseModel):
    rankings: list[_ScoredArticle]


def _score_with_llm(candidates: list[dict]) -> list[dict]:
    summary = "\n".join(f"[{i}] {c['title']} — {c['content'][:300]}" for i, c in enumerate(candidates))
    llm = ChatGoogleGenerativeAI(model=settings.llm_model)
    structured = llm.with_structured_output(_ArticleRanking)
    prompt = f"{RESEARCHER_SYSTEM_PROMPT}\n\nCandidates:\n{summary}"
    with agent_span(
        "researcher.score_articles",
        model=settings.llm_model,
        prompt=prompt,
        response_format=_ArticleRanking.__name__,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
    ) as call:
        ranking: _ArticleRanking = structured.invoke(prompt)
        call["output"] = ranking

    scored: list[dict] = []
    for entry in ranking.rankings:
        if 0 <= entry.index < len(candidates):
            scored.append({**candidates[entry.index], "virality_score": entry.virality_score})
    return scored


def researcher_node(state: PersonaRunState) -> ResearcherResult:
    """Fetches news candidates, scores them by virality with an LLM, and saves the winner to the Run row."""

    run_id = state.get("run_id")
    if not run_id:
        return {"is_fatal_error": True, "error_message": "run_id is required"}

    with Session(get_engine()) as session:
        if not session.get(Run, run_id):
            return {"is_fatal_error": True, "error_message": f"Run {run_id} not found"}

    fetch_input = {"topic": state.get("topic")}
    with tool_span("fetch_news_candidates", input=fetch_input) as call:
        candidates = fetch_news_candidates.invoke(fetch_input)
        call["output"] = candidates
    if not candidates:
        return {"is_fatal_error": True, "error_message": "No articles found"}

    scored = _score_with_llm(candidates)

    if not scored:
        return {"is_fatal_error": True, "error_message": "No scored articles"}

    best = max(scored, key=lambda c: c["virality_score"])

    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            return {
                "is_fatal_error": True,
                "error_message": f"Run {run_id} not found",
            }
        run.source_article_url = best["url"]
        run.source_article_title = best["title"]
        session.commit()

    return {
        "source_article_url": best["url"],
        "source_article_title": best["title"],
        "source_article_content": best["content"],
    }
