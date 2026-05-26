from langgraph.graph import END, START, StateGraph
from sqlmodel import Session, select

from db import get_engine
from models import Persona

from nodes.video_assembly_graph.compose_node.simple_node import compose_simple_node
from nodes.video_assembly_graph.align_node.node import align_node
from nodes.video_assembly_graph.compose_node.node import compose_node
from nodes.state import PersonaRunState


def _router(state: PersonaRunState) -> str:
    pid = state.get("persona_id")
    if not pid:
        return "compose_simple_node"
    with Session(get_engine()) as session:
        persona = session.exec(select(Persona).where(Persona.id == pid)).first()
    return (
        "align_node" if (persona and persona.show_captions) else "compose_simple_node"
    )


def video_assembly_graph():
    graph = StateGraph(state_schema=PersonaRunState)

    graph.add_node(align_node)
    graph.add_node(compose_node)
    graph.add_node(compose_simple_node)

    graph.add_conditional_edges(START, _router)
    graph.add_edge("compose_simple_node", END)

    graph.add_edge("align_node", "compose_node")
    graph.add_edge("compose_node", END)

    return graph.compile()
