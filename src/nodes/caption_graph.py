from langgraph.graph import END, START, StateGraph

from nodes.align_node import align_node
from nodes.compose_node import compose_node
from nodes.state import PersonaRunState


def build_caption_graph():
    graph = StateGraph(state_schema=PersonaRunState)
    graph.add_node(align_node)
    graph.add_node(compose_node)
    graph.add_edge(START, "align_node")
    graph.add_edge("align_node", "compose_node")
    graph.add_edge("compose_node", END)
    return graph.compile()
