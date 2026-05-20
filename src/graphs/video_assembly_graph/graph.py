from langgraph.graph import END, START, StateGraph
from sqlmodel import Session, select

from db import get_engine
from models import Persona
from graphs.caption_graph.graph import build_caption_graph
from nodes.compose_node.simple_node import compose_simple_node
from nodes.state import PersonaRunState


def _route_captions(state: PersonaRunState) -> str:
    pid = state.get("persona_id")
    if not pid:
        return "compose_simple_node"
    with Session(get_engine()) as session:
        persona = session.exec(select(Persona).where(Persona.id == pid)).first()
    return "caption" if (persona and persona.show_captions) else "compose_simple_node"


def build_video_assembly_graph():
    graph = StateGraph(state_schema=PersonaRunState)
    graph.add_node("caption", build_caption_graph())
    graph.add_node(compose_simple_node)
    graph.add_conditional_edges(START, _route_captions)
    graph.add_edge("caption", END)
    graph.add_edge("compose_simple_node", END)
    return graph.compile()
