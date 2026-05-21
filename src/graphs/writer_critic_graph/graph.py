from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START, END
from sqlmodel import select, Session, update

from config import settings
from db import get_engine
from models import Run, Persona

from nodes.state import PersonaRunState
from graphs.writer_critic_graph.state import WriterCriticState
# from nodes.writer_node.node import writer_node
# from nodes.critic_node.node import critic_node


class WriterCriticResult(TypedDict, total=False):
    is_fatal_error: bool
    error_message: str | None


def _build_graph():
    graph_builder = StateGraph(WriterCriticState)

    # graph_builder.add_node(writer_node)
    # graph_builder.add_node(critic_node)

    graph_builder.add_edge(START, "writer_node")
    graph_builder.add_edge("writer_node", "critic_node")
    graph_builder.add_edge("critic_node", _router)

    return graph_builder.compile()


def _router(state: WriterCriticState) -> str:
    if (
        state["reliability_score"] >= settings.script_reliability_threshold
        or state["iterations"] == settings.writer_critic_max_iters
        or state["is_fatal_error"]
    ):
        return END
    else:
        return "writer_node"


def writer_critic_graph(state: PersonaRunState) -> WriterCriticResult:
    with Session(get_engine()) as session:
        run = session.exec(select(Run).where(Run.id == state["run_id"])).first()
        if not run:
            return {
                "is_fatal_error": True,
                "error_message": f"Run with id {state['run_id']} not found.",
            }

        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()
        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    if not run.source_article_url or not run.source_article_title:
        return {
            "is_fatal_error": True,
            "error_message": "Run is missing source article information.",
        }
    elif not persona.language or not persona.style or not persona.tone:
        return {
            "is_fatal_error": True,
            "error_message": "Persona is missing language, style, or tone information.",
        }

    graph = _build_graph()

    base_state: WriterCriticState = {
        "article_url": run.source_article_url,
        "article_title": run.source_article_title,
        "persona_language": persona.language,
        "persona_style": persona.style,
        "persona_tone": persona.tone,
        "real_news_ratio": persona.real_news_ratio,
        "draft_script": None,
        "reliability_score": None,
        "corrections": None,
        "iterations": 0,
        "is_fatal_error": False,
        "error_message": None,
    }

    result = graph.invoke(base_state)
    if result["is_fatal_error"]:
        return {
            "is_fatal_error": True,
            "error_message": result["error_message"],
        }

    with Session(get_engine()) as session:
        session.exec(
            update(Run)
            .where(Run.id == state["run_id"])
            .values(base_script=result["draft_script"])
        )
        session.commit()

    return {}
