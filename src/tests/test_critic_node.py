import pytest
from unittest.mock import patch, MagicMock
from langgraph.graph import StateGraph, START, END

from nodes.writer_critic_graph.critic_node.node import critic_node
from nodes.writer_critic_graph.critic_node.response_format import (
    CriticAgentResponseFormat,
)
from nodes.writer_critic_graph.state import WriterCriticState

from tests.base_test_class import BaseTestClass


BASE_STATE: WriterCriticState = {
    "article_url": "https://example.com/article",
    "article_title": "Big news story",
    "persona_language": "en",
    "persona_style": "dramatic",
    "persona_tone": "serious",
    "real_news_ratio": 0.8,
    "draft_script": "Breaking news! This is huge.",
    "review": None,
    "iterations": 0,
    "is_fatal_error": False,
    "error_message": None,
}


class TestCriticNode(BaseTestClass):
    """Tests for the critic node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=WriterCriticState)
        graph.add_node(critic_node)
        graph.add_edge(START, "critic_node")
        graph.add_edge("critic_node", END)
        return graph

    def _mock_agent(self, parsed: CriticAgentResponseFormat | None) -> MagicMock:
        mock = MagicMock()
        mock.invoke.return_value = (
            {"structured_response": parsed} if parsed is not None else {}
        )
        return mock

    def test_successful_review(self, graph: StateGraph):
        """Reliability score is the mean of the four sub-scores; iterations increments."""

        parsed = CriticAgentResponseFormat(
            coherence_score=0.8,
            grammar_score=1.0,
            unambiguity_score=0.6,
            catchiness_score=0.4,
            corrections="Punch up the opening line.",
        )
        mock_agent = self._mock_agent(parsed)

        with (
            patch("nodes.writer_critic_graph.critic_node.node.ChatGoogleGenerativeAI"),
            patch(
                "nodes.writer_critic_graph.critic_node.node.create_agent",
                return_value=mock_agent,
            ),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert not result.get("is_fatal_error")
        assert result["review"] == {
            "coherence_score": 0.8,
            "grammar_score": 1.0,
            "unambiguity_score": 0.6,
            "catchiness_score": 0.4,
            "corrections": "Punch up the opening line.",
        }
        assert result["iterations"] == 1

    def test_prompt_contains_script_and_persona(self, graph: StateGraph):
        """The draft script and persona fields are included in the prompt."""

        parsed = CriticAgentResponseFormat(
            coherence_score=1.0,
            grammar_score=1.0,
            unambiguity_score=1.0,
            catchiness_score=1.0,
            corrections="",
        )
        mock_agent = self._mock_agent(parsed)

        with (
            patch("nodes.writer_critic_graph.critic_node.node.ChatGoogleGenerativeAI"),
            patch(
                "nodes.writer_critic_graph.critic_node.node.create_agent",
                return_value=mock_agent,
            ),
        ):
            graph.compile().invoke(BASE_STATE)

        prompt_text = mock_agent.invoke.call_args[0][0]["messages"][0].content
        assert BASE_STATE["draft_script"] in prompt_text
        assert BASE_STATE["persona_language"] in prompt_text
        assert BASE_STATE["persona_style"] in prompt_text
        assert BASE_STATE["persona_tone"] in prompt_text

    def test_no_structured_response(self, graph: StateGraph):
        """Fatal error when agent returns no structured_response."""

        mock_agent = self._mock_agent(None)

        with (
            patch("nodes.writer_critic_graph.critic_node.node.ChatGoogleGenerativeAI"),
            patch(
                "nodes.writer_critic_graph.critic_node.node.create_agent",
                return_value=mock_agent,
            ),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["is_fatal_error"]
        assert result["error_message"] == "Failed to parse critic response."

    def test_agent_failure_returns_fatal_error(self, graph: StateGraph):
        """An exception from the LLM agent results in a fatal error state."""

        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = RuntimeError("LLM unavailable")

        with (
            patch("nodes.writer_critic_graph.critic_node.node.ChatGoogleGenerativeAI"),
            patch(
                "nodes.writer_critic_graph.critic_node.node.create_agent",
                return_value=mock_agent,
            ),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["is_fatal_error"]
        assert "Critic agent failed" in result["error_message"]
