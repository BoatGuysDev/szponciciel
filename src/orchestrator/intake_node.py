from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from config import settings
from db import get_engine
from models import Persona, Run
from orchestrator.state import OrchestratorState

INTAKE_SYSTEM_PROMPT = """You extract the news topic a user wants short videos about.

Given the user's instruction, return the specific news topic to research as a \
short search phrase (e.g. "USA-Iran conflict"). If the instruction is generic \
and names no particular subject (e.g. "research and post a few videos"), return \
null."""


class _TopicExtraction(BaseModel):
    topic: str | None = Field(
        default=None,
        description="Short search phrase for the topic, or null if none was given.",
    )


def _extract_topic(prompt: str) -> str | None:
    llm = ChatGoogleGenerativeAI(model=settings.llm_model)
    structured = llm.with_structured_output(_TopicExtraction)
    result: _TopicExtraction = structured.invoke(
        f"{INTAKE_SYSTEM_PROMPT}\n\nInstruction:\n{prompt}"
    )
    topic = (result.topic or "").strip()
    return topic or None


def intake_node(state: OrchestratorState) -> OrchestratorState:
    """Creates the Run, parses the prompt into a topic, and selects active personas."""

    with Session(get_engine()) as session:
        run = Run(status="running")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    topic: str | None = None
    prompt = (state.get("prompt") or "").strip()
    if prompt:
        try:
            topic = _extract_topic(prompt)
        except Exception as e:
            return {
                "run_id": run_id,
                "is_fatal_error": True,
                "error_message": f"Topic extraction failed: {e}",
            }

    with Session(get_engine()) as session:
        personas = session.exec(select(Persona).where(Persona.is_active)).all()
        persona_ids = [p.id for p in personas]

    if not persona_ids:
        return {
            "run_id": run_id,
            "topic": topic,
            "is_fatal_error": True,
            "error_message": "No active personas to run.",
        }

    return {"run_id": run_id, "topic": topic, "persona_ids": persona_ids}
