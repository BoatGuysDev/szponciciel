from langgraph.graph import END, START, StateGraph

from logging_config import get_logger
from nodes.caption_node.node import caption_node
from nodes.narrator_node.node import narrator_node
from nodes.select_background_node.node import select_background_node
from nodes.state import PersonaRunState, end_if_fatal
from nodes.tts_node.node import tts_node
from nodes.video_assembly_graph.graph import video_assembly_graph
from utils.agent_utils import LLM_RETRY
from utils.graph_utils import build_error_handler

log = get_logger(__name__)

_narrator_error_handler = build_error_handler(
    log,
    "narrator.failed",
    "Narration generation failed",
    context_keys=("run_id", "persona_id"),
)
_tts_error_handler = build_error_handler(
    log, "tts.failed", "TTS generation failed", context_keys=("run_id", "persona_id")
)
_background_error_handler = build_error_handler(
    log,
    "background.failed",
    "Background selection failed",
    context_keys=("run_id", "persona_id"),
)
_video_assembly_error_handler = build_error_handler(
    log,
    "video_assembly.failed",
    "Video assembly failed",
    context_keys=("run_id", "persona_id"),
)
_caption_error_handler = build_error_handler(
    log,
    "caption.failed",
    "Caption generation failed",
    context_keys=("run_id", "persona_id"),
)


def generate_tiktok_graph():
    graph = StateGraph(state_schema=PersonaRunState)

    graph.add_node(narrator_node, retry_policy=LLM_RETRY, error_handler=_narrator_error_handler)
    graph.add_node(tts_node, retry_policy=LLM_RETRY, error_handler=_tts_error_handler)
    graph.add_node(
        select_background_node,
        retry_policy=LLM_RETRY,
        error_handler=_background_error_handler,
    )
    graph.add_node(
        "video_assembly_subgraph",
        video_assembly_graph(),
        retry_policy=LLM_RETRY,
        error_handler=_video_assembly_error_handler,
    )
    graph.add_node(caption_node, retry_policy=LLM_RETRY, error_handler=_caption_error_handler)

    graph.add_edge(START, "narrator_node")
    graph.add_conditional_edges("narrator_node", end_if_fatal("tts_node"), ["tts_node", END])
    graph.add_conditional_edges(
        "tts_node",
        end_if_fatal("select_background_node"),
        ["select_background_node", END],
    )
    graph.add_conditional_edges(
        "select_background_node",
        end_if_fatal("video_assembly_subgraph"),
        ["video_assembly_subgraph", END],
    )
    graph.add_conditional_edges("video_assembly_subgraph", end_if_fatal("caption_node"), ["caption_node", END])
    graph.add_edge("caption_node", END)

    return graph.compile()
