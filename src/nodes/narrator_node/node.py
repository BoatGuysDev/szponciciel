from typing import TypedDict

from sqlmodel import Session, select

from db import get_engine
from models import Persona, Run
from nodes.narrator_node.response_format import NarratorAgentResponseFormat
from nodes.narrator_node.system_prompt import NARRATOR_SYSTEM_PROMPT
from nodes.state import PersonaRunState
from utils.agent_utils import call_agent


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

    prompt = f"""
        Create a narration for the following script: {base_script}

        Story mode: {state.get("story_mode", "real_news")}.
        The narration must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    narration = call_agent(NARRATOR_SYSTEM_PROMPT, NarratorAgentResponseFormat, prompt=prompt).narration

    return {
        "narration": narration,
    }
