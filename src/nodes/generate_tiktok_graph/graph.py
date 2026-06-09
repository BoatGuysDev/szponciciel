from langgraph.graph import END, START, StateGraph

from nodes.caption_node.node import caption_node
from nodes.narrator_node.node import narrator_node
from nodes.select_background_node.node import select_background_node
from nodes.state import PersonaRunState, end_if_fatal
from nodes.tts_node.node import tts_node
from nodes.video_assembly_graph.graph import video_assembly_graph


def generate_tiktok_graph():
    graph = StateGraph(state_schema=PersonaRunState)

    graph.add_node(narrator_node)
    graph.add_node(tts_node)
    graph.add_node(select_background_node)
    graph.add_node("video_assembly_subgraph", video_assembly_graph())
    graph.add_node(caption_node)

    graph.add_edge(START, "narrator_node")
    graph.add_conditional_edges(
        "narrator_node", end_if_fatal("tts_node"), ["tts_node", END]
    )
    graph.add_conditional_edges(
        "tts_node", end_if_fatal("select_background_node"), ["select_background_node", END]
    )
    graph.add_conditional_edges(
        "select_background_node",
        end_if_fatal("video_assembly_subgraph"),
        ["video_assembly_subgraph", END],
    )
    graph.add_conditional_edges(
        "video_assembly_subgraph", end_if_fatal("caption_node"), ["caption_node", END]
    )
    graph.add_edge("caption_node", END)

    return graph.compile()
