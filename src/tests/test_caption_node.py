import pytest
from unittest.mock import patch, MagicMock
from langgraph.graph import StateGraph, START, END
from sqlmodel import Session
from sqlalchemy import Engine

from nodes import caption_node, PersonaRunState
from models import Persona
from nodes.caption_node.response_format import CaptionAgentResponseFormat

from tests.base_test_class import BaseTestClass


class TestCaptionNode(BaseTestClass):
    """Tests for the caption node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(caption_node)
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

    def _mock_agent(self, caption: str, hashtags: list[str]) -> MagicMock:
        mock = MagicMock()
        mock.invoke.return_value = {
            "structured_response": CaptionAgentResponseFormat(
                caption=caption, hashtags=hashtags
            )
        }
        return mock

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
        assert (
            result["error_message"] == "Missing required information to create caption."
        )

    def test_missing_language(self, graph: StateGraph, engine: Engine):
        """Fatal error when persona.language is None."""

        with Session(engine) as session:
            session.add(self._make_persona(language=None))
            session.commit()

            result = graph.compile().invoke(
                {"persona_id": "1", "narration": "Some narration."}
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"] == "Missing required information to create caption."
        )

    def test_missing_style(self, graph: StateGraph, engine: Engine):
        """Fatal error when persona.style is None."""

        with Session(engine) as session:
            session.add(self._make_persona(style=None))
            session.commit()

            result = graph.compile().invoke(
                {"persona_id": "1", "narration": "Some narration."}
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"] == "Missing required information to create caption."
        )

    def test_missing_tone(self, graph: StateGraph, engine: Engine):
        """Fatal error when persona.tone is None."""

        with Session(engine) as session:
            session.add(self._make_persona(tone=None))
            session.commit()

            result = graph.compile().invoke(
                {"persona_id": "1", "narration": "Some narration."}
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"] == "Missing required information to create caption."
        )

    def test_no_structured_response(self, graph: StateGraph, engine: Engine):
        """Fatal error when agent returns no structured_response."""

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {}

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with (
                patch("nodes.caption_node.node.ChatGoogleGenerativeAI"),
                patch("nodes.caption_node.node.create_agent", return_value=mock_agent),
            ):
                result = graph.compile().invoke(
                    {"persona_id": "1", "narration": "Some narration text."}
                )

        assert result["is_fatal_error"]
        assert result["error_message"] == "Failed to parse agent response."

    def test_successful_caption_structured(self, graph: StateGraph, engine: Engine):
        """Mocked LLM returns valid structured response; result contains tiktok_caption and hashtags."""

        expected_caption = "Breaking news just dropped."
        expected_hashtags = ["#news", "#breaking", "#today", "#viral", "#trending"]
        mock_agent = self._mock_agent(expected_caption, expected_hashtags)

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with (
                patch("nodes.caption_node.node.ChatGoogleGenerativeAI"),
                patch("nodes.caption_node.node.create_agent", return_value=mock_agent),
            ):
                result = graph.compile().invoke(
                    {"persona_id": "1", "narration": "Some narration text."}
                )

        assert result.get("is_fatal_error") is False
        assert result.get("error_message") is None
        assert result["tiktok_caption"] == expected_caption
        assert result["hashtags"] == expected_hashtags

    def test_caption_truncated(self, graph: StateGraph, engine: Engine):
        """Caption longer than 2200 chars is truncated to 2200."""

        long_caption = "x" * 3000
        mock_agent = self._mock_agent(long_caption, ["#news"] * 5)

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with (
                patch("nodes.caption_node.node.ChatGoogleGenerativeAI"),
                patch("nodes.caption_node.node.create_agent", return_value=mock_agent),
            ):
                result = graph.compile().invoke(
                    {"persona_id": "1", "narration": "Some narration text."}
                )

        assert result.get("is_fatal_error") is False
        assert result.get("error_message") is None
        assert len(result["tiktok_caption"]) == 2200
