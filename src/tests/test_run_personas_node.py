from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session, select

from models import Persona, PersonaRun, Run
from orchestrator.run_personas_node import run_personas_node
from orchestrator.state import OrchestratorState
from tests.base_test_class import BaseTestClass


def _seed(engine: Engine) -> str:
    with Session(engine) as session:
        run = Run(status="running")
        session.add(run)
        for pid in ("p1", "p2"):
            session.add(
                Persona(
                    id=pid,
                    tiktok_account_id=f"acct-{pid}",
                    language="English",
                    style="dramatic",
                    tone="serious",
                )
            )
        session.commit()
        session.refresh(run)
        return run.id


class TestRunPersonasNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=OrchestratorState)
        graph.add_node(run_personas_node)
        graph.add_edge(START, "run_personas_node")
        graph.add_edge("run_personas_node", END)
        return graph

    def test_runs_each_persona_and_records_outcomes(self, graph: StateGraph, engine: Engine):
        run_id = _seed(engine)

        mock_compiled = MagicMock()
        mock_compiled.invoke.side_effect = [
            {
                "narration": "n",
                "tiktok_caption": "c",
                "output_video_path": "out.mp4",
                "tiktok_post_id": "post-123",
            },
            {"is_fatal_error": True, "error_message": "boom"},
        ]

        with patch("orchestrator.run_personas_node.persona_graph", return_value=mock_compiled):
            result = graph.compile().invoke({"run_id": run_id, "persona_ids": ["p1", "p2"]})

        outcomes = {o["persona_id"]: o for o in result["outcomes"]}
        assert outcomes["p1"]["status"] == "completed"
        assert outcomes["p1"]["tiktok_post_id"] == "post-123"
        assert outcomes["p2"]["status"] == "failed"
        assert outcomes["p2"]["error_message"] == "boom"

        # both personas processed despite p2 failing
        assert mock_compiled.invoke.call_count == 2
        first_state = mock_compiled.invoke.call_args_list[0].args[0]
        assert first_state["story_mode"] in {"real_news", "fictional_news"}
        assert "content_type" not in first_state

        with Session(engine) as session:
            rows = session.exec(select(PersonaRun).where(PersonaRun.run_id == run_id)).all()
            by_persona = {r.persona_id: r for r in rows}
            assert by_persona["p1"].status == "completed"
            assert by_persona["p1"].tiktok_post_id == "post-123"
            assert by_persona["p1"].story_mode in {"real_news", "fictional_news"}
            assert by_persona["p2"].status == "failed"
            assert by_persona["p2"].error_message == "boom"

    def test_pipeline_crash_is_caught_and_marked_failed(self, graph: StateGraph, engine: Engine):
        run_id = _seed(engine)

        mock_compiled = MagicMock()
        mock_compiled.invoke.side_effect = RuntimeError("kaboom")

        with patch("orchestrator.run_personas_node.persona_graph", return_value=mock_compiled):
            result = graph.compile().invoke({"run_id": run_id, "persona_ids": ["p1"]})

        assert result["outcomes"][0]["status"] == "failed"
        assert "kaboom" in result["outcomes"][0]["error_message"]

    def test_missing_persona_is_marked_failed_and_skipped(self, graph: StateGraph, engine: Engine):
        run_id = _seed(engine)
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = {"tiktok_post_id": "ok"}

        with patch("orchestrator.run_personas_node.persona_graph", return_value=mock_compiled):
            result = graph.compile().invoke({"run_id": run_id, "persona_ids": ["p1", "missing-persona"]})

        outcomes = {o["persona_id"]: o for o in result["outcomes"]}
        assert outcomes["missing-persona"]["status"] == "failed"
        assert outcomes["missing-persona"]["error_message"] == "Persona not found."
        assert mock_compiled.invoke.call_count == 1

        with Session(engine) as session:
            missing_rows = session.exec(select(PersonaRun).where(PersonaRun.persona_id == "missing-persona")).all()
            assert missing_rows == []
