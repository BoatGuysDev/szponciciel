from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from sqlmodel import Session
from sqlalchemy import Engine

from models import Run
from nodes.researcher_node import node as researcher_module
from nodes.researcher_node import tools as tools_module
from nodes.researcher_node.node import researcher_node
from nodes.state import PersonaRunState
from tests.base_test_class import BaseTestClass


def _mock_tavily(articles: list[dict]):
    tool = MagicMock()
    tool.invoke.return_value = {"results": articles}
    mock_cls = MagicMock(return_value=tool)
    return patch.object(tools_module, "TavilySearch", mock_cls)


def _mock_scoring(scored: list[dict]):
    return patch.object(researcher_module, "_score_with_llm", return_value=scored)


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
        graph.add_node(researcher_node)
        graph.add_edge(START, "researcher_node")
        graph.add_edge("researcher_node", END)
        return graph

    def test_picks_highest_virality_and_saves_to_db(
        self, graph: StateGraph, engine: Engine
    ):
        run_id = _seed_run(engine)
        articles = [
            {"title": "Low", "url": "https://example.com/low", "content": "..."},
            {"title": "High", "url": "https://example.com/high", "content": "..."},
        ]
        scored = [
            {
                "title": "Low",
                "url": "https://example.com/low",
                "content": "...",
                "virality_score": 0.3,
            },
            {
                "title": "High",
                "url": "https://example.com/high",
                "content": "...",
                "virality_score": 0.9,
            },
        ]

        with _mock_tavily(articles), _mock_scoring(scored):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.source_article_title == "High"
            assert run.source_article_url == "https://example.com/high"

    def test_deduplicates_by_url_across_categories(
        self, graph: StateGraph, engine: Engine
    ):
        run_id = _seed_run(engine)
        duplicate = [{"title": "Dup", "url": "https://dup.com", "content": "x"}]

        with _mock_tavily(duplicate):
            captured: list = []

            def capture(candidates):
                captured.append(candidates)
                return [{**candidates[0], "virality_score": 0.5}] if candidates else []

            with patch.object(
                researcher_module, "_score_with_llm", side_effect=capture
            ):
                graph.compile().invoke({"run_id": run_id})

        assert len(captured[0]) == 1

    def test_missing_run_id_returns_fatal_error(
        self, graph: StateGraph, engine: Engine
    ):
        articles = [{"title": "X", "url": "https://x.com", "content": "..."}]
        scored = [
            {
                "title": "X",
                "url": "https://x.com",
                "content": "...",
                "virality_score": 0.5,
            }
        ]

        with _mock_tavily(articles), _mock_scoring(scored):
            result = graph.compile().invoke({})

        assert result["is_fatal_error"] is True
        assert "run_id" in result["error_message"]

    def test_run_not_found_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        articles = [{"title": "X", "url": "https://x.com", "content": "..."}]
        scored = [
            {
                "title": "X",
                "url": "https://x.com",
                "content": "...",
                "virality_score": 0.5,
            }
        ]

        with _mock_tavily(articles), _mock_scoring(scored):
            result = graph.compile().invoke({"run_id": "nonexistent-id"})

        assert result["is_fatal_error"] is True
        assert "not found" in result["error_message"]

    def test_no_articles_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)

        with _mock_tavily([]):
            result = graph.compile().invoke({"run_id": run_id})

        assert result["is_fatal_error"] is True
        assert "No articles found" in result["error_message"]

    def test_failed_category_does_not_stop_others(
        self, graph: StateGraph, engine: Engine
    ):
        run_id = _seed_run(engine)
        call_count = 0

        def side_effect(payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fetch error")
            return {
                "results": [{"title": "OK", "url": "https://ok.com", "content": "..."}]
            }

        tool = MagicMock()
        tool.invoke.side_effect = side_effect
        mock_cls = MagicMock(return_value=tool)

        scored = [
            {
                "title": "OK",
                "url": "https://ok.com",
                "content": "...",
                "virality_score": 0.7,
            }
        ]

        with (
            patch.object(tools_module, "TavilySearch", mock_cls),
            _mock_scoring(scored),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.source_article_url == "https://ok.com"

    def test_scoring_failure_returns_fatal_error(
        self, graph: StateGraph, engine: Engine
    ):
        run_id = _seed_run(engine)
        articles = [{"title": "X", "url": "https://x.com", "content": "..."}]

        with (
            _mock_tavily(articles),
            patch.object(
                researcher_module,
                "_score_with_llm",
                side_effect=RuntimeError("LLM down"),
            ),
        ):
            result = graph.compile().invoke({"run_id": run_id})

        assert result["is_fatal_error"] is True
        assert "Scoring error" in result["error_message"]

    def test_topic_searches_single_query_not_categories(self):
        captured: list[str] = []

        tool = MagicMock()

        def invoke(payload):
            captured.append(payload["query"])
            return {"results": [{"title": "T", "url": "https://t.com", "content": "c"}]}

        tool.invoke.side_effect = invoke

        with patch.object(tools_module, "TavilySearch", MagicMock(return_value=tool)):
            result = tools_module.fetch_news_candidates.invoke(
                {"topic": "USA-Iran conflict"}
            )

        assert captured == ["USA-Iran conflict"]
        assert result == [{"title": "T", "url": "https://t.com", "content": "c"}]

    def test_node_threads_topic_to_fetch(self, engine: Engine):
        run_id = _seed_run(engine)
        scored = [
            {
                "title": "T",
                "url": "https://t.com",
                "content": "c",
                "virality_score": 0.9,
            }
        ]

        with (
            patch.object(researcher_module, "fetch_news_candidates") as mock_fetch,
            _mock_scoring(scored),
        ):
            mock_fetch.invoke.return_value = [
                {"title": "T", "url": "https://t.com", "content": "c"}
            ]
            researcher_node({"run_id": run_id, "topic": "USA-Iran conflict"})

        mock_fetch.invoke.assert_called_once_with({"topic": "USA-Iran conflict"})

    def test_graph_threads_topic_to_fetch(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        scored = [
            {"title": "T", "url": "https://t.com", "content": "c", "virality_score": 0.9}
        ]

        with (
            patch.object(researcher_module, "fetch_news_candidates") as mock_fetch,
            _mock_scoring(scored),
        ):
            mock_fetch.invoke.return_value = [
                {"title": "T", "url": "https://t.com", "content": "c"}
            ]
            graph.compile().invoke({"run_id": run_id, "topic": "USA-Iran conflict"})

        mock_fetch.invoke.assert_called_once_with({"topic": "USA-Iran conflict"})
