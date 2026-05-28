import importlib
from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph

researcher_module = importlib.import_module("nodes.researcher_node.node")
researcher_node = researcher_module.researcher_node
from nodes.state import ResearcherState
from tests.base_test_class import BaseTestClass


def _make_tool(return_value):
    tool = MagicMock()
    tool.invoke.return_value = return_value
    return tool


def _mock_tavily(return_value):
    """Context manager that patches _TavilySearchResults and returns a tool mock."""
    mock_cls = MagicMock(return_value=_make_tool(return_value))
    return patch.object(researcher_module, "_TavilySearchResults", mock_cls)


class TestResearcherNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=ResearcherState)
        graph.add_node(researcher_node)
        graph.add_edge(START, "researcher_node")
        graph.add_edge("researcher_node", END)
        return graph

    def test_returns_one_result_per_category(self, graph: StateGraph, engine):
        single_hit = [{"title": "Test Article", "url": "https://example.com/article"}]

        with _mock_tavily(single_hit):
            result = graph.compile().invoke({})

        assert "is_fatal_error" not in result
        assert len(result["results"]) == len(researcher_module.CATEGORIES)

    def test_result_has_category_title_url(self, graph: StateGraph, engine):
        with _mock_tavily([{"title": "AI News", "url": "https://ai.com/news"}]):
            result = graph.compile().invoke({})

        first = result["results"][0]
        assert first["category"] == "AI"
        assert first["title"] == "AI News"
        assert first["url"] == "https://ai.com/news"

    def test_skips_failed_category(self, graph: StateGraph, engine):
        call_count = 0

        def side_effect(payload):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fetch error")
            return [{"title": "Article", "url": "https://example.com"}]

        tool = MagicMock()
        tool.invoke.side_effect = side_effect
        mock_cls = MagicMock(return_value=tool)

        with patch.object(researcher_module, "_TavilySearchResults", mock_cls):
            result = graph.compile().invoke({})

        assert "is_fatal_error" not in result
        assert len(result["results"]) == len(researcher_module.CATEGORIES) - 1

    def test_empty_tavily_response(self, graph: StateGraph, engine):
        with _mock_tavily([]):
            result = graph.compile().invoke({})

        assert "is_fatal_error" not in result
        assert result["results"] == []

    def test_tavily_unavailable(self, graph: StateGraph, engine):
        with patch.object(researcher_module, "_TavilySearchResults", None):
            result = graph.compile().invoke({})

        assert result["is_fatal_error"] is True
        assert "error_message" in result
