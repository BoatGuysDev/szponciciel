from typing import TypedDict
from sqlmodel import select, Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from config import settings
from db import get_engine
from models import Run, Persona

from nodes.narrator_node.system_prompt import NARRATOR_SYSTEM_PROMPT
from nodes.state import PersonaRunState
from nodes.utils import AgentResponseError, invoke_agent


class NarratorResult(TypedDict, total=False):
    narration: str
    is_fatal_error: bool
    error_message: str | None


def narrator_node(state: PersonaRunState) -> NarratorResult:
    """Adapts the approved script into a narration with specific language and style."""

    with Session(get_engine()) as session:
        run = session.exec(select(Run).where(Run.id == state["run_id"])).first()
        if not run:
            return {
                "is_fatal_error": True,
                "error_message": f"Run with id {state['run_id']} not found.",
            }

        persona = session.exec(select(Persona).where(Persona.id == state["persona_id"])).first()
        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    base_script = state.get("base_script") or run.base_script
    if not all([base_script, persona.language, persona.style, persona.tone]):
        return {
            "is_fatal_error": True,
            "error_message": "Missing required information to create narration.",
        }

    agent = create_agent(
        model=ChatGoogleGenerativeAI(model=settings.llm_model),
        system_prompt=NARRATOR_SYSTEM_PROMPT,
    )

    prompt = f"""
        Create a narration for the following script: {base_script}

        The narration must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    try:
        narration = invoke_agent(agent, prompt)
    except AgentResponseError as e:
        return {
            "is_fatal_error": True,
            "error_message": f"Narration generation failed: {e}",
        }

    return {
        "narration": narration,
    }
