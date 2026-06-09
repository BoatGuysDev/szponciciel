from langgraph.graph import END, START, StateGraph

from logging_config import setup_logging
from nodes.researcher_node.node import researcher_node
from orchestrator.finalize_node import finalize_node
from orchestrator.intake_node import intake_node
from orchestrator.run_personas_node import run_personas_node
from orchestrator.state import OrchestratorState


def _after_intake(state: OrchestratorState) -> str:
    return "finalize" if state.get("is_fatal_error") else "research"


def _after_research(state: OrchestratorState) -> str:
    return "finalize" if state.get("is_fatal_error") else "run_personas"


def build_orchestrator():
    setup_logging()
    graph = StateGraph(OrchestratorState)

    graph.add_node("intake", intake_node)
    graph.add_node("research", researcher_node)
    graph.add_node("run_personas", run_personas_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", _after_intake, ["research", "finalize"])
    graph.add_conditional_edges("research", _after_research, ["run_personas", "finalize"])
    graph.add_edge("run_personas", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


graph = build_orchestrator()
