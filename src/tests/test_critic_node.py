from unittest.mock import patch

import pytest
from langgraph.graph import END, START, StateGraph

from logging_config import get_logger
from nodes.writer_critic_graph.critic_node.node import critic_node
from nodes.writer_critic_graph.critic_node.response_format import (
    CriticAgentResponseFormat,
)
from nodes.writer_critic_graph.state import WriterCriticState
from tests.base_test_class import BaseTestClass
from tests.retry_policy import FAST_LLM_RETRY
from utils.agent_utils import AgentResponseError
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_critic_error_handler = build_error_handler(
    log,
    "critic.failed",
    "Critic failed",
    context_keys=("article_url",),
)

BASE_STATE: WriterCriticState = {
    "article_url": "https://example.com/article",
    "article_title": "Big news story",
    "article_content": "The article says this is huge.",
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
        graph.add_node(critic_node, retry_policy=FAST_LLM_RETRY, error_handler=_critic_error_handler)
        graph.add_edge(START, "critic_node")
        graph.add_edge("critic_node", END)
        return graph

    def test_successful_review(self, graph: StateGraph):
        """Reliability score is the mean of the four sub-scores; iterations increments."""

        parsed = CriticAgentResponseFormat(
            coherence_score=0.8,
            grammar_score=1.0,
            unambiguity_score=0.6,
            catchiness_score=0.4,
            corrections="Punch up the opening line.",
        )
        with patch(
            "nodes.writer_critic_graph.critic_node.node.call_agent",
            return_value=parsed,
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
        with patch("nodes.writer_critic_graph.critic_node.node.call_agent", return_value=parsed) as mock_call_agent:
            graph.compile().invoke(BASE_STATE)

        prompt_text = mock_call_agent.call_args.kwargs["prompt"]
        assert BASE_STATE["draft_script"] in prompt_text
        assert BASE_STATE["persona_language"] in prompt_text
        assert BASE_STATE["persona_style"] in prompt_text
        assert BASE_STATE["persona_tone"] in prompt_text

    def test_no_structured_response(self, graph: StateGraph):
        """Fatal error when agent returns no structured_response."""

        with patch(
            "nodes.writer_critic_graph.critic_node.node.call_agent",
            side_effect=AgentResponseError("Agent response did not include structured_response."),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["is_fatal_error"]
        assert result["error_message"] == (
            "Critic failed: AgentResponseError: Agent response did not include structured_response."
        )

    def test_agent_failure_returns_fatal_error(self, graph: StateGraph):
        """An exception from the LLM agent results in a fatal error state."""

        with patch(
            "nodes.writer_critic_graph.critic_node.node.call_agent",
            side_effect=RuntimeError("LLM unavailable"),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["is_fatal_error"]
        assert result["error_message"] == "Critic failed: RuntimeError: LLM unavailable"
