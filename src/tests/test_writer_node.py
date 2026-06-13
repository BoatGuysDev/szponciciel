from unittest.mock import patch

import pytest
from langgraph.graph import END, START, StateGraph

from config import settings
from logging_config import get_logger
from nodes.writer_critic_graph.state import WriterCriticState
from nodes.writer_critic_graph.writer_node.node import writer_node
from nodes.writer_critic_graph.writer_node.response_format import WriterAgentResponseFormat
from tests.base_test_class import BaseTestClass
from utils.agent_utils import LLM_RETRY, AgentResponseError
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_writer_error_handler = build_error_handler(
    log,
    "writer.failed",
    "Writer failed",
    context_keys=("article_url",),
)

BASE_STATE: WriterCriticState = {
    "article_url": "https://example.com/article",
    "article_title": "Big news story",
    "persona_language": "en",
    "persona_style": "dramatic",
    "persona_tone": "serious",
    "real_news_ratio": 0.8,
    "draft_script": None,
    "review": None,
    "iterations": 0,
    "is_fatal_error": False,
    "error_message": None,
}


class TestWriterNode(BaseTestClass):
    """Tests for the writer node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=WriterCriticState)
        graph.add_node(writer_node, retry_policy=LLM_RETRY, error_handler=_writer_error_handler)
        graph.add_edge(START, "writer_node")
        graph.add_edge("writer_node", END)
        return graph

    def test_successful_first_iteration(self, graph: StateGraph):
        """Script is set and iterations increments to 1 on a clean first pass."""

        expected_script = "Breaking news! This is huge."
        with (
            patch(
                "nodes.writer_critic_graph.writer_node.node.call_agent",
                return_value=WriterAgentResponseFormat(draft_script=expected_script),
            ),
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
            "review": {
                "coherence_score": 0.7,
                "grammar_score": 0.8,
                "unambiguity_score": 0.6,
                "catchiness_score": 0.5,
                "corrections": corrections,
            },
            "iterations": 1,
        }
        with patch(
            "nodes.writer_critic_graph.writer_node.node.call_agent",
            return_value=WriterAgentResponseFormat(draft_script="Revised script here."),
        ) as mock_call_agent:
            graph.compile().invoke(state)

        prompt_text = mock_call_agent.call_args.kwargs["prompt"]
        assert draft_script in prompt_text
        assert corrections in prompt_text

    def test_script_truncated_to_max_length(self, graph: StateGraph):
        """Output longer than max_script_length is truncated."""

        long_content = "x" * (settings.max_script_length + 1000)
        with (
            patch(
                "nodes.writer_critic_graph.writer_node.node.call_agent",
                return_value=WriterAgentResponseFormat(draft_script=long_content),
            ),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert len(result["draft_script"]) == settings.max_script_length
        assert result["draft_script"].endswith("...")

    def test_agent_failure_returns_fatal_error(self, graph: StateGraph):
        """An exception from the LLM agent results in a fatal error state."""

        with (
            patch(
                "nodes.writer_critic_graph.writer_node.node.call_agent",
                side_effect=AgentResponseError("Agent response did not include structured_response."),
            ),
        ):
            result = graph.compile().invoke(BASE_STATE)

        assert result["is_fatal_error"]
        assert result["error_message"] == (
            "Writer failed: AgentResponseError: Agent response did not include structured_response."
        )
