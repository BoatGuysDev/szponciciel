from langgraph.graph import END, START, StateGraph

from nodes.generate_tiktok_graph.graph import generate_tiktok_graph
from nodes.state import PersonaRunState
from nodes.upload_node.node import upload_node


def persona_graph():
    graph = StateGraph(state_schema=PersonaRunState)

    graph.add_node("generate_tiktok_subgraph", generate_tiktok_graph())
    graph.add_node(upload_node)

    graph.add_edge(START, "generate_tiktok_subgraph")
    graph.add_edge("generate_tiktok_subgraph", "upload_node")
    graph.add_edge("upload_node", END)

    return graph.compile()
