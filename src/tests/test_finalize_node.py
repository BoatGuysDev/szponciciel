import pytest
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session

from models import Run
from orchestrator.finalize_node import finalize_node
from orchestrator.state import OrchestratorState
from tests.base_test_class import BaseTestClass


def _seed_run(engine: Engine) -> str:
    with Session(engine) as session:
        run = Run(status="running")
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id


class TestFinalizeNode(BaseTestClass):
    @pytest.fixture(name="graph")
    def create_graph(self) -> StateGraph:
        graph = StateGraph(state_schema=OrchestratorState)
        graph.add_node(finalize_node)
        graph.add_edge(START, "finalize_node")
        graph.add_edge("finalize_node", END)
        return graph

    def _status(self, engine: Engine, run_id: str) -> str:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.completed_at is not None
            return run.status

    def test_marks_completed(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        graph.compile().invoke({"run_id": run_id, "outcomes": [{"status": "completed"}]})
        assert self._status(engine, run_id) == "completed"

    def test_marks_failed_on_fatal_error(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        graph.compile().invoke({"run_id": run_id, "is_fatal_error": True})
        assert self._status(engine, run_id) == "failed"

    def test_marks_failed_when_all_personas_failed(self, graph: StateGraph, engine: Engine):
        run_id = _seed_run(engine)
        graph.compile().invoke(
            {
                "run_id": run_id,
                "outcomes": [{"status": "failed"}, {"status": "failed"}],
            }
        )
        assert self._status(engine, run_id) == "failed"
