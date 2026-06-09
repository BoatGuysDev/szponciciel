from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START, END
from sqlmodel import select, Session, update

from config import settings
from db import get_engine
from models import Run, Persona

from nodes.state import PersonaRunState
from nodes.writer_critic_graph.state import WriterCriticState, Review
from nodes.writer_critic_graph.writer_node.node import writer_node
from nodes.writer_critic_graph.critic_node.node import critic_node


class WriterCriticResult(TypedDict, total=False):
    base_script: str
    is_fatal_error: bool
    error_message: str | None


def _writer_router(state: WriterCriticState) -> str:
    return END if state["is_fatal_error"] else "critic_node"


def _reliability_score(review: Review) -> float:
    return (
        review["coherence_score"]
        + review["grammar_score"]
        + review["unambiguity_score"]
        + review["catchiness_score"]
    ) / 4


def _critic_router(state: WriterCriticState) -> str:
    if (
        state["is_fatal_error"]
        or state["iterations"] == settings.writer_critic_max_iters
        or _reliability_score(state["review"]) >= settings.script_reliability_threshold
    ):
        return END
    else:
        return "writer_node"


def _build_graph():
    graph_builder = StateGraph(WriterCriticState)

    graph_builder.add_node(writer_node)
    graph_builder.add_node(critic_node)

    graph_builder.add_edge(START, "writer_node")
    graph_builder.add_conditional_edges("writer_node", _writer_router)
    graph_builder.add_conditional_edges("critic_node", _critic_router)

    return graph_builder.compile()


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
        "review": None,
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
    draft_script = result.get("draft_script")
    if not draft_script:
        return {
            "is_fatal_error": True,
            "error_message": "Writer/critic finished without producing a draft script.",
        }

    with Session(get_engine()) as session:
        session.exec(
            update(Run)
            .where(Run.id == state["run_id"])
            .values(base_script=draft_script)
        )
        session.commit()

    return {"base_script": draft_script}
