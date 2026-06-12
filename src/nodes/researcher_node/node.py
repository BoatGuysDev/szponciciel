from __future__ import annotations

from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import settings
from db import get_engine
from logging_config import get_logger
from models import Run
from nodes.researcher_node.system_prompt import RESEARCHER_SYSTEM_PROMPT
from nodes.researcher_node.tools import fetch_news_candidates
from nodes.state import PersonaRunState
from utils.logging import describe_exception, log_exception

log = get_logger(__name__)


class ResearcherResult(TypedDict, total=False):
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
    ranking: _ArticleRanking = structured.invoke(f"{RESEARCHER_SYSTEM_PROMPT}\n\nCandidates:\n{summary}")

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

    candidates = fetch_news_candidates.invoke({"topic": state.get("topic")})
    if not candidates:
        return {"is_fatal_error": True, "error_message": "No articles found"}

    try:
        scored = _score_with_llm(candidates)
    except Exception as exc:
        log_exception(log, "researcher.scoring_failed", exc, run_id=run_id, candidate_count=len(candidates))
        return {"is_fatal_error": True, "error_message": f"Scoring error: {describe_exception(exc)}"}

    if not scored:
        return {"is_fatal_error": True, "error_message": "No scored articles"}

    best = max(scored, key=lambda c: c["virality_score"])

    try:
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
    except Exception as exc:
        log_exception(log, "researcher.db_write_failed", exc, run_id=run_id, article_url=best["url"])
        return {"is_fatal_error": True, "error_message": f"DB error: {describe_exception(exc)}"}

    return {}
