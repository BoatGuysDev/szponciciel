import json

import pytest
from unittest.mock import patch, MagicMock
from langgraph.graph import StateGraph, START, END
from sqlmodel import Session
from sqlalchemy import Engine

from src.nodes import caption_node, PersonaRunState
from src.models import Persona
from src.nodes.caption_node.response_format import CaptionAgentResponseFormat

from .base_test_class import BaseTestClass


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

    def _mock_agent(
        self, caption: str, hashtags: list[str], formatted_output: bool = True
    ) -> MagicMock:
        structured_response = CaptionAgentResponseFormat(
            caption=caption, hashtags=hashtags
        )
        mock = MagicMock()
        mock.invoke.return_value = (
            {"structured_response": structured_response}
            if formatted_output
            else {
                "messages": [
                    MagicMock(
                        content=json.dumps({"caption": caption, "hashtags": hashtags})
                    )
                ]
            }
        )
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

    def test_successful_caption_structured(self, graph: StateGraph, engine: Engine):
        """Mocked LLM returns valid structured response; result contains tiktok_caption and hashtags."""

        expected_caption = "Breaking news just dropped."
        expected_hashtags = ["#news", "#breaking", "#today", "#viral", "#trending"]
        mock_agent = self._mock_agent(
            expected_caption, expected_hashtags, formatted_output=True
        )

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with (
                patch("src.nodes.caption_node.node.ChatGoogleGenerativeAI"),
                patch(
                    "src.nodes.caption_node.node.create_agent", return_value=mock_agent
                ),
            ):
                result = graph.compile().invoke(
                    {"persona_id": "1", "narration": "Some narration text."}
                )

        assert result.get("is_fatal_error") is None
        assert result.get("error_message") is None
        assert result["tiktok_caption"] == expected_caption
        assert result["hashtags"] == expected_hashtags

    def test_successful_caption_json(self, graph: StateGraph, engine: Engine):
        """Mocked LLM returns valid JSON; result contains tiktok_caption and hashtags."""

        expected_caption = "Breaking news just dropped."
        expected_hashtags = ["#news", "#breaking", "#today", "#viral", "#trending"]
        mock_agent = self._mock_agent(
            expected_caption, expected_hashtags, formatted_output=False
        )

        with Session(engine) as session:
            session.add(self._make_persona())
            session.commit()

            with (
                patch("src.nodes.caption_node.node.ChatGoogleGenerativeAI"),
                patch(
                    "src.nodes.caption_node.node.create_agent", return_value=mock_agent
                ),
            ):
                result = graph.compile().invoke(
                    {"persona_id": "1", "narration": "Some narration text."}
                )

        assert result.get("is_fatal_error") is None
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
                patch("src.nodes.caption_node.node.ChatGoogleGenerativeAI"),
                patch(
                    "src.nodes.caption_node.node.create_agent", return_value=mock_agent
                ),
            ):
                result = graph.compile().invoke(
                    {"persona_id": "1", "narration": "Some narration text."}
                )

        assert result.get("is_fatal_error") is None
        assert len(result["tiktok_caption"]) == 2200
