import importlib
from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from sqlmodel import Session
from sqlalchemy import Engine

researcher_module = importlib.import_module("nodes.researcher_node.node")
researcher_node = researcher_module.researcher_node
from nodes.state import ResearcherState
from models import Run
from tests.base_test_class import BaseTestClass


def _make_tool(articles: list[dict]):
    tool = MagicMock()
    tool.invoke.return_value = {"results": articles}
    return tool


def _mock_tavily(articles: list[dict]):
    mock_cls = MagicMock(return_value=_make_tool(articles))
    return patch.object(researcher_module, "TavilySearch", mock_cls)


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
        graph = StateGraph(state_schema=ResearcherState)
        graph.add_node(researcher_node)
        graph.add_edge(START, "researcher_node")
        graph.add_edge("researcher_node", END)
        return graph

    def test_picks_most_viral_and_saves_to_db(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        articles = [
            {"title": "Low score", "url": "https://example.com/low", "score": 0.3},
            {"title": "High score", "url": "https://example.com/high", "score": 0.9},
        ]

        with _mock_tavily(articles):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result
        assert result["source_article_title"] == "High score"
        assert result["source_article_url"] == "https://example.com/high"

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.source_article_title == "High score"
            assert run.source_article_url == "https://example.com/high"

    def test_topic_boost_breaks_tie(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)

        call_count = 0
        def side_effect(payload):
            nonlocal call_count
            call_count += 1
            # CATEGORIES order: AI(1), Tech(2), Finance(3), Politics(4), World(5)
            category_articles = {
                1: [{"title": "AI News", "url": "https://ai.com", "score": 0.8}],
                5: [{"title": "World News", "url": "https://world.com", "score": 0.8}],
            }
            return {"results": category_articles.get(call_count, [])}

        tool = MagicMock()
        tool.invoke.side_effect = side_effect
        mock_cls = MagicMock(return_value=tool)

        with patch.object(researcher_module, "TavilySearch", mock_cls):
            result = graph.compile().invoke({"run_id": run_id})

        # AI gets 0.15 topic boost, World gets 0.0 — AI wins
        assert result["source_article_title"] == "AI News"

    def test_missing_run_id_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        with _mock_tavily([{"title": "X", "url": "https://x.com", "score": 0.5}]):
            result = graph.compile().invoke({})

        assert result["is_fatal_error"] is True
        assert "run_id" in result["error_message"]

    def test_run_not_found_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        articles = [{"title": "X", "url": "https://x.com", "score": 0.5}]

        with _mock_tavily(articles):
            result = graph.compile().invoke({"run_id": "nonexistent-id"})

        assert result["is_fatal_error"] is True
        assert "not found" in result["error_message"]

    def test_no_articles_returns_fatal_error(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)

        with _mock_tavily([]):
            result = graph.compile().invoke({"run_id": run_id})

        assert result["is_fatal_error"] is True
        assert "No articles found" in result["error_message"]

    def test_failed_category_does_not_stop_others(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        call_count = 0

        def side_effect(payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fetch error")
            return {"results": [{"title": "Article", "url": "https://example.com", "score": 0.5}]}

        tool = MagicMock()
        tool.invoke.side_effect = side_effect
        mock_cls = MagicMock(return_value=tool)

        with patch.object(researcher_module, "TavilySearch", mock_cls):
            result = graph.compile().invoke({"run_id": run_id})

        assert "is_fatal_error" not in result
        assert result["source_article_url"] == "https://example.com"
