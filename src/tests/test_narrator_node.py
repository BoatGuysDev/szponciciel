import pytest
from unittest.mock import patch, MagicMock
from langgraph.graph import StateGraph, START, END
from sqlmodel import Session
from sqlalchemy import Engine

from src.nodes import narrator_node, PersonaRunState
from src.models import Run, Persona

from .base_test_class import BaseTestClass


class TestNarratorNode(BaseTestClass):
    """Tests for the narrator node."""

    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=PersonaRunState)
        graph.add_node(narrator_node)
        graph.add_edge(START, "narrator_node")
        graph.add_edge("narrator_node", END)

        return graph

    def test_missing_run(self, graph: StateGraph):
        """Test that the narrator node returns a fatal error if the run_id is missing."""

        result = graph.compile().invoke(
            {
                "run_id": "1",
            }
        )

        assert result["is_fatal_error"]
        assert result["error_message"] == "Run with id 1 not found."

    def test_missing_persona(self, graph: StateGraph, engine: Engine):
        """Test that the narrator node returns a fatal error if the persona_id is missing."""

        with Session(engine) as session:
            run = Run(status="pending")
            session.add(run)
            session.commit()

            result = graph.compile().invoke(
                {
                    "run_id": run.id,
                    "persona_id": "1",
                }
            )

        assert result["is_fatal_error"]
        assert result["error_message"] == "Persona with id 1 not found."

    def test_missing_base_script(self, graph: StateGraph, engine: Engine):
        """Test that the narrator node returns a fatal error if the base_script is missing."""

        with Session(engine) as session:
            run = Run(status="pending", base_script=None)
            persona = Persona(
                id="1",
                tiktok_account_id="tiktok-news",
                language="English",
                style="dramatic",
                tone="serious",
            )

            session.add(run)
            session.add(persona)
            session.commit()

            result = graph.compile().invoke(
                {
                    "run_id": run.id,
                    "persona_id": persona.id,
                }
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"]
            == "Missing required information to create narration."
        )

    def test_missing_narration_language(self, graph: StateGraph, engine: Engine):
        """Test that the narrator node returns a fatal error if the narration language is missing."""

        with Session(engine) as session:
            run = Run(status="pending", base_script="This is a test script.")
            persona = Persona(
                id="1",
                tiktok_account_id="tiktok-news",
                language=None,
                style="dramatic",
                tone="serious",
            )

            session.add(run)
            session.add(persona)
            session.commit()

            result = graph.compile().invoke(
                {
                    "run_id": run.id,
                    "persona_id": persona.id,
                }
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"]
            == "Missing required information to create narration."
        )

    def test_missing_narration_style(self, graph: StateGraph, engine: Engine):
        """Test that the narrator node returns a fatal error if the narration style is missing."""

        with Session(engine) as session:
            run = Run(status="pending", base_script="This is a test script.")
            persona = Persona(
                id="1",
                tiktok_account_id="tiktok-news",
                language="English",
                style=None,
                tone="serious",
            )

            session.add(run)
            session.add(persona)
            session.commit()

            result = graph.compile().invoke(
                {
                    "run_id": run.id,
                    "persona_id": persona.id,
                }
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"]
            == "Missing required information to create narration."
        )

    def test_missing_narration_tone(self, graph: StateGraph, engine: Engine):
        """Test that the narrator node returns a fatal error if the narration tone is missing."""

        with Session(engine) as session:
            run = Run(status="pending", base_script="This is a test script.")
            persona = Persona(
                id="1",
                tiktok_account_id="tiktok-news",
                language="English",
                style="dramatic",
                tone=None,
            )

            session.add(run)
            session.add(persona)
            session.commit()

            result = graph.compile().invoke(
                {
                    "run_id": run.id,
                    "persona_id": persona.id,
                }
            )

        assert result["is_fatal_error"]
        assert (
            result["error_message"]
            == "Missing required information to create narration."
        )

    def test_successful_narration(self, graph: StateGraph, engine: Engine):
        """Test that the narrator node returns a narration when all required data is present."""

        expected_narration = "This is the generated narration."

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content=expected_narration)]
        }

        with Session(engine) as session:
            run = Run(status="pending", base_script="This is a test script.")
            persona = Persona(
                id="1",
                tiktok_account_id="tiktok-news",
                language="English",
                style="dramatic",
                tone="serious",
            )

            session.add(run)
            session.add(persona)
            session.commit()

            with (
                patch("src.nodes.narrator_node.node.ChatGoogleGenerativeAI"),
                patch(
                    "src.nodes.narrator_node.node.create_agent", return_value=mock_agent
                ),
            ):
                result = graph.compile().invoke(
                    {
                        "run_id": run.id,
                        "persona_id": persona.id,
                    }
                )

        assert result.get("is_fatal_error", None) is None
        assert result.get("error_message", None) is None
        assert result["narration"] == expected_narration
