from __future__ import annotations

import json
from typing import Literal
from typing import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import settings
from db import get_engine
from models import Run
from nodes.researcher_node.scoring import compute_research_score
from nodes.researcher_node.system_prompt import RESEARCHER_SYSTEM_PROMPT
from nodes.researcher_node.tools import fetch_news_candidates
from nodes.state import PersonaRunState
from research_categories import NEWS_CATEGORY_IDS
from services import ResearchAnalyticsService
from utils.pipeline_log import agent_span, tool_span

SearchKind = Literal["exploit", "explore"]
MIN_RESEARCH_ITERS = 5
MAX_RESEARCH_ITERS = 8
REQUIRED_EXPLOIT_SEARCHES = 3
REQUIRED_EXPLORE_SEARCHES = 2
CANDIDATE_CONTENT_LIMIT = 300


class ResearcherResult(TypedDict, total=False):
    source_article_url: str
    source_article_title: str
    source_article_content: str
    topic: str
    news_category: str
    research_query: str
    is_fatal_error: bool
    error_message: str | None


class _SearchPlan(BaseModel):
    query: str = Field(description="Concrete news search query.")
    category: str = Field(description="Lowercase news category for this query.")
    search_kind: SearchKind | None = Field(default=None, description="Use exploit or explore for adaptive searches.")
    rationale: str


class _CandidateAssessment(BaseModel):
    index: int = Field(description="Zero-based index of the candidate.")
    topic: str
    category: str
    hook_strength: float = Field(ge=0.0, le=1.0)
    urgency: float = Field(ge=0.0, le=1.0)
    emotional_intensity: float = Field(ge=0.0, le=1.0)
    audience_breadth: float = Field(ge=0.0, le=1.0)
    reason: str


class _CandidateAssessments(BaseModel):
    assessments: list[_CandidateAssessment]


class _ResearchStopDecision(BaseModel):
    should_stop: bool
    reason: str


def _plan_next_search(
    *,
    analytics: dict,
    topic: str | None,
    previous_queries: list[str],
    search_kind: SearchKind | None,
    iteration: int,
) -> _SearchPlan:
    llm = ChatGoogleGenerativeAI(model=settings.llm_model)
    structured = llm.with_structured_output(_SearchPlan)
    prompt = "\n\n".join(
        [
            RESEARCHER_SYSTEM_PROMPT,
            f"Iteration: {iteration}",
            f"Required search kind: {search_kind or 'adaptive; choose exploit or explore'}",
            f"User requested topic, if any: {topic or 'none'}",
            f"Previous queries: {json.dumps(previous_queries, ensure_ascii=False)}",
            f"Analytics summary: {_compact_json(analytics)}",
            "Return the next search query, one category, and search_kind.",
        ]
    )
    with agent_span(
        "researcher.plan_search",
        model=settings.llm_model,
        prompt=prompt,
        response_format=_SearchPlan.__name__,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
    ) as call:
        plan: _SearchPlan = structured.invoke(prompt)
        call["output"] = plan
    category = plan.category.strip().lower()
    if category not in NEWS_CATEGORY_IDS:
        category = _fallback_category(analytics, search_kind or plan.search_kind or "exploit")
    effective_search_kind = search_kind or plan.search_kind
    if effective_search_kind not in {"exploit", "explore"}:
        effective_search_kind = "exploit"
    return _SearchPlan(
        query=plan.query.strip(),
        category=category,
        search_kind=effective_search_kind,
        rationale=plan.rationale,
    )


def _assess_candidates_with_llm(candidates: list[dict], analytics: dict) -> list[_CandidateAssessment]:
    summary = _candidate_summary(candidates)
    llm = ChatGoogleGenerativeAI(model=settings.llm_model)
    structured = llm.with_structured_output(_CandidateAssessments)
    prompt = "\n\n".join(
        [
            RESEARCHER_SYSTEM_PROMPT,
            f"Analytics summary: {_compact_json(analytics)}",
            f"Candidates:\n{summary}",
            "Return one assessment per candidate, referenced by zero-based index.",
        ]
    )
    with agent_span(
        "researcher.assess_candidates",
        model=settings.llm_model,
        prompt=prompt,
        response_format=_CandidateAssessments.__name__,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
    ) as call:
        result: _CandidateAssessments = structured.invoke(prompt)
        call["output"] = result
    return result.assessments


def _score_candidates(candidates: list[dict], analytics: dict) -> list[dict]:
    assessments = _assess_candidates_with_llm(candidates, analytics)
    scored: list[dict] = []
    for assessment in assessments:
        if not 0 <= assessment.index < len(candidates):
            continue
        candidate = candidates[assessment.index]
        category = assessment.category.strip().lower()
        if category not in NEWS_CATEGORY_IDS:
            category = (candidate.get("category") or "").strip().lower()
        score = compute_research_score(
            topic=assessment.topic,
            category=category,
            analytics=analytics,
            hook_strength=assessment.hook_strength,
            urgency=assessment.urgency,
            emotional_intensity=assessment.emotional_intensity,
            audience_breadth=assessment.audience_breadth,
            search_kind=candidate.get("search_kind") or "exploit",
        )
        scored.append(
            {
                **candidate,
                "topic": assessment.topic,
                "category": category,
                "llm_content_reason": assessment.reason,
                **score,
            }
        )
    return scored


def _should_stop(*, best: dict, analytics: dict, iterations: int, exploit_count: int, explore_count: int) -> bool:
    llm = ChatGoogleGenerativeAI(model=settings.llm_model)
    structured = llm.with_structured_output(_ResearchStopDecision)
    prompt = "\n\n".join(
        [
            RESEARCHER_SYSTEM_PROMPT,
            f"Iterations completed: {iterations}",
            f"Exploit searches completed: {exploit_count}",
            f"Explore searches completed: {explore_count}",
            f"Analytics summary: {_compact_json(analytics)}",
            f"Current best candidate: {_compact_json(_compact_best(best))}",
            "Decide whether the research goal is now satisfied.",
        ]
    )
    with agent_span(
        "researcher.stop_decision",
        model=settings.llm_model,
        prompt=prompt,
        response_format=_ResearchStopDecision.__name__,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
    ) as call:
        decision: _ResearchStopDecision = structured.invoke(prompt)
        call["output"] = decision
    return decision.should_stop


def researcher_node(state: PersonaRunState) -> ResearcherResult:
    """Iteratively researches, scores, and saves the best article to the Run row."""

    run_id = state.get("run_id")
    if not run_id:
        return {"is_fatal_error": True, "error_message": "run_id is required"}

    with Session(get_engine()) as session:
        if not session.get(Run, run_id):
            return {"is_fatal_error": True, "error_message": f"Run {run_id} not found"}

    analytics = ResearchAnalyticsService().summarize()
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    previous_queries: list[str] = []
    best: dict | None = None
    exploit_count = 0
    explore_count = 0

    for iteration in range(1, MAX_RESEARCH_ITERS + 1):
        requested_search_kind = _next_search_kind(exploit_count=exploit_count, explore_count=explore_count)
        plan = _plan_next_search(
            analytics=analytics,
            topic=state.get("topic"),
            previous_queries=previous_queries,
            search_kind=requested_search_kind,
            iteration=iteration,
        )
        search_kind = plan.search_kind or requested_search_kind or "exploit"
        if search_kind == "exploit":
            exploit_count += 1
        else:
            explore_count += 1
        previous_queries.append(plan.query)

        fetch_input = {"query": plan.query, "category": plan.category}
        with tool_span("fetch_news_candidates", input=fetch_input) as call:
            fetched = fetch_news_candidates.invoke(fetch_input)
            call["output"] = fetched

        for candidate in fetched:
            url = candidate.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    **candidate,
                    "query": candidate.get("query") or plan.query,
                    "category": candidate.get("category") or plan.category,
                    "search_kind": search_kind,
                }
            )

        if not candidates:
            continue

        scored = _score_candidates(_top_unscored_or_all(candidates), analytics)
        candidates_by_url = {candidate["url"]: candidate for candidate in candidates}
        for scored_candidate in scored:
            candidates_by_url[scored_candidate["url"]].update(scored_candidate)

        scored_candidates = [candidate for candidate in candidates if "final_research_score" in candidate]
        if scored_candidates:
            best = max(scored_candidates, key=lambda c: c["final_research_score"])

        if (
            best
            and _can_stop(iteration, exploit_count, explore_count)
            and _should_stop(
                best=best,
                analytics=analytics,
                iterations=iteration,
                exploit_count=exploit_count,
                explore_count=explore_count,
            )
        ):
            break

    if not candidates:
        return {"is_fatal_error": True, "error_message": "No articles found"}
    if not best:
        return {"is_fatal_error": True, "error_message": "No scored articles"}

    with Session(get_engine()) as session:
        run = session.get(Run, run_id)
        if not run:
            return {
                "is_fatal_error": True,
                "error_message": f"Run {run_id} not found",
            }
        run.source_article_url = best["url"]
        run.source_article_title = best["title"]
        run.topic = best.get("topic")
        run.news_category = best.get("category")
        run.research_query = best.get("query")
        session.commit()

    return {
        "source_article_url": best["url"],
        "source_article_title": best["title"],
        "source_article_content": best["content"],
        "topic": best.get("topic"),
        "news_category": best.get("category"),
        "research_query": best.get("query"),
    }


def _next_search_kind(*, exploit_count: int, explore_count: int) -> SearchKind | None:
    if exploit_count < REQUIRED_EXPLOIT_SEARCHES:
        return "exploit"
    if explore_count < REQUIRED_EXPLORE_SEARCHES:
        return "explore"
    return None


def _can_stop(iteration: int, exploit_count: int, explore_count: int) -> bool:
    return (
        iteration >= MIN_RESEARCH_ITERS
        and exploit_count >= REQUIRED_EXPLOIT_SEARCHES
        and explore_count >= REQUIRED_EXPLORE_SEARCHES
    )


def _candidate_summary(candidates: list[dict]) -> str:
    return "\n".join(
        f"[{i}] category={candidate.get('category') or 'unknown'} query={candidate.get('query') or ''} "
        f"title={candidate.get('title') or ''} content={(candidate.get('content') or '')[:CANDIDATE_CONTENT_LIMIT]}"
        for i, candidate in enumerate(candidates)
    )


def _top_unscored_or_all(candidates: list[dict]) -> list[dict]:
    unscored = [candidate for candidate in candidates if "final_research_score" not in candidate]
    return unscored or sorted(candidates, key=lambda c: c.get("final_research_score", 0.0), reverse=True)[:20]


def _fallback_category(analytics: dict, search_kind: str) -> str:
    if search_kind == "explore" and analytics["underexplored_categories"]:
        return analytics["underexplored_categories"][0]
    if analytics["top_categories"]:
        return analytics["top_categories"][0]["name"]
    return "world"


def _compact_json(value: dict | list) -> str:
    return json.dumps(value, ensure_ascii=False)[:4000]


def _compact_best(best: dict) -> dict:
    return {
        "title": best.get("title"),
        "url": best.get("url"),
        "topic": best.get("topic"),
        "category": best.get("category"),
        "query": best.get("query"),
        "final_research_score": best.get("final_research_score"),
        "score_components": {
            "category_performance_score": best.get("category_performance_score"),
            "similar_topic_performance_score": best.get("similar_topic_performance_score"),
            "content_fit_score": best.get("content_fit_score"),
            "exploration_bonus": best.get("exploration_bonus"),
        },
    }
