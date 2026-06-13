from langgraph.graph import END, START, StateGraph

from logging_config import get_logger
from nodes.generate_tiktok_graph.graph import generate_tiktok_graph
from nodes.state import PersonaRunState, end_if_fatal
from nodes.upload_node.node import upload_node
from nodes.writer_critic_graph.graph import writer_critic_graph
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler

log = get_logger(__name__)

_writer_critic_error_handler = build_error_handler(
    log,
    "writer_critic.failed",
    "Writer/critic pipeline failed",
    context_keys=("run_id", "persona_id"),
)
_generate_tiktok_error_handler = build_error_handler(
    log,
    "generate_tiktok.failed",
    "TikTok generation pipeline failed",
    context_keys=("run_id", "persona_id"),
)
_upload_error_handler = build_error_handler(
    log,
    "upload.failed",
    "Upload failed",
    context_keys=("run_id", "persona_id"),
)


def persona_graph():
    graph = StateGraph(state_schema=PersonaRunState)

    graph.add_node(
        "writer_critic",
        writer_critic_graph,
        retry_policy=LLM_RETRY,
        error_handler=_writer_critic_error_handler,
    )
    graph.add_node(
        "generate_tiktok_subgraph",
        generate_tiktok_graph(),
        retry_policy=LLM_RETRY,
        error_handler=_generate_tiktok_error_handler,
    )
    graph.add_node(upload_node, retry_policy=LLM_RETRY, error_handler=_upload_error_handler)

    graph.add_edge(START, "writer_critic")
    graph.add_conditional_edges(
        "writer_critic",
        end_if_fatal("generate_tiktok_subgraph"),
        ["generate_tiktok_subgraph", END],
    )
    graph.add_conditional_edges("generate_tiktok_subgraph", end_if_fatal("upload_node"), ["upload_node", END])
    graph.add_edge("upload_node", END)

    return graph.compile()
