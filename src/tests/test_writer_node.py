import pytest
from unittest.mock import patch, MagicMock
from langgraph.graph import StateGraph, START, END

from nodes.writer_node.node import writer_node
from graphs.writer_critic_graph.state import WriterCriticState
from config import settings

from tests.base_test_class import BaseTestClass


BASE_STATE: WriterCriticState = {
    "article_url": "https://example.com/article",
    "article_title": "Big news story",
    "persona_language": "en",
    "persona_style": "dramatic",
    "persona_tone": "serious",
    "real_news_ratio": 0.8,
    "draft_script": None,
    "reliability_score": None,
    "corrections": None,
    "iterations": 0,
    "is_fatal_error": False,
    "error_message": None,
}


class TestWriterNode(BaseTestClass):
    """Tests for the writer node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=WriterCriticState)
        graph.add_node(writer_node)
        graph.add_edge(START, "writer_node")
        graph.add_edge("writer_node", END)
        return graph

    def _mock_agent(self, content: str) -> MagicMock:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"messages": [MagicMock(content=content)]}

        return mock_agent

    def test_successful_first_iteration(self, graph: StateGraph):
        """Script is set and iterations increments to 1 on a clean first pass."""

        expected_script = "Breaking news! This is huge."
        mock_agent = self._mock_agent(expected_script)

        with (
            patch("nodes.writer_node.node.ChatGoogleGenerativeAI"),
            patch("nodes.writer_node.node.create_agent", return_value=mock_agent),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["draft_script"] == expected_script
        assert not result.get("is_fatal_error")

    def test_successful_with_corrections(self, graph: StateGraph):
        """Corrections from the critic are appended to the prompt on subsequent iterations."""

        draft_script = "Initial draft script."
        corrections = "Be more concise in the opening line."
        state = {
            **BASE_STATE,
            "draft_script": draft_script,
            "corrections": corrections,
            "iterations": 1,
        }
        mock_agent = self._mock_agent("Revised script here.")

        with (
            patch("nodes.writer_node.node.ChatGoogleGenerativeAI"),
            patch("nodes.writer_node.node.create_agent", return_value=mock_agent),
        ):
            graph.compile().invoke(state)

        call_args = mock_agent.invoke.call_args
        prompt_text = call_args[0][0]["messages"][0].content
        assert draft_script in prompt_text
        assert corrections in prompt_text

    def test_script_truncated_to_max_length(self, graph: StateGraph):
        """Output longer than max_script_length is truncated."""

        long_content = "x" * (settings.max_script_length + 1000)
        expected_content = "x" * settings.max_script_length + "..."
        mock_agent = self._mock_agent(long_content)

        with (
            patch("nodes.writer_node.node.ChatGoogleGenerativeAI"),
            patch("nodes.writer_node.node.create_agent", return_value=mock_agent),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert len(result["draft_script"]) == len(expected_content)
        assert result["draft_script"] == expected_content

    def test_agent_failure_returns_fatal_error(self, graph: StateGraph):
        """An exception from the LLM agent results in a fatal error state."""

        mock_agent = self._mock_agent("This content won't be used.")
        mock_agent.invoke.side_effect = RuntimeError("LLM unavailable")

        with (
            patch("nodes.writer_node.node.ChatGoogleGenerativeAI"),
            patch("nodes.writer_node.node.create_agent", return_value=mock_agent),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["is_fatal_error"]
        assert "Writer agent failed" in result["error_message"]
