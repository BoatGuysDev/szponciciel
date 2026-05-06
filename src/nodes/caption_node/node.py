from sqlmodel import select, Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage

from src.db import get_engine
from src.models import Persona
from .response_format import CaptionAgentResponseFormat

from .system_prompt import CAPTION_SYSTEM_PROMPT
from ..state import PersonaRunState


def caption_node(state: PersonaRunState) -> dict:
    """Generates the TikTok post caption and hashtags from the narration."""

    with Session(get_engine()) as session:
        persona = session.exec(
            select(Persona).where(Persona.id == state["persona_id"])
        ).first()
        if not persona:
            return {
                "is_fatal_error": True,
                "error_message": f"Persona with id {state['persona_id']} not found.",
            }

    if not all([state.get("narration"), persona.language, persona.style, persona.tone]):
        return {
            "is_fatal_error": True,
            "error_message": "Missing required information to create caption.",
        }

    agent = create_agent(
        model=ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite"),
        system_prompt=CAPTION_SYSTEM_PROMPT,
        response_format=CaptionAgentResponseFormat,
    )

    prompt = f"""
        Create a TikTok post caption for the following narration: {state["narration"]}

        The caption must be in {persona.language} and match the following style and tone: {persona.style}, {persona.tone}.
    """

    response = agent.invoke({"messages": [HumanMessage(content=prompt)]})

    output = response["structured_response"]
    caption = output.tiktok_caption[:2200]
    hashtags = output.hashtags

    return {
        "tiktok_caption": caption,
        "hashtags": hashtags,
    }
