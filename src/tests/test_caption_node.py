from unittest.mock import patch

import pytest
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session

from logging_config import get_logger
from models import Persona
from nodes import PersonaRunState, caption_node
from nodes.caption_node.response_format import CaptionAgentResponseFormat
from tests.base_test_class import BaseTestClass
from tests.retry_policy import FAST_LLM_RETRY
from utils.agent_utils import AgentResponseError
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_caption_error_handler = build_error_handler(
    log,
    "caption.failed",
    "Caption generation failed",
    context_keys=("persona_id",),
)


class TestCaptionNode(BaseTestClass):
    """Tests for the caption node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(caption_node, retry_policy=FAST_LLM_RETRY, error_handler=_caption_error_handler)
        graph.add_edge(START, "caption_node")
        graph.add_edge("caption_node", END)

        return graph

    def _make_persona(self, **kwargs) -> Persona:
        defaults = {
            "id": "1",
            "tiktok_account_id": "tiktok-news",
            "language": "en",
            "style": "dramatic",
            "tone": "serious",
        }
        defaults.update(kwargs)
        return Persona(**defaults)

    def test_missing_persona(self, graph: StateGraph):
        """Fatal error when persona is not in DB."""

        result = graph.compile().invoke(
            {
                "persona_id": "nonexistent",
                "narration": "Some narration.",
            }
        )

        assert result["is_fatal_error"]
        assert result["error_message"] == "Persona with id nonexistent not found."

    def test_missing_narration(self, graph: StateGraph, engine: Engine):
        """Fatal error when narration is absent from state."""

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            result = graph.compile().invoke({"persona_id": "1"})

        assert result["is_fatal_error"]
        assert result["error_message"] == "Missing required information to create caption."

    def test_missing_language(self, graph: StateGraph, engine: Engine):
        """Fatal error when persona.language is None."""

        with Session(engine) as session:
            session.add(self._make_persona(language=None))
            session.commit()

            result = graph.compile().invoke({"persona_id": "1", "narration": "Some narration."})

        assert result["is_fatal_error"]
        assert result["error_message"] == "Missing required information to create caption."

    def test_missing_style(self, graph: StateGraph, engine: Engine):
        """Fatal error when persona.style is None."""

        with Session(engine) as session:
            session.add(self._make_persona(style=None))
            session.commit()

            result = graph.compile().invoke({"persona_id": "1", "narration": "Some narration."})

        assert result["is_fatal_error"]
        assert result["error_message"] == "Missing required information to create caption."

    def test_missing_tone(self, graph: StateGraph, engine: Engine):
        """Fatal error when persona.tone is None."""

        with Session(engine) as session:
            session.add(self._make_persona(tone=None))
            session.commit()

            result = graph.compile().invoke({"persona_id": "1", "narration": "Some narration."})

        assert result["is_fatal_error"]
        assert result["error_message"] == "Missing required information to create caption."

    def test_no_structured_response(self, graph: StateGraph, engine: Engine):
        """Fatal error when agent returns no structured_response."""

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with patch(
                "nodes.caption_node.node.call_agent",
                side_effect=AgentResponseError("Agent response did not include structured_response."),
            ):
                result = graph.compile().invoke({"persona_id": "1", "narration": "Some narration text."})

        assert result["is_fatal_error"]
        assert (
            result["error_message"]
            == "Caption generation failed: AgentResponseError: Agent response did not include structured_response."
        )

    def test_successful_caption_structured(self, graph: StateGraph, engine: Engine):
        """Mocked LLM returns valid structured response; result contains tiktok_caption and hashtags."""

        expected_caption = "Breaking news just dropped."
        expected_hashtags = ["#news", "#breaking", "#today", "#viral", "#trending"]
        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with patch(
                "nodes.caption_node.node.call_agent",
                return_value=CaptionAgentResponseFormat(
                    caption=expected_caption,
                    hashtags=expected_hashtags,
                    diagnostic_reasoning="Caption follows the narration.",
                ),
            ):
                result = graph.compile().invoke({"persona_id": "1", "narration": "Some narration text."})

        assert result.get("is_fatal_error") is False
        assert result.get("error_message") is None
        assert result["tiktok_caption"] == expected_caption
        assert result["hashtags"] == expected_hashtags

    def test_caption_truncated(self, graph: StateGraph, engine: Engine):
        """Caption longer than 2200 chars is truncated to 2200."""

        long_caption = "x" * 3000
        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with patch(
                "nodes.caption_node.node.call_agent",
                return_value=CaptionAgentResponseFormat(
                    caption=long_caption,
                    hashtags=["#news"] * 5,
                    diagnostic_reasoning="Caption follows the narration.",
                ),
            ):
                result = graph.compile().invoke({"persona_id": "1", "narration": "Some narration text."})

        assert result.get("is_fatal_error") is False
        assert result.get("error_message") is None
        assert len(result["tiktok_caption"]) == 2200
