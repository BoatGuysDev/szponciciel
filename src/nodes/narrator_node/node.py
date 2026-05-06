import os
from sqlmodel import select, Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage

from src.db import get_engine
from src.models import Run, Persona

from .system_prompt import NARRATOR_SYSTEM_PROMPT
from ..state import PersonaRunState


def narrator_node(state: PersonaRunState) -> dict[str, str | bool]:
    """Adapts the approved script into a narration with specific language and style."""

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

    if not all([run.base_script, persona.language, persona.style, persona.tone]):
        return {
            "is_fatal_error": True,
            "error_message": "Missing required information to create narration.",
        }

    agent = create_agent(
        model=ChatGoogleGenerativeAI(model=os.getenv("MODEL", "gemini-2.5-flash-lite")),
        system_prompt=NARRATOR_SYSTEM_PROMPT,
    )

    prompt = f"""
        Create a narration for the following script: {run.base_script}

        The narration must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    response = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    return {
        "narration": response["messages"][-1].content,
    }
