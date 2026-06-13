from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from config import settings
from db import get_engine
from logging_config import get_logger
from models import Persona, Run
from orchestrator.state import OrchestratorState
from utils.pipeline_log import agent_span, node_span, start_run, update_run

log = get_logger(__name__)

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
    agent_prompt = f"{INTAKE_SYSTEM_PROMPT}\n\nInstruction:\n{prompt}"
    with agent_span(
        "intake.extract_topic",
        model=settings.llm_model,
        prompt=agent_prompt,
        response_format=_TopicExtraction.__name__,
    ) as call:
        result: _TopicExtraction = structured.invoke(agent_prompt)
        call["output"] = result
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

    start_run(run_id, prompt=prompt)
    with node_span(run_id, "intake", parameters={"prompt": prompt}):
        if prompt:
            topic = _extract_topic(prompt)

        with Session(get_engine()) as session:
            personas = session.exec(select(Persona).where(Persona.is_active)).all()
            persona_ids = [p.id for p in personas]

        update_run(run_id, topic=topic, persona_ids=persona_ids)

        if not persona_ids:
            log.error("intake.no_active_personas", run_id=run_id)
            return {
                "run_id": run_id,
                "topic": topic,
                "is_fatal_error": True,
                "error_message": "No active personas to run.",
            }

        log.info("intake.ready", run_id=run_id, topic=topic, personas=len(persona_ids))
        return {"run_id": run_id, "topic": topic, "persona_ids": persona_ids}
