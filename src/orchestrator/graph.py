from langgraph.graph import END, START, StateGraph

from logging_config import get_logger, setup_logging
from nodes.researcher_node.node import researcher_node
from orchestrator.finalize_node import finalize_node
from orchestrator.intake_node import intake_node
from orchestrator.run_personas_node import run_personas_node
from orchestrator.state import OrchestratorState
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler, instrument_node

log = get_logger(__name__)

_intake_error_handler = build_error_handler(log, "intake.failed", "Intake failed", context_keys=("run_id",))
_research_error_handler = build_error_handler(log, "research.failed", "Research failed", context_keys=("run_id",))
_run_personas_error_handler = build_error_handler(
    log,
    "run_personas.failed",
    "Persona pipeline failed",
    context_keys=("run_id",),
)
_finalize_error_handler = build_error_handler(log, "finalize.failed", "Finalize failed", context_keys=("run_id",))


def _after_intake(state: OrchestratorState) -> str:
    return "finalize" if state.get("is_fatal_error") else "research"


def _after_research(state: OrchestratorState) -> str:
    return "finalize" if state.get("is_fatal_error") else "run_personas"


def build_orchestrator():
    setup_logging()
    graph = StateGraph(OrchestratorState)

    graph.add_node(
        "intake", instrument_node("intake", intake_node), retry_policy=LLM_RETRY, error_handler=_intake_error_handler
    )
    graph.add_node(
        "research",
        instrument_node("research", researcher_node),
        retry_policy=LLM_RETRY,
        error_handler=_research_error_handler,
    )
    graph.add_node(
        "run_personas",
        instrument_node("run_personas", run_personas_node),
        retry_policy=LLM_RETRY,
        error_handler=_run_personas_error_handler,
    )
    graph.add_node(
        "finalize",
        finalize_node,
        retry_policy=LLM_RETRY,
        error_handler=_finalize_error_handler,
    )

    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", _after_intake, ["research", "finalize"])
    graph.add_conditional_edges("research", _after_research, ["run_personas", "finalize"])
    graph.add_edge("run_personas", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


graph = build_orchestrator()
