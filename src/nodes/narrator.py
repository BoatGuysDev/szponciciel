from sqlmodel import select, Session

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage

from src.db import get_engine
from src.models import Run, Persona
from src.prompts import NARRATOR_SYSTEM_PROMPT
from .state import PersonaRunState


def narrator_node(state: PersonaRunState) -> dict[str, str]:
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

    agent = create_agent(
        model=init_chat_model(model="", temperature=0.3),
        tools=[],
        system_prompt=NARRATOR_SYSTEM_PROMPT,
    )
    prompt = f"""
        Create a narration for the following script: {run.script}

        The narration must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    response = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    return {
        "narration": response["messages"][-1],
    }
