from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session

from logging_config import get_logger
from models import Run
from nodes.researcher_node import node as researcher_module
from nodes.researcher_node import tools as tools_module
from nodes.researcher_node.node import researcher_node
from nodes.researcher_node.scoring import compute_research_score
from nodes.state import PersonaRunState
from tests.base_test_class import BaseTestClass
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_research_error_handler = build_error_handler(
    log,
    "research.failed",
    "Research failed",
    context_keys=("run_id",),
)

EMPTY_ANALYTICS = {
    "top_categories": [],
    "top_topics": [],
    "underexplored_categories": ["ai", "finance", "politics", "tech", "world"],
    "recent_winners": [],
}


def _mock_tavily(articles: list[dict]):
    tool = MagicMock()
    tool.invoke.return_value = {"results": articles}
    mock_cls = MagicMock(return_value=tool)
    return patch.object(tools_module, "TavilySearch", mock_cls)


def _mock_analytics(summary: dict | None = None):
    service = MagicMock()
    service.summarize.return_value = summary or EMPTY_ANALYTICS
    return patch.object(researcher_module, "ResearchAnalyticsService", MagicMock(return_value=service))


def _plans() -> list[researcher_module._SearchPlan]:
    return [
        researcher_module._SearchPlan(query="ai agents", category="ai", rationale="exploit"),
        researcher_module._SearchPlan(query="market shock", category="finance", rationale="exploit"),
        researcher_module._SearchPlan(query="election update", category="politics", rationale="exploit"),
        researcher_module._SearchPlan(query="new science discovery", category="tech", rationale="explore"),
        researcher_module._SearchPlan(query="world extreme weather", category="world", rationale="explore"),
        researcher_module._SearchPlan(query="backup query", category="world", rationale="backup"),
        researcher_module._SearchPlan(query="backup query 2", category="ai", rationale="backup"),
        researcher_module._SearchPlan(query="backup query 3", category="tech", rationale="backup"),
    ]


def _score_by_url(candidates: list[dict], _analytics: dict) -> list[dict]:
    scored = []
    for candidate in candidates:
        high = "high" in candidate["url"]
        scored.append(
            {
                **candidate,
                "topic": "AI agents" if candidate["category"] == "ai" else "Markets",
                "category": candidate["category"],
                "final_research_score": 0.9 if high else 0.3,
                "category_performance_score": 0.7,
                "similar_topic_performance_score": 0.6,
                "content_fit_score": 0.8,
                "recency_score": 1.0,
                "exploration_bonus": 0.0,
            }
        )
    return scored


def _seed_run(engine: Engine) -> str:
    with Session(engine) as session:
        run = Run(status="running")
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


class TestResearcherNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(researcher_node, retry_policy=LLM_RETRY, error_handler=_research_error_handler)
        graph.add_edge(START, "researcher_node")
        graph.add_edge("researcher_node", END)
        return graph

    def test_iterates_and_persists_highest_analytics_backed_score(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        articles = [
            {"title": "Low", "url": "https://example.com/low", "content": "..."},
            {"title": "High", "url": "https://example.com/high", "content": "..."},
        ]

        with (
            _mock_tavily(articles),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
            patch.object(researcher_module, "_score_candidates", side_effect=_score_by_url),
            patch.object(researcher_module, "_should_stop", return_value=True),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result
        assert result["source_article_content"] == "..."
        assert result["source_article_title"] == "High"
        assert result["source_article_url"] == "https://example.com/high"
        assert result["topic"] == "AI agents"
        assert result["news_category"] == "ai"
        assert result["research_query"] == "ai agents"

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.source_article_title == "High"
            assert run.source_article_url == "https://example.com/high"
            assert run.topic == "AI agents"
            assert run.news_category == "ai"
            assert run.research_query == "ai agents"

    def test_deduplicates_by_url_across_iterations(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        duplicate = [{"title": "Dup", "url": "https://dup.com", "content": "x"}]
        captured: list[list[dict]] = []

        def capture(candidates: list[dict], analytics: dict) -> list[dict]:
            captured.append(candidates)
            return _score_by_url(candidates, analytics)

        with (
            _mock_tavily(duplicate),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
            patch.object(researcher_module, "_score_candidates", side_effect=capture),
            patch.object(researcher_module, "_should_stop", return_value=True),
        ):
            graph.compile().invoke({"run_id": run_id})

        assert all(len(batch) == 1 for batch in captured)

    def test_missing_run_id_returns_fatal_error(self, graph: StateGraph):
        result = graph.compile().invoke({})

        assert result["is_fatal_error"] is True
        assert "run_id" in result["error_message"]

    def test_run_not_found_returns_fatal_error(self, graph: StateGraph):
        result = graph.compile().invoke({"run_id": "nonexistent-id"})

        assert result["is_fatal_error"] is True
        assert "not found" in result["error_message"]

    def test_no_articles_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)

        with (
            _mock_tavily([]),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert result["is_fatal_error"] is True
        assert "No articles found" in result["error_message"]

    def test_failed_fetch_iteration_does_not_stop_later_iterations(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        call_count = 0

        def side_effect(_payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fetch error")
            return {"results": [{"title": "OK", "url": "https://ok.com/high", "content": "..."}]}

        tool = MagicMock()
        tool.invoke.side_effect = side_effect
        mock_cls = MagicMock(return_value=tool)

        with (
            patch.object(tools_module, "TavilySearch", mock_cls),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
            patch.object(researcher_module, "_score_candidates", side_effect=_score_by_url),
            patch.object(researcher_module, "_should_stop", return_value=True),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.source_article_url == "https://ok.com/high"

    def test_scoring_failure_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        articles = [{"title": "X", "url": "https://x.com", "content": "..."}]

        with (
            _mock_tavily(articles),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
            patch.object(
                researcher_module,
                "_score_candidates",
                side_effect=RuntimeError("LLM down"),
            ),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert result["is_fatal_error"] is True
        assert result["error_message"] == "Research failed: RuntimeError: LLM down"

    def test_fetch_news_candidates_searches_custom_query(self):
        captured: list[dict] = []

        tool = MagicMock()

        def invoke(payload):
            captured.append(payload)
            return {"results": [{"title": "T", "url": "https://t.com", "content": "c"}]}

        tool.invoke.side_effect = invoke

        with patch.object(tools_module, "TavilySearch", MagicMock(return_value=tool)):
            result = tools_module.fetch_news_candidates.invoke({"query": "USA-Iran conflict", "category": "world"})

        assert captured == [{"query": "USA-Iran conflict"}]
        assert result == [
            {
                "title": "T",
                "url": "https://t.com",
                "content": "c",
                "query": "USA-Iran conflict",
                "category": "world",
            }
        ]

    def test_node_threads_planned_queries_to_fetch(self, engine: Engine):
        run_id = _seed_run(engine)

        with (
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
            patch.object(researcher_module, "fetch_news_candidates") as mock_fetch,
            patch.object(researcher_module, "_score_candidates", side_effect=_score_by_url),
            patch.object(researcher_module, "_should_stop", return_value=True),
        ):
            mock_fetch.invoke.return_value = [{"title": "T", "url": "https://t.com/high", "content": "c"}]
            researcher_node({"run_id": run_id, "topic": "USA-Iran conflict"})

        assert mock_fetch.invoke.call_count == researcher_module.MIN_RESEARCH_ITERS
        assert mock_fetch.invoke.call_args_list[0].args[0] == {"query": "ai agents", "category": "ai"}

    def test_minimum_coverage_before_self_stop(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        search_kinds: list[str] = []

        def plan(**kwargs):
            search_kinds.append(kwargs["search_kind"])
            return _plans()[len(search_kinds) - 1]

        with (
            _mock_tavily([{"title": "T", "url": "https://t.com/high", "content": "c"}]),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=plan),
            patch.object(researcher_module, "_score_candidates", side_effect=_score_by_url),
            patch.object(researcher_module, "_should_stop", return_value=True) as stop,
        ):
            graph.compile().invoke({"run_id": run_id})

        assert search_kinds == ["exploit", "exploit", "exploit", "explore", "explore"]
        assert stop.call_count == 1

    def test_max_iteration_cutoff_when_agent_does_not_stop(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)

        with (
            _mock_tavily([{"title": "T", "url": "https://t.com/high", "content": "c"}]),
            _mock_analytics(),
            patch.object(researcher_module, "_plan_next_search", side_effect=_plans()),
            patch.object(researcher_module, "_score_candidates", side_effect=_score_by_url),
            patch.object(researcher_module, "_should_stop", return_value=False),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result
        assert result["source_article_url"] == "https://t.com/high"


def test_analytics_backed_score_weights_historical_category_performance():
    analytics = {
        "top_categories": [
            {"name": "ai", "videos": 3, "score": 0.9, "avg_views_per_hour": 500.0, "avg_engagement_rate": 0.12}
        ],
        "top_topics": [
            {"name": "AI agents", "videos": 2, "score": 0.8, "avg_views_per_hour": 450.0, "avg_engagement_rate": 0.1}
        ],
        "underexplored_categories": ["world"],
        "recent_winners": [],
    }

    score = compute_research_score(
        topic="AI agents replace office tasks",
        category="ai",
        analytics=analytics,
        hook_strength=0.8,
        urgency=0.7,
        emotional_intensity=0.6,
        audience_breadth=0.9,
        search_kind="exploit",
    )

    assert score["category_performance_score"] == 0.9
    assert score["final_research_score"] > 0.6
