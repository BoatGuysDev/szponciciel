from langgraph.graph import END, START, StateGraph

from nodes.narrator_node import narrator_node
from nodes.state import PersonaRunState
from nodes.tts_node import tts_node
from nodes.video_assembly_graph.graph import video_assembly_graph


def persona_graph():
    graph = StateGraph(state_schema=PersonaRunState)

    graph.add_node(narrator_node)
    graph.add_node(tts_node)
    graph.add_node("video_assembly_subgraph", video_assembly_graph())

    graph.add_edge(START, "narrator_node")
    graph.add_edge("narrator_node", "tts_node")
    graph.add_edge("tts_node", "video_assembly_subgraph")
    graph.add_edge("video_assembly_subgraph", END)

    return graph.compile()
