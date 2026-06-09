from langgraph.graph import END, START, StateGraph

from nodes.caption_node.node import caption_node
from nodes.narrator_node.node import narrator_node
from nodes.select_background_node.node import select_background_node
from nodes.state import PersonaRunState
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
    graph.add_edge("narrator_node", "tts_node")
    graph.add_edge("tts_node", "select_background_node")
    graph.add_edge("select_background_node", "video_assembly_subgraph")
    graph.add_edge("video_assembly_subgraph", "caption_node")
    graph.add_edge("caption_node", END)

    return graph.compile()
