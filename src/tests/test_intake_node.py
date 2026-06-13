from unittest.mock import patch

import pytest
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session

from logging_config import get_logger
from models import Persona, Run
from orchestrator.intake_node import intake_node
from orchestrator.state import OrchestratorState
from tests.base_test_class import BaseTestClass
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler

log = get_logger(__name__)
_intake_error_handler = build_error_handler(
    log,
    "intake.failed",
    "Intake failed",
    context_keys=("run_id",),
)


def _seed_persona(engine: Engine, persona_id: str, is_active: bool) -> None:
    with Session(engine) as session:
        session.add(
            Persona(
                id=persona_id,
                tiktok_account_id=f"acct-{persona_id}",
                language="English",
                style="dramatic",
                tone="serious",
                is_active=is_active,
            )
        )
        session.commit()


class TestIntakeNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=OrchestratorState)
        graph.add_node(intake_node, retry_policy=LLM_RETRY, error_handler=_intake_error_handler)
        graph.add_edge(START, "intake_node")
        graph.add_edge("intake_node", END)
        return graph

    def test_creates_run_and_selects_active_personas(self, graph: StateGraph, engine: Engine):
        _seed_persona(engine, "active", is_active=True)
        _seed_persona(engine, "inactive", is_active=False)

        with patch("orchestrator.intake_node._extract_topic", return_value="USA-Iran conflict"):
            result = graph.compile().invoke({"prompt": "post videos about the conflict"})

        assert "is_fatal_error" not in result
        assert result["topic"] == "USA-Iran conflict"
        assert result["persona_ids"] == ["active"]

        with Session(engine) as session:
            run = session.get(Run, result["run_id"])
            assert run is not None
            assert run.status == "running"

    def test_generic_prompt_yields_no_topic_and_skips_llm(self, graph: StateGraph, engine: Engine):
        _seed_persona(engine, "p1", is_active=True)

        with patch("orchestrator.intake_node._extract_topic") as mock_extract:
            result = graph.compile().invoke({"prompt": "   "})

        assert result["topic"] is None
        mock_extract.assert_not_called()

    def test_no_active_personas_returns_fatal(self, graph: StateGraph, engine: Engine):
        _seed_persona(engine, "inactive", is_active=False)

        with patch("orchestrator.intake_node._extract_topic", return_value=None):
            result = graph.compile().invoke({"prompt": "anything"})

        assert result["is_fatal_error"] is True
        assert "No active personas" in result["error_message"]

    def test_topic_extraction_failure_returns_fatal(self, graph: StateGraph, engine: Engine):
        _seed_persona(engine, "p1", is_active=True)

        with patch(
            "orchestrator.intake_node._extract_topic",
            side_effect=RuntimeError("LLM down"),
        ):
            result = graph.compile().invoke({"prompt": "post about X"})

        assert result["is_fatal_error"] is True
        assert result["error_message"] == "Intake failed: RuntimeError: LLM down"
